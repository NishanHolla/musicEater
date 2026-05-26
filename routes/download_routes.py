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
from routes.auth_routes import login_required

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
    thumbnail_url
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
                thumbnail_url
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ''',
            (
                title,
                uploader,
                duration,
                youtube_url,
                s3_bucket,
                s3_key,
                s3_url,
                thumbnail_url
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

def process_downloaded_song(info):

    title = info.get("title")
    uploader = info.get("uploader")
    duration = info.get("duration")
    webpage_url = info.get("webpage_url")
    thumbnail = info.get("thumbnail")
    video_id = info.get("id")

    filename = f"{video_id}.mp3"

    local_path = os.path.join(
        DOWNLOAD_DIR,
        filename
    )

    if not os.path.exists(local_path):

        print(f"ERROR: File missing {local_path}")
        return

    s3_key = f"{uuid4()}.mp3"

    print(f"Uploading '{title}' to MinIO...")

    minio_client.fput_object(
        MINIO_BUCKET,
        s3_key,
        local_path,
        content_type="audio/mpeg"
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
        thumbnail_url=thumbnail
    )

    if os.path.exists(local_path):

        os.remove(local_path)

        print(f"Deleted local file: {local_path}")

# =========================================
# DOWNLOAD WORKER
# =========================================

def start_download(url):

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "noplaylist": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(url, download=True)

        entries = info.get("entries")

        if entries:

            for entry in entries:
                process_downloaded_song(entry)

        else:

            process_downloaded_song(info)

# =========================================
# DOWNLOAD ROUTE
# =========================================

@download_bp.route("/download", methods=["POST"])
@login_required
def download():

    url = request.form.get("url")

    if not url:
        return "Missing URL"

    thread = threading.Thread(
        target=start_download,
        args=(url,)
    )

    thread.start()

    return render_template(
        "success.html",
        url=url
    )