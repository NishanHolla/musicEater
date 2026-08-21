CREATE TABLE songs (
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
