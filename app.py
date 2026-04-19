from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import requests
import datetime
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

    # Fetch all booked seats for this bus
    booked_seats = conn.execute(
        "SELECT seat_number FROM bookings WHERE bus_id = ?", 
        (bus_id,)
    ).fetchall()
    booked_seat_numbers = [seat["seat_number"] for seat in booked_seats]

    conn.close()
    return render_template("booking.html", bus=bus, booked_seats=booked_seat_numbers)


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

@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()

    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not fullname or not email or not password:
            conn.close()
            return redirect(url_for("admin_dashboard", error="All staff fields are required."))

        if len(password) < 6:
            conn.close()
            return redirect(url_for("admin_dashboard", error="Password must be at least 6 characters."))

        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            conn.close()
            return redirect(url_for("admin_dashboard", error="That email is already registered."))

        conn.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            (
                fullname,
                email,
                generate_password_hash(password),
                "staff"
            )
        )
        conn.commit()

    users = conn.execute(
        "SELECT id, fullname, email, role FROM users"
    ).fetchall()

    buses = conn.execute(
        "SELECT * FROM buses"
    ).fetchall()

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

        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO bookings (user_id, bus_id, passenger_name, contact, seat_number, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                session["user_id"],
                bus_id,
                passenger_name,
                contact,
                seat_number,
                created_at
            )
        )
        conn.commit()
        conn.close()

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

    bookings_by_date = {}
    for row in bookings:
        created_at = row['created_at'] or ''
        try:
            parsed = datetime.datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            date_key = parsed.strftime('%B %d, %Y')
            time_label = parsed.strftime('%I:%M %p')
        except Exception:
            date_key = 'Unknown Date'
            time_label = created_at

        bookings_by_date.setdefault(date_key, []).append({
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
            'created_time': time_label
        })

    buses_json = [dict(bus) for bus in buses]
    conn.close()

    return render_template(
        "staff_dashboard.html",
        buses=buses,
        bookings=bookings,
        bookings_by_date=bookings_by_date,
        booked_seats_by_bus=booked_seats_by_bus,
        buses_json=buses_json,
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
        route = request.form["route"]
        departure = request.form["departure"]
        arrival = request.form["arrival"]
        price = request.form["price"]

        if bus_id:
            conn.execute(
                "UPDATE buses SET bus_no = ?, route = ?, departure = ?, arrival = ?, price = ? WHERE id = ?",
                (bus_no, route, departure, arrival, price, bus_id)
            )
        else:
            conn.execute(
                "INSERT INTO buses (bus_no, route, departure, arrival, price) VALUES (?, ?, ?, ?, ?)",
                (bus_no, route, departure, arrival, price)
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