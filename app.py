# app.py

from flask import Flask
from routes.auth_routes import auth_bp
from routes.download_routes import download_bp
from routes.music_routes import music_bp

from config import SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

app.register_blueprint(auth_bp)
app.register_blueprint(download_bp)
app.register_blueprint(music_bp)

if __name__ == "__main__":
    # app.run(debug=True, port=5000)
    app.run(host="0.0.0.0" ,debug=True, port=5000)