import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import requests
import datetime
from flask import jsonify
import urllib.parse
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "busgo_secret_key"
app.config['TEMPLATES_AUTO_RELOAD'] = True
PAYMONGO_SECRET_KEY = os.environ.get("PAYMONGO_SECRET_KEY", "sk_test_2Qq7gVeyLzRf1eB7xYyMUTUF")
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
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS buses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_no TEXT UNIQUE NOT NULL,
            capacity INTEGER DEFAULT 52,
            status TEXT DEFAULT 'available',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL
        )
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_id INTEGER,
            route_id INTEGER,
            departure TEXT,
            arrival TEXT,
            price REAL,
            status TEXT DEFAULT 'scheduled',
            FOREIGN KEY(bus_id) REFERENCES buses(id),
            FOREIGN KEY(route_id) REFERENCES routes(id)
        )
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS passengers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT,
            contact TEXT
        )
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            trip_id INTEGER,
            passenger_id INTEGER,
            seat_number TEXT,
            status TEXT DEFAULT 'waiting for payment',
            booking_type TEXT DEFAULT 'Online',
            payment_method TEXT DEFAULT 'Online',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(trip_id) REFERENCES trips(id),
            FOREIGN KEY(passenger_id) REFERENCES passengers(id)
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
    
def ensure_bookings_trip_id_column():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()]

    if 'trip_id' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN trip_id INTEGER")
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


def ensure_buses_updated_at_column():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(buses)").fetchall()]
    if 'updated_at' not in columns:
        conn.execute("ALTER TABLE buses ADD COLUMN updated_at TEXT")
        conn.execute("UPDATE buses SET updated_at = created_at WHERE updated_at IS NULL")
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
ensure_buses_updated_at_column()
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

    trips = conn.execute("""
        SELECT 
            t.id AS trip_id,
            b.id AS bus_id,
            b.bus_no,
            b.status,
            b.capacity,
            r.origin,
            r.destination,
            t.departure,
            t.arrival,
            t.price,
            COUNT(bo.id) AS booked_count
        FROM trips t
        JOIN buses b ON b.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
        LEFT JOIN bookings bo ON bo.trip_id = t.id
        GROUP BY t.id
    """).fetchall()

    conn.close()

    return render_template("schedules.html", buses=trips)


@app.route("/booking/<int:trip_id>", methods=["GET", "POST"])
def booking(trip_id):
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()

    trip = conn.execute("""
        SELECT 
            t.id,
            t.bus_id,
            t.departure,
            t.arrival,
            t.price,
            b.bus_no,
            b.capacity,
            b.status,
            r.origin,
            r.destination
        FROM trips t
        JOIN buses b ON b.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
        WHERE t.id = ?
    """, (trip_id,)).fetchone()

    if not trip or trip["status"] != "available":
        conn.close()
        flash("This trip is unavailable.")
        return redirect(url_for("schedules"))

    if request.method == "POST":
        passenger_name = request.form["passenger_name"]
        contact = request.form["contact"]
        seat_number = request.form["seat_number"]

        if not contact.isdigit() or len(contact) != 11:
            conn.close()
            flash("Invalid contact number.")
            return redirect(url_for("booking", trip_id=trip_id))

        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur = conn.execute(
            "INSERT INTO passengers (fullname, contact) VALUES (?, ?)",
            (passenger_name, contact)
        )
        passenger_id = cur.lastrowid

        cur = conn.execute("""
            INSERT INTO bookings (
                user_id, trip_id, passenger_id, seat_number,
                status, booking_type, payment_method, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            trip_id,
            passenger_id,
            seat_number,
            "waiting for payment",
            "Online",
            "Online",
            created_at
        ))

        conn.commit()
        booking_id = cur.lastrowid
        conn.close()

        return redirect(url_for("view_booking", booking_id=booking_id))

    booked_seats = conn.execute("""
        SELECT seat_number
        FROM bookings
        WHERE trip_id = ?
    """, (trip_id,)).fetchall()

    booked_seat_numbers = [s["seat_number"] for s in booked_seats]
    available_seats = max(0, trip["capacity"] - len(booked_seat_numbers))

    conn.close()

    return render_template(
        "booking.html",
        trip=trip,
        booked_seats=booked_seat_numbers,
        available_seats=available_seats,
        back_url=url_for("schedules")
    )


@app.route("/user")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT 
            b.id,
            bs.bus_no,
            r.origin,
            r.destination,
            t.departure,
            t.arrival,
            t.price,
            b.status,
            b.created_at
        FROM bookings b
        JOIN trips t ON t.id = b.trip_id
        JOIN buses bs ON bs.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
        WHERE b.user_id = ?
        ORDER BY b.id DESC
    """, (session["user_id"],)).fetchall()

    bookings = []
    for row in rows:
        created_at_raw = row['created_at'] or ''
        try:
            parsed = datetime.datetime.strptime(created_at_raw, '%Y-%m-%d %H:%M:%S')
            booked_on = parsed.strftime('%b %d, %I:%M %p')
        except:
            booked_on = created_at_raw

        bookings.append({
            'id': row['id'],
            'bus_no': row['bus_no'],
            'origin': row['origin'],
            'destination': row['destination'],
            'departure': row['departure'],
            'arrival': row['arrival'],
            'price': row['price'],
            'status': row['status'],
            'booked_on': booked_on
        })
    conn.close()

    return render_template("user_dashboard.html", bookings=bookings)

@app.route("/api/booked-seats/<int:trip_id>")
def booked_seats(trip_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT seat_number FROM bookings WHERE trip_id = ?",
        (trip_id,)
    ).fetchall()
    conn.close()

    seats = [row["seat_number"] for row in rows]
    return jsonify(seats)

@app.route("/user/booking/<int:booking_id>")
def view_booking(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT 
            b.id,
            b.trip_id,
            b.seat_number,
            b.status,
            b.created_at,
            b.booking_type,
            b.payment_method,

            u.fullname AS customer,

            p.fullname AS passenger_name,
            p.contact,

            t.departure,
            t.arrival,
            t.price,

            r.origin,
            r.destination,

            (r.origin || ' → ' || r.destination) AS route,

            bu.bus_no

        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN passengers p ON b.passenger_id = p.id
        JOIN trips t ON b.trip_id = t.id
        JOIN buses bu ON t.bus_id = bu.id
        JOIN routes r ON t.route_id = r.id
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    
    if not booking:
        conn.close()
        return redirect(url_for("user_dashboard"))

    # Calculate available seats for this bus
    booked_seats_count = conn.execute(
        "SELECT COUNT(*) as count FROM bookings WHERE trip_id = ?",
        (booking["trip_id"],)
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
        SELECT b.id, t.price, b.status
        FROM bookings b
        JOIN trips t ON t.id = b.trip_id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()

    if not booking:
        conn.close()
        return redirect(url_for("user_dashboard"))
    
    # Check if booking is already paid
    if booking["status"] == "paid":
        conn.close()
        flash("This booking has already been paid.")
        return redirect(url_for("ticket", booking_id=booking_id))

    amount = int(float(booking["price"]) * 100)

    url = "https://api.paymongo.com/v1/sources"

    payload = {
        "data": {
            "attributes": {
                "amount": amount,
                "currency": "PHP",
                "type": "gcash",
                "redirect": {
                    "success": url_for("payment_success", booking_id=booking_id, _external=True),
                    "failed": url_for("payment_page", booking_id=booking_id, status="failed", _external=True)
                },
                "metadata": {
                    "booking_id": str(booking_id)
                }
            }
        }
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            auth=(PAYMONGO_SECRET_KEY, "")
        )

        response.raise_for_status()
        data = response.json()

        checkout_url = data["data"]["attributes"]["redirect"]["checkout_url"]

        # Update booking status to processing payment
        conn.execute("""
            UPDATE bookings
            SET status = 'processing payment'
            WHERE id = ?
        """, (booking_id,))
        conn.commit()
        conn.close()

        return redirect(checkout_url)

    except Exception as e:
        print(f"PayMongo Error: {e}")
        conn.close()
        flash("Payment initialization failed. Please try again.")
        return redirect(url_for("payment_page", booking_id=booking_id, status="failed"))


@app.route("/payment/<int:booking_id>")
def payment_page(booking_id):
    if "user_id" not in session:
        return redirect(url_for("home", login_required=1))
    
    conn = get_db_connection()
    
    # Get complete booking details
    booking = conn.execute("""
        SELECT 
            b.id,
            b.seat_number,
            b.status,
            b.booking_type,
            b.payment_method,
            p.fullname AS passenger_name,
            p.contact,
            t.departure,
            t.arrival,
            t.price,
            r.origin,
            r.destination,
            r.origin || ' → ' || r.destination AS route,
            bu.bus_no,
            bu.capacity
        FROM bookings b
        JOIN passengers p ON b.passenger_id = p.id
        JOIN trips t ON b.trip_id = t.id
        JOIN buses bu ON t.bus_id = bu.id
        JOIN routes r ON t.route_id = r.id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()
    
    if not booking:
        conn.close()
        flash("Booking not found")
        return redirect(url_for("user_dashboard"))
    
    # Check if booking is already paid
    if booking["status"] == "paid":
        conn.close()
        flash("This booking has already been paid.")
        return redirect(url_for("ticket", booking_id=booking_id))
    
    # Calculate available seats
    booked_seats_count = conn.execute("""
        SELECT COUNT(*) as count FROM bookings 
        WHERE trip_id = (SELECT trip_id FROM bookings WHERE id = ?)
    """, (booking_id,)).fetchone()["count"]
    
    available_seats = booking["capacity"] - booked_seats_count
    
    conn.close()
    
    # Get payment status from query parameter
    payment_status = request.args.get("status", "pending")
    
    # IMPORTANT: Make sure to pass available_seats to the template
    return render_template(
        "payment.html",
        booking=booking,
        available_seats=available_seats,
        back_url=url_for("view_booking", booking_id=booking_id),
        payment_status=payment_status
    )

@app.route("/paymongo/webhook", methods=["POST"])
def paymongo_webhook():
    data = request.get_json(silent=True)

    if not data:
        return "", 400

    try:
        event_type = data.get("data", {}).get("attributes", {}).get("type")

        # Only proceed when payment is chargeable
        if event_type != "source.chargeable":
            return "", 200

        source_data = data["data"]["attributes"]["data"]

        source_id = source_data.get("id")
        amount = source_data.get("attributes", {}).get("amount")

        metadata = source_data.get("attributes", {}).get("metadata", {})
        booking_id = metadata.get("booking_id")

        # fallback (only if metadata is missing)
        if not booking_id:
            redirect_data = source_data.get("attributes", {}).get("redirect", {})
            success_url = redirect_data.get("success", "")
            booking_id = success_url.rstrip("/").split("/")[-1] if success_url else None

        if not source_id or not booking_id:
            return "", 200  # ignore invalid webhook payload

        # Step 2: Capture payment
        payment_url = "https://api.paymongo.com/v1/payments"

        payment_payload = {
            "data": {
                "attributes": {
                    "amount": amount,
                    "currency": "PHP",
                    "source": {
                        "id": source_id,
                        "type": "source"
                    },
                    "description": f"BusGo Payment for Booking #{booking_id}"
                }
            }
        }

        capture_res = requests.post(
            payment_url,
            json=payment_payload,
            auth=(PAYMONGO_SECRET_KEY, "")
        )

        if capture_res.status_code == 200:
            conn = get_db_connection()

            # ✅ AUTOMATED CONFIRMATION
            conn.execute("""
                UPDATE bookings
                SET status = 'paid',
                    payment_method = 'GCash'
                WHERE id = ?
            """, (booking_id,))

            conn.commit()
            conn.close()

        return "", 200

    except Exception as e:
        print(f"Webhook Error: {e}")
        return "", 500

@app.route("/staff/walkin/gcash", methods=["POST"])
def staff_walkin_gcash():
    conn = get_db_connection()

    trip_id = request.form["trip_id"]
    passenger_name = request.form["passenger_name"]
    contact = request.form["contact"]
    seat_number = request.form["seat_number"]

    trip = conn.execute("""
        SELECT id, price FROM trips WHERE id = ?
    """, (trip_id,)).fetchone()

    if not trip:
        conn.close()
        return redirect(url_for("staff_dashboard"))

    # create passenger
    cur = conn.execute("""
        INSERT INTO passengers (fullname, contact)
        VALUES (?, ?)
    """, (passenger_name, contact))

    passenger_id = cur.lastrowid

    # create booking immediately as PAID (since it's walk-in confirmed)
    cur = conn.execute("""
        INSERT INTO bookings (
            user_id, trip_id, passenger_id,
            seat_number, status, booking_type, payment_method
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session.get("user_id"),
        trip_id,
        passenger_id,
        seat_number,
        "waiting for payment",
        "Walk-in",
        "GCash"
    ))

    booking_id = cur.lastrowid
    conn.commit()
    conn.close()

    return redirect(url_for("pay_booking", booking_id=booking_id))
    

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

        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO users (fullname, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                fullname,
                email,
                generate_password_hash(password),
                role,
                created_at
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
        trip_id = request.form.get("trip_id")
        passenger_name = request.form.get("passenger_name", "").strip()
        contact = request.form.get("contact", "").strip()
        seat_number = request.form.get("seat_number", "").strip()

        if not trip_id or not passenger_name or not contact or not seat_number:
            conn.close()
            return redirect(url_for("staff_dashboard"))

        if not contact.isdigit() or len(contact) != 11:
            conn.close()
            return redirect(url_for("staff_dashboard"))

        trip = conn.execute("""
            SELECT t.id, t.bus_id, b.status
            FROM trips t
            JOIN buses b ON b.id = t.bus_id
            WHERE t.id = ?
        """, (trip_id,)).fetchone()

        if not trip or trip["status"] != "available":
            conn.close()
            return redirect(url_for("staff_dashboard"))

        existing_seat = conn.execute("""
            SELECT 1 FROM bookings
            WHERE trip_id = ? AND seat_number = ?
        """, (trip_id, seat_number)).fetchone()

        if existing_seat:
            conn.close()
            return redirect(url_for("staff_dashboard"))

        payment_method = request.form.get("payment_method", "").lower()
        
        booking_type = "Walk-in"

        if payment_method == "cash":
            payment_status = "paid"
            payment_method = "Cash"

        elif payment_method == "gcash":
            payment_status = "waiting for payment"
            payment_method = "GCash"

        else:
            conn.close()
            return redirect(url_for("staff_dashboard"))

        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        passenger = conn.execute("""
            INSERT INTO passengers (fullname, contact)
            VALUES (?, ?)
        """, (passenger_name, contact))

        passenger_id = passenger.lastrowid

        cur = conn.execute("""
            INSERT INTO bookings (
                user_id, trip_id, passenger_id, seat_number,
                status, booking_type, payment_method, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            trip_id,
            passenger_id,
            seat_number,
            payment_status,
            booking_type,
            payment_method,
            created_at
        ))

        booking_id = cur.lastrowid

        conn.commit()
        conn.close()

        if payment_status == "paid":
            return redirect(url_for("ticket", booking_id=booking_id))
        else:
            return redirect(url_for("pay_booking", booking_id=booking_id))

    trips = conn.execute("""
        SELECT 
            t.id,
            b.bus_no,
            r.origin,
            r.destination,
            t.departure,
            t.arrival,
            t.price
        FROM trips t
        JOIN buses b ON b.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
    """).fetchall()

    bookings = conn.execute("""
        SELECT 
            b.id,
            p.fullname AS passenger_name,
            p.contact,
            b.seat_number,
            b.status,
            b.created_at,
            bs.bus_no,
            r.origin || ' → ' || r.destination AS route,
            t.departure,
            t.arrival,
            t.price
        FROM bookings b
        JOIN passengers p ON p.id = b.passenger_id
        JOIN trips t ON t.id = b.trip_id
        JOIN buses bs ON bs.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
        WHERE b.user_id = ?
        ORDER BY b.created_at DESC
    """, (session["user_id"],)).fetchall()

    booked_seats_by_bus = {}
    all_bookings = conn.execute("SELECT trip_id, seat_number FROM bookings").fetchall()

    for row in all_bookings:
        booked_seats_by_bus.setdefault(str(row["trip_id"]), []).append(str(row["seat_number"]))

    active_bookings_by_date = {}
    history_bookings_by_date = {}

    today_str = datetime.datetime.now().strftime("%B %d, %Y")

    for row in bookings:
        created_at = row["created_at"] or ""

        try:
            parsed = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            date_key = parsed.strftime("%B %d, %Y")
            time_label = parsed.strftime("%I:%M %p")
        except:
            date_key = "Unknown Date"
            time_label = created_at

        item = {
            "id": row["id"],
            "passenger_name": row["passenger_name"],
            "contact": row["contact"],
            "seat_number": row["seat_number"],
            "status": row["status"],
            "bus_no": row["bus_no"],
            "route": row["route"],
            "departure": row["departure"],
            "arrival": row["arrival"],
            "price": row["price"],
            "created_time": time_label
        }

        if date_key == today_str:
            active_bookings_by_date.setdefault(date_key, []).append(item)
        else:
            history_bookings_by_date.setdefault(date_key, []).append(item)

    trips_json = [dict(t) for t in trips]

    conn.close()

    return render_template(
        "staff_dashboard.html",
        trips=trips,
        trips_json=trips_json,
        bookings=bookings,
        active_bookings_by_date=active_bookings_by_date,
        history_bookings_by_date=history_bookings_by_date,
        booked_seats_by_bus=booked_seats_by_bus
    )


@app.route("/staff/booking/<int:booking_id>")
def staff_view_booking(booking_id):
    if "user_id" not in session or session.get("role") != "staff":
        return redirect(url_for("home"))

    conn = get_db_connection()

    booking = conn.execute("""
        SELECT 
            b.id,
            b.trip_id,
            b.seat_number,
            b.status,
            b.created_at,
            b.booking_type,
            b.payment_method,

            p.fullname AS passenger_name,
            p.contact,

            bs.bus_no,

            r.origin,
            r.destination,
            (r.origin || ' → ' || r.destination) AS route,

            t.departure,
            t.arrival,
            t.price

        FROM bookings b
        JOIN passengers p ON p.id = b.passenger_id
        JOIN trips t ON t.id = b.trip_id
        JOIN buses bs ON bs.id = t.bus_id
        JOIN routes r ON t.route_id = r.id
        WHERE b.id = ? AND b.user_id = ?
    """, (booking_id, session["user_id"])).fetchone()

    if not booking:
        conn.close()
        return redirect(url_for("staff_dashboard"))

    booked_seats_count = conn.execute(
        "SELECT COUNT(*) as count FROM bookings WHERE trip_id = ?",
        (booking["trip_id"],)
    ).fetchone()["count"]

    available_seats = 52 - booked_seats_count

    conn.close()

    return render_template(
        "status.html",
        booking=booking,
        available_seats=available_seats,
        back_url=url_for("staff_dashboard"),
        user_role="staff"
    )

@app.route("/admin/buses", methods=["GET", "POST"])
def admin_buses():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    edit_bus = None

    if request.method == "POST":
        bus_id = request.form.get("bus_id")
        bus_no = request.form["bus_no"]

        origin = request.form["origin"]
        destination = request.form["destination"]

        departure = request.form["departure"]
        arrival = request.form["arrival"]
        price = request.form["price"]
        status = request.form.get("status", "available")

        updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        
        route_row = conn.execute(
            "SELECT id FROM routes WHERE origin = ? AND destination = ?",
            (origin, destination)
        ).fetchone()

        if route_row:
            route_id = route_row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO routes (origin, destination) VALUES (?, ?)",
                (origin, destination)
            )
            route_id = cur.lastrowid

        if bus_id:
            
            conn.execute(
                "UPDATE buses SET bus_no = ?, status = ?, updated_at = ? WHERE id = ?",
                (bus_no, status, updated_at, bus_id)
            )

            conn.execute("""
                UPDATE trips
                SET route_id = ?, departure = ?, arrival = ?, price = ?
                WHERE bus_id = ?
            """, (route_id, departure, arrival, price, bus_id))

        else:
            
            cur = conn.execute(
                "INSERT INTO buses (bus_no, status, updated_at) VALUES (?, ?, ?)",
                (bus_no, status, updated_at)
            )
            new_bus_id = cur.lastrowid

            conn.execute("""
                INSERT INTO trips (bus_id, route_id, departure, arrival, price)
                VALUES (?, ?, ?, ?, ?)
            """, (new_bus_id, route_id, departure, arrival, price))

        conn.commit()
        conn.close()
        return redirect(url_for("admin_buses"))

    edit_id = request.args.get("edit_id")
    if edit_id:
        edit_bus = conn.execute("""
            SELECT b.id, b.bus_no, b.status,
                   r.origin, r.destination,
                   t.departure, t.arrival, t.price
            FROM buses b
            JOIN trips t ON t.bus_id = b.id
            JOIN routes r ON r.id = t.route_id
            WHERE b.id = ?
        """, (edit_id,)).fetchone()

    buses = conn.execute("""
        SELECT b.id, b.bus_no, b.status,
               r.origin || ' - ' || r.destination AS route,
               t.departure, t.arrival, t.price
        FROM buses b
        JOIN trips t ON t.bus_id = b.id
        JOIN routes r ON r.id = t.route_id
        ORDER BY b.id DESC
    """).fetchall()

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
        updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE buses SET status = ?, updated_at = ? WHERE id = ?", (new_status, updated_at, bus_id))
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
        SELECT 
            b.id,
            b.seat_number,
            b.status,
            b.created_at,
            b.booking_type,
            u.fullname AS user,
            t.id AS trip_id,
            bs.bus_no,
            r.origin || ' → ' || r.destination AS route,
            t.departure,
            t.arrival
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN trips t ON t.id = b.trip_id
        JOIN buses bs ON bs.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
        ORDER BY b.created_at DESC
    """).fetchall()

    today_str = datetime.datetime.now().strftime('%B %d, %Y')

    today_bookings = []
    history_bookings_by_date = {}
    walkin_bookings_by_date = {}

    for row in rows:
        created_at_raw = row["created_at"] or ""

        try:
            parsed = datetime.datetime.strptime(created_at_raw, "%Y-%m-%d %H:%M:%S")
            created_date = parsed.strftime("%B %d, %Y")
            created_time = parsed.strftime("%I:%M %p")
        except Exception:
            created_date = created_at_raw
            created_time = ""

        booking_item = {
            "id": row["id"],
            "user": row["user"],
            "bus_no": row["bus_no"],
            "route": row["route"],
            "seat_number": row["seat_number"],
            "status": row["status"],
            "created_date": created_date,
            "created_time": created_time,
            "booking_type": row["booking_type"]
        }

        if booking_item["booking_type"] == "Walk-in":
            walkin_bookings_by_date.setdefault(created_date, []).append(booking_item)
        elif booking_item["status"] in ["paid", "cancelled"]:
            history_bookings_by_date.setdefault(created_date, []).append(booking_item)
        elif created_date == today_str:
            today_bookings.append(booking_item)

    conn.close()

    return render_template(
        "admin_bookings.html",
        today_bookings=today_bookings,
        history_bookings_by_date=history_bookings_by_date,
        walkin_bookings_by_date=walkin_bookings_by_date,
        today_str=today_str
    )

@app.route("/admin/booking/<int:booking_id>")
def admin_view_booking(booking_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    booking = conn.execute("""
        SELECT 
            b.id,
            b.seat_number,
            b.status,
            b.trip_id,
            b.created_at,
            b.booking_type,
            b.payment_method,

            p.fullname AS passenger_name,
            p.contact,

            t.departure,
            t.arrival,
            t.price,

            r.origin,
            r.destination,
            (r.origin || ' → ' || r.destination) AS route,

            bu.bus_no,

            u.fullname AS user_name,
            u.email AS user_email

        FROM bookings b
        JOIN passengers p ON b.passenger_id = p.id
        JOIN trips t ON b.trip_id = t.id
        JOIN buses bu ON t.bus_id = bu.id
        JOIN routes r ON t.route_id = r.id
        JOIN users u ON b.user_id = u.id

        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    
    if not booking:
        conn.close()
        return redirect(url_for("admin_bookings"))

    # Calculate available seats for this bus
    booked_seats_count = conn.execute(
        "SELECT COUNT(*) as count FROM bookings WHERE trip_id = ?",
        (booking["trip_id"],)
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
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO users (fullname, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                fullname,
                email,
                generate_password_hash(password),
                "user",
                created_at
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

    # Update booking status to paid
    conn.execute("""
        UPDATE bookings 
        SET status = 'paid', 
            payment_method = 'GCash'
        WHERE id = ? AND user_id = ?
    """, (booking_id, session["user_id"]))

    conn.commit()
    conn.close()

    # Redirect to ticket page on success
    flash("Payment successful! Your booking has been confirmed.")
    return redirect(url_for("ticket", booking_id=booking_id))
    
@app.route("/admin/confirm_payment/<int:booking_id>")
def confirm_payment(booking_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()

    conn.execute(
        "UPDATE bookings SET status = 'paid', payment_method = 'GCash' WHERE id = ?",
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
        SELECT 
            b.id,
            b.seat_number,
            b.status,
            b.created_at,
            b.booking_type,
            b.payment_method,
            p.fullname AS passenger_name,
            p.contact,
            t.departure,
            t.arrival,
            t.price,
            r.origin,
            r.destination,
            bu.bus_no
        FROM bookings b
        JOIN passengers p ON b.passenger_id = p.id
        JOIN trips t ON b.trip_id = t.id
        JOIN buses bu ON t.bus_id = bu.id
        JOIN routes r ON t.route_id = r.id
        WHERE b.id = ?
    """, (booking_id,)).fetchone()

    if not booking or booking["status"] != "paid":
        conn.close()
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_view_booking", booking_id=booking_id))
        elif role == "staff":
            return redirect(url_for("staff_view_booking", booking_id=booking_id))
        else:
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
        f"Booking Type: {booking['booking_type'] if 'booking_type' in booking.keys() else 'N/A'}\n"
        f"Bus No: {booking['bus_no']}\n"
        f"Seat No: {booking['seat_number']}\n"
        f"Departure: {booking['departure']}\n"
        f"Arrival: {booking['arrival']}\n"
        f"Payment Method: {booking['payment_method']}\n"
    )
    qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=280x280&data=" + urllib.parse.quote(qr_data)

    user_role = session.get("role")
    if user_role == "admin":
        back_url = url_for("admin_dashboard")
    elif user_role == "staff":
        back_url = url_for("staff_dashboard")
    else:
        back_url = url_for("user_dashboard")

    conn.close()
    return render_template("booking_detail.html", booking=booking, booking_created_at=formatted_created_at, qr_url=qr_url, back_url=back_url)


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

    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin_view_booking", booking_id=booking_id))
    elif role == "staff":
        return redirect(url_for("staff_view_booking", booking_id=booking_id))
    else:
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