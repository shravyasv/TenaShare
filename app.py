import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "tenasshare.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "TENASSHARE_SECRET_KEY",
    "dev-only-change-this-secret"
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")

    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            quantity TEXT NOT NULL,
            pickup_location TEXT NOT NULL,
            pickup_time TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    db.commit()
    db.close()
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    db = get_db()
    donations = db.execute("""
        SELECT donations.*, users.name AS donor_name
        FROM donations
        JOIN users ON users.id = donations.user_id
        WHERE donations.status = 'Available'
        ORDER BY donations.created_at DESC
    """).fetchall()

    return render_template("index.html", donations=donations)
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("register"))

        db = get_db()

        existing_user = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            flash("Email already registered.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )

        db.commit()

        flash("Registration successful! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if user is None:
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        if not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]

        flash("Login successful!")
        return redirect(url_for("dashboard"))

    return render_template("login.html")
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()

    donations = db.execute(
        """
        SELECT * FROM donations
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template(
        "dashboard.html",
        donations=donations
    )
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("index"))
@app.route("/donations/new", methods=["GET", "POST"])
@login_required
def new_donation():
    if request.method == "POST":
        food_name = request.form["food_name"].strip()
        quantity = request.form["quantity"].strip()
        pickup_location = request.form["pickup_location"].strip()
        pickup_time = request.form["pickup_time"].strip()
        description = request.form["description"].strip()

        if not food_name or not quantity or not pickup_location or not pickup_time:
            flash("Please fill in all required fields.")
            return redirect(url_for("new_donation"))

        db = get_db()

        db.execute(
            """
            INSERT INTO donations
            (user_id, food_name, quantity, pickup_location,
             pickup_time, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                food_name,
                quantity,
                pickup_location,
                pickup_time,
                description
            )
        )

        db.commit()

        flash("Food donation posted successfully!")
        return redirect(url_for("dashboard"))

    return render_template("donations/new_donation.html")
@app.route("/donations/<int:donation_id>")
def donation_detail(donation_id):
    db = get_db()

    donation = db.execute(
        """
        SELECT donations.*, users.name AS donor_name
        FROM donations
        JOIN users ON users.id = donations.user_id
        WHERE donations.id = ?
        """,
        (donation_id,)
    ).fetchone()

    if donation is None:
        flash("Donation not found.")
        return redirect(url_for("index"))

    return render_template(
        "donation_detail.html",
        donation=donation
    )
@app.route("/admin")
@login_required
def admin():
    db = get_db()

    user = db.execute(
        "SELECT email FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if user["email"] != os.environ.get("TENASSHARE_ADMIN_EMAIL"):
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    donations = db.execute(
        """
        SELECT donations.*, users.name AS donor_name
        FROM donations
        JOIN users ON users.id = donations.user_id
        ORDER BY donations.created_at DESC
        """
    ).fetchall()

    return render_template("admin.html", donations=donations)
@app.route("/admin")
@login_required
def admin():
    db = get_db()

    user = db.execute(
        "SELECT email FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if user["email"] != os.environ.get("TENASSHARE_ADMIN_EMAIL"):
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    donations = db.execute(
        """
        SELECT donations.*, users.name AS donor_name
        FROM donations
        JOIN users ON users.id = donations.user_id
        ORDER BY donations.created_at DESC
        """
    ).fetchall()

    return render_template("admin.html", donations=donations)
@app.route("/admin")
@login_required
def admin():
    db = get_db()

    user = db.execute(
        "SELECT email FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if user["email"] != os.environ.get("TENASSHARE_ADMIN_EMAIL"):
        flash("Access denied. Admin only.")
        return redirect(url_for("dashboard"))

    donations = db.execute(
        """
        SELECT donations.*, users.name AS donor_name
        FROM donations
        JOIN users ON users.id = donations.user_id
        ORDER BY donations.created_at DESC
        """
    ).fetchall()

    return render_template("admin.html", donations=donations)
