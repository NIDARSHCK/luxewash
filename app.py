import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# PostgreSQL (Render)
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

# -------------------- Database Setup --------------------
def get_db_connection():
    """Connect to SQLite locally or PostgreSQL on Render."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:  # Render/Postgres
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    else:       # Local SQLite
        conn = sqlite3.connect("luxewash.db")
        conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize tables if they don’t exist."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin BOOLEAN DEFAULT FALSE
    )
    """)

    # Bookings table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id SERIAL PRIMARY KEY,
        name TEXT,
        phone TEXT,
        email TEXT,
        car_type TEXT,
        service_type TEXT,
        date TEXT,
        time TEXT,
        address TEXT,
        status TEXT DEFAULT 'Pending'
    )
    """)

    # Feedback table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id SERIAL PRIMARY KEY,
        name TEXT,
        rating INTEGER,
        text TEXT
    )
    """)

    # Shops table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shops (
        id SERIAL PRIMARY KEY,
        shop_name TEXT,
        owner_name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        city TEXT,
        pincode TEXT,
        services TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------- Routes --------------------
@app.route("/")
def home():
    return render_template("index.html")

# ---- Signup ----
@app.route("/signup", methods=["POST"])
def signup():
    email = request.form.get("email")
    password = request.form.get("password")
    conn = get_db_connection()
    cur = conn.cursor()

    hashed = generate_password_hash(password)

    try:
        cur.execute(
            "INSERT INTO users (email, password) VALUES (%s, %s)"
            if isinstance(cur, psycopg2.extensions.cursor)
            else "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, hashed),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

    return redirect(url_for("home"))

# ---- Signin ----
@app.route("/signin", methods=["POST"])
def signin():
    email = request.form.get("email")
    password = request.form.get("password")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE email=%s"
        if isinstance(cur, psycopg2.extensions.cursor)
        else "SELECT * FROM users WHERE email=?",
        (email,),
    )
    user = cur.fetchone()
    conn.close()

    if user and check_password_hash(user["password"], password):
        session["user"] = {
            "id": user["id"],
            "email": user["email"],
            "is_admin": user.get("is_admin", False)
            if isinstance(user, dict)
            else user["is_admin"],
        }
        return redirect(url_for("home"))
    return "Invalid login", 401

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# ---- Booking ----
@app.route("/booking", methods=["POST"])
def booking():
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
    INSERT INTO bookings (name, phone, email, car_type, service_type, date, time, address)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """
        if isinstance(cur, psycopg2.extensions.cursor)
        else """
    INSERT INTO bookings (name, phone, email, car_type, service_type, date, time, address)
    VALUES (?,?,?,?,?,?,?,?)
    """,
        (
            data.get("name"),
            data.get("phone"),
            data.get("email"),
            data.get("carType"),
            data.get("serviceType"),
            data.get("date"),
            data.get("time"),
            data.get("address"),
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

# ---- Feedback ----
@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
    INSERT INTO feedback (name, rating, text) VALUES (%s,%s,%s)
    """
        if isinstance(cur, psycopg2.extensions.cursor)
        else "INSERT INTO feedback (name, rating, text) VALUES (?,?,?)",
        (data.get("name"), data.get("rating"), data.get("text")),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

# ---- Shop Registration ----
@app.route("/shop/register", methods=["POST"])
def register_shop():
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
    INSERT INTO shops (shop_name, owner_name, email, phone, address, city, pincode, services)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """
        if isinstance(cur, psycopg2.extensions.cursor)
        else "INSERT INTO shops (shop_name, owner_name, email, phone, address, city, pincode, services) VALUES (?,?,?,?,?,?,?,?)",
        (
            data.get("shopName"),
            data.get("ownerName"),
            data.get("email"),
            data.get("phone"),
            data.get("address"),
            data.get("city"),
            data.get("pincode"),
            data.get("services"),
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

# ---- Simple Admin ----
@app.route("/admin")
def admin():
    if "user" not in session or not session["user"]["is_admin"]:
        return "Unauthorized", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bookings")
    bookings = cur.fetchall()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    conn.close()
    return render_template("admin.html", bookings=bookings, users=users)

# ---- Advanced Admin Dashboard ----
@app.route("/admin/db")
def admin_db():
    if "user" not in session or not session["user"]["is_admin"]:
        return "Unauthorized", 403

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM bookings")
    bookings = cur.fetchall()

    cur.execute("SELECT * FROM users")
    users = cur.fetchall()

    cur.execute("SELECT * FROM feedback")
    feedback = cur.fetchall()

    cur.execute("SELECT * FROM shops")
    shops = cur.fetchall()

    conn.close()
    return render_template(
        "admin_db.html", bookings=bookings, users=users, feedback=feedback, shops=shops
    )

# -------------------- Main --------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
