from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3, random

app = Flask(__name__)
CORS(app)

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("luxewash.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT UNIQUE, password TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, phone TEXT, service TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# --- Routes ---
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    try:
        conn = sqlite3.connect("luxewash.db")
        c = conn.cursor()
        c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                  (data["name"], data["email"], data["password"]))
        conn.commit()
        return jsonify({"status":"success"})
    except:
        return jsonify({"status":"error", "msg":"Email already exists"})
    finally:
        conn.close()

@app.route("/signin", methods=["POST"])
def signin():
    data = request.json
    conn = sqlite3.connect("luxewash.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=? AND password=?",(data["email"],data["password"]))
    user = c.fetchone()
    conn.close()
    if user:
        otp = random.randint(100000,999999)
        return jsonify({"status":"success","otp":otp})
    return jsonify({"status":"error","msg":"Invalid credentials"})

@app.route("/book", methods=["POST"])
def book():
    data = request.json
    conn = sqlite3.connect("luxewash.db")
    c = conn.cursor()
    c.execute("INSERT INTO bookings(name,phone,service) VALUES(?,?,?)",
              (data["name"], data["phone"], data["service"]))
    conn.commit()
    conn.close()
    return jsonify({"status":"success"})

@app.route("/orders", methods=["GET"])
def orders():
    conn = sqlite3.connect("luxewash.db")
    c = conn.cursor()
    c.execute("SELECT name, phone, service FROM bookings")
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    conn = sqlite3.connect("luxewash.db")
    c = conn.cursor()
    c.execute("INSERT INTO feedback(text) VALUES(?)",(data["text"],))
    conn.commit()
    conn.close()
    return jsonify({"status":"success"})

@app.route("/feedbacks", methods=["GET"])
def get_feedbacks():
    conn = sqlite3.connect("luxewash.db")
    c = conn.cursor()
    c.execute("SELECT text FROM feedback ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([r[0] for r in rows])

@app.route("/services", methods=["GET"])
def services():
    return jsonify([
        {"name":"Exterior Wash","price":"₹1,200"},
        {"name":"Interior Cleaning","price":"₹1,500"},
        {"name":"Full Detailing","price":"₹3,000"},
        {"name":"Ceramic Coating","price":"₹9,500"}
    ])
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
