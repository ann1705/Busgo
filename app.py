import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import requests
import datetime
from flask import jsonify
import urllib.parse
from flask import flash
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__)
app.secret_key = "busgo_secret_key"
app.config['TEMPLATES_AUTO_RELOAD'] = True
PAYMONGO_SECRET_KEY = os.environ.get("PAYMONGO_SECRET_KEY", "sk_test_2Qq7gVeyLzRf1eB7xYyMUTUF")
DATABASE = "busgo.db"
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "AIzaSyAHXSF5ijWwrf6K_FLw8YI6NCd5yebxLng")


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
            destination TEXT NOT NULL,
            distance REAL DEFAULT 0,
            geometry_json TEXT
        )
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_id INTEGER,
            route_id INTEGER,
            departure TEXT,
            arrival TEXT,
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
            price REAL DEFAULT 0,
            distance REAL DEFAULT 0,
            fare_type TEXT DEFAULT 'regular',
            discount_type TEXT,
            travel_date TEXT,
            id_photo_path TEXT, -- New column for ID photo path
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(trip_id) REFERENCES trips(id),
            FOREIGN KEY(passenger_id) REFERENCES passengers(id)
        )
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS seat_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            seat_number TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trip_id, seat_number),
            FOREIGN KEY(trip_id) REFERENCES trips(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
        """)

    conn.commit()
    conn.close()

def ensure_bookings_travel_date_column():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()]
    if 'travel_date' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN travel_date TEXT")
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


def ensure_bookings_fare_columns():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()]
    if 'price' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN price REAL DEFAULT 0")
    if 'distance' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN distance REAL DEFAULT 0")
    if 'fare_type' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN fare_type TEXT DEFAULT 'regular'")
    if 'discount_type' not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN discount_type TEXT")
    if 'id_photo_path' not in columns: # Add new column if it doesn't exist
        conn.execute("ALTER TABLE bookings ADD COLUMN id_photo_path TEXT")
    conn.commit()
    conn.close()


def ensure_routes_columns():
    conn = get_db_connection()
    columns = [row['name'] for row in conn.execute("PRAGMA table_info(routes)").fetchall()]
    if 'distance' not in columns:
        conn.execute("ALTER TABLE routes ADD COLUMN distance REAL DEFAULT 0")
    if 'geometry_json' not in columns:
        conn.execute("ALTER TABLE routes ADD COLUMN geometry_json TEXT")
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


def ensure_seat_blocks_table():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seat_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            seat_number TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trip_id, seat_number),
            FOREIGN KEY(trip_id) REFERENCES trips(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
    """)

    blocked_rows = conn.execute("""
        SELECT id, trip_id, seat_number, user_id, created_at
        FROM bookings
        WHERE status = 'blocked'
    """).fetchall()
    for row in blocked_rows:
        conn.execute("""
            INSERT OR IGNORE INTO seat_blocks (trip_id, seat_number, created_by, created_at)
            VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
        """, (row["trip_id"], row["seat_number"], row["user_id"], row["created_at"]))
    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE status = 'blocked'")
    conn.commit()
    conn.close()


def get_blocked_seats(conn, trip_id):
    rows = conn.execute("""
        SELECT seat_number
        FROM seat_blocks
        WHERE trip_id = ?
    """, (trip_id,)).fetchall()
    return {str(row["seat_number"]) for row in rows}


def get_seat_statuses(conn, trip_id, travel_date=None):
    params = [trip_id]
    query = """
        SELECT seat_number, status
        FROM bookings
        WHERE trip_id = ? AND status != 'cancelled'
    """
    if travel_date:
        query += " AND travel_date = ?"
        params.append(travel_date)

    statuses = {
        str(row["seat_number"]): row["status"]
        for row in conn.execute(query, params).fetchall()
    }
    for seat_number in get_blocked_seats(conn, trip_id):
        statuses.setdefault(seat_number, "blocked")
    return statuses


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
ensure_bookings_travel_date_column()
ensure_bookings_fare_columns()
ensure_bus_status_column()
ensure_routes_columns()
ensure_users_created_at_column()
ensure_buses_created_at_column()
ensure_buses_updated_at_column()
ensure_seat_blocks_table()
create_default_admin()

route_geo_cache = {}

def haversine_distance(lat1, lon1, lat2, lon2):
    from math import radians, cos, sin, asin, sqrt
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c


def geocode_place(place):
    if not place:
        return None
    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "BusGo-App/1.0"}
        params = {
            "q": f"{place}, Philippines",
            "format": "json",
            "limit": 1
        }
        response = requests.get(url, params=params, headers=headers, timeout=6)
        response.raise_for_status()
        results = response.json()
        if not results:
            return None
        return {
            "lat": float(results[0]["lat"]),
            "lon": float(results[0]["lon"])
        }
    except Exception:
        return None


def get_route_geo(origin, destination):
    key = f"{origin}|{destination}"
    if key in route_geo_cache:
        return route_geo_cache[key]

    origin_geo = geocode_place(origin)
    destination_geo = geocode_place(destination)
    
    if origin_geo and destination_geo:
        # Default values in case OSRM fails
        route_distance = 20.0
        route_geometry = [[origin_geo["lat"], origin_geo["lon"]], [destination_geo["lat"], destination_geo["lon"]]]
        
        # Fetch actual road distance and geometry from OSRM
        try:
            # OSRM expects coordinates as lon,lat
            osrm_url = f"https://router.project-osrm.org/route/v1/driving/{origin_geo['lon']},{origin_geo['lat']};{destination_geo['lon']},{destination_geo['lat']}?overview=full&geometries=geojson"
            
            res = requests.get(osrm_url, headers={"User-Agent": "BusGo-App/1.0"}, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                if data.get("routes") and len(data["routes"]) > 0:
                    route = data["routes"][0]
                    route_distance = round(route["distance"] / 1000, 1)  # Convert meters to km
                    
                    # OSRM returns [lng, lat], convert to [lat, lng] for Leaflet
                    if route.get("geometry") and route["geometry"].get("coordinates"):
                        route_geometry = [[coord[1], coord[0]] for coord in route["geometry"]["coordinates"]]
                    else:
                        # Fallback to straight line if no geometry
                        route_geometry = [[origin_geo["lat"], origin_geo["lon"]], [destination_geo["lat"], destination_geo["lon"]]]
                else:
                    # No route found, use straight line
                    distance_km_straight = round(haversine_distance(
                        origin_geo["lat"], origin_geo["lon"],
                        destination_geo["lat"], destination_geo["lon"]
                    ), 2)
                    route_distance = max(5.0, round(distance_km_straight * 1.2, 1))
                    route_geometry = [[origin_geo["lat"], origin_geo["lon"]], [destination_geo["lat"], destination_geo["lon"]]]
            else:
                # OSRM request failed, use straight line approximation
                distance_km_straight = round(haversine_distance(
                    origin_geo["lat"], origin_geo["lon"],
                    destination_geo["lat"], destination_geo["lon"]
                ), 2)
                route_distance = max(5.0, round(distance_km_straight * 1.2, 1))
                route_geometry = [[origin_geo["lat"], origin_geo["lon"]], [destination_geo["lat"], destination_geo["lon"]]]
                
        except requests.exceptions.Timeout:
            # Timeout fallback
            distance_km_straight = round(haversine_distance(
                origin_geo["lat"], origin_geo["lon"],
                destination_geo["lat"], destination_geo["lon"]
            ), 2)
            route_distance = max(5.0, round(distance_km_straight * 1.2, 1))
            route_geometry = [[origin_geo["lat"], origin_geo["lon"]], [destination_geo["lat"], destination_geo["lon"]]]
        except Exception as e:
            # Any other error fallback
            print(f"OSRM Error: {e}")
            distance_km_straight = round(haversine_distance(
                origin_geo["lat"], origin_geo["lon"],
                destination_geo["lat"], destination_geo["lon"]
            ), 2)
            route_distance = max(5.0, round(distance_km_straight * 1.2, 1))
            route_geometry = [[origin_geo["lat"], origin_geo["lon"]], [destination_geo["lat"], destination_geo["lon"]]]

        route_geo_cache[key] = {
            "origin_lat": origin_geo["lat"],
            "origin_lon": origin_geo["lon"],
            "destination_lat": destination_geo["lat"],
            "destination_lon": destination_geo["lon"],
            "route_distance": route_distance,
            "geometry": route_geometry
        }
    else:
        route_geo_cache[key] = {
            "origin_lat": None,
            "origin_lon": None,
            "destination_lat": None,
            "destination_lon": None,
            "route_distance": 20.0,
            "geometry": []
        }

    return route_geo_cache[key]


def calculate_fare(distance, discount_type='regular'):
    try:
        distance = float(distance)
    except Exception:
        distance = 0.0

    fare_type = 'regular'
    if discount_type in ['student', 'senior', 'pwd']:
        fare_type = 'discount'

    # Base fare for first 5 km
    if fare_type == 'discount':
        base = 14.40  # 20% discount from 18.00
    else:
        base = 18.00  # Regular fare for first 5 km

    if distance <= 5:
        return round(base, 2), fare_type

    # Additional 2.97 pesos per succeeding km
    extra_km = max(0.0, distance - 5.0)
    total = base + (extra_km * 2.97)
    return round(total, 2), fare_type


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


def create_default_conductor():
    conn = get_db_connection()
    conductor = conn.execute("SELECT * FROM users WHERE role='conductor'").fetchone()
    if not conductor:
        conn.execute(
            "INSERT INTO users (fullname, email, password, role) VALUES (?, ?, ?, ?)",
            (
                "BusGo Conductor",
                "conductor@busgo.com",
                generate_password_hash("conductor123"),
                "conductor"
            )
        )
        conn.commit()
    conn.close()

create_default_staff()
create_default_conductor()

@app.context_processor
def inject_user_info():
    """Makes user role and fullname available to all templates for navigation logic."""
    return dict(
        user_role=session.get("role"),
        user_name=session.get("fullname")
    )

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
    conn = get_db_connection()

    raw_trips = conn.execute("""
        SELECT 
            t.id AS trip_id,
            b.id AS bus_id,
            b.bus_no,
            b.status,
            b.capacity,
            r.origin,
            r.destination,
            r.distance AS route_distance,
            t.departure,
            t.arrival,
            (SELECT COUNT(*) FROM bookings bo WHERE bo.trip_id = t.id AND bo.status != 'cancelled') +
            (SELECT COUNT(*) FROM seat_blocks sb WHERE sb.trip_id = t.id) AS booked_count
        FROM trips t
        JOIN buses b ON b.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
    """).fetchall()

    trips_with_fare = []
    for trip_row in raw_trips:
        trip = dict(trip_row) # Convert sqlite3.Row to dict for easier modification
        # Assuming 'regular' fare type for display in schedules
        fare, _ = calculate_fare(trip["route_distance"], 'regular')
        trip["calculated_fare"] = fare
        trips_with_fare.append(trip)

    conn.close()

    return render_template("schedules.html", buses=trips_with_fare)


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
            b.bus_no,
            b.capacity,
            b.status,
            r.origin,
            r.destination,
            r.distance AS route_distance,
            r.geometry_json
        FROM trips t
        JOIN buses b ON b.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
        WHERE t.id = ?
    """, (trip_id,)).fetchone()

    if not trip or trip["status"] != "available":
        conn.close()
        flash("This trip is unavailable.")
        return redirect(url_for("schedules"))

    import json
    
    # Check if geometry exists in database
    geometry = []
    if trip["geometry_json"]:
        try:
            geometry = json.loads(trip["geometry_json"])
        except:
            geometry = []
    
    # If no geometry in DB, fetch from OSRM
    if not geometry:
        geo = get_route_geo(trip["origin"], trip["destination"])
        geometry = geo['geometry']
        route_distance = geo['route_distance']
        
        # Save to database for future use
        if geometry:
            conn.execute("""
                UPDATE routes 
                SET distance = ?, geometry_json = ? 
                WHERE id = (SELECT route_id FROM trips WHERE id = ?)
            """, (route_distance, json.dumps(geometry), trip_id))
            conn.commit()

    # Prepare route_info for template with actual road geometry
    route_info = {
        "origin": trip["origin"],
        "destination": trip["destination"],
        "route_distance": trip["route_distance"] if trip["route_distance"] > 0 else 20.0,
        "geometry": geometry if geometry else [],
        "origin_lat": geometry[0][0] if geometry and len(geometry) > 0 else None,
        "origin_lon": geometry[0][1] if geometry and len(geometry) > 0 else None,
        "destination_lat": geometry[-1][0] if geometry and len(geometry) > 0 else None,
        "destination_lon": geometry[-1][1] if geometry and len(geometry) > 0 else None
    }
    
    # If still no coordinates, geocode them
    if not route_info["origin_lat"]:
        origin_geo = geocode_place(trip["origin"])
        dest_geo = geocode_place(trip["destination"])
        if origin_geo and dest_geo:
            route_info["origin_lat"] = origin_geo["lat"]
            route_info["origin_lon"] = origin_geo["lon"]
            route_info["destination_lat"] = dest_geo["lat"]
            route_info["destination_lon"] = dest_geo["lon"]
    
    # Rest of your existing booking code remains the same...
    # (keep all the existing POST handling and other logic unchanged)
    if request.method == "POST":
            passenger_name = request.form["passenger_name"]
            contact = request.form["contact"]
            seat_number = request.form["seat_number"]
            travel_date = request.form.get("travel_date")
            distance = request.form.get("distance", "0").strip()
            discount_type = request.form.get("discount_type", "regular")
            id_photo_path = None

            try:
                distance_value = float(distance)
            except ValueError:
                distance_value = 0.0

            if not contact.isdigit() or len(contact) != 11:
                conn.close()
                flash("Invalid contact number.")
                return redirect(url_for("booking", trip_id=trip_id))

            if seat_number in get_blocked_seats(conn, trip_id):
                conn.close()
                flash(f"Seat #{seat_number} is blocked by the admin. Please choose another seat.")
                return redirect(url_for("booking", trip_id=trip_id))

            # Check if seat is already taken for that specific day.
            existing = conn.execute("""
                SELECT id, status FROM bookings
                WHERE trip_id = ? AND seat_number = ? AND travel_date = ? AND status != 'cancelled'
            """, (trip_id, seat_number, travel_date)).fetchone()

            if existing:
                conn.close()
                flash(f"Seat #{seat_number} is already booked for {travel_date}. Please choose another seat.")
                return redirect(url_for("booking", trip_id=trip_id))

            if distance_value <= 0 or distance_value > route_info["route_distance"]:
                conn.close()
                flash("Selected destination exceeds the available route for this trip.")
                return redirect(url_for("booking", trip_id=trip_id))

            # Verification check for Discounted IDs (ID Scan required)
            if discount_type != 'regular':
                if request.form.get('id_scanned') != '1':
                    flash("Discount ID must be verified via scanner.")
                    return redirect(url_for("booking", trip_id=trip_id))

            price, fare_type = calculate_fare(distance_value, discount_type)

            created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cur = conn.execute(
                "INSERT INTO passengers (fullname, contact) VALUES (?, ?)",
                (passenger_name, contact)
            )
            passenger_id = cur.lastrowid

            cur = conn.execute("""
                INSERT INTO bookings (
                    user_id, trip_id, passenger_id, seat_number,
                    status, booking_type, payment_method, price, distance,
                    fare_type, discount_type, travel_date, id_photo_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                trip_id,
                passenger_id,
                seat_number,
                "waiting for payment",
                "Online",
                "Online",
                price,
                distance_value,
                fare_type,
                discount_type,
                travel_date,
                id_photo_path,
                created_at
            ))

            conn.commit()
            booking_id = cur.lastrowid
            conn.close()

            return redirect(url_for("view_booking", booking_id=booking_id))

    
    today = datetime.date.today().isoformat()
    seat_statuses = get_seat_statuses(conn, trip_id, today)
    booked_seat_numbers = list(seat_statuses.keys())
    available_seats = max(0, trip["capacity"] - len(booked_seat_numbers))
    conn.close()

    return render_template(
        "booking.html",
        trip=trip,
        booked_seats=booked_seat_numbers,
        seat_statuses=seat_statuses,
        available_seats=available_seats,
        today=today,
        route_info=route_info,
        google_maps_api_key=GOOGLE_MAPS_API_KEY,
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
            b.price,
            b.status,
            b.created_at,
            b.travel_date
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
            'booked_on': booked_on,
            'travel_date': row['travel_date']
        })
    conn.close()

    # Pass today's date to template
    return render_template("user_dashboard.html", bookings=bookings, now=datetime.datetime.now())

@app.route("/api/booked-seats/<int:trip_id>")
def booked_seats(trip_id):
    travel_date = request.args.get('date')
    conn = get_db_connection()
    status_map = get_seat_statuses(conn, trip_id, travel_date)
    conn.close()

    seats = [{"seat": seat, "status": status} for seat, status in status_map.items()]
    return jsonify(seats)

@app.route("/admin/api/toggle-seat", methods=["POST"])
def admin_toggle_seat():
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    data = request.get_json()
    trip_id = data.get("trip_id")
    date = data.get("date")
    seat = str(data.get("seat_number"))

    if not trip_id or not date or not seat:
        return jsonify({"success": False, "message": "Missing trip, date, or seat."}), 400
    
    conn = get_db_connection()
    
    existing_booking = conn.execute("""
        SELECT id, status FROM bookings 
        WHERE trip_id = ? AND travel_date = ? AND seat_number = ? AND status != 'cancelled'
    """, (trip_id, date, seat)).fetchone()
    existing_block = conn.execute("""
        SELECT id FROM seat_blocks
        WHERE trip_id = ? AND seat_number = ?
    """, (trip_id, seat)).fetchone()
    
    if existing_block:
        conn.execute("DELETE FROM seat_blocks WHERE id = ?", (existing_block["id"],))
        message = "Seat is now Available"
        success = True
        new_status = "available"
    elif existing_booking:
        message = "Cannot toggle: Seat is already booked by a customer."
        success = False
        new_status = existing_booking["status"]
    else:
        conn.execute("""
            INSERT OR IGNORE INTO seat_blocks (trip_id, seat_number, created_by, created_at)
            VALUES (?, ?, ?, ?)
        """, (trip_id, seat, session["user_id"], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        message = "Seat is now Blocked"
        success = True
        new_status = "blocked"
        
    conn.commit()
    conn.close()
    return jsonify({"success": success, "message": message, "new_status": new_status})

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
            b.travel_date,
            b.booking_type,
            b.payment_method,
            b.id_photo_path, -- Retrieve ID photo path
            b.price,
            b.distance,
            b.fare_type,
            b.discount_type,
            b.id_photo_path, -- Retrieve ID photo path

            u.fullname AS customer,

            p.fullname AS passenger_name,
            p.contact,

            t.departure,
            t.arrival,

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

    available_seats = 52 - len(get_seat_statuses(conn, booking["trip_id"], booking["travel_date"]))
    
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
        SELECT b.id, b.price, b.status
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
            b.trip_id,
            b.seat_number,
            b.status,
            b.booking_type,
            b.payment_method,
            b.price,
            b.distance,
            b.fare_type,
            b.discount_type,
            b.travel_date,
            p.fullname AS passenger_name,
            p.contact,
            t.departure,
            t.arrival,
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
    
    available_seats = booking["capacity"] - len(get_seat_statuses(conn, booking["trip_id"], booking["travel_date"]))
    
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
    distance = request.form.get("distance", "0").strip()
    discount_type = request.form.get("discount_type", "regular")
    today_iso = datetime.date.today().isoformat()

    try:
        distance_value = float(distance)
    except ValueError:
        distance_value = 0.0

    trip = conn.execute("""
        SELECT t.id, r.origin, r.destination
        FROM trips t
        JOIN routes r ON r.id = t.route_id
        WHERE t.id = ?
    """, (trip_id,)).fetchone()

    if not trip:
        conn.close()
        return redirect(url_for("staff_dashboard"))

    route_geo = get_route_geo(trip["origin"], trip["destination"])
    if distance_value <= 0 or distance_value > route_geo["route_distance"]:
        conn.close()
        return redirect(url_for("staff_dashboard"))

    if seat_number in get_blocked_seats(conn, trip_id):
        conn.close()
        flash(f"Seat #{seat_number} is blocked by the admin.")
        return redirect(url_for("staff_dashboard"))

    # Check for existing booking today
    existing = conn.execute("""
        SELECT 1 FROM bookings 
        WHERE trip_id = ? AND seat_number = ? AND travel_date = ? AND status != 'cancelled'
    """, (trip_id, seat_number, today_iso)).fetchone()
    
    if existing:
        conn.close()
        flash(f"Seat #{seat_number} is already booked for today.")
        return redirect(url_for("staff_dashboard"))

    price, fare_type = calculate_fare(distance_value, discount_type)

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
            seat_number, status, booking_type, payment_method,
            price, distance, fare_type, discount_type, travel_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session.get("user_id"),
        trip_id,
        passenger_id,
        seat_number,
        "waiting for payment",
        "Walk-in",
        "GCash",
        price,
        distance_value,
        fare_type,
        discount_type,
        today_iso
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
        distance = request.form.get("distance", "0").strip()
        discount_type = request.form.get("discount_type", "regular")
        id_photo_path = None

        try:
            distance_value = float(distance)
        except ValueError:
            distance_value = 0.0

        if not trip_id or not passenger_name or not contact or not seat_number:
            conn.close()
            return redirect(url_for("staff_dashboard"))

        if not contact.isdigit() or len(contact) != 11:
            conn.close()
            return redirect(url_for("staff_dashboard"))

        today_iso = datetime.date.today().isoformat()

        if seat_number in get_blocked_seats(conn, trip_id):
            conn.close()
            flash(f"Seat #{seat_number} is blocked by the admin.")
            return redirect(url_for("staff_dashboard"))

        # Check if seat is already taken today
        existing_seat = conn.execute("""
            SELECT 1 FROM bookings
            WHERE trip_id = ? AND seat_number = ? AND travel_date = ? AND status != 'cancelled'
        """, (trip_id, seat_number, today_iso)).fetchone()

        if existing_seat:
            conn.close()
            flash(f"Seat #{seat_number} is already booked for today.")
            return redirect(url_for("staff_dashboard"))

        trip = conn.execute("""
            SELECT t.id, t.bus_id, b.status, r.origin, r.destination
            FROM trips t
            JOIN buses b ON b.id = t.bus_id
            JOIN routes r ON r.id = t.route_id
            WHERE t.id = ?
        """, (trip_id,)).fetchone()

        if not trip or trip["status"] != "available":
            conn.close()
            return redirect(url_for("staff_dashboard"))

        route_geo = get_route_geo(trip["origin"], trip["destination"])
        if distance_value <= 0 or distance_value > route_geo["route_distance"]:
            conn.close()
            return redirect(url_for("staff_dashboard"))

        # Handle Discount Verification for Staff Walk-ins (ID Scan required)
        if discount_type != 'regular':
            if request.form.get('id_scanned') != '1':
                flash("Customer ID must be verified via scanner.")
                return redirect(url_for("staff_dashboard"))

        price, fare_type = calculate_fare(distance_value, discount_type)

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
                status, booking_type, payment_method, price,
                distance, fare_type, discount_type, travel_date, id_photo_path, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            trip_id,
            passenger_id,
            seat_number,
            payment_status,
            booking_type,
            payment_method,
            price,
            distance_value,
            fare_type,
            discount_type,
            today_iso,
            id_photo_path,
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
            r.distance AS route_distance,
            r.geometry_json,
            t.departure,
            t.arrival
        FROM trips t
        JOIN buses b ON b.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
    """).fetchall()
    trips = [dict(t) for t in trips]

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
            b.price
        FROM bookings b
        JOIN passengers p ON p.id = b.passenger_id
        JOIN trips t ON t.id = b.trip_id
        JOIN buses bs ON bs.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
        WHERE b.user_id = ?
        ORDER BY b.created_at DESC
    """, (session["user_id"],)).fetchall()

    today_iso = datetime.date.today().isoformat()
    booked_seats_by_bus = {}
    for trip in trips:
        booked_seats_by_bus[str(trip["id"])] = get_seat_statuses(conn, trip["id"], today_iso)

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
            b.travel_date,
            b.booking_type,
            b.payment_method,
            b.id_photo_path, -- Retrieve ID photo path

            p.fullname AS passenger_name,
            p.contact,

            bs.bus_no,

            r.origin,
            r.destination,
            (r.origin || ' → ' || r.destination) AS route,

            t.departure,
            t.arrival,
            b.price

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

    available_seats = 52 - len(get_seat_statuses(conn, booking["trip_id"], booking["travel_date"]))

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
        status = request.form.get("status", "available")

        updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        
        route_row = conn.execute(
            "SELECT id, geometry_json FROM routes WHERE origin = ? AND destination = ?",
            (origin, destination)
        ).fetchone()

        # If route exists but geometry is missing, fetch it
        if not route_row or not route_row["geometry_json"]:
            geo = get_route_geo(origin, destination)
            import json
            if route_row:
                conn.execute("UPDATE routes SET distance = ?, geometry_json = ? WHERE id = ?",
                             (geo['route_distance'], json.dumps(geo['geometry']), route_row["id"]))
                route_id = route_row["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO routes (origin, destination, distance, geometry_json) VALUES (?, ?, ?, ?)",
                    (origin, destination, geo['route_distance'], json.dumps(geo['geometry'])))
                route_id = cur.lastrowid
        else:
            route_id = route_row["id"]

        if bus_id:
            
            conn.execute(
                "UPDATE buses SET bus_no = ?, status = ?, updated_at = ? WHERE id = ?",
                (bus_no, status, updated_at, bus_id)
            )

            conn.execute("""
                UPDATE trips
                SET route_id = ?, departure = ?, arrival = ?
                WHERE bus_id = ?
            """, (route_id, departure, arrival, bus_id))

        else:
            
            cur = conn.execute(
                "INSERT INTO buses (bus_no, status, updated_at) VALUES (?, ?, ?)",
                (bus_no, status, updated_at)
            )
            new_bus_id = cur.lastrowid

            conn.execute("""
                INSERT INTO trips (bus_id, route_id, departure, arrival)
                VALUES (?, ?, ?, ?)
            """, (new_bus_id, route_id, departure, arrival))

        conn.commit()
        conn.close()
        return redirect(url_for("admin_buses"))

    edit_id = request.args.get("edit_id")
    if edit_id:
        edit_bus = conn.execute("""
            SELECT b.id, b.bus_no, b.status,
                   r.origin, r.destination,
                   t.departure, t.arrival
            FROM buses b
            JOIN trips t ON t.bus_id = b.id
            JOIN routes r ON r.id = t.route_id
            WHERE b.id = ?
        """, (edit_id,)).fetchone()

    buses = conn.execute("""
        SELECT b.id, b.bus_no, b.status,
               r.origin || ' - ' || r.destination AS route,
               t.id AS trip_id,
               t.departure, t.arrival
        FROM buses b
        JOIN trips t ON t.bus_id = b.id
        JOIN routes r ON r.id = t.route_id
        ORDER BY b.id DESC
    """).fetchall()

    today_date = datetime.date.today().isoformat()
    conn.close()
    return render_template("admin_buses.html", buses=buses, edit_bus=edit_bus, today_date=today_date)


@app.route("/admin/delete_bus/<int:bus_id>")
def delete_bus(bus_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    try:
        conn = get_db_connection()
        
        # First, delete related bookings
        # You need to delete from trips first if there are foreign key constraints
        # Get all trips for this bus
        trips = conn.execute("SELECT id FROM trips WHERE bus_id = ?", (bus_id,)).fetchall()
        
        for trip in trips:
            # Delete bookings for each trip
            conn.execute("DELETE FROM bookings WHERE trip_id = ?", (trip[0],))
        
        # Delete trips for this bus
        conn.execute("DELETE FROM trips WHERE bus_id = ?", (bus_id,))
        
        # Delete the bus
        conn.execute("DELETE FROM buses WHERE id = ?", (bus_id,))
        
        conn.commit()
        conn.close()
        
        flash('Bus deleted successfully!', 'success')
        
    except Exception as e:
        conn.rollback() if conn else None
        conn.close() if conn else None
        flash(f'Error deleting bus: {str(e)}', 'danger')
    
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
            b.travel_date,
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
    today_iso = datetime.date.today().isoformat()
    
    now = datetime.datetime.now()

    active_bookings = []  # Bookings with travel_date = today and status not in completed/cancelled
    scheduled_bookings_by_date = {}  # Bookings with travel_date > today and status = paid
    history_bookings_by_date = {}  # Bookings with status = arrived, cancelled, or travel_date < today
    walkin_bookings_by_date = {}

    print(f"Total bookings found: {len(rows)}")  # Debug line
    print(f"Today's date (ISO): {today_iso}")  # Debug line

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
            "travel_date": row["travel_date"] or "Not set",
            "status": row["status"],
            "created_date": created_date,
            "created_time": created_time,
            "booking_type": row["booking_type"]
        }

        travel_date_raw = row["travel_date"] or ""
        
        print(f"Booking #{row['id']}: travel_date={travel_date_raw}, status={row['status']}, type={row['booking_type']}")  # Debug line
        
        # Walk-in bookings
        if booking_item["booking_type"] == "Walk-in":
            walkin_bookings_by_date.setdefault(created_date, []).append(booking_item)
        
        # Active Bookings (today's trips that are paid, waiting, or processing)
        elif travel_date_raw == today_iso and row["status"] not in ["arrived", "cancelled"]:
            active_bookings.append(booking_item)
            print(f"Added to Active Bookings: #{row['id']}")  # Debug line
        
        # Scheduled Bookings (future travel dates with paid status)
        elif travel_date_raw > today_iso and row["status"] == "paid":
            scheduled_bookings_by_date.setdefault(travel_date_raw, []).append(booking_item)
            print(f"Added to Scheduled Bookings: #{row['id']} for date {travel_date_raw}")  # Debug line
        
        # History Bookings (past travel dates OR completed/cancelled status)
        else:
            history_bookings_by_date.setdefault(created_date, []).append(booking_item)
            print(f"Added to History Bookings: #{row['id']}")  # Debug line

    # Sort scheduled bookings by date
    scheduled_bookings_by_date = dict(sorted(scheduled_bookings_by_date.items()))
    
    # Sort history by date (newest first)
    history_bookings_by_date = dict(sorted(history_bookings_by_date.items(), reverse=True))

    print(f"Active count: {len(active_bookings)}")  # Debug line
    print(f"Scheduled count: {sum(len(v) for v in scheduled_bookings_by_date.values())}")  # Debug line
    print(f"History count: {sum(len(v) for v in history_bookings_by_date.values())}")  # Debug line
    print(f"Walk-in count: {sum(len(v) for v in walkin_bookings_by_date.values())}")  # Debug line

    conn.close()

    return render_template(
        "admin_bookings.html",
        active_bookings=active_bookings,
        scheduled_bookings_by_date=scheduled_bookings_by_date,
        history_bookings_by_date=history_bookings_by_date,
        walkin_bookings_by_date=walkin_bookings_by_date,
        today_str=today_str,
        now=now
    )

@app.route("/admin/revenue")
def admin_revenue():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db_connection()
    
    filter_date = request.args.get('date')

    # Query for filtered revenue
    filtered_query_params = []
    filtered_where_clauses = ["b.status = 'paid'"]

    if filter_date:
        filtered_where_clauses.append("date(b.created_at) = ?")
        filtered_query_params.append(filter_date)
    
    filtered_where_clause_str = " AND ".join(filtered_where_clauses)

    # Get all paid bookings with their details
    filtered_rows = conn.execute(f"""
        SELECT
            b.id,
            b.created_at,
            COALESCE(b.price, 0) AS fare,
            bs.bus_no,
            b.status,
            b.travel_date,
            u.fullname AS user_name
        FROM bookings b
        JOIN trips t ON t.id = b.trip_id
        JOIN buses bs ON bs.id = t.bus_id
        JOIN users u ON u.id = b.user_id
        WHERE {filtered_where_clause_str}
        ORDER BY date(b.created_at) DESC, b.created_at DESC
    """, filtered_query_params).fetchall()

    revenue_by_date = {}
    total_filtered_revenue = 0
    total_transactions = 0

    for row in filtered_rows:
        created_at_raw = row["created_at"] or ""
        date_key = "Unknown Date"
        time_label = created_at_raw
        fare = float(row["fare"] or 0)
        
        # Skip zero or negative fares (shouldn't happen but safe check)
        if fare <= 0:
            continue

        try:
            parsed = datetime.datetime.strptime(created_at_raw, "%Y-%m-%d %H:%M:%S")
            date_key = parsed.strftime("%B %d, %Y")
            time_label = parsed.strftime("%I:%M %p")
        except Exception:
            pass

        total_filtered_revenue += fare
        total_transactions += 1

        # Initialize the date group if it doesn't exist
        if date_key not in revenue_by_date:
            revenue_by_date[date_key] = {
                "transactions": [],
                "total_amount": 0,
                "transaction_count": 0
            }
        
        revenue_by_date[date_key]["transactions"].append({
            "ticket_id": row["id"],
            "bus_number": row["bus_no"],
            "time": time_label,
            "price": fare,
            "user_name": row["user_name"],
            "travel_date": row["travel_date"]
        })
        revenue_by_date[date_key]["total_amount"] += fare
        revenue_by_date[date_key]["transaction_count"] += 1

    # Calculate today's revenue (unfiltered, all paid bookings today)
    today_iso = datetime.date.today().isoformat()
    today_stats = conn.execute("""
        SELECT 
            COALESCE(SUM(b.price), 0) as total,
            COUNT(b.id) as count
        FROM bookings b
        WHERE b.status = 'paid' AND date(b.created_at) = ?
    """, (today_iso,)).fetchone()
    
    today_revenue = today_stats["total"] if today_stats else 0
    today_count = today_stats["count"] if today_stats else 0
    today_date = datetime.datetime.now().strftime('%B %d, %Y')
    
    # Calculate overall statistics
    overall_stats = conn.execute("""
        SELECT 
            COALESCE(SUM(price), 0) as total,
            COUNT(id) as count,
            AVG(price) as average
        FROM bookings
        WHERE status = 'paid'
    """).fetchone()
    
    overall_total = overall_stats["total"] if overall_stats else 0
    overall_count = overall_stats["count"] if overall_stats else 0
    average_fare = overall_stats["average"] if overall_stats and overall_stats["average"] else 0
    
    conn.close()

    # Debug output
    print(f"=== Revenue Summary ===")
    print(f"Filter applied: {filter_date if filter_date else 'None'}")
    print(f"Total revenue: ₱{total_filtered_revenue:,.2f}")
    print(f"Total transactions: {total_transactions}")
    print(f"Today's revenue: ₱{today_revenue:,.2f} ({today_count} transactions)")
    print(f"Overall revenue: ₱{overall_total:,.2f} ({overall_count} transactions)")
    print(f"Average fare: ₱{average_fare:,.2f}")

    return render_template(
        "admin_revenue.html",
        revenue_by_date=revenue_by_date,
        total_revenue=total_filtered_revenue,
        total_transactions=total_transactions,
        today_revenue=today_revenue,
        today_count=today_count,
        today_date=today_date,
        overall_total=overall_total,
        overall_count=overall_count,
        average_fare=average_fare,
        filter_date=filter_date
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
            b.travel_date,
            b.booking_type,
            b.payment_method,

            p.fullname AS passenger_name,
            p.contact,

            t.departure,
            t.arrival,
            b.price,
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

    available_seats = 52 - len(get_seat_statuses(conn, booking["trip_id"], booking["travel_date"]))
    
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

    # Update booking status to paid (not completed)
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
            b.travel_date,
            b.booking_type,
            b.payment_method,
            p.fullname AS passenger_name,
            p.contact,
            t.departure,
            t.arrival,
            b.price,
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

    if not booking or booking["status"] not in ["paid", "dispatched", "onboard", "arrived"]:
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

    # Map status to display text and badge color
    status_display = {
        'paid': ('Confirmed - Ready for Boarding', 'status-paid'),
        'dispatched': ('Dispatched - On Board', 'status-dispatched'),
        'onboard': ('Onboard - Currently Traveling', 'status-onboard'),
        'arrived': ('Arrived - Trip Completed', 'status-arrived')
    }
    
    status_text, status_class = status_display.get(booking['status'], (booking['status'].capitalize(), ''))

    qr_data = (
        f"Ticket #{booking['id']}\n"
        f"Passenger: {booking['passenger_name']}\n"
        f"Booking Type: {booking['booking_type'] if 'booking_type' in booking.keys() else 'N/A'}\n"
        f"Travel Date: {booking['travel_date']}\n"
        f"Bus No: {booking['bus_no']}\n"
        f"Seat No: {booking['seat_number']}\n"
        f"Departure: {booking['departure']}\n"
        f"Arrival: {booking['arrival']}\n"
        f"Payment Method: {booking['payment_method']}\n"
        f"Status: {status_text}\n"
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
    return render_template("booking_detail.html", 
                         booking=booking, 
                         booking_created_at=formatted_created_at, 
                         qr_url=qr_url, 
                         back_url=back_url,
                         status_text=status_text,
                         status_class=status_class)

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
            elif user["role"] == "conductor":
                return redirect(url_for("conductor_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))
        
        return redirect(url_for("home", error="Invalid email or password"))
    
    except Exception as e:
        print(f"Login error: {str(e)}")
        return redirect(url_for("home", error="An error occurred during login. Please try again."))


@app.route("/conductor")
def conductor_dashboard():
    if "user_id" not in session or session.get("role") != "conductor":
        return redirect(url_for("home", login_required=1))
    return render_template("conductor_dashboard.html")

@app.route("/api/scan_ticket", methods=["POST"])
def scan_ticket():
    if "user_id" not in session or session.get("role") not in ["admin", "conductor"]:
        return jsonify({"success": False, "message": "Unauthorized access"}), 403

    data = request.get_json()
    qr_content = data.get("qr_content", "")

    # Extract ID from "Ticket #ID" pattern generated in the ticket route
    match = re.search(r"Ticket #(\d+)", qr_content)
    if not match:
        return jsonify({"success": False, "message": "Invalid QR code format."}), 400

    booking_id = match.group(1)
    conn = get_db_connection()
    booking = conn.execute("SELECT id, status, passenger_id, travel_date FROM bookings WHERE id = ?", (booking_id,)).fetchone()

    if not booking:
        conn.close()
        return jsonify({"success": False, "message": "Booking not found."}), 404

    current_status = booking["status"]
    new_status = None
    msg = ""

    # Get today's date to validate if boarding is allowed on this schedule
    today_iso = datetime.date.today().isoformat()

    if current_status == "paid":
        # Validate that the passenger is boarding on their scheduled travel date
        if booking["travel_date"] and booking["travel_date"] != today_iso:
            conn.close()
            if booking["travel_date"] > today_iso:
                return jsonify({"success": False, "message": f"Access Denied: Advance booking for {booking['travel_date']}. Boarding not allowed today."}), 400
            else:
                return jsonify({"success": False, "message": f"Access Denied: Ticket expired. Scheduled travel was for {booking['travel_date']}."}), 400

        new_status = "dispatched"
        msg = "Passenger Boarded Successfully! Status: Dispatched (On Bus)"
        
    elif current_status == "dispatched":
        new_status = "onboard"
        msg = "Passenger is now ONBOARD and traveling to destination."
        
    elif current_status == "onboard":
        new_status = "arrived"
        msg = "Passenger has ARRIVED at destination. Trip completed."
        
    elif current_status == "arrived":
        conn.close()
        return jsonify({"success": False, "message": "Error: This ticket has already been completed (Arrived)."}), 400
    elif current_status == "cancelled":
        conn.close()
        return jsonify({"success": False, "message": "Error: This ticket has been cancelled."}), 400
    else:
        conn.close()
        return jsonify({"success": False, "message": f"Invalid ticket status: {current_status}. Must be 'Paid' to board."}), 400

    conn.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": msg, "new_status": new_status})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True) 
    app.run(host='0.0.0.0', port=5000, debug=True)