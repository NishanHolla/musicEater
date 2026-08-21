# musicEater

musicEater is a personal YouTube music library. Paste a video or playlist URL, and the app downloads the audio, stores it, and lets you play it in the browser.

Each login belongs to a **tenant**. You only see songs imported under your tenant.

## What you need

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Postgres and MinIO)
- Python 3.10 or newer
- [FFmpeg](https://ffmpeg.org/) (used by `yt-dlp` to convert audio to MP3)

On macOS with Homebrew:

```bash
brew install ffmpeg
```

## Setup

### 1. Clone the project and add config

```bash
cp .env.example .env
```

The example file already works for local development. Default login is `admin` / `admin`.

### 2. Start the database and file storage

```bash
docker compose up -d
```

Wait until both containers are running. You can check with `docker compose ps`.

| Service | Address |
| --- | --- |
| Postgres | `localhost:5435` |
| MinIO API | [http://localhost:9100](http://localhost:9100) |
| MinIO console | [http://localhost:9101](http://localhost:9101) |

MinIO console login is `minioadmin` / `minioadmin`. The `songs` bucket is created automatically the first time you start the app.

### 3. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate with `venv\Scripts\activate`.

### 4. Create tables and the admin user

```bash
python seed_db.py
```

This creates the `auth` and `songs` tables and seeds the default admin account.

### 5. Run the app

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

## First login

1. Sign in with **admin** / **admin**.
2. You will be asked to set a new password (at least 8 characters; not `admin`).
3. After that, you land on the library.

To sign out, use **Logout** in the top right.

## Using the library

- **Import a song:** paste a YouTube video URL and click **Import to Library**.
- **Import a playlist:** paste the playlist URL the same way. Each track is saved as soon as it downloads. If one video is unavailable, the rest still import.
- **Search:** type in the search box to filter your library.
- **Play:** click a song. Use **Play Next** or **Add to Queue** to control playback order.

Imports run in the background. Audio is staged briefly in `temp_downloads/`, uploaded to MinIO, then deleted locally. The library list refreshes on its own, so new tracks appear as they finish.

## Extra tenants

Songs are isolated by the `tenant` field on each user in the `auth` table. The seeded admin user lives in tenant `admin`. Add more rows in `auth` with a different `tenant` if you want separate libraries.

## Stopping locally

```bash
# stop the Flask app with Ctrl+C in that terminal
docker compose down
```

Data stays in Docker volumes until you remove them on purpose.

## License

This project is licensed under the [MIT License](LICENSE).
