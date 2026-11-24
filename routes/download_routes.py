# routes/download_routes.py

from flask import Blueprint, jsonify, render_template, request, session
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import yt_dlp
import threading
import os

from uuid import uuid4

from config import (
    DOWNLOAD_DIR,
    MINIO_BUCKET,
    MINIO_ENDPOINT
)

from db import get_db_connection
from download_jobs import (
    attach_process,
    cancel_job,
    create_job,
    get_jobs,
    increment_job,
    is_cancel_requested,
    update_job,
)
from minio_client import minio_client
from routes.auth_routes import current_tenant, login_required
from spotify import parse_spotify_link

download_bp = Blueprint("download", __name__)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
IMPORT_SLOT = threading.Semaphore(1)
MAX_TRACK_ATTEMPTS = 3

# =========================================
# HOME
# =========================================

@download_bp.route("/")
@login_required
def home():
    return render_template("index.html", user=session.get("user"))

# =========================================
# SAVE SONG
# =========================================

def save_song(
    title,
    uploader,
    duration,
    youtube_url,
    s3_bucket,
    s3_key,
    s3_url,
    thumbnail_url,
    tenant,
):

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{tenant}:{youtube_url}",))
        cur.execute(
            "SELECT 1 FROM songs WHERE tenant = %s AND youtube_url = %s LIMIT 1",
            (tenant, youtube_url),
        )
        if cur.fetchone():
            conn.commit()
            return False

        cur.execute(
            '''
            INSERT INTO songs (
                title,
                uploader,
                duration,
                youtube_url,
                s3_bucket,
                s3_key,
                s3_url,
                thumbnail_url,
                tenant
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ''',
            (
                title,
                uploader,
                duration,
                youtube_url,
                s3_bucket,
                s3_key,
                s3_url,
                thumbnail_url,
                tenant,
            )
        )

        conn.commit()

        print(f"SUCCESS: PostgreSQL insert completed for '{title}'")

        cur.close()
        conn.close()
        return True

    except Exception as e:

        print(f"ERROR: PostgreSQL insert failed for '{title}'")
        print(e)
        return False


def song_exists(tenant, source_url):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM songs WHERE tenant = %s AND youtube_url = %s LIMIT 1",
                (tenant, source_url),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()

# =========================================
# PROCESS SONG
# =========================================

def cleanup_local_files(video_id):
    if not video_id or not os.path.isdir(DOWNLOAD_DIR):
        return

    prefix = f"{video_id}."
    for name in os.listdir(DOWNLOAD_DIR):
        if name == f"{video_id}.mp3" or name.startswith(prefix):
            path = os.path.join(DOWNLOAD_DIR, name)
            try:
                os.remove(path)
                print(f"Deleted local file: {path}")
            except OSError as e:
                print(f"ERROR: could not delete {path}: {e}")


def process_downloaded_song(info, tenant, job_id=None):
    title = info.get("title")
    uploader = info.get("uploader")
    duration = info.get("duration")
    webpage_url = info.get("webpage_url")
    thumbnail = info.get("thumbnail")
    video_id = info.get("id")
    local_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    try:
        if song_exists(tenant, webpage_url):
            if job_id:
                increment_job(job_id, "skipped")
            return "skipped"
        if not os.path.exists(local_path):
            print(f"ERROR: File missing {local_path}")
            return

        s3_key = f"{uuid4()}.mp3"
        print(f"Uploading '{title}' to MinIO...")

        minio_client.fput_object(
            MINIO_BUCKET,
            s3_key,
            local_path,
            content_type="audio/mpeg",
        )

        s3_url = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{s3_key}"
        print(f"SUCCESS: Uploaded to MinIO -> {s3_url}")

        saved = save_song(
            title=title,
            uploader=uploader,
            duration=duration,
            youtube_url=webpage_url,
            s3_bucket=MINIO_BUCKET,
            s3_key=s3_key,
            s3_url=s3_url,
            thumbnail_url=thumbnail,
            tenant=tenant,
        )
        if not saved:
            minio_client.remove_object(MINIO_BUCKET, s3_key)
            return "skipped"
        return "completed"
    finally:
        cleanup_local_files(video_id)


def start_spotify_download(url, tenant, job_id):
    try:
        update_job(job_id, state="running", message="Reading Spotify playlist")
        with TemporaryDirectory(prefix="spotify-", dir=DOWNLOAD_DIR) as temp_dir:
            output_dir = Path(temp_dir)
            spotdl_env = os.environ.copy()
            spotdl_env["USERPROFILE"] = str(output_dir)
            process = subprocess.Popen(
                [
                    sys.executable, "-m", "spotdl", "download", url,
                    "--format", "mp3",
                    "--lyrics",
                    "--max-retries", str(MAX_TRACK_ATTEMPTS),
                    "--output", str(output_dir / "{track-id}.{output-ext}"),
                    "--save-file", str(output_dir / "tracks.spotdl"),
                    "--simple-tui",
                ],
                stdin=subprocess.DEVNULL,
                env=spotdl_env,
            )
            attach_process(job_id, process)
            try:
                result_code = process.wait(timeout=3600)
            except subprocess.TimeoutExpired:
                process.terminate()
                result_code = process.wait()

            if is_cancel_requested(job_id):
                return
            if result_code:
                print(f"spotDL exited with status {result_code} for {url}")

            manifest = output_dir / "tracks.spotdl"
            if not manifest.is_file():
                print(f"spotDL did not produce track metadata for {url}")
                update_job(job_id, state="failed", message="spotDL did not return any tracks")
                return

            songs = json.loads(manifest.read_text(encoding="utf-8"))
            update_job(job_id, total=len(songs), message="Adding downloaded tracks to library")
            for song in songs:
                track_id = song.get("song_id")
                audio_path = output_dir / f"{track_id}.mp3"
                if not track_id or not audio_path.is_file() or not audio_path.stat().st_size:
                    increment_job(job_id, "failed")
                    continue

                info = {
                    "title": song.get("name"),
                    "uploader": ", ".join(song.get("artists") or []) or song.get("artist"),
                    "duration": song.get("duration"),
                    "webpage_url": song.get("url") or url,
                    "thumbnail": song.get("cover_url"),
                    "id": track_id,
                }
                s3_key = f"{uuid4()}.mp3"
                try:
                    if song_exists(tenant, info["webpage_url"]):
                        increment_job(job_id, "skipped")
                        continue
                    minio_client.fput_object(
                        MINIO_BUCKET, s3_key, str(audio_path), content_type="audio/mpeg"
                    )
                    saved = save_song(
                        title=info["title"],
                        uploader=info["uploader"],
                        duration=info["duration"],
                        youtube_url=info["webpage_url"],
                        s3_bucket=MINIO_BUCKET,
                        s3_key=s3_key,
                        s3_url=f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{s3_key}",
                        thumbnail_url=info["thumbnail"],
                        tenant=tenant,
                    )
                    if saved:
                        increment_job(job_id, "completed")
                    else:
                        minio_client.remove_object(MINIO_BUCKET, s3_key)
                        increment_job(job_id, "skipped")
                except Exception as error:
                    print(f"Could not store Spotify track {track_id}: {error}")
                    increment_job(job_id, "failed")

            update_job(job_id, state="completed", message="Import finished")

    except Exception as error:
        print(f"Spotify download failed for {url}: {error}")
        update_job(job_id, state="failed", message="Spotify import failed")

# =========================================
# DOWNLOAD WORKER
# =========================================

YDL_DOWNLOAD_OPTS = {
    "format": "bestaudio/best",
    "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ],
    "noplaylist": True,
    "ignoreerrors": False,
    "keepvideo": False,
}

YDL_LIST_OPTS = {
    "extract_flat": True,
    "skip_download": True,
    "quiet": True,
    "noplaylist": False,
    "ignoreerrors": True,
}


def _entry_url(entry):
    webpage = entry.get("webpage_url") or entry.get("original_url")
    if webpage:
        return webpage

    video_id = entry.get("id")
    ie_key = (entry.get("ie_key") or entry.get("extractor_key") or "").lower()
    url = entry.get("url")

    if video_id and "youtube" in ie_key:
        return f"https://www.youtube.com/watch?v={video_id}"

    if url and str(url).startswith("http"):
        return url

    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"

    return url


def collect_entry_urls(url):
    with yt_dlp.YoutubeDL(YDL_LIST_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        return [url]

    entries = info.get("entries")
    if not entries:
        return [info.get("webpage_url") or info.get("original_url") or url]

    urls = []
    for entry in entries:
        if not entry:
            print("Skipping unavailable playlist entry")
            continue

        entry_url = _entry_url(entry)
        if entry_url:
            urls.append(entry_url)
        else:
            print(f"Skipping playlist entry with no URL: {entry}")

    return urls


def download_one(url, tenant, job_id):
    print(f"Downloading '{url}'...")
    for attempt in range(1, MAX_TRACK_ATTEMPTS + 1):
        if is_cancel_requested(job_id):
            return
        info = None
        try:
            update_job(
                job_id,
                message=f"Downloading track, attempt {attempt} of {MAX_TRACK_ATTEMPTS}",
            )
            with yt_dlp.YoutubeDL(YDL_DOWNLOAD_OPTS) as ydl:
                info = ydl.extract_info(url, download=True)

            if not info:
                raise RuntimeError("No metadata returned")

            result = process_downloaded_song(info, tenant, job_id)
            if result == "completed":
                increment_job(job_id, "completed")
            elif result == "skipped":
                increment_job(job_id, "skipped")
            else:
                increment_job(job_id, "failed")
            return
        except Exception as error:
            print(f"Download attempt {attempt} failed for '{url}': {error}")
            if info and info.get("id"):
                cleanup_local_files(info.get("id"))

    increment_job(job_id, "failed")


def run_import(worker, url, tenant, job_id):
    with IMPORT_SLOT:
        if is_cancel_requested(job_id):
            return
        worker(url, tenant, job_id)


def start_download(url, tenant, job_id):
    try:
        update_job(job_id, state="running", message="Reading link")
        entry_urls = collect_entry_urls(url)
        update_job(job_id, total=len(entry_urls), message="Downloading tracks")
        print(f"Found {len(entry_urls)} item(s) to download")

        for entry_url in entry_urls:
            if is_cancel_requested(job_id):
                return
            download_one(entry_url, tenant, job_id)
        if not is_cancel_requested(job_id):
            update_job(job_id, state="completed", message="Import finished")
    except Exception as e:
        print(f"ERROR: playlist processing failed for '{url}'")
        print(e)
        update_job(job_id, state="failed", message="Could not read this link")

# =========================================
# DOWNLOAD ROUTE
# =========================================

@download_bp.route("/download", methods=["POST"])
@login_required
def download():

    url = request.form.get("url", "").strip()
    tenant = current_tenant()

    if not url:
        return jsonify(error="Enter a music URL."), 400

    if not tenant:
        return "Missing tenant", 400

    try:
        spotify_item = parse_spotify_link(url)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    if spotify_item:
        item_type, spotify_id = spotify_item
        url = f"https://open.spotify.com/{item_type}/{spotify_id}"
        worker = start_spotify_download
    else:
        worker = start_download

    job_id = create_job(tenant, url)

    thread = threading.Thread(
        target=run_import,
        args=(worker, url, tenant, job_id),
    )

    thread.start()

    return jsonify(message="Added to the import queue.", job_id=job_id), 202


@download_bp.route("/api/downloads", methods=["GET"])
@login_required
def downloads():
    return jsonify(get_jobs(current_tenant()))


@download_bp.route("/api/downloads/<job_id>", methods=["DELETE"])
@login_required
def cancel_download(job_id):
    if not cancel_job(job_id, current_tenant()):
        return jsonify(error="This import cannot be canceled."), 404
    return jsonify(message="Import canceled.")
