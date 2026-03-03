from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "busgo_secret_key"

DATABASE = "busgo.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_table():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS buses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_no TEXT UNIQUE NOT NULL,
            route TEXT NOT NULL,
            departure TEXT NOT NULL,
            arrival TEXT NOT NULL,
            price REAL NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bus_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed',
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(bus_id) REFERENCES buses(id)
        )
    """)

    cur = conn.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]
    if 'role' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

    conn.commit()
    conn.close()


def create_default_admin():
    conn = get_db_connection()

    # Check if any admin already exists
    admin = conn.execute(
        "SELECT * FROM users WHERE role = 'admin'"
    ).fetchone()

    if not admin:
        default_email = "admin@busgo.com"
        default_password = "admin123"
        hashed_password = generate_password_hash(default_password)

        conn.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            ("System Admin", default_email, hashed_password, "admin")
        )

        conn.commit()
        print("Default admin account created.")
        print("Email:", default_email)
        print("Password:", default_password)

    conn.close()

create_table()
create_default_admin()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/schedules")
def schedules():
    return render_template("schedules.html")


@app.route("/booking", methods=["GET", "POST"])
def booking():
    if "user_id" not in session:
        flash("Please login first!")
        return redirect(url_for("home"))

    if request.method == "POST":
        bus_id = request.form["bus_id"]

        conn = get_db_connection()
        cur = conn.execute(
            "INSERT INTO bookings (user_id, bus_id) VALUES (?, ?)",
            (session["user_id"], bus_id)
        )
        conn.commit()
        booking_id = cur.lastrowid
        conn.close()

        return redirect(url_for("view_booking", booking_id=booking_id))

    conn = get_db_connection()
    buses = conn.execute("SELECT * FROM buses").fetchall()
    conn.close()

    return render_template("booking.html", buses=buses)


@app.route("/booking/<int:booking_id>")
def view_booking(booking_id):
    if "user_id" not in session:
        flash("Please login first!")
        return redirect(url_for("home"))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.id, b.passenger_name, b.contact, b.status,
               bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()

    conn.close()

    if not booking:
        flash("Booking not found.")
        return redirect(url_for("home"))

    return render_template("status.html", booking=booking)





@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        flash("You do not have permission to access that page.")
        return redirect(url_for("home"))
    # compute simple stats for dashboard
    conn = get_db_connection()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    bus_count = conn.execute("SELECT COUNT(*) FROM buses").fetchone()[0]
    booking_count = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    conn.close()
    return render_template("admin_home.html", user_count=user_count, bus_count=bus_count, booking_count=booking_count)


@app.route("/user")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("home"))

    # redirect other roles to their own dashboards
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    if session.get("role") == "driver":
        return redirect(url_for("driver_dashboard"))

    # fetch user's bookings
    conn = get_db_connection()
    bookings = conn.execute(
        """
        SELECT b.id, bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price, b.status
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.user_id = ?
        ORDER BY b.id DESC
        """,
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("user_dashboard.html", bookings=bookings)

@app.route("/user/booking/<int:booking_id>")
def view_booking(booking_id):
    if "user_id" not in session:
        flash("Please login first!")
        return redirect(url_for("home"))
    conn = get_db_connection()
    booking = conn.execute(
        """
        SELECT b.id, b.user_id, bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price, b.status
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.id = ?
        """,
        (booking_id,)
    ).fetchone()
    conn.close()
    if not booking or booking["user_id"] != session["user_id"]:
        flash("Booking not found.")
        return redirect(url_for("user_dashboard"))
    return render_template("booking_detail.html", booking=booking)

@app.route("/user/booking/<int:booking_id>/cancel", methods=["POST"])
def cancel_user_booking(booking_id):
    if "user_id" not in session:
        flash("Please login first!")
        return redirect(url_for("home"))
    conn = get_db_connection()
    booking = conn.execute("SELECT user_id FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking or booking["user_id"] != session["user_id"]:
        flash("Booking not found.")
        return redirect(url_for("user_dashboard"))
    conn.execute("UPDATE bookings SET status='cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    flash("Booking cancelled successfully.")
    return redirect(url_for("user_dashboard"))

# admin-specific management routes
@app.route("/admin/buses", methods=["GET", "POST"])
def admin_buses():
    if session.get("role") != "admin":
        flash("You do not have permission to access that page.")
        return redirect(url_for("home"))
    conn = get_db_connection()
    if request.method == "POST":
        bus_no = request.form["bus_no"]
        route = request.form["route"]
        departure = request.form["departure"]
        arrival = request.form["arrival"]
        price = request.form["price"]
        try:
            conn.execute(
                "INSERT INTO buses (bus_no, route, departure, arrival, price) VALUES (?, ?, ?, ?, ?)",
                (bus_no, route, departure, arrival, price)
            )
            conn.commit()
            flash("Bus added successfully.")
        except sqlite3.IntegrityError:
            flash("Bus number already exists.")
        return redirect(url_for("admin_buses"))
    buses = conn.execute("SELECT * FROM buses").fetchall()
    conn.close()
    return render_template("admin_buses.html", buses=buses)

@app.route("/admin/buses/delete/<int:bus_id>")
def delete_bus(bus_id):
    if session.get("role") != "admin":
        flash("You do not have permission to perform that action.")
        return redirect(url_for("home"))
    conn = get_db_connection()
    conn.execute("DELETE FROM buses WHERE id = ?", (bus_id,))
    conn.commit()
    conn.close()
    flash("Bus removed.")
    return redirect(url_for("admin_buses"))

@app.route("/admin/bookings")
def admin_bookings():
    if session.get("role") != "admin":
        flash("You do not have permission to access that page.")
        return redirect(url_for("home"))
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT b.id, u.fullname as user, bs.bus_no, bs.route, b.status
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN buses bs ON bs.id = b.bus_id
        """
    ).fetchall()
    conn.close()
    return render_template("admin_bookings.html", bookings=rows)

@app.route('/admin/bookings/cancel/<int:booking_id>')
def cancel_booking(booking_id):
    if session.get("role") != "admin":
        flash("You do not have permission to perform that action.")
        return redirect(url_for("home"))
    conn = get_db_connection()
    conn.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()
    flash("Booking marked as cancelled.")
    return redirect(url_for("admin_bookings"))


@app.route("/register", methods=["POST"])
def register():
    fullname = request.form["fullname"]
    email = request.form["email"]
    password = request.form["password"]
    confirm = request.form.get("confirm_password", "")
    role = "user"

    if password != confirm:
        flash("Passwords do not match!")
        return redirect(url_for("home"))

    hashed_password = generate_password_hash(password)

    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            (fullname, email, hashed_password, role)
        )
        conn.commit()
        conn.close()
        flash("Registration successful! Please login.")
    except sqlite3.IntegrityError:
        flash("Email already registered!")

    return redirect(url_for("home"))


@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()
    conn.close()

    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["id"]
        session["fullname"] = user["fullname"]
        session["role"] = user["role"]

        flash(f"Welcome back, {user['fullname']}!")

        # dispatch based on role
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        elif user["role"] == "driver":
            return redirect(url_for("driver_dashboard"))
        else:
            return redirect(url_for("user_dashboard"))
    else:
        flash("Invalid email or password!")
        return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)