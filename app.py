# app.py

from flask import Flask
from routes.download_routes import download_bp
from routes.music_routes import music_bp

app = Flask(__name__)

app.register_blueprint(download_bp)
app.register_blueprint(music_bp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)