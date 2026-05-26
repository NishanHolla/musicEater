from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session

from config import AUTH_PASSWORD, AUTH_USERNAME

auth_bp = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session["user"] = username
            return redirect(url_for("download.home"))

        error = "Invalid username or password"

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth.login"))
