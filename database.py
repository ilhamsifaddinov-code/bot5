import sqlite3
from typing import List, Dict, Optional

DB_PATH = "clinic.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Qániygelikler (Departments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
    """)

    # 2. Shıpakerler (Doctors)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        experience TEXT NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    )
    """)

    # 3. Qabıllawǵa jazılıwlar (Appointments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        user_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        patient_name TEXT NOT NULL,
        doctor_id INTEGER NOT NULL,
        doctor_name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        price REAL NOT NULL,
        app_date TEXT NOT NULL,
        app_time TEXT NOT NULL,
        status TEXT DEFAULT 'confirmed', -- confirmed, cancelled, completed
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id)
    )
    """)

    # Baslanǵısh qániygelikler
    cursor.execute("SELECT COUNT(*) FROM departments")
    if cursor.fetchone()[0] == 0:
        deps = [
            ("🦷 Stomatologiya",),
            ("🩺 Terapiya",),
            ("👶 Pediatriya (Balalar)",),
            ("❤️ Kardiologiya",),
            ("👁️ Oftalmologiya (Kóz)",)
        ]
        cursor.executemany("INSERT INTO departments (name) VALUES (?)", deps)

    # Baslanǵısh shıpakerler
    cursor.execute("SELECT COUNT(*) FROM doctors")
    if cursor.fetchone()[0] == 0:
        docs = [
            (1, "Dr. Aziz Allanazarov", "8 jıl tájiriybe", 80000),
            (1, "Dr. Zuxra Ernazarova", "5 jıl tájiriybe", 70000),
            (2, "Dr. Berdaq Pirnazarov", "14 jıl tájiriybe", 60000),
            (3, "Dr. Aygúl Maxsetova", "10 jıl tájiriybe", 65000),
            (4, "Dr. Timur Qudaybergenov", "12 jıl tájiriybe", 90000),
            (5, "Dr. Nargiza Jumabayeva", "7 jıl tájiriybe", 60000),
        ]
        cursor.executemany("INSERT INTO doctors (department_id, name, experience, price) VALUES (?, ?, ?, ?)", docs)

    conn.commit()
    conn.close()

# Bos qabıllaw waqıtları (09:00 dan 17:00 ge shekem)
CLINIC_HOURS = ["09:00", "09:40", "10:20", "11:00", "11:40", "14:00", "14:40", "15:20", "16:00", "16:40"]

def get_available_doctor_slots(doctor_id: int, date_str: str) -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT app_time FROM appointments 
        WHERE doctor_id = ? AND app_date = ? AND status = 'confirmed'
    """, (doctor_id, date_str))
    booked = [r['app_time'] for r in cursor.fetchall()]
    conn.close()
    return [slot for slot in CLINIC_HOURS if slot not in booked]

def create_appointment(user_id: int, user_name: str, phone: str, patient_name: str,
                       doctor_id: int, doctor_name: str, specialty: str, price: float,
                       date_str: str, time_str: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO appointments (user_id, user_name, phone, patient_name, doctor_id, doctor_name, specialty, price, app_date, app_time)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, user_name, phone, patient_name, doctor_id, doctor_name, specialty, price, date_str, time_str))
    app_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return app_id

def get_user_appointments(user_id: int) -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM appointments WHERE user_id = ? AND status = 'confirmed' ORDER BY app_date, app_time", (user_id,)).fetchall()
    conn.close()
    return rows

def cancel_appointment(app_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (app_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_all_active_appointments() -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM appointments WHERE status = 'confirmed' ORDER BY app_date, app_time").fetchall()
    conn.close()
    return rows

def get_clinic_stats() -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    total = cursor.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    active = cursor.execute("SELECT COUNT(*) FROM appointments WHERE status = 'confirmed'").fetchone()[0]
    revenue = cursor.execute("SELECT COALESCE(SUM(price), 0) FROM appointments WHERE status = 'confirmed'").fetchone()[0]
    conn.close()
    return {"total": total, "active": active, "revenue": revenue}