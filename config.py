# config.py

import os
from dotenv import load_dotenv

load_dotenv()

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5435)),
    "database": os.getenv("POSTGRES_DB", "musicEater"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9100")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "songs")

SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-this-secret")
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "admin")
AUTH_TENANT = os.getenv("AUTH_TENANT", AUTH_USERNAME)

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "temp_downloads")