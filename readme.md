Seed MiniIo
brew install minio/stable/mc

mc alias set local http://localhost:9000 minioadmin minioadmin

# dotenv support
Create a `.env` file from `.env.example` and ensure `python-dotenv` is installed in the virtual environment.
