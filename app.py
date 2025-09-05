from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import psycopg2
import os
import time

app = Flask(__name__)
CORS(app)

# ------------------- DB Connection -------------------
def get_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

# ------------------- Initialize Tables -------------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT,
            email TEXT,
            cartype TEXT,
            service TEXT,
            date TEXT,
            time TEXT,
            address TEXT,
            status TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            rating INT,
            name TEXT,
            text TEXT,
            ts BIGINT
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

# Run table creation once
init_db()

# ------------------- Routes -------------------
@app.route("/")
def home():
    return render_template("index.html")

# ---------- User Signup ----------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s) RETURNING id",
                    (data["name"], data["email"], data["password"]))
        conn.commit()
        user_id = cur.fetchone()[0]
        return jsonify({"success": True, "id": user_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)})
    finally:
        cur.close()
        conn.close()

# ---------- User Signin ----------
@app.route("/signin", methods=["POST"])
def signin():
    data = request.json
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE email=%s AND password=%s",
                (data["email"], data["password"]))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if user:
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "error": "Invalid credentials"})

# ---------- Booking ----------
@app.route("/book", methods=["POST"])
def book():
    data = request.json
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""INSERT INTO bookings 
        (name, phone, email, cartype, service, date, time, address, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (data["name"], data["phone"], data["email"], data["cartype"], data["service"],
         data["date"], data["time"], data["address"], "Pending"))
    conn.commit()
    booking_id = cur.fetchone()[0]

    cur.close()
    conn.close()

    return jsonify({"success": True, "id": booking_id})

# ---------- View Orders ----------
@app.route("/orders", methods=["GET"])
def orders():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM bookings ORDER BY id DESC")
    orders = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(orders)

# ---------- Feedback ----------
@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    conn = get_db()
    cur = conn.cursor()

    cur.execute("INSERT INTO feedback (rating, name, text, ts) VALUES (%s, %s, %s, %s) RETURNING id",
                (data["rating"], data.get("name"), data["text"], int(time.time())))
    conn.commit()
    fb_id = cur.fetchone()[0]

    cur.close()
    conn.close()

    return jsonify({"success": True, "id": fb_id})

@app.route("/feedbacks", methods=["GET"])
def feedbacks():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM feedback ORDER BY id DESC LIMIT 10")
    feedbacks = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(feedbacks)

# ---------- Admin DB Viewer ----------
@app.route("/admin/db")
def admin_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users")
    users = cur.fetchall()

    cur.execute("SELECT * FROM bookings")
    bookings = cur.fetchall()

    cur.execute("SELECT * FROM feedback")
    feedbacks = cur.fetchall()

    cur.close()
    conn.close()

    return f"""
    <h1>Database Viewer</h1>
    <h2>Users</h2><pre>{users}</pre>
    <h2>Bookings</h2><pre>{bookings}</pre>
    <h2>Feedback</h2><pre>{feedbacks}</pre>
    """

# ------------------- Run -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
