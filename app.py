from flask import Flask, render_template_string, request, jsonify, make_response
import psycopg2
import os
import datetime
import barcode
from barcode.writer import ImageWriter
import base64
from io import BytesIO
from docx import Document

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

ADMIN_USER = os.environ.get("ADMIN_USER", "slsu")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "jge")

USER_USER = os.environ.get("USER_USER", "jge")
USER_PASS = os.environ.get("USER_PASS", "slsu")

def get_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"DB Connect Error: {e}")
        return None

def get_ph_time():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return now.strftime("%I:%M %p")

def get_ph_date():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")

def init_db():
    conn = get_db()

    if not conn:
        print("Cannot connect to database")
        return

    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            id_type TEXT NOT NULL,
            full_name TEXT NOT NULL,
            department TEXT,
            major TEXT,
            contact_number TEXT,
            address TEXT,
            year_level TEXT,
            id_number TEXT NOT NULL UNIQUE,
            registered_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            time_in TEXT,
            time_out TEXT,
            scan_date TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    print("DATABASE READY")

init_db()

def generate_barcode_b64(id_number):
    code128 = barcode.get_barcode_class("code128")
    writer = ImageWriter()
    writer.set_options({"module_width":0.3, "module_height":10, "font_size":8, "text_distance":2})
    img = code128(id_number, writer=writer).render()
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def is_logged_in():
    return request.cookies.get('logged_in') == 'true'

def get_role():
    return request.cookies.get('role', 'user')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form.get('username', '').strip()
        pword = request.form.get('password', '').strip()

        if uname == ADMIN_USER and pword == ADMIN_PASS:
            resp = make_response("<script>window.location='/';</script>")
            resp.set_cookie('logged_in', 'true', max_age=31536000)
            resp.set_cookie('role', 'admin', max_age=31536000)
            return resp

        if uname == USER_USER and pword == USER_PASS:
            resp = make_response("<script>window.location='/user';</script>")
            resp.set_cookie('logged_in', 'true', max_age=31536000)
            resp.set_cookie('role', 'user', max_age=31536000)
            return resp

        return """
<!DOCTYPE html>
<html>
<head>
    <title>Sign In — Library Attendance System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#eef0f3;min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;}
        .card{background:#ffffff;padding:0;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 2px 12px rgba(15,25,43,0.08);width:100%;max-width:440px;overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:44px 40px;}
        h1{text-align:center;color:#1b2a41;margin-bottom:10px;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
        .subtitle{text-align:center;color:#64748b;margin-bottom:30px;font-size:14px;}
        .error-box{background:#fbeaea;color:#8a1f1f;padding:14px 16px;border-left:3px solid #c0392b;border-radius:4px;margin-bottom:26px;text-align:left;font-size:14px;}
        a.back-link{display:block;text-align:center;padding:13px;background:#1b2a41;color:#fff;border-radius:4px;text-decoration:none;font-weight:600;font-size:14px;letter-spacing:.3px;transition:background 0.2s;}
        a.back-link:hover{background:#10192b;}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-top"></div>
        <div class="card-body">
            <h1>Invalid Credentials</h1>
            <p class="subtitle">SLSU–JGE Library Attendance System</p>
            <div class="error-box">The username or password you entered is incorrect. Please try again.</div>
            <a href="/login" class="back-link">Return to Sign In</a>
        </div>
    </div>
</body>
</html>"""

    return """
<!DOCTYPE html>
<html>
<head>
    <title>Sign In — Library Attendance System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#eef0f3;min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;}
        .card{background:#ffffff;padding:0;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 2px 12px rgba(15,25,43,0.08);width:100%;max-width:440px;overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:44px 40px;}
        .brand-mark{width:56px;height:56px;margin:0 auto 18px auto;background:#1b2a41;color:#e8c766;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:13px;letter-spacing:.5px;}
        h1{text-align:center;color:#1b2a41;margin-bottom:6px;font-size:24px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
        .subtitle{text-align:center;color:#64748b;margin-bottom:34px;font-size:14px;}
        .form-group{margin-bottom:20px;}
        label{display:block;margin-bottom:8px;color:#374151;font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:.4px;}
        input{width:100%;padding:13px 15px;border:1px solid #d1d5db;border-radius:4px;font-size:15px;transition:border-color 0.2s,box-shadow 0.2s;background:#fafbfc;}
        input:focus{outline:none;border-color:#1b2a41;background:#fff;box-shadow:0 0 0 3px rgba(27,42,65,0.1);}
        button{width:100%;padding:14px;background:#1b2a41;color:white;border:none;border-radius:4px;font-size:15px;font-weight:600;cursor:pointer;transition:background 0.2s;letter-spacing:.3px;margin-top:6px;}
        button:hover{background:#10192b;}
        .hint{margin-top:22px;text-align:center;font-size:12px;color:#94a3b8;line-height:1.7;border-top:1px solid #eef0f3;padding-top:16px;}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-top"></div>
        <div class="card-body">
            <div class="brand-mark">SLSUJGE</div>
            <h1>Sign In</h1>
            <p class="subtitle">Library Attendance System</p>
            <form method="POST">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" required placeholder="Enter your username">
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required placeholder="Enter your password">
                </div>
                <button type="submit">Sign In</button>
            </form>
           
        </div>
    </div>
</body>
</html>"""

@app.route('/user')
def user_panel():
    if not is_logged_in() or get_role() != 'user':
        return "<script>window.location='/login';</script>"
    return render_template_string(USER_FRONTEND)

@app.route('/')
def home():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    if get_role() != 'admin':
        return "<script>window.location='/user';</script>"
    return render_template_string(ADMIN_FRONTEND)

@app.route('/scan', methods=['POST'])
def scan():
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    id_number = data.get('id_number', '').strip()

    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500

    c = conn.cursor()
    today = get_ph_date()
    now = get_ph_time()

    c.execute("SELECT id, full_name, id_number FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
    user = c.fetchone()

    if not user:
        conn.close()
        return jsonify({"success": False, "message": f"ID {id_number} was not found in the records."})

    user_id, full_name, _ = user

    c.execute("SELECT id, time_in, time_out FROM attendance WHERE user_id = %s AND scan_date = %s ORDER BY id DESC LIMIT 1", (user_id, today))
    last_attendance = c.fetchone()

    if not last_attendance or last_attendance[2]:
        c.execute("INSERT INTO attendance (user_id, time_in, scan_date) VALUES (%s, %s, %s)", (user_id, now, today))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"TIME IN recorded — {full_name} — {now}"})
    else:
        c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"TIME OUT recorded — {full_name} — {now}"})

@app.route('/register', methods=['POST'])
def register():
    if not is_logged_in():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        id_type = request.form.get('id_type', '').strip()
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip() or None
        major = request.form.get('major', '').strip() or None
        contact_number = request.form.get('contact_number', '').strip() or None
        address = request.form.get('address', '').strip() or None
        year_level = request.form.get('year_level', '').strip() or None
        id_number = request.form.get('id_number', '').strip().upper()
        registered_at = get_ph_date() + " " + get_ph_time()

        if not id_type or not full_name or not id_number:
            return jsonify({"success": False, "error": "Please complete all required fields."}), 400

        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database connection failed."}), 500

        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
        if c.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "This ID number is already registered."}), 400

        c.execute("""INSERT INTO users 
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at))
        conn.commit()
        conn.close()

        barcode_b64 = generate_barcode_b64(id_number)
        info = f"{full_name}  |  ID: {id_number}  |  {id_type}"
        return jsonify({"success": True, "info": info, "barcode": barcode_b64})

    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        return jsonify({"success": False, "error": f"An error occurred: {str(e)}"}), 500

@app.route('/get-students')
def get_students():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"students": []}), 403

    conn = get_db()

    if not conn:
        return jsonify({"students": []}), 500

    c = conn.cursor()

    c.execute("""
        SELECT
            id,
            id_type,
            full_name,
            department,
            major,
            contact_number,
            address,
            year_level,
            id_number
        FROM users
        ORDER BY full_name
    """)

    students = [
        {
            "id": row[0],
            "id_type": row[1],
            "full_name": row[2],
            "department": row[3],
            "major": row[4],
            "contact_number": row[5],
            "address": row[6],
            "year_level": row[7],
            "id_number": row[8]
        }
        for row in c.fetchall()
    ]

    conn.close()

    return jsonify({"students": students})


@app.route('/update-student', methods=['POST'])
def update_student():
    if not is_logged_in():
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        student_id = request.form.get('id', '').strip()
        id_type = request.form.get('id_type', '').strip()
        id_number = request.form.get('id_number', '').strip().upper()
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip() or None
        major = request.form.get('major', '').strip() or None
        contact_number = request.form.get('contact_number', '').strip() or None
        address = request.form.get('address', '').strip() or None
        year_level = request.form.get('year_level', '').strip() or None

        if not all([student_id, id_type, id_number, full_name]):
            return jsonify({"success": False, "error": "Missing required fields."}), 400

        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database error."}), 500

        c = conn.cursor()
        c.execute("""UPDATE users SET 
            id_type = %s, id_number = %s, full_name = %s, department = %s, 
            major = %s, contact_number = %s, address = %s, year_level = %s
            WHERE id = %s""",
            (id_type, id_number, full_name, department, major, contact_number, address, year_level, student_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

    except Exception as e:
        print(f"UPDATE ERROR: {e}")
        return jsonify({"success": False, "error": f"An error occurred: {str(e)}"}), 500

@app.route('/get-records')
def get_records():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"records": []}), 403

    conn = get_db()

    if not conn:
        return jsonify({"records": []}), 500

    c = conn.cursor()

    c.execute("""
        SELECT
            u.full_name,
            u.department,
            a.time_in,
            a.time_out
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.scan_date = %s
        ORDER BY a.id DESC
    """, (get_ph_date(),))

    records = [
        {
            "full_name": row[0],
            "department": row[1] or "-",
            "time_in": row[2],
            "time_out": row[3]
        }
        for row in c.fetchall()
    ]

    conn.close()

    return jsonify({"records": records})


@app.route('/get-monthly-history')
def get_monthly_history():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"records": []}), 403

    month = request.args.get('month', '').strip()

    if not month:
        return jsonify({"records": []})

    conn = get_db()

    if not conn:
        return jsonify({"records": []}), 500

    c = conn.cursor()

    c.execute("""
        SELECT
            a.scan_date,
            u.full_name,
            u.department,
            a.time_in,
            a.time_out
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.scan_date LIKE %s
        ORDER BY a.scan_date DESC, a.id DESC
    """, (f"{month}%",))

    records = [
        {
            "scan_date": row[0],
            "full_name": row[1],
            "department": row[2] or "-",
            "time_in": row[3],
            "time_out": row[4]
        }
        for row in c.fetchall()
    ]

    conn.close()

    return jsonify({"records": records})


@app.route('/download-word')
def download_word():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    conn = get_db()
    if not conn:
        return "Database error"
    today = get_ph_date()
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_number, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.scan_date = %s ORDER BY a.id""", (today,))
    records = c.fetchall()
    conn.close()

    doc = Document()
    doc.add_heading(f'Library Attendance Report — {today}', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('SLSU–JGE Library Attendance System')

    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    hdr[0].text = 'Full Name'
    hdr[1].text = 'ID Number'
    hdr[2].text = 'Time In'
    hdr[3].text = 'Time Out'

    for rec in records:
        row = table.add_row().cells
        row[0].text = rec[0]
        row[1].text = rec[1]
        row[2].text = rec[2] or '-'
        row[3].text = rec[3] or '-'

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Disposition'] = f'attachment; filename=attendance_report_{today}.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp

@app.route('/download-monthly-word')
def download_monthly_word():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    month = request.args.get('month', '').strip()
    conn = get_db()
    if not conn:
        return "Database error"
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_number, a.scan_date, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id
        WHERE a.scan_date LIKE %s ORDER BY a.scan_date, a.id""", (f"{month}%",))
    records = c.fetchall()
    conn.close()

    doc = Document()
    doc.add_heading(f'Monthly Attendance Report — {month}', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('SLSU–JGE Library Attendance System')

    table = doc.add_table(rows=1, cols=5)
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    hdr[0].text = 'Date'
    hdr[1].text = 'Full Name'
    hdr[2].text = 'ID Number'
    hdr[3].text = 'Time In'
    hdr[4].text = 'Time Out'

    for rec in records:
        row = table.add_row().cells
        row[0].text = rec[2]
        row[1].text = rec[0]
        row[2].text = rec[1]
        row[3].text = rec[3] or '-'
        row[4].text = rec[4] or '-'

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Disposition'] = f'attachment; filename=monthly_attendance_{month}.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp

@app.route('/print-monthly')
def print_monthly():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    month = request.args.get('month', '').strip()
    return f"""
<!DOCTYPE html><html><head><title>Monthly Report — {month}</title>
<style>
*{{box-sizing:border-box;}}
body{{font-family:'Segoe UI',Arial,sans-serif;padding:40px;max-width:1100px;margin:0 auto;color:#1f2937;}}
.report-header{{border-bottom:3px solid #1b2a41;padding-bottom:16px;margin-bottom:24px;}}
h1{{color:#1b2a41;font-family:Georgia,'Times New Roman',serif;font-size:24px;margin-bottom:6px;}}
.meta{{color:#64748b;font-size:13px;}}
table{{width:100%;border-collapse:collapse;margin-top:10px;}}
th,td{{border:1px solid #d8dbe0;padding:10px 12px;text-align:left;font-size:13px;}}
th{{background:#1b2a41;color:#fff;font-weight:600;}}
tr:nth-child(even){{background:#f7f8fa;}}
button{{padding:11px 26px;font-size:14px;cursor:pointer;background:#1b2a41;color:white;border:none;border-radius:4px;font-weight:600;margin-bottom:20px;}}
@media print{{button{{display:none;}}body{{padding:0;}}}}
</style>
</head><body>
<div class="report-header">
<h1>Monthly Attendance Report — {month}</h1>
<p class="meta">SLSU–JGE Library Attendance System &nbsp;•&nbsp; Generated: {get_ph_date()} {get_ph_time()}</p>
</div>
<button onclick="window.print()">Print Report</button>
<script>fetch('/get-monthly-history?month={month}').then(r=>r.json()).then(d=>{{
let html='<table><tr><th>Date</th><th>Full Name</th><th>ID Number</th><th>Time In</th><th>Time Out</th></tr>';
d.records.forEach(r=>html+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+r.id_number+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>');
html+='</table>';document.body.innerHTML+=html;
}})</script>
</body></html>"""

USER_FRONTEND = """
<!DOCTYPE html>
<html>
<head>
    <title>User Registration — SLSU-JGE</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#eef0f3;min-height:100vh;display:flex;justify-content:center;align-items:center;padding:30px;}
        .container{width:100%;max-width:560px;}
        .card{background:#ffffff;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 2px 12px rgba(15,25,43,0.08);overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:42px 40px;}
        .brand-mark{width:52px;height:52px;margin:0 auto 16px auto;background:#1b2a41;color:#e8c766;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:12px;text-align:center;line-height:1.2;}
        h1{text-align:center;color:#1b2a41;margin-bottom:6px;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
        .subtitle{text-align:center;color:#64748b;margin-bottom:32px;font-size:14px;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:8px;color:#374151;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;}
        input,select{width:100%;padding:12px 14px;border:1px solid #d1d5db;border-radius:4px;font-size:14px;transition:border-color 0.2s,box-shadow 0.2s;background:#fafbfc;}
        input:focus,select:focus{outline:none;border-color:#1b2a41;background:#fff;box-shadow:0 0 0 3px rgba(27,42,65,0.1);}
        button{width:100%;padding:14px;background:#1b2a41;color:white;border:none;border-radius:4px;font-size:15px;font-weight:600;cursor:pointer;transition:background 0.2s;margin-top:6px;letter-spacing:.3px;}
        button:hover{background:#10192b;}
        #barcode-result{display:none;margin-top:28px;text-align:center;padding:26px;background:#f7f8fa;border-radius:6px;border:1px solid #d8dbe0;}
        #barcode-result h3{color:#1b2a41;margin-bottom:12px;font-size:16px;font-family:Georgia,'Times New Roman',serif;}
        #student-info{font-size:15px;color:#1f2937;}
        .barcode-img{max-width:280px;margin:18px auto;display:block;padding:14px;background:white;border:1px solid #d8dbe0;border-radius:4px;}
        .btn-print{background:#1e6b34;margin-top:16px;}
        .btn-print:hover{background:#175628;}
        .logout-link{display:block;text-align:center;margin-top:22px;color:#64748b;text-decoration:none;font-size:13px;border-top:1px solid #eef0f3;padding-top:18px;}
        .logout-link:hover{color:#1b2a41;}
        @media(max-width:600px){.form-row{grid-template-columns:1fr;}.card-body{padding:30px 24px;}}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="card-top"></div>
            <div class="card-body">
                <div class="brand-mark">SLSU<br>JGE</div>
                <h1>User Registration</h1>
                <p class="subtitle">Complete the form to generate an attendance barcode</p>
                <form id="register-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>ID Type *</label>
                            <select name="id_type" id="id-type-select" required>
                                <option value="Student">Student</option>
                                <option value="Employee">Employee</option>
                                <option value="Visitor">Visitor</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>ID Number *</label>
                            <input type="text" name="id_number" required placeholder="e.g. 2024-0001">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Full Name *</label>
                        <input type="text" name="full_name" required placeholder="Last, First Middle">
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Department</label>
                            <select name="department" id="dept-select">
                                <option value="">-- Select Department --</option>
                                <option value="CT">BSIT</option>
                                <option value="BSED">BSED</option>
                                <option value="BEED">BEED</option>
                                <option value="BSFI">BSFI</option>
                                <option value="BSBA">BSBA</option>
                                <option value="EMPLOYEE">EMPLOYEE</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Year Level</label>
                            <select name="year_level" id="year-select">
                                <option value="1st Year">1st Year</option>
                                <option value="2nd Year">2nd Year</option>
                                <option value="3rd Year">3rd Year</option>
                                <option value="4th Year">4th Year</option>
                                <option value="N/A">N/A — Not Applicable</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Contact Number</label>
                            <input type="text" name="contact_number" placeholder="09XX-XXX-XXXX">
                        </div>
                        <div class="form-group">
                            <label>Address</label>
                            <input type="text" name="address" placeholder="City, Province">
                        </div>
                    </div>
                    <button type="submit">Register & Generate Barcode</button>
                </form>
                <div id="barcode-result">
                    <h3>Registration Successful</h3>
                    <p id="student-info"></p>
                    <img id="barcode-img" class="barcode-img"><br>
                    <button class="btn-print" onclick="window.print()">Print Barcode</button>
                </div>
                <a href="/login" class="logout-link">← Back to Sign In</a>
            </div>
        </div>
    </div>
<script>
document.addEventListener("DOMContentLoaded",function(){
    const form = document.getElementById("register-form");
    form.addEventListener("submit",function(e){
        e.preventDefault();
        const formData = new FormData(form);
        fetch("/register",{method:"POST",body:formData})
        .then(res=>res.json())
        .then(data=>{
            if(data.success){
                document.getElementById("barcode-result").style.display="block";
                document.getElementById("student-info").textContent=data.info;
                document.getElementById("barcode-img").src="data:image/png;base64,"+data.barcode;
                form.reset();
                document.getElementById("dept-select").value="";
            }else{
                alert(data.error);
            }
        })
        .catch(err=>alert("Error: "+err));
    });
});
</script>
</body>
</html>
"""

ADMIN_FRONTEND = """
<!DOCTYPE html>
<html>
<head>
    <title>Library Attendance — SLSU-JGE Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#eef0f3;min-height:100vh;}
        .app-container{display:flex;height:100vh;}
        .sidebar{width:270px;background:#1b2a41;display:flex;flex-direction:column;padding:0;position:relative;transition:width 0.25s ease;border-right:1px solid #10192b;}
        .sidebar.collapsed{width:74px;}
        .toggle-btn{position:absolute;right:-14px;top:26px;width:28px;height:28px;background:#1b2a41;border:1px solid #34455f;border-radius:50%;color:#e8c766;font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;z-index:10;transition:transform 0.2s;}
        .sidebar.collapsed .toggle-btn{transform:rotate(180deg);}
        .sidebar-header{padding:26px 22px 22px 22px;border-bottom:1px solid #2a3b56;}
        .sidebar.collapsed .sidebar-header{padding:26px 0;text-align:center;}
        .sidebar.collapsed .sidebar-header .full-title,.sidebar.collapsed .sidebar-header p{display:none;}
        .sidebar-header .brand-mark{width:40px;height:40px;background:#24344f;color:#e8c766;border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:11px;margin:0 auto 10px auto;}
        .sidebar-header h2{color:#f1f3f6;font-size:16px;font-weight:700;text-align:center;font-family:Georgia,'Times New Roman',serif;}
        .sidebar-header p{color:#8b9bb5;font-size:11px;margin-top:4px;text-align:center;letter-spacing:.3px;}
        .sidebar-menu{display:flex;flex-direction:column;gap:2px;padding:16px 12px;flex:1;}
        .menu-item{display:flex;align-items:center;gap:14px;padding:12px 14px;color:#c3cede;border-radius:4px;cursor:pointer;transition:background 0.2s,color 0.2s;font-size:14px;font-weight:500;border-left:3px solid transparent;white-space:nowrap;}
        .sidebar.collapsed .menu-item{justify-content:center;padding:12px 0;}
        .sidebar.collapsed .menu-item span.label{display:none;}
        .menu-item:hover{background:#233450;color:#fff;}
        .menu-item.active{background:#24344f;color:#fff;border-left:3px solid #e8c766;}
        .menu-item .badge{width:26px;height:26px;flex:0 0 26px;background:#0f1c30;border:1px solid #34455f;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#e8c766;}
        .menu-item.active .badge{background:#1b2a41;border-color:#e8c766;}
        .sidebar-footer{padding:18px;border-top:1px solid #2a3b56;margin-top:auto;}
        .sidebar.collapsed .sidebar-footer{padding:18px 8px;}
        .logout-btn{width:100%;padding:12px;background:#7a1f1f;color:white;border:none;border-radius:4px;font-size:13px;font-weight:600;cursor:pointer;transition:background 0.2s;letter-spacing:.3px;}
        .logout-btn:hover{background:#5e1717;}
        .main-content{flex:1;padding:28px;overflow-y:auto;}
        .content-header{margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #d8dbe0;}
        .content-header h1{color:#1b2a41;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
        .content-card{background:#ffffff;border-radius:6px;border:1px solid #d8dbe0;padding:32px;min-height:calc(100vh - 150px);}
        h2{color:#1b2a41;margin-bottom:22px;font-size:18px;font-weight:700;font-family:Georgia,'Times New Roman',serif;border-bottom:1px solid #eef0f3;padding-bottom:14px;}
        h3{font-family:Georgia,'Times New Roman',serif;color:#1b2a41;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:7px;color:#374151;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;}
        input,select{width:100%;padding:11px 14px;border:1px solid #d1d5db;border-radius:4px;font-size:14px;transition:border-color 0.2s,box-shadow 0.2s;background:#fafbfc;}
        input:focus,select:focus{outline:none;border-color:#1b2a41;background:white;box-shadow:0 0 0 3px rgba(27,42,65,0.1);}
        button{background:#1b2a41;color:white;border:none;padding:12px 26px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;transition:background 0.2s;margin:4px 4px 4px 0;letter-spacing:.2px;}
        button:hover{background:#10192b;}
        .scan-area{text-align:center;padding:36px;background:#f7f8fa;border-radius:6px;margin-bottom:20px;border:1px solid #d8dbe0;}
        #scan-input{font-size:20px;text-align:center;padding:16px;width:100%;max-width:460px;border-radius:4px;border:1px solid #b9c2cf;}
        .status{font-size:16px;font-weight:600;margin-top:18px;padding:16px;border-radius:4px;border-left:4px solid;}
        .success{background:#e8f5ec;color:#1e6b34;border-color:#2f8a4e;}
        .info{background:#eaf1f8;color:#1b4f72;border-color:#3a75a3;}
        .error{background:#fbeaea;color:#8a1f1f;border-color:#c0392b;}
        table{width:100%;border-collapse:collapse;margin-top:18px;}
        th,td{padding:13px 14px;text-align:left;border:1px solid #e5e7eb;font-size:13px;}
        th{background:#1b2a41;color:#fff;font-weight:600;}
        tr:nth-child(even){background:#f7f8fa;}
        tr:hover{background:#eef1f5;}
        .tab-content{display:none;}
        .tab-content.active{display:block;}
        .barcode-img{max-width:300px;margin:18px auto;display:block;padding:14px;background:white;border:1px solid #d8dbe0;border-radius:4px;}
        .btn-print{background:#1e6b34;}
        .btn-print:hover{background:#175628;}
        .btn-download{background:#8a6d1f;color:white;}
        .btn-download:hover{background:#6e5718;}
        .btn-edit{background:#3a4f75;color:white;padding:7px 16px;font-size:12px;border-radius:4px;}
        .btn-edit:hover{background:#2c3c59;}
        .btn-save{background:#1e6b34;}
        .btn-save:hover{background:#175628;}
        .btn-cancel{background:#5b6472;}
        .btn-cancel:hover{background:#464d59;}
        .edit-form{background:#f7f8fa;padding:24px;border-radius:6px;margin-top:20px;border:1px solid #d8dbe0;}
        .hidden{display:none !important;}
        .dept-tabs{display:flex;gap:8px;margin:18px 0;flex-wrap:wrap;}
        .dept-tab{padding:9px 16px;background:#f1f3f6;color:#374151;border:1px solid #d8dbe0;border-radius:4px;cursor:pointer;font-weight:600;transition:all 0.2s;font-size:13px;}
        .dept-tab:hover{background:#e5e8ec;}
        .dept-tab.active{background:#1b2a41;color:white;border-color:#1b2a41;}
        .search-box{margin-bottom:18px;}
        .search-box input{font-size:14px;padding:11px 14px;}
        .month-filter{display:flex;gap:10px;align-items:center;margin-bottom:18px;flex-wrap:wrap;}
        .month-filter select{max-width:200px;}
        .btn-month-print{background:#5b3a75;color:white;}
        .btn-month-print:hover{background:#452b59;}
        @media(max-width:900px){
            .sidebar{width:74px;}
            .sidebar-header .full-title,.sidebar-header p,.menu-item span.label{display:none;}
            .menu-item{justify-content:center;padding:12px 0;}
            .form-row{grid-template-columns:1fr;}
            .main-content{padding:14px;}
            .content-card{padding:20px;}
        }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="sidebar" id="sidebar">
            <button class="toggle-btn" onclick="toggleSidebar()">◀</button>
            <div class="sidebar-header">
                <div class="brand-mark">SLSU<br>JGE</div>
                <h2 class="full-title">Library System</h2>
                <p>Attendance Administration</p>
            </div>
            <div class="sidebar-menu">
                <div class="menu-item active" onclick="showContent('scan')">
                    <span class="badge">01</span> <span class="label">Scan / Attendance</span>
                </div>
                <div class="menu-item" onclick="showContent('register')">
                    <span class="badge">02</span> <span class="label">Register User</span>
                </div>
                <div class="menu-item" onclick="showContent('students')">
                    <span class="badge">03</span> <span class="label">Students List</span>
                </div>
                <div class="menu-item" onclick="showContent('records')">
                    <span class="badge">04</span> <span class="label">Daily Records</span>
                </div>
                <div class="menu-item" onclick="showContent('history')">
                    <span class="badge">05</span> <span class="label">Monthly History</span>
                </div>
                <div class="menu-item" onclick="showContent('export')">
                    <span class="badge">06</span> <span class="label">Export Reports</span>
                </div>
            </div>
            <div class="sidebar-footer">
                <button class="logout-btn" onclick="logout()">Log Out</button>
            </div>
        </div>
        <div class="main-content">
            <div class="content-header">
                <h1 id="page-title">Scan / Attendance</h1>
            </div>
            <div class="content-card">
                <!-- ============= SCAN / ATTENDANCE ============= -->
                <div id="scan" class="tab-content active">
                    <h2>Scan Barcode — Time In / Time Out</h2>
                    <div class="scan-area">
                        <input type="text" id="scan-input" placeholder="Scan barcode or type ID number..." autofocus>
                        <div id="status-box" class="status info">Waiting for scan...</div>
                    </div>
                </div>
                <!-- ============= REGISTER USER ============= -->
                <div id="register" class="tab-content">
                    <h2>Register New User</h2>
                    <form id="register-form">
                        <div class="form-row">
                            <div class="form-group">
                                <label>ID Type *</label>
                                <select name="id_type" id="id-type-select" required>
                                    <option value="Student">Student</option>
                                    <option value="Employee">Employee</option>
                                    <option value="Visitor">Visitor</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>ID Number *</label>
                                <input type="text" name="id_number" required placeholder="e.g. 2024-0001">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Full Name *</label>
                                <input type="text" name="full_name" required placeholder="Last, First Middle">
                            </div>
                            <div class="form-group">
                                <label>Department</label>
                                <select name="department" id="dept-select">
                                    <option value="">-- Select Department --</option>
                                    <option value="CT">BSIT / Computer Technology</option>
                                    <option value="BSED">BSED</option>
                                    <option value="BEED">BEED</option>
                                    <option value="BSFI">BSFI / BSAF</option>
                                    <option value="BSBA">BSBA</option>
                                    <option value="BPA">BPA</option>
                                    <option value="EMPLOYEE">EMPLOYEE</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-row" id="major-row">
                            <div class="form-group">
                                <label>Major / Specialization</label>
                                <select name="major" id="major-select">
                                    <option value="">-- Select Department First --</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Year Level</label>
                                <select name="year_level" id="year-select">
                                    <option value="1st Year">1st Year</option>
                                    <option value="2nd Year">2nd Year</option>
                                    <option value="3rd Year">3rd Year</option>
                                    <option value="4th Year">4th Year</option>
                                    <option value="N/A">N/A — Not Applicable</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Contact Number</label>
                                <input type="text" name="contact_number" placeholder="09XX-XXX-XXXX">
                            </div>
                            <div class="form-group">
                                <label>Complete Address</label>
                                <input type="text" name="address" placeholder="City, Province">
                            </div>
                        </div>
                        <button type="submit" class="btn-primary">Register & Generate Barcode</button>
                    </form>
                    <div id="barcode-result" style="display:none;margin-top:28px;text-align:center;padding:26px;background:#f7f8fa;border-radius:6px;border:1px solid #d8dbe0;">
                        <h3>Registration Successful</h3>
                        <p style="font-size:16px;margin:14px 0;"><strong id="student-info"></strong></p>
                        <img id="barcode-img" class="barcode-img"><br><br>
                        <button class="btn-print" onclick="window.print()">Print Barcode</button>
                    </div>
                </div>
                <!-- ============= STUDENTS LIST ============= -->
                <div id="students" class="tab-content">
                    <h2>Registered Users — By Department</h2>
                    <div class="search-box">
                        <input type="text" id="search-input" placeholder="Search by Name or ID Number..." oninput="filterStudents()">
                    </div>
                    <div class="dept-tabs">
                        <button class="dept-tab active" id="dept-ALL" onclick="switchDept('ALL')">ALL</button>
                        <button class="dept-tab" id="dept-CT" onclick="switchDept('CT')">CT</button>
                        <button class="dept-tab" id="dept-BSED" onclick="switchDept('BSED')">BSED</button>
                        <button class="dept-tab" id="dept-BEED" onclick="switchDept('BEED')">BEED</button>
                        <button class="dept-tab" id="dept-BSFI" onclick="switchDept('BSFI')">BSFI</button>
                        <button class="dept-tab" id="dept-BSBA" onclick="switchDept('BSBA')">BSBA</button>
                        <button class="dept-tab" id="dept-EMPLOYEE" onclick="switchDept('EMPLOYEE')">EMPLOYEE</button>
                        <button class="dept-tab" id="dept-Visitor" onclick="switchDept('Visitor')">VISITOR</button>
                    </div>
                    <button class="btn-refresh" onclick="loadStudents()">Refresh List</button>
                    <div id="students-table"></div>

                    <div id="edit-form-container" class="edit-form hidden">
                        <h3>Edit User Information</h3>
                        <form id="edit-form">
                            <input type="hidden" id="edit-id" name="id">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>ID Type</label>
                                    <select id="edit-id-type" name="id_type">
                                        <option value="Student">Student</option>
                                        <option value="Employee">Employee</option>
                                        <option value="Visitor">Visitor</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>ID Number</label>
                                    <input type="text" id="edit-idnum" name="id_number" required>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Full Name</label>
                                    <input type="text" id="edit-fullname" name="full_name" required>
                                </div>
                                <div class="form-group">
                                    <label>Department</label>
                                    <select id="edit-dept" name="department">
                                        <option value="">-- Select --</option>
                                        <option value="CT">BSIT / Computer Technology</option>
                                        <option value="BSED">BSED</option>
                                        <option value="BEED">BEED</option>
                                        <option value="BSFI">BSFI / BSAF</option>
                                        <option value="BSBA">BSBA</option>
                                        <option value="BPA">BPA</option>
                                        <option value="EMPLOYEE">EMPLOYEE</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Major / Specialization</label>
                                    <select id="edit-major" name="major"></select>
                                </div>
                                <div class="form-group">
                                    <label>Year Level</label>
                                    <select id="edit-year" name="year_level">
                                        <option value="1st Year">1st Year</option>
                                        <option value="2nd Year">2nd Year</option>
                                        <option value="3rd Year">3rd Year</option>
                                        <option value="4th Year">4th Year</option>
                                        <option value="N/A">N/A</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Contact Number</label>
                                    <input type="text" id="edit-contact" name="contact_number">
                                </div>
                                <div class="form-group">
                                    <label>Complete Address</label>
                                    <input type="text" id="edit-address" name="address">
                                </div>
                            </div>
                            <button type="submit" class="btn-save">Save Changes</button>
                            <button type="button" class="btn-cancel" onclick="hideEditForm()">Cancel</button>
                        </form>
                    </div>
                </div>
                <!-- ============= DAILY RECORDS ============= -->
                <div id="records" class="tab-content">
                    <h2>Today's Attendance Records</h2>
                    <button class="btn-refresh" onclick="loadRecords()">Refresh Records</button>
                    <div id="records-table"></div>
                </div>
                <!-- ============= MONTHLY HISTORY ============= -->
                <div id="history" class="tab-content">
                    <h2>Monthly Attendance History</h2>
                    <div class="month-filter">
                        <label style="margin-bottom:0;">Select Month:</label>
                        <select id="month-select" onchange="loadMonthlyHistory()">
                            <option value="2026-01">January 2026</option>
                            <option value="2026-02">February 2026</option>
                            <option value="2026-03">March 2026</option>
                            <option value="2026-04">April 2026</option>
                            <option value="2026-05">May 2026</option>
                            <option value="2026-06">June 2026</option>
                            <option value="2026-07">July 2026</option>
                            <option value="2026-08">August 2026</option>
                            <option value="2026-09" selected>September 2026</option>
                            <option value="2026-10">October 2026</option>
                            <option value="2026-11">November 2026</option>
                            <option value="2026-12">December 2026</option>
                        </select>
                        <button class="btn-month-print" onclick="printMonthlyReport()">Print Monthly Report</button>
                        <button class="btn-download" onclick="downloadMonthlyReport()">Download Word</button>
                    </div>
                    <button class="btn-refresh" onclick="loadMonthlyHistory()">Load Records</button>
                    <div id="history-table"></div>
                </div>
                <!-- ============= EXPORT REPORTS ============= -->
                <div id="export" class="tab-content">
                    <h2>Export & Print Reports</h2>
                    <p style="font-size:15px;color:#64748b;margin-bottom:22px;">Download today's complete attendance as a Microsoft Word document or print directly.</p>
                    <button class="btn-download" onclick="window.location.href='/download-word'">Download Today's Report</button><br><br>
                    <button class="btn-print" onclick="window.print()">Print Page</button>
                </div>
            </div>
        </div>
    </div>
<script>
const MAJORS = {
    "BSBA": ["Marketing Management", "Financial Management"],
    "BSED": ["English", "Mathematics", "Science"],
    "CT": ["Computer Technology", "Food Technology"],
    "BSFI": ["Food Service Management", "Hospitality Management"],
};
const PAGE_TITLES = {
    scan: "Scan / Attendance",
    register: "Register New User",
    students: "Registered Users",
    records: "Daily Attendance Records",
    history: "Monthly Attendance History",
    export: "Export & Print Reports"
};
let editingStudentId = null;
let currentDept = "ALL";
let allStudents = [];
function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    sidebar.classList.toggle("collapsed");
    const btn = sidebar.querySelector(".toggle-btn");
    btn.textContent = sidebar.classList.contains("collapsed") ? "▶" : "◀";
}
function logout() {
    document.cookie = "logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    document.cookie = "role=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    window.location.href = "/login";
}
function showContent(pageId) {
    document.querySelectorAll(".menu-item").forEach(item => item.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(tab => tab.classList.remove("active"));
    const menuIndex = ["scan", "register", "students", "records", "history", "export"].indexOf(pageId);
    if (menuIndex !== -1) {
        document.querySelectorAll(".menu-item")[menuIndex].classList.add("active");
    }
    const targetTab = document.getElementById(pageId);
    if (targetTab) {
        targetTab.classList.add("active");
    }
    document.getElementById("page-title").textContent = PAGE_TITLES[pageId] || "Library System";
    if (pageId === "scan") {
        setTimeout(() => document.getElementById("scan-input")?.focus(), 100);
    }
    if (pageId === "students") loadStudents();
    if (pageId === "records") loadRecords();
    if (pageId === "history") loadMonthlyHistory();
}
function switchDept(dept) {
    document.querySelectorAll(".dept-tab").forEach(tab => tab.classList.remove("active"));
    document.getElementById("dept-" + dept).classList.add("active");
    currentDept = dept;
    filterStudents();
}
function updateMajorOptions(deptSelectId, majorSelectId, yearSelectId) {
    const dept = document.getElementById(deptSelectId).value;
    const majorSelect = document.getElementById(majorSelectId);
    const yearSelect = yearSelectId ? document.getElementById(yearSelectId) : null;

    majorSelect.innerHTML = '<option value="">-- Select Major --</option>';

    if (dept === "Visitor" || dept === "EMPLOYEE" || !dept) {
        if (yearSelect) { yearSelect.value = "N/A"; yearSelect.disabled = true; }
        return;
    }

    if (yearSelect) yearSelect.disabled = false;

    if (MAJORS[dept]) {
        MAJORS[dept].forEach(major => {
            const option = document.createElement("option");
            option.value = major;
            option.textContent = major;
            majorSelect.appendChild(option);
        });
    }
}
function submitScan() {
    const input = document.getElementById("scan-input");
    const idNumber = input.value.trim();
    if (!idNumber) return;
    fetch("/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_number: idNumber })
    })
    .then(res => res.json())
    .then(data => {
        const statusBox = document.getElementById("status-box");
        statusBox.className = "status " + (data.success ? "success" : "error");
        statusBox.textContent = data.message;
        input.value = "";
    })
    .catch(err => {
        document.getElementById("status-box").className = "status error";
        document.getElementById("status-box").textContent = "Error: " + err;
    });
}
function loadStudents() {
    fetch("/get-students")
        .then(res => res.json())
        .then(data => {
            allStudents = data.students || [];
            filterStudents();
        })
        .catch(err => alert("Load Error: " + err));
}
function filterStudents() {
    const search = document.getElementById("search-input")?.value.toLowerCase() || "";
    let filtered = allStudents;
    if (currentDept !== "ALL") {
        filtered = filtered.filter(s =>
            s.department === currentDept ||
            (currentDept === "Visitor" && s.id_type === "Visitor")
        );
    }
    if (search) {
        filtered = filtered.filter(s =>
            s.full_name.toLowerCase().includes(search) ||
            s.id_number.toLowerCase().includes(search)
        );
    }
    const table = document.getElementById("students-table");
    if (filtered.length > 0) {
        table.innerHTML = `
            <table>
                <tr><th>ID Number</th><th>Full Name</th><th>Type</th><th>Department</th><th>Action</th></tr>
                ${filtered.map(s => `
                    <tr>
                        <td><strong>${s.id_number}</strong></td>
                        <td>${s.full_name}</td>
                        <td>${s.id_type}</td>
                        <td>${s.department || "-"}</td>
                        <td><button class='btn-edit' onclick='editStudent(${s.id})'>Edit</button></td>
                    </tr>
                `).join("")}
            </table>
        `;
    } else {
        table.innerHTML = '<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No records found.</p>';
    }
}
function editStudent(id) {
    const student = allStudents.find(s => s.id === id);
    if (!student) return;

    editingStudentId = id;
    document.getElementById("edit-id").value = student.id;
    document.getElementById("edit-id-type").value = student.id_type;
    document.getElementById("edit-idnum").value = student.id_number;
    document.getElementById("edit-fullname").value = student.full_name;
    document.getElementById("edit-dept").value = student.department || "";
    document.getElementById("edit-major").value = student.major || "";
    document.getElementById("edit-year").value = student.year_level || "";
    document.getElementById("edit-contact").value = student.contact_number || "";
    document.getElementById("edit-address").value = student.address || "";

    document.getElementById("edit-form-container").classList.remove("hidden");
    document.getElementById("edit-form-container").scrollIntoView({ behavior: "smooth" });
}
function hideEditForm() {
    document.getElementById("edit-form-container").classList.add("hidden");
    editingStudentId = null;
    document.getElementById("edit-form").reset();
}
function loadRecords() {
    fetch("/get-records")
        .then(res => res.json())
        .then(data => {
            const records = data.records || [];
            const table = document.getElementById("records-table");

            if (records.length > 0) {
                table.innerHTML = `
                    <table>
                        <tr><th>Date</th><th>Full Name</th><th>ID Number</th><th>Time In</th><th>Time Out</th></tr>
                        ${records.map(r => `
                            <tr>
                                <td><strong>${r.scan_date}</strong></td>
                                <td>${r.full_name}</td>
                                <td>${r.id_number}</td>
                                <td style='color:#1e6b34;font-weight:600;'>${r.time_in || "-"}</td>
                                <td style='color:#8a1f1f;font-weight:600;'>${r.time_out || "-"}</td>
                            </tr>
                        `).join("")}
                    </table>
                `;
            } else {
                table.innerHTML = '<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No attendance records yet.</p>';
            }
        })
        .catch(err => alert("Load Error: " + err));
}
function loadMonthlyHistory() {
    const month = document.getElementById("month-select").value;
    fetch("/get-monthly-history?month=" + month)
        .then(res => res.json())
        .then(data => {
            const records = data.records || [];
            const table = document.getElementById("history-table");

            if (records.length > 0) {
                table.innerHTML = `
                    <h3 style='margin:18px 0;font-size:16px;'>Records for ${month}</h3>
                    <table>
                        <tr><th>Date</th><th>Full Name</th><th>ID Number</th><th>Time In</th><th>Time Out</th></tr>
                        ${records.map(r => `
                            <tr>
                                <td><strong>${r.scan_date}</strong></td>
                                <td>${r.full_name}</td>
                                <td>${r.id_number}</td>
                                <td style='color:#1e6b34;font-weight:600;'>${r.time_in || "-"}</td>
                                <td style='color:#8a1f1f;font-weight:600;'>${r.time_out || "-"}</td>
                            </tr>
                        `).join("")}
                    </table>
                `;
            } else {
                table.innerHTML = `<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No records for ${month}.</p>`;
            }
        })
        .catch(err => alert("Load Error: " + err));
}
function printMonthlyReport() {
    const month = document.getElementById("month-select").value;
    window.open("/print-monthly?month=" + month, "_blank");
}
function downloadMonthlyReport() {
    const month = document.getElementById("month-select").value;
    window.location.href = "/download-monthly-word?month=" + month;
}
document.addEventListener("DOMContentLoaded", function() {
    const scanInput = document.getElementById("scan-input");
    if (scanInput) {
        scanInput.addEventListener("keypress", e => {
            if (e.key === "Enter") submitScan();
        });
    }
    const deptSelect = document.getElementById("dept-select");
    if (deptSelect) {
        deptSelect.addEventListener("change", () => updateMajorOptions("dept-select", "major-select", "year-select"));
    }
    const editDeptSelect = document.getElementById("edit-dept");
    if (editDeptSelect) {
        editDeptSelect.addEventListener("change", () => updateMajorOptions("edit-dept", "edit-major", "edit-year"));
    }
    const registerForm = document.getElementById("register-form");
    if (registerForm) {
        registerForm.addEventListener("submit", e => {
            e.preventDefault();
            const formData = new FormData(registerForm);

            fetch("/register", {
                method: "POST",
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    document.getElementById("barcode-result").style.display = "block";
                    document.getElementById("student-info").textContent = data.info;
                    document.getElementById("barcode-img").src = "data:image/png;base64," + data.barcode;
                    registerForm.reset();
                    document.getElementById("major-select").innerHTML = '<option value="">-- Select Department First --</option>';
                } else {
                    alert("Error: " + data.error);
                }
            })
            .catch(err => alert("Error: " + err));
        });
    }
    const editForm = document.getElementById("edit-form");
    if (editForm) {
        editForm.addEventListener("submit", e => {
            e.preventDefault();
            const formData = new FormData(editForm);

            fetch("/update-student", {
                method: "POST",
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert("Updated successfully.");
                    hideEditForm();
                    loadStudents();
                } else {
                    alert("Error: " + data.error);
                }
            })
            .catch(err => alert("Error: " + err));
        });
    }
});
</script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
