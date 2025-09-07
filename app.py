import os
import sqlite3
from flask import Flask, render_template, request, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
# It's crucial to set a strong, secret key in your production environment
app.secret_key = os.getenv("SECRET_KEY", "a_very_secret_dev_key")

# -------------------- Database Setup --------------------

def get_db_connection():
    """Connects to the PostgreSQL database on Render or a local SQLite database."""
    db_url = os.getenv("DATABASE_URL")
    try:
        if db_url:
            conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        else:
            conn = sqlite3.connect("luxewash.db")
            conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    """Initializes the database tables if they don't already exist."""
    conn = get_db_connection()
    if not conn:
        print("Could not connect to the database. Aborting table initialization.")
        return
    
    with conn.cursor() as cur:
        # Users table (removed is_admin, added name and phone)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)

        # Bookings table (added user_id to link bookings to users)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
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

# Initialize the database when the app starts
init_db()

# -------------------- API Routes --------------------

@app.route("/")
def home():
    """Serves the main HTML page."""
    return render_template("index.html")

# ---- User Authentication API ----

@app.route("/api/signup", methods=["POST"])
def signup():
    """API endpoint for user registration."""
    data = request.form
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")

    if not all([name, email, phone, password]):
        return jsonify({"error": "Missing required fields"}), 400

    hashed_password = generate_password_hash(password)
    
    conn = get_db_connection()
    is_postgres = hasattr(conn.cursor, '__enter__')
    sql = """
        INSERT INTO users (name, email, phone, password) VALUES (%s, %s, %s, %s)
    """ if is_postgres else """
        INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (name, email, phone, hashed_password))
        conn.commit()
    except (sqlite3.IntegrityError, psycopg2.IntegrityError):
        conn.rollback()
        return jsonify({"error": "Email or phone number already registered."}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"success": True, "message": "Account created successfully."}), 201

@app.route("/api/signin", methods=["POST"])
def signin():
    """API endpoint for user login."""
    data = request.form
    login_identifier = data.get("login") # This can be email or phone
    password = data.get("password")

    if not login_identifier or not password:
        return jsonify({"error": "Missing login credentials"}), 400

    conn = get_db_connection()
    is_postgres = hasattr(conn.cursor, '__enter__')
    sql = """
        SELECT * FROM users WHERE email = %s OR phone = %s
    """ if is_postgres else """
        SELECT * FROM users WHERE email = ? OR phone = ?
    """
    
    with conn.cursor() as cur:
        cur.execute(sql, (login_identifier, login_identifier))
        user = cur.fetchone()
    conn.close()

    if user and check_password_hash(user["password"], password):
        # Create session
        session["user"] = dict(user)
        return jsonify({
            "success": True, 
            "message": "Login successful.",
            "user": session["user"]
        }), 200
    
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    """API endpoint for user logout."""
    session.pop("user", None)
    return jsonify({"success": True, "message": "Logged out successfully."}), 200

@app.route("/api/session")
def check_session():
    """API endpoint to check if a user is currently logged in."""
    if "user" in session:
        return jsonify({"isLoggedIn": True, "user": session["user"]}), 200
    return jsonify({"isLoggedIn": False}), 200


# ---- Data Handling API ----

@app.route("/api/booking", methods=["POST"])
def booking():
    """API endpoint to create a new booking."""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.form
    user_id = session["user"]["id"]
    
    conn = get_db_connection()
    is_postgres = hasattr(conn.cursor, '__enter__')
    sql = """
    INSERT INTO bookings (user_id, name, phone, email, car_type, service_type, date, time, address)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """ if is_postgres else """
    INSERT INTO bookings (user_id, name, phone, email, car_type, service_type, date, time, address)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                data.get("name"), data.get("phone"), data.get("email"),
                data.get("carType"), data.get("serviceType"), # Corrected keys
                data.get("date"), data.get("time"), data.get("address")
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
    return jsonify({"success": True, "message": "Booking created successfully."}), 201

@app.route("/api/orders", methods=["GET"])
def get_orders():
    """API endpoint to fetch all orders for the logged-in user."""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session["user"]["id"]
    conn = get_db_connection()
    is_postgres = hasattr(conn.cursor, '__enter__')
    sql = "SELECT * FROM bookings WHERE user_id = %s ORDER BY id DESC" if is_postgres else "SELECT * FROM bookings WHERE user_id = ? ORDER BY id DESC"

    with conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        orders = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    return jsonify(orders), 200

@app.route("/api/orders/<int:order_id>", methods=["DELETE"])
def cancel_order(order_id):
    """API endpoint to cancel/delete an order."""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session["user"]["id"]
    conn = get_db_connection()
    is_postgres = hasattr(conn.cursor, '__enter__')
    sql = "DELETE FROM bookings WHERE id = %s AND user_id = %s" if is_postgres else "DELETE FROM bookings WHERE id = ? AND user_id = ?"

    try:
        with conn.cursor() as cur:
            cur.execute(sql, (order_id, user_id))
            # rowcount check ensures the user can only delete their own bookings
            if cur.rowcount == 0:
                conn.rollback()
                return jsonify({"error": "Order not found or not owned by user"}), 404
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
    return jsonify({"success": True, "message": "Order cancelled."}), 200


@app.route("/api/orders/<int:order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    """API endpoint to update an order's status."""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session["user"]["id"]
    data = request.json
    new_status = data.get("status")

    if not new_status:
        return jsonify({"error": "New status not provided"}), 400

    conn = get_db_connection()
    is_postgres = hasattr(conn.cursor, '__enter__')
    sql = "UPDATE bookings SET status = %s WHERE id = %s AND user_id = %s" if is_postgres else "UPDATE bookings SET status = ? WHERE id = ? AND user_id = ?"
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (new_status, order_id, user_id))
            if cur.rowcount == 0:
                conn.rollback()
                return jsonify({"error": "Order not found or not owned by user"}), 404
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
    return jsonify({"success": True, "message": f"Order status updated to {new_status}."}), 200


@app.route("/api/feedback", methods=["GET", "POST"])
def feedback():
    """API endpoint to submit or retrieve feedback."""
    conn = get_db_connection()
    is_postgres = hasattr(conn.cursor, '__enter__')

    if request.method == "POST":
        data = request.form
        sql = "INSERT INTO feedback (name, rating, text) VALUES (%s, %s, %s)" if is_postgres else "INSERT INTO feedback (name, rating, text) VALUES (?, ?, ?)"
        
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (data.get("name", "Anonymous"), data.get("rating"), data.get("text")))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()
        return jsonify({"success": True, "message": "Feedback submitted."}), 201

    else: # GET request
        sql = "SELECT * FROM feedback ORDER BY id DESC LIMIT 10"
        with conn.cursor() as cur:
            cur.execute(sql)
            feedback_list = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify(feedback_list), 200

@app.route("/api/shop/register", methods=["POST"])
def register_shop():
    """API endpoint for shop registration."""
    data = request.form
    conn = get_db_connection()
    is_postgres = hasattr(conn.cursor, '__enter__')
    sql = """
    INSERT INTO shops (shop_name, owner_name, email, phone, address, city, pincode, services)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """ if is_postgres else """
    INSERT INTO shops (shop_name, owner_name, email, phone, address, city, pincode, services) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (
                data.get("shopName"), data.get("ownerName"), data.get("email"),
                data.get("phone"), data.get("address"), data.get("city"),
                data.get("pincode"), data.get("services")
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
    return jsonify({"success": True, "message": "Shop registered successfully."}), 201


# -------------------- Main Execution --------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5432))
    app.run(host="0.0.0.0", port=port, debug=True)

