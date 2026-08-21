# routes/download_routes.py

from flask import Blueprint, render_template, request, session
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
from minio_client import minio_client
from routes.auth_routes import current_tenant, login_required

download_bp = Blueprint("download", __name__)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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

    except Exception as e:

        print(f"ERROR: PostgreSQL insert failed for '{title}'")
        print(e)

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


def process_downloaded_song(info, tenant):
    title = info.get("title")
    uploader = info.get("uploader")
    duration = info.get("duration")
    webpage_url = info.get("webpage_url")
    thumbnail = info.get("thumbnail")
    video_id = info.get("id")
    local_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    try:
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

        save_song(
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
    finally:
        cleanup_local_files(video_id)

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


def download_one(url, tenant):
    print(f"Downloading '{url}'...")
    info = None

    try:
        with yt_dlp.YoutubeDL(YDL_DOWNLOAD_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)

        if not info:
            print(f"ERROR: no metadata for '{url}', skipping")
            return

        process_downloaded_song(info, tenant)
    except Exception as e:
        print(f"ERROR: skipping unavailable or failed download '{url}'")
        print(e)
        if info and info.get("id"):
            cleanup_local_files(info.get("id"))


def start_download(url, tenant):
    try:
        entry_urls = collect_entry_urls(url)
        print(f"Found {len(entry_urls)} item(s) to download")

        for entry_url in entry_urls:
            download_one(entry_url, tenant)
    except Exception as e:
        print(f"ERROR: playlist processing failed for '{url}'")
        print(e)

# =========================================
# DOWNLOAD ROUTE
# =========================================

@download_bp.route("/download", methods=["POST"])
@login_required
def download():

    url = request.form.get("url")
    tenant = current_tenant()

    if not url:
        return "Missing URL"

    if not tenant:
        return "Missing tenant", 400

    thread = threading.Thread(
        target=start_download,
        args=(url, tenant),
    )

    thread.start()

    return render_template(
        "success.html",
        url=url
    )