# ======================================
# ATTENDANCE SYSTEM - PRO VERSION (FINAL)
# Includes:
# ✅ Login System (Admin)
# ✅ Responsive UI (Tailwind)
# ✅ Excel Export
# ✅ Salary + Late Deduction
# ✅ Ready for EXE + Deployment
# ======================================

# INSTALL:
# pip install flask pandas openpyxl werkzeug
#run pyinstaller --onefile app.py (later) then go to dist/app.exe
#change app.run(debug=True) to app.run(host="0.0.0.0", port=10000) when you want to deploy on server

from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, time, timedelta
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "secret123"

START_TIME = time(8, 0)
GRACE_MINUTES = 15
WORK_HOURS_PER_DAY = 8
WORK_DAYS = 22

# ---------------- DATABASE ----------------

def get_db():
    return sqlite3.connect("database.db")


def init_db():
    db = get_db()

    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        salary REAL
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        date TEXT,
        clock_in TEXT,
        clock_out TEXT
    )
    """)

    # Create default admin
    user = db.execute("SELECT * FROM users").fetchone()
    if not user:
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                   ("admin", generate_password_hash("admin123")))

    db.commit()

# ---------------- AUTH ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

        if user and check_password_hash(user[2], password):
            session["user"] = username
            return redirect("/")

    return render_template("login.html")


def auth():
    if "user" not in session:
        return False
    return True

# ---------------- LOGIC ----------------

def calculate_late(clock_in):
    allowed = datetime.combine(clock_in.date(), START_TIME) + timedelta(minutes=GRACE_MINUTES)
    if clock_in <= allowed:
        return 0
    return int((clock_in - allowed).total_seconds() / 60)


def hourly_rate(salary):
    return salary / (WORK_DAYS * WORK_HOURS_PER_DAY)

# ---------------- ROUTES ----------------

@app.route("/")
def index():
    if not auth(): return redirect("/login")

    db = get_db()
    staff = db.execute("SELECT * FROM staff").fetchall()
    return render_template("index.html", staff=staff)


@app.route("/add_staff", methods=["POST"])
def add_staff():
    if not auth(): return redirect("/login")

    name = request.form["name"]
    salary = float(request.form["salary"])

    db = get_db()
    db.execute("INSERT INTO staff (name, salary) VALUES (?, ?)", (name, salary))
    db.commit()

    return redirect("/")


@app.route("/clock", methods=["POST"])
def clock():
    if not auth(): return redirect("/login")

    staff_id = request.form["staff_id"]
    action = request.form["action"]
    now = datetime.now()
    today = now.date()

    db = get_db()

    record = db.execute("SELECT * FROM attendance WHERE staff_id=? AND date=?",
                        (staff_id, today)).fetchone()

    if action == "in":
        if record:
            return "Already clocked in"
        db.execute("INSERT INTO attendance (staff_id, date, clock_in) VALUES (?, ?, ?)",
                   (staff_id, today, now))

    elif action == "out":
        db.execute("UPDATE attendance SET clock_out=? WHERE staff_id=? AND date=?",
                   (now, staff_id, today))

    db.commit()
    return redirect("/")


@app.route("/report")
def report():
    if not auth(): return redirect("/login")

    db = get_db()
    data = db.execute("""
        SELECT staff.name, staff.salary, attendance.date, attendance.clock_in, attendance.clock_out
        FROM attendance
        JOIN staff ON staff.id = attendance.staff_id
    """).fetchall()

    rows = []
    summary = {}

    for name, salary, date, clock_in, clock_out in data:
        late = calculate_late(datetime.fromisoformat(clock_in))
        rows.append([name, date, clock_in, clock_out, late])

        if name not in summary:
            summary[name] = {"late": 0, "salary": salary}
        summary[name]["late"] += late

    summary_rows = []
    for name, info in summary.items():
        late_hours = info["late"] / 60
        rate = hourly_rate(info["salary"])
        deduction = late_hours * rate
        final_salary = info["salary"] - deduction

        summary_rows.append([name, info["late"], round(deduction,2), round(final_salary,2)])

    return render_template("report.html", rows=rows, summary=summary_rows)


@app.route("/export")
def export():
    if not auth(): return redirect("/login")

    db = get_db()
    data = db.execute("""
        SELECT staff.name, attendance.date, attendance.clock_in, attendance.clock_out
        FROM attendance
        JOIN staff ON staff.id = attendance.staff_id
    """).fetchall()

    df = pd.DataFrame(data, columns=["Name","Date","Clock In","Clock Out"])
    file = "attendance.xlsx"
    df.to_excel(file, index=False)

    return send_file(file, as_attachment=True)

# ---------------- UI ----------------

def create_templates():
    os.makedirs("templates", exist_ok=True)

    # LOGIN PAGE
    with open("templates/login.html","w") as f:
        f.write("""
<html>
<head>
<script src='https://cdn.tailwindcss.com'></script>
</head>
<body class='bg-gray-900 flex items-center justify-center h-screen'>
<form method='POST' class='bg-gray-800 p-6 rounded'>
<h2 class='text-white mb-4'>Login</h2>
<input name='username' placeholder='Username' class='w-full mb-2 p-2'>
<input name='password' type='password' placeholder='Password' class='w-full mb-2 p-2'>
<button class='bg-blue-500 w-full p-2 text-white'>Login</button>
</form>
</body>
</html>
""")

    # MAIN PAGE
    with open("templates/index.html","w") as f:
        f.write("""
<html>
<head>
<script src='https://cdn.tailwindcss.com'></script>
</head>
<body class='bg-gray-900 text-white p-6'>
<h1 class='text-3xl mb-4'>Dashboard</h1>

<form method='POST' action='/add_staff'>
<input name='name' placeholder='Name' class='p-2 text-black'>
<input name='salary' placeholder='Salary' class='p-2 text-black'>
<button class='bg-green-500 p-2'>Add</button>
</form>

<form method='POST' action='/clock' class='mt-4'>
<select name='staff_id' class='text-black'>
{% for s in staff %}
<option value='{{s[0]}}'>{{s[1]}}</option>
{% endfor %}
</select>
<button name='action' value='in' class='bg-blue-500 p-2'>IN</button>
<button name='action' value='out' class='bg-red-500 p-2'>OUT</button>
</form>

<div class='mt-4'>
<a href='/report'>Report</a> |
<a href='/export'>Excel</a>
</div>
</body>
</html>
""")

    # REPORT PAGE
    with open("templates/report.html","w") as f:
        f.write("""
<html>
<head>
<script src='https://cdn.tailwindcss.com'></script>
</head>
<body class='bg-gray-900 text-white p-6'>
<h1>Report</h1>
<table class='w-full'>
{% for r in rows %}
<tr><td>{{r[0]}}</td><td>{{r[1]}}</td><td>{{r[4]}}</td></tr>
{% endfor %}
</table>
</body>
</html>
""")

# ---------------- RUN ----------------

if __name__ == "__main__":
    init_db()
    create_templates()

    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("ENV") != "production"

    app.run(host="0.0.0.0", port=port, debug=debug)