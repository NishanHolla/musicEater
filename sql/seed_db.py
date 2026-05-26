from db import get_db_connection

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS songs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    uploader TEXT,
    duration INTEGER,
    youtube_url TEXT,
    local_path TEXT,
    s3_bucket TEXT,
    s3_key TEXT,
    s3_url TEXT,
    thumbnail_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""


def seed_database():
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(CREATE_TABLE_SQL)

        print("Songs table created (if it did not already exist).")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
