from flask import Flask, render_template, request
import yt_dlp
import threading
import os
import psycopg2
from minio import Minio
from minio.error import S3Error
from uuid import uuid4

# =========================================
# CONFIG
# =========================================

POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "musicEater",
    "user": "postgres",
    "password": "postgres"
}

MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_BUCKET = "songs"

DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================================
# FLASK
# =========================================

app = Flask(__name__)

# =========================================
# MINIO CLIENT
# =========================================

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# Create bucket if missing
found = minio_client.bucket_exists(MINIO_BUCKET)

if not found:
    minio_client.make_bucket(MINIO_BUCKET)

# =========================================
# POSTGRES
# =========================================

def get_db_connection():
    return psycopg2.connect(**POSTGRES_CONFIG)

# =========================================
# HOME
# =========================================

@app.route("/")
def home():
    return render_template("index.html")

# =========================================
# SAVE SONG TO DB
# =========================================

def save_song(
    title,
    uploader,
    duration,
    youtube_url,
    local_path,
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
                local_path,
                s3_bucket,
                s3_key,
                s3_url,
                thumbnail_url
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ''',
            (
                title,
                uploader,
                duration,
                youtube_url,
                local_path,
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
# DOWNLOAD + S3 UPLOAD
# =========================================

def start_download(url):

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
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

        # Playlist
        if entries:

            for entry in entries:

                process_downloaded_song(entry)

        # Single video
        else:

            process_downloaded_song(info)

# =========================================
# PROCESS DOWNLOADED SONG
# =========================================

def process_downloaded_song(info):

    title = info.get("title")
    uploader = info.get("uploader")
    duration = info.get("duration")
    webpage_url = info.get("webpage_url")
    thumbnail = info.get("thumbnail")

    filename = f"{title}.mp3"
    local_path = os.path.join(DOWNLOAD_DIR, filename)

    if not os.path.exists(local_path):
        print(f"File missing: {local_path}")
        return

    s3_key = f"{uuid4()}.mp3"

    # Upload to MinIO
    minio_client.fput_object(
        MINIO_BUCKET,
        s3_key,
        local_path,
        content_type="audio/mpeg"
    )

    s3_url = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{s3_key}"

    # Save DB record
    save_song(
        title=title,
        uploader=uploader,
        duration=duration,
        youtube_url=webpage_url,
        local_path=local_path,
        s3_bucket=MINIO_BUCKET,
        s3_key=s3_key,
        s3_url=s3_url,
        thumbnail_url=thumbnail
    )

    print(f"Uploaded to MinIO: {s3_url}")

    # Delete local file after successful upload
    if os.path.exists(local_path):
        os.remove(local_path)
        print(f"Deleted local file: {local_path}")
    
# =========================================
# DOWNLOAD ROUTE
# =========================================

@app.route("/download", methods=["POST"])
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

# =========================================
# MAIN
# =========================================

if __name__ == "__main__":
    app.run(debug=True, port=6969)