from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import requests
import datetime
import urllib.parse
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
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS buses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_no TEXT UNIQUE NOT NULL,
            route TEXT NOT NULL,
            departure TEXT NOT NULL,
            arrival TEXT NOT NULL,
            price REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            status TEXT NOT NULL DEFAULT 'waiting for payment',
            booking_type TEXT NOT NULL DEFAULT 'Online',
            payment_method TEXT DEFAULT 'Online',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(bus_id) REFERENCES buses(id)
        )
    """)

    conn.commit()
    conn.close()


def ensure_bookings_created_at_column():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()]
    if 'created_at' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN created_at TEXT")
        conn.execute("UPDATE bookings SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        conn.commit()
    conn.close()


def ensure_bookings_ticket_columns():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()]
    if 'booking_type' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN booking_type TEXT DEFAULT 'Online'")
        conn.execute("UPDATE bookings SET booking_type = 'Online' WHERE booking_type IS NULL")
    if 'payment_method' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN payment_method TEXT DEFAULT 'Online'")
        conn.execute("UPDATE bookings SET payment_method = 'Online' WHERE payment_method IS NULL")
    conn.commit()
    conn.close()


def ensure_bus_status_column():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(buses)").fetchall()]
    if 'status' not in columns:
        conn.execute("ALTER TABLE buses ADD COLUMN status TEXT DEFAULT 'available'")
        conn.commit()
    conn.close()


def ensure_users_created_at_column():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if 'created_at' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
        conn.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        conn.commit()
    conn.close()


def ensure_buses_created_at_column():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(buses)").fetchall()]
    if 'created_at' not in columns:
        conn.execute("ALTER TABLE buses ADD COLUMN created_at TEXT")
        conn.execute("UPDATE buses SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
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
ensure_bookings_created_at_column()
ensure_bookings_ticket_columns()
ensure_bus_status_column()
ensure_users_created_at_column()
ensure_buses_created_at_column()
create_default_admin()

def create_default_staff():
    conn = get_db_connection()
    staff = conn.execute("SELECT * FROM users WHERE role='staff'").fetchone()

    if not staff:
        conn.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            (
                "BusGo Staff",
                "staff@busgo.com",
                generate_password_hash("staff123"),
                "staff"
            )
        )
        conn.commit()

    conn.close()


create_default_staff()


@app.route("/")
def home():
    login_required = request.args.get("login_required")
    return render_template("index.html", login_required=login_required)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/schedules")
def schedules():
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    buses = conn.execute("""
        SELECT b.*, COUNT(bo.id) AS booked_count
        FROM buses b
        LEFT JOIN bookings bo ON b.id = bo.bus_id
        GROUP BY b.id
    """).fetchall()
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
        # Explicitly set the creation time and initial status
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur = conn.execute(
            "INSERT INTO bookings (user_id, bus_id, passenger_name, contact, seat_number, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], bus_id, passenger_name, contact, seat_number, 'waiting for payment', created_at)
        )
        conn.commit()
        booking_id = cur.lastrowid
        conn.close()

        return redirect(url_for("view_booking", booking_id=booking_id))

    # Fetch all booked seats for this bus
    booked_seats = conn.execute(
        "SELECT seat_number FROM bookings WHERE bus_id = ?", 
        (bus_id,)
    ).fetchall()
    booked_seat_numbers = [seat["seat_number"] for seat in booked_seats]
    booked_count = len(booked_seat_numbers)
    available_seats = max(0, 52 - booked_count)

    conn.close()
    return render_template(
        "booking.html",
        bus=bus,
        booked_seats=booked_seat_numbers,
        available_seats=available_seats,
        back_url=url_for('schedules')
    )


@app.route("/user")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT b.id, bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price, b.status, b.created_at
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.user_id = ?
        ORDER BY b.id DESC
    """, (session["user_id"],)).fetchall()

    bookings = []
    for row in rows:
        created_at_raw = row['created_at'] or ''
        try:
            parsed = datetime.datetime.strptime(created_at_raw, '%Y-%m-%d %H:%M:%S')
            booked_on = parsed.strftime('%b %d, %I:%M %p')
        except Exception:
            booked_on = created_at_raw
            
        bookings.append({
            'id': row['id'],
            'bus_no': row['bus_no'],
            'route': row['route'],
            'departure': row['departure'],
            'price': row['price'],
            'status': row['status'],
            'booked_on': booked_on
        })
    conn.close()

    return render_template("user_dashboard.html", bookings=bookings)


@app.route("/user/booking/<int:booking_id>")
def view_booking(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.id, b.passenger_name, b.contact, b.seat_number,
               b.booking_type, b.payment_method,
               bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price, b.status, b.bus_id, b.created_at
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()
    
    if not booking:
        conn.close()
        return redirect(url_for("user_dashboard"))

    # Calculate available seats for this bus
    booked_seats_count = conn.execute(
        "SELECT COUNT(*) as count FROM bookings WHERE bus_id = ?",
        (booking["bus_id"],)
    ).fetchone()["count"]
    
    available_seats = 52 - booked_seats_count
    
    created_at_raw = booking['created_at'] if booking['created_at'] else None
    formatted_created_at = created_at_raw
    if created_at_raw:
        try:
            created_at_parsed = datetime.datetime.strptime(created_at_raw, '%Y-%m-%d %H:%M:%S')
            formatted_created_at = created_at_parsed.strftime('%B %d, %Y %I:%M %p')
        except Exception:
            formatted_created_at = created_at_raw

    conn.close()

    return render_template("status.html", booking=booking, available_seats=available_seats, back_url=url_for('user_dashboard'), user_role='user', booking_created_at=formatted_created_at)

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

    url = "https://api.paymongo.com/v1/sources"

    payload = {
    "data": {
        "attributes": {
            "amount": amount,
            "redirect": {
                "success": url_for("payment_success", booking_id=booking_id, _external=True),
                "failed": url_for("view_booking", booking_id=booking_id, _external=True)
            },
            "type": "gcash",
            "currency": "PHP"
        }
    }
}

    response = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        auth=(PAYMONGO_SECRET_KEY, "")
    )

    if response.status_code != 200:
        return f"PayMongo Error: {response.text}"

    data = response.json()

    if "data" not in data:
        return f"PayMongo Error: {data}"

    checkout_url = data["data"]["attributes"]["redirect"]["checkout_url"]

    return redirect(checkout_url)

@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()

    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    bus_count = conn.execute("SELECT COUNT(*) FROM buses").fetchone()[0]
    booking_count = conn.execute("SELECT COUNT(*) FROM bookings WHERE date(created_at) = date('now')").fetchone()[0]

    conn.close()

    return render_template("admin_home.html",
                           user_count=user_count,
                           bus_count=bus_count,
                           booking_count=booking_count)


@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()

    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")

        if not fullname or not email or not password:
            conn.close()
            return redirect(url_for("admin_users", error="All fields are required."))

        if len(password) < 6:
            conn.close()
            return redirect(url_for("admin_users", error="Password must be at least 6 characters."))

        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            conn.close()
            return redirect(url_for("admin_users", error="That email is already registered."))

        conn.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            (
                fullname,
                email,
                generate_password_hash(password),
                role
            )
        )
        conn.commit()

    users = conn.execute(
        "SELECT id, fullname, email, role FROM users"
    ).fetchall()

    conn.close()

    return render_template("admin_users.html", users=users)


@app.route("/staff", methods=["GET", "POST"])
def staff_dashboard():
    if "user_id" not in session or session.get("role") != "staff":
        return redirect(url_for("home"))

    conn = get_db_connection()

    if request.method == "POST":
        bus_id = request.form.get("bus_id")
        passenger_name = request.form.get("passenger_name", "").strip()
        contact = request.form.get("contact", "").strip()
        seat_number = request.form.get("seat_number", "").strip()

        if not bus_id or not passenger_name or not contact or not seat_number:
            conn.close()
            return redirect(url_for("staff_dashboard", error="All fields are required."))

        existing_seat = conn.execute(
            "SELECT 1 FROM bookings WHERE bus_id = ? AND seat_number = ?",
            (bus_id, seat_number)
        ).fetchone()

        if existing_seat:
            conn.close()
            return redirect(url_for("staff_dashboard", error="That seat is already booked for the selected bus."))

        payment_status = request.form.get("payment_status", "waiting for payment").strip() or "waiting for payment"
        payment_method = request.form.get("payment_method", "Walk-in").capitalize()
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            "INSERT INTO bookings (user_id, bus_id, passenger_name, contact, seat_number, status, booking_type, payment_method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session["user_id"],
                bus_id,
                passenger_name,
                contact,
                seat_number,
                payment_status,
                "Walk-in",
                payment_method,
                created_at
            )
        )
        booking_id = cur.lastrowid
        conn.commit()
        conn.close()

        if payment_status == "paid":
            return redirect(url_for("ticket", booking_id=booking_id))

        return redirect(url_for("staff_dashboard", success="Walk-in booking added successfully."))

    buses = conn.execute("SELECT * FROM buses").fetchall()
    bookings = conn.execute("""
        SELECT b.id, b.passenger_name, b.contact, b.seat_number, b.status, b.created_at,
               bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.user_id = ?
        ORDER BY b.created_at DESC
    """, (session["user_id"],)).fetchall()

    booked_seats_by_bus = {}
    all_bookings = conn.execute("SELECT bus_id, seat_number FROM bookings").fetchall()
    for row in all_bookings:
        bus_key = str(row["bus_id"])
        booked_seats_by_bus.setdefault(bus_key, []).append(str(row["seat_number"]))

    active_bookings_by_date = {}
    history_bookings_by_date = {}
    for row in bookings:
        created_at = row['created_at'] or ''
        try:
            parsed = datetime.datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            date_key = parsed.strftime('%B %d, %Y')
            time_label = parsed.strftime('%I:%M %p')
        except Exception:
            date_key = 'Unknown Date'
            time_label = created_at

        booking_item = {
            'id': row['id'],
            'passenger_name': row['passenger_name'],
            'contact': row['contact'],
            'seat_number': row['seat_number'],
            'status': row['status'],
            'bus_no': row['bus_no'],
            'route': row['route'],
            'departure': row['departure'],
            'arrival': row['arrival'],
            'price': row['price'],
            'created_time': time_label,
            'created_date': date_key
        }

        if row['status'] in ('paid', 'cancelled'):
            history_bookings_by_date.setdefault(date_key, []).append(booking_item)
        else:
            active_bookings_by_date.setdefault(date_key, []).append(booking_item)

    buses_json = [dict(bus) for bus in buses]
    conn.close()

    return render_template(
        "staff_dashboard.html",
        buses=buses,
        bookings=bookings,
        active_bookings_by_date=active_bookings_by_date,
        history_bookings_by_date=history_bookings_by_date,
        booked_seats_by_bus=booked_seats_by_bus,
        buses_json=buses_json,
    )


@app.route("/staff/booking/<int:booking_id>")
def staff_view_booking(booking_id):
    if "user_id" not in session or session.get("role") != "staff":
        return redirect(url_for("home"))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.id, b.passenger_name, b.contact, b.seat_number,
               bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price, b.status, b.bus_id, b.created_at,
               u.fullname AS user_name, u.email AS user_email
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        JOIN users u ON u.id = b.user_id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()
    
    if not booking:
        conn.close()
        return redirect(url_for("staff_dashboard"))

    # Calculate available seats for this bus
    booked_seats_count = conn.execute(
        "SELECT COUNT(*) as count FROM bookings WHERE bus_id = ?",
        (booking["bus_id"],)
    ).fetchone()["count"]
    
    available_seats = 52 - booked_seats_count
    
    created_at_raw = booking['created_at'] if booking['created_at'] else None
    formatted_created_at = created_at_raw
    if created_at_raw:
        try:
            created_at_parsed = datetime.datetime.strptime(created_at_raw, '%Y-%m-%d %H:%M:%S')
            formatted_created_at = created_at_parsed.strftime('%B %d, %Y %I:%M %p')
        except Exception:
            formatted_created_at = created_at_raw

    conn.close()

    return render_template("status.html", booking=booking, available_seats=available_seats, back_url=url_for('staff_dashboard'), user_role='staff', booking_created_at=formatted_created_at)


@app.route("/admin/buses", methods=["GET", "POST"])
def admin_buses():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    edit_bus = None

    if request.method == "POST":
        bus_id = request.form.get("bus_id")
        bus_no = request.form["bus_no"]
        route = request.form["route"]
        departure = request.form["departure"]
        arrival = request.form["arrival"]
        price = request.form["price"]
        status = request.form.get("status", "available")

        if bus_id:
            conn.execute(
                "UPDATE buses SET bus_no = ?, route = ?, departure = ?, arrival = ?, price = ?, status = ? WHERE id = ?",
                (bus_no, route, departure, arrival, price, status, bus_id)
            )
        else:
            conn.execute(
                "INSERT INTO buses (bus_no, route, departure, arrival, price, status) VALUES (?, ?, ?, ?, ?, ?)",
                (bus_no, route, departure, arrival, price, status)
            )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_buses"))

    edit_id = request.args.get("edit_id")
    if edit_id:
        edit_bus = conn.execute("SELECT * FROM buses WHERE id = ?", (edit_id,)).fetchone()

    buses = conn.execute("SELECT * FROM buses").fetchall()
    conn.close()
    return render_template("admin_buses.html", buses=buses, edit_bus=edit_bus)


@app.route("/admin/delete_bus/<int:bus_id>")
def delete_bus(bus_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    conn.execute("DELETE FROM buses WHERE id = ?", (bus_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_buses"))


@app.route("/admin/toggle_bus_status/<int:bus_id>")
def toggle_bus_status(bus_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    bus = conn.execute("SELECT status FROM buses WHERE id = ?", (bus_id,)).fetchone()
    if bus:
        new_status = 'available' if bus['status'] == 'under_maintenance' else 'under_maintenance'
        conn.execute("UPDATE buses SET status = ? WHERE id = ?", (new_status, bus_id))
        conn.commit()
    conn.close()

    return redirect(url_for("admin_buses"))


@app.route("/admin/delete_user/<int:user_id>")
def delete_user(user_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_users"))


@app.route("/admin/bookings")
def admin_bookings():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT b.id,
               u.fullname AS user,
               u.role AS user_role,
               bs.bus_no,
               bs.route,
               b.seat_number,
               b.status,
               b.created_at
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN buses bs ON bs.id = b.bus_id
        ORDER BY b.id DESC
    """).fetchall()

    bookings = []
    for row in rows:
        created_at_raw = row['created_at'] or ''
        try:
            parsed = datetime.datetime.strptime(created_at_raw, '%Y-%m-%d %H:%M:%S')
            created_date = parsed.strftime('%B %d, %Y')
            created_time = parsed.strftime('%I:%M %p')
        except Exception:
            created_date = created_at_raw
            created_time = ''

        bookings.append({
            'id': row['id'],
            'user': row['user'],
            'user_role': row['user_role'],
            'bus_no': row['bus_no'],
            'route': row['route'],
            'seat_number': row['seat_number'],
            'status': row['status'],
            'created_date': created_date,
            'created_time': created_time,
            'booking_type': 'Walk-in' if row['user_role'] == 'staff' else 'Online'
        })
    conn.close()

    return render_template("admin_bookings.html", bookings=bookings)


@app.route("/admin/booking/<int:booking_id>")
def admin_view_booking(booking_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.id, b.passenger_name, b.contact, b.seat_number,
               bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price, b.status, b.bus_id, b.created_at,
               u.fullname AS user_name, u.email AS user_email
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        JOIN users u ON u.id = b.user_id
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    
    if not booking:
        conn.close()
        return redirect(url_for("admin_bookings"))

    # Calculate available seats for this bus
    booked_seats_count = conn.execute(
        "SELECT COUNT(*) as count FROM bookings WHERE bus_id = ?",
        (booking["bus_id"],)
    ).fetchone()["count"]
    
    available_seats = 52 - booked_seats_count
    
    created_at_raw = booking['created_at'] if booking['created_at'] else None
    formatted_created_at = created_at_raw
    if created_at_raw:
        try:
            created_at_parsed = datetime.datetime.strptime(created_at_raw, '%Y-%m-%d %H:%M:%S')
            formatted_created_at = created_at_parsed.strftime('%B %d, %Y %I:%M %p')
        except Exception:
            formatted_created_at = created_at_raw

    conn.close()

    return render_template("status.html", booking=booking, available_seats=available_seats, back_url=url_for('admin_bookings'), user_role='admin', booking_created_at=formatted_created_at)


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


@app.route("/user/delete_booking/<int:booking_id>")
def user_delete_booking(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    booking = conn.execute(
        "SELECT status FROM bookings WHERE id = ? AND user_id = ?",
        (booking_id, session["user_id"])
    ).fetchone()

    if booking and booking["status"] in ("paid", "cancelled"):
        conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()

    conn.close()
    return redirect(url_for("user_dashboard"))


@app.route("/admin/delete_booking/<int:booking_id>")
def admin_delete_booking(booking_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    booking = conn.execute(
        "SELECT b.status, u.role AS user_role FROM bookings b JOIN users u ON u.id = b.user_id WHERE b.id = ?",
        (booking_id,)
    ).fetchone()

    if booking and (booking["status"] in ("paid", "cancelled") or booking["user_role"] == 'staff'):
        conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()

    conn.close()
    return redirect(url_for("admin_bookings"))


@app.route("/register", methods=["POST"])
def register():
    try:
        email = request.form.get("email", "").strip()
        fullname = request.form.get("fullname", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        # Validation
        if not email or not fullname or not password:
            return redirect(url_for("home", error="All fields are required"))
        
        if password != confirm_password:
            return redirect(url_for("home", error="Passwords do not match"))
        
        if len(password) < 6:
            return redirect(url_for("home", error="Password must be at least 6 characters"))
        
        conn = get_db_connection()
        
        # Check if email already exists
        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        
        if existing_user:
            conn.close()
            return redirect(url_for("home", error="Email already registered. Please login or use a different email."))
        
        # Register new user
        conn.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            (
                fullname,
                email,
                generate_password_hash(password),
                "user"
            )
        )
        conn.commit()
        conn.close()
        
        return redirect(url_for("home", success="Registration successful! Please log in."))
    
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return redirect(url_for("home", error="An error occurred during registration. Please try again."))


@app.route("/payment_success/<int:booking_id>")
def payment_success(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home"))

    conn = get_db_connection()

    conn.execute(
        "UPDATE bookings SET status = 'verifying payment', payment_method = 'Online' WHERE id = ? AND user_id = ?",
        (booking_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect(url_for("view_booking", booking_id=booking_id))

@app.route("/admin/confirm_payment/<int:booking_id>")
def confirm_payment(booking_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()

    conn.execute(
        "UPDATE bookings SET status = 'paid' WHERE id = ?",
        (booking_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_bookings"))

@app.route("/ticket/<int:booking_id>")
def ticket(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home"))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT b.id, b.passenger_name, b.contact, b.seat_number,
               b.booking_type, b.payment_method, b.status, b.created_at,
               bs.bus_no, bs.route, bs.departure, bs.arrival, bs.price
        FROM bookings b
        JOIN buses bs ON bs.id = b.bus_id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()

    if not booking or booking["status"] != "paid":
        conn.close()
        return redirect(url_for("view_booking", booking_id=booking_id))

    created_at_raw = booking['created_at'] if booking['created_at'] else None
    formatted_created_at = created_at_raw
    if created_at_raw:
        try:
            created_at_parsed = datetime.datetime.strptime(created_at_raw, '%Y-%m-%d %H:%M:%S')
            formatted_created_at = created_at_parsed.strftime('%B %d, %Y %I:%M %p')
        except Exception:
            formatted_created_at = created_at_raw

    qr_data = (
        f"Ticket #{booking['id']}\n"
        f"Passenger: {booking['passenger_name']}\n"
        f"Booking Type: {booking['booking_type']}\n"
        f"Bus No: {booking['bus_no']}\n"
        f"Seat No: {booking['seat_number']}\n"
        f"Departure: {booking['departure']}\n"
        f"Arrival: {booking['arrival']}\n"
        f"Payment Method: {booking['payment_method']}\n"
    )
    qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=280x280&data=" + urllib.parse.quote(qr_data)

    conn.close()
    return render_template("booking_detail.html", booking=booking, booking_created_at=formatted_created_at, qr_url=qr_url)


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
    try:
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not email or not password:
            return redirect(url_for("home", error="Email and password are required"))
        
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["fullname"] = user["fullname"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user["role"] == "staff":
                return redirect(url_for("staff_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))
        
        return redirect(url_for("home", error="Invalid email or password"))
    
    except Exception as e:
        print(f"Login error: {str(e)}")
        return redirect(url_for("home", error="An error occurred during login. Please try again."))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)