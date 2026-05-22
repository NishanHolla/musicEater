# routes/music_routes.py

from flask import Blueprint, jsonify, Response, request

from db import get_db_connection
from minio_client import minio_client

music_bp = Blueprint("music", __name__)

# =========================================
# GET ALL SONGS
# =========================================

@music_bp.route("/api/songs", methods=["GET"])
def get_songs():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            title,
            uploader,
            duration,
            youtube_url,
            s3_bucket,
            s3_key,
            thumbnail_url,
            created_at
        FROM songs
        ORDER BY created_at DESC
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    songs = []

    for row in rows:

        songs.append({
            "id": str(row[0]),
            "title": row[1],
            "uploader": row[2],
            "duration": row[3],
            "youtube_url": row[4],
            "s3_bucket": row[5],
            "s3_key": row[6],
            "thumbnail_url": row[7],
            "created_at": row[8].isoformat()
        })

    return jsonify(songs)

# =========================================
# STREAM SONG WITH SEEK SUPPORT
# =========================================

@music_bp.route("/api/stream/<song_id>")
def stream_song(song_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            s3_bucket,
            s3_key
        FROM songs
        WHERE id = %s
        """,
        (song_id,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return "Song not found", 404

    bucket_name = row[0]
    object_name = row[1]

    try:

        stat = minio_client.stat_object(
            bucket_name,
            object_name
        )

        file_size = stat.size

        range_header = request.headers.get("Range", None)

        start = 0
        end = file_size - 1

        if range_header:

            range_value = range_header.replace("bytes=", "")

            start_str, end_str = range_value.split("-")

            start = int(start_str)

            if end_str:
                end = int(end_str)

        length = end - start + 1

        data = minio_client.get_object(
            bucket_name,
            object_name,
            offset=start,
            length=length
        )

        response_data = data.read()

        response = Response(
            response_data,
            status=206 if range_header else 200,
            mimetype="audio/mpeg"
        )

        response.headers["Accept-Ranges"] = "bytes"

        response.headers["Content-Length"] = str(length)

        response.headers["Content-Range"] = (
            f"bytes {start}-{end}/{file_size}"
        )

        return response

    except Exception as e:

        print(e)

        return "Streaming failed", 500