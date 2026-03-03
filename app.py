from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import requests
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "busgo_secret_key"
PAYMONGO_SECRET_KEY = "sk_test_XXXXXXXXXXXXXXXX"
DATABASE = "busgo.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
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
            passenger_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            seat_number TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed',
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(bus_id) REFERENCES buses(id)
        )
    """)

    conn.commit()
    conn.close()


def create_default_admin():
    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM users WHERE role='admin'").fetchone()

    if not admin:
        conn.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            (
                "System Admin",
                "admin@busgo.com",
                generate_password_hash("admin123"),
                "admin"
            )
        )
        conn.commit()

    conn.close()


create_tables()
create_default_admin()


@app.route("/")
def home():
    login_required = request.args.get("login_required")
    return render_template("index.html", login_required=login_required)


@app.route("/schedules")
def schedules():
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    buses = conn.execute("SELECT * FROM buses").fetchall()
    conn.close()
    return render_template("schedules.html", buses=buses)


@app.route("/booking/<int:bus_id>", methods=["GET", "POST"])
def booking(bus_id):
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    bus = conn.execute("SELECT * FROM buses WHERE id = ?", (bus_id,)).fetchone()

    if request.method == "POST":
        passenger_name = request.form["passenger_name"]
        contact = request.form["contact"]
        seat_number = request.form["seat_number"]

        cur = conn.execute(
            "INSERT INTO bookings (user_id, bus_id, passenger_name, contact, seat_number) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], bus_id, passenger_name, contact, seat_number)
        )
        conn.commit()
        booking_id = cur.lastrowid
        conn.close()

        return redirect(url_for("view_booking", booking_id=booking_id))

    conn.close()
    return render_template("booking.html", bus=bus)


@app.route("/user")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    bookings = conn.execute("""
        SELECT b.id, bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price, b.status
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.user_id = ?
        ORDER BY b.id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("user_dashboard.html", bookings=bookings)


@app.route("/user/booking/<int:booking_id>")
def view_booking(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.id, b.passenger_name, b.contact, b.seat_number,
               bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price, b.status
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()
    conn.close()

    if not booking:
        return redirect(url_for("user_dashboard"))

    return render_template("status.html", booking=booking)

@app.route("/pay/<int:booking_id>")
def pay_booking(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home"))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.id, bs.price
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()
    conn.close()

    if not booking:
        return redirect(url_for("user_dashboard"))

    amount = int(float(booking["price"]) * 100)

    url = "https://api.paymongo.com/v1/checkout_sessions"

    payload = {
        "data": {
            "attributes": {
                "send_email_receipt": False,
                "show_description": True,
                "show_line_items": True,
                "line_items": [{
                    "currency": "PHP",
                    "amount": amount,
                    "name": "BusGo Ticket Payment",
                    "quantity": 1
                }],
                "payment_method_types": ["gcash", "card"],
                "success_url": url_for("payment_success", booking_id=booking_id, _external=True),
                "cancel_url": url_for("view_booking", booking_id=booking_id, _external=True)
            }
        }
    }

    response = requests.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json"
        },
        auth=(PAYMONGO_SECRET_KEY, "")
    )

    # SAFETY CHECK
    if response.status_code != 200:
        return f"PayMongo Error: {response.text}"

    response_data = response.json()

    if "data" not in response_data:
        return f"PayMongo Error: {response_data}"

    checkout_url = response_data["data"]["attributes"]["checkout_url"]

    return redirect(checkout_url)

@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()

    users = conn.execute(
        "SELECT id, fullname, email, role FROM users"
    ).fetchall()

    buses = conn.execute(
        "SELECT * FROM buses"
    ).fetchall()

    conn.close()

    return render_template("admin_dashboard.html",
                           users=users,
                           buses=buses)

    conn = get_db_connection()

    if request.method == "POST":
        conn.execute(
            "INSERT INTO buses (bus_no, route, departure, arrival, price) VALUES (?, ?, ?, ?, ?)",
            (
                request.form["bus_no"],
                request.form["route"],
                request.form["departure"],
                request.form["arrival"],
                request.form["price"]
            )
        )
        conn.commit()

    users = conn.execute("SELECT id, fullname, email, role FROM users").fetchall()

    buses = conn.execute("SELECT * FROM buses").fetchall()

    bookings = conn.execute("""
        SELECT b.id,
               u.fullname AS user,
               bs.bus_no,
               b.seat_number,
               b.status
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN buses bs ON bs.id = b.bus_id
        ORDER BY b.id DESC
    """).fetchall()

    conn.close()

    return render_template("admin_dashboard.html",
                           users=users,
                           buses=buses,
                           bookings=bookings)

@app.route("/admin/buses", methods=["GET", "POST"])
def admin_buses():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()

    if request.method == "POST":
        conn.execute(
            "INSERT INTO buses (bus_no, route, departure, arrival, price) VALUES (?, ?, ?, ?, ?)",
            (
                request.form["bus_no"],
                request.form["route"],
                request.form["departure"],
                request.form["arrival"],
                request.form["price"]
            )
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_buses"))

    buses = conn.execute("SELECT * FROM buses").fetchall()
    conn.close()
    return render_template("admin_buses.html", buses=buses)


@app.route("/admin/delete_bus/<int:bus_id>")
def delete_bus(bus_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    conn.execute("DELETE FROM buses WHERE id = ?", (bus_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_buses"))


@app.route("/admin/bookings")
def admin_bookings():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    bookings = conn.execute("""
        SELECT b.id,
               u.fullname AS user,
               bs.bus_no,
               bs.route,
               b.seat_number,
               b.status
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN buses bs ON bs.id = b.bus_id
        ORDER BY b.id DESC
    """).fetchall()
    conn.close()

    return render_template("admin_bookings.html", bookings=bookings)


@app.route("/admin/cancel_booking/<int:booking_id>")
def cancel_booking(booking_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    conn.execute(
        "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
        (booking_id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin_bookings"))


@app.route("/register", methods=["POST"])
def register():
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
        (
            request.form["fullname"],
            request.form["email"],
            generate_password_hash(request.form["password"]),
            "user"
        )
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))


@app.route("/payment_success/<int:booking_id>")
def payment_success(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home"))

    conn = get_db_connection()
    conn.execute(
        "UPDATE bookings SET status = 'paid' WHERE id = ? AND user_id = ?",
        (booking_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("view_booking", booking_id=booking_id))


@app.route("/user/cancel/<int:booking_id>")
def user_cancel_booking(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home"))

    conn = get_db_connection()
    conn.execute(
        "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND user_id = ?",
        (booking_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("view_booking", booking_id=booking_id))


@app.route("/login", methods=["POST"])
def login():
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (request.form["email"],)
    ).fetchone()
    conn.close()

    if user and check_password_hash(user["password"], request.form["password"]):
        session["user_id"] = user["id"]
        session["role"] = user["role"]

        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("user_dashboard"))

    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)