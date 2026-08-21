from werkzeug.security import generate_password_hash

from config import AUTH_PASSWORD, AUTH_TENANT, AUTH_USERNAME
from db import get_db_connection

CREATE_AUTH_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS auth (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    tenant TEXT NOT NULL,
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

ADD_MUST_CHANGE_PASSWORD_SQL = """
ALTER TABLE auth
ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT TRUE;
"""

CREATE_SONGS_TABLE_SQL = """
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
    tenant TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

ADD_SONGS_TENANT_SQL = """
ALTER TABLE songs
ADD COLUMN IF NOT EXISTS tenant TEXT;
"""

CREATE_SONGS_TENANT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS songs_tenant_idx ON songs (tenant);
"""

RENAME_NISHAN_USER_SQL = """
UPDATE auth
SET username = %s,
    password = %s,
    tenant = %s,
    must_change_password = TRUE
WHERE username = 'nishan'
  AND NOT EXISTS (
      SELECT 1 FROM auth WHERE username = %s
  );
"""

SEED_AUTH_USER_SQL = """
INSERT INTO auth (username, password, tenant, must_change_password)
VALUES (%s, %s, %s, TRUE)
ON CONFLICT (username) DO NOTHING;
"""

DELETE_NISHAN_USER_SQL = """
DELETE FROM auth
WHERE username = 'nishan';
"""

BACKFILL_SONGS_TENANT_SQL = """
UPDATE songs
SET tenant = %s
WHERE tenant IS NULL OR tenant = 'nishan';
"""


def seed_database():
    username = AUTH_USERNAME or "admin"
    password = AUTH_PASSWORD or "admin"
    tenant = AUTH_TENANT or username
    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(CREATE_AUTH_TABLE_SQL)
                cursor.execute(ADD_MUST_CHANGE_PASSWORD_SQL)
                cursor.execute(CREATE_SONGS_TABLE_SQL)
                cursor.execute(ADD_SONGS_TENANT_SQL)
                cursor.execute(CREATE_SONGS_TENANT_INDEX_SQL)
                cursor.execute(
                    RENAME_NISHAN_USER_SQL,
                    (username, password_hash, tenant, username),
                )
                cursor.execute(
                    SEED_AUTH_USER_SQL,
                    (username, password_hash, tenant),
                )
                cursor.execute(DELETE_NISHAN_USER_SQL)
                cursor.execute(BACKFILL_SONGS_TENANT_SQL, (tenant,))

        print("Auth and songs tables are ready.")
        print(f"Default login is '{username}' / '{password}'. You will be asked to change the password after first login.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
