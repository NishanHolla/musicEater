from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db_connection

auth_bp = Blueprint("auth", __name__)

PASSWORD_CHANGE_EXEMPT = {"auth.login", "auth.logout", "auth.change_password"}


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user") or not session.get("tenant"):
            return redirect(url_for("auth.login"))
        if session.get("must_change_password") and request.endpoint not in PASSWORD_CHANGE_EXEMPT:
            return redirect(url_for("auth.change_password"))
        return view(*args, **kwargs)

    return wrapped_view


def current_tenant():
    return session.get("tenant")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT username, password, tenant, must_change_password
                    FROM auth
                    WHERE username = %s
                    """,
                    (username,),
                )
                row = cur.fetchone()
        finally:
            conn.close()

        if row and password and check_password_hash(row[1], password):
            session["user"] = row[0]
            session["tenant"] = row[2]
            session["must_change_password"] = bool(row[3])
            if session["must_change_password"]:
                return redirect(url_for("auth.change_password"))
            return redirect(url_for("download.home"))

        error = "Invalid username or password"

    return render_template("login.html", error=error)


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not session.get("user"):
        return redirect(url_for("auth.login"))

    error = None

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT password
                    FROM auth
                    WHERE username = %s
                    """,
                    (session["user"],),
                )
                row = cur.fetchone()

                if not row or not current_password or not check_password_hash(row[0], current_password):
                    error = "Current password is incorrect"
                elif not new_password or len(new_password) < 8:
                    error = "New password must be at least 8 characters"
                elif new_password != confirm_password:
                    error = "New passwords do not match"
                elif new_password == current_password:
                    error = "New password must be different from the current password"
                elif new_password.lower() == "admin":
                    error = "Choose a password other than the default"
                else:
                    cur.execute(
                        """
                        UPDATE auth
                        SET password = %s,
                            must_change_password = FALSE
                        WHERE username = %s
                        """,
                        (generate_password_hash(new_password), session["user"]),
                    )
                    conn.commit()
                    session["must_change_password"] = False
                    return redirect(url_for("download.home"))
        finally:
            conn.close()

    return render_template("change_password.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("tenant", None)
    session.pop("must_change_password", None)
    return redirect(url_for("auth.login"))
