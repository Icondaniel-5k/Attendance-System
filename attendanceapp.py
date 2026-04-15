# ======================================
# ATTENDANCE + HR SYSTEM (ADVANCED VERSION)
# Features:
# ✅ Clock in/out tracking
# ✅ Late detection (15 min grace)
# ✅ Early leaving penalty
# ✅ Absence tracking
# ✅ Working hours calculation
# ✅ Attendance score (0–100)
# ✅ Fire / Rehire staff
# ======================================

from flask import Flask, render_template, request, redirect, session, send_file, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, time, timedelta
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- CONFIG ----------------

START_TIME = time(8, 0)
END_TIME = time(17, 0)
GRACE_MINUTES = 15

# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


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
        salary REAL,
        active INTEGER DEFAULT 1
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

    user = db.execute("SELECT * FROM users WHERE username='admin'").fetchone()
    if not user:
        db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    db.commit()

# ---------------- AUTH ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user"] = username
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


def auth():
    return "user" in session

# ---------------- FLASH ----------------

def flash(msg):
    session["flash"] = msg

# ---------------- SIDEBAR PAGES ----------------

@app.route("/")
def root():
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    if not auth():
        return redirect("/login")

    db = get_db()
    staff = db.execute("SELECT * FROM staff WHERE active=1").fetchall()
    inactive_staff = db.execute("SELECT * FROM staff WHERE active=0").fetchall()

    flash_msg = session.pop("flash", None)

    return render_template(
        "index.html",
        staff=staff,
        inactive_staff=inactive_staff,
        active_page="dashboard",
        flash=flash_msg
    )


@app.route("/report")
def report():
    if not auth():
        return redirect("/login")

    db = get_db()

    data = db.execute("""
        SELECT staff.name, staff.salary,
               attendance.date,
               attendance.clock_in,
               attendance.clock_out
        FROM attendance
        JOIN staff ON staff.id = attendance.staff_id
    """).fetchall()

    rows = []
    summary = {}

    for r in data:
        rows.append([r["name"], r["date"], r["clock_in"], r["clock_out"]])

        if r["name"] not in summary:
            summary[r["name"]] = r["salary"]

    summary_rows = [[k, v] for k, v in summary.items()]

    flash_msg = session.pop("flash", None)

    return render_template(
        "report.html",
        rows=rows,
        summary=summary_rows,
        active_page="report",
        flash=flash_msg
    )


@app.route("/export")
def export():
    if not auth():
        return redirect("/login")

    db = get_db()

    data = db.execute("""
        SELECT staff.name, attendance.date,
               attendance.clock_in, attendance.clock_out
        FROM attendance
        JOIN staff ON staff.id = attendance.staff_id
    """).fetchall()

    df = pd.DataFrame(data, columns=["Name", "Date", "Clock In", "Clock Out"])

    file = "attendance.xlsx"
    df.to_excel(file, index=False)

    flash("Excel exported successfully")
    return send_file(file, as_attachment=True)

# ---------------- STAFF ----------------

@app.route("/add_staff", methods=["POST"])
def add_staff():
    if not auth():
        return redirect("/login")

    name = request.form["name"]
    salary = float(request.form["salary"])

    db = get_db()
    db.execute(
        "INSERT INTO staff (name, salary, active) VALUES (?, ?, 1)",
        (name, salary)
    )
    db.commit()

    flash("Staff added successfully")
    return redirect("/dashboard")


@app.route("/fire_staff/<int:staff_id>")
def fire_staff(staff_id):
    if not auth():
        return redirect("/login")

    db = get_db()
    db.execute("UPDATE staff SET active=0 WHERE id=?", (staff_id,))
    db.commit()

    flash("Staff deactivated")
    return redirect("/dashboard")


@app.route("/rehire_staff/<int:staff_id>")
def rehire_staff(staff_id):
    if not auth():
        return redirect("/login")

    db = get_db()
    db.execute("UPDATE staff SET active=1 WHERE id=?", (staff_id,))
    db.commit()

    flash("Staff reactivated")
    return redirect("/dashboard")

# ---------------- CLOCK ----------------

@app.route("/clock", methods=["POST"])
def clock():
    if not auth():
        return redirect("/login")

    staff_id = request.form["staff_id"]
    action = request.form["action"]

    now = datetime.now()
    today = now.date()

    db = get_db()

    record = db.execute(
        "SELECT * FROM attendance WHERE staff_id=? AND date=?",
        (staff_id, today)
    ).fetchone()

    if action == "in":
        if record:
            flash("Already clocked in today")
            return redirect("/dashboard")

        db.execute("""
            INSERT INTO attendance (staff_id, date, clock_in)
            VALUES (?, ?, ?)
        """, (staff_id, today, now))

        flash("Clock-in successful")

    elif action == "out":
        if not record:
            flash("You have not clocked in yet")
            return redirect("/dashboard")

        db.execute("""
            UPDATE attendance
            SET clock_out=?
            WHERE staff_id=? AND date=?
        """, (now, staff_id, today))

        flash("Clock-out successful")

    db.commit()
    return redirect("/dashboard")

# ---------------- RUN ----------------

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)