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

    with conn.cursor() as c:
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
    writer.set_options({"module_width": 0.3, "module_height": 10, "font_size": 8, "text_distance": 2})
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

        return render_template_string(INVALID_CREDENTIALS_HTML)

    return render_template_string(LOGIN_HTML)

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

    with conn.cursor() as c:
        today = get_ph_date()
        now = get_ph_time()

        c.execute("SELECT id, full_name, id_number FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
        user = c.fetchone()

        if not user:
            return jsonify({"success": False, "message": f"ID {id_number} was not found in the records."})

        user_id, full_name, _ = user

        c.execute("SELECT id, time_in, time_out FROM attendance WHERE user_id = %s AND scan_date = %s ORDER BY id DESC LIMIT 1", (user_id, today))
        last_attendance = c.fetchone()

        if not last_attendance or last_attendance[2]:
            c.execute("INSERT INTO attendance (user_id, time_in, scan_date) VALUES (%s, %s, %s)", (user_id, now, today))
            conn.commit()
            return jsonify({"success": True, "message": f"TIME IN recorded — {full_name} — {now}"})
        else:
            c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
            conn.commit()
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
        registered_at = f"{get_ph_date()} {get_ph_time()}"

        if not id_type or not full_name or not id_number:
            return jsonify({"success": False, "error": "Please complete all required fields."}), 400

        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database connection failed."}), 500

        with conn.cursor() as c:
            c.execute("SELECT id FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
            if c.fetchone():
                return jsonify({"success": False, "error": "This ID number is already registered."}), 400

            c.execute("""
                INSERT INTO users (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at))
            conn.commit()

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

    with conn.cursor() as c:
        c.execute("""
            SELECT id, id_type, full_name, department, major, contact_number, address, year_level, id_number
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

        with conn.cursor() as c:
            c.execute("""UPDATE users SET 
                id_type = %s, id_number = %s, full_name = %s, department = %s,
                major = %s, contact_number = %s, address = %s, year_level = %s
                WHERE id = %s""",
                (id_type, id_number, full_name, department, major, contact_number, address, year_level, student_id))
            conn.commit()
        
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

    with conn.cursor() as c:
        c.execute("""
            SELECT u.full_name, u.department, a.time_in, a.time_out
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

    with conn.cursor() as c:
        c.execute("""
            SELECT a.scan_date, u.full_name, u.department, a.time_in, a.time_out
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

    with conn.cursor() as c:
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

    with conn.cursor() as c:
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
<!DOCTYPE html>
<html>
<head>
    <title>Monthly Report — {month}</title>
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
</head>
<body>
    <div class="report-header">
        <h1>Monthly Attendance Report — {month}</h1>
        <p class="meta">SLSU–JGE Library Attendance System &nbsp;•&nbsp; Generated: {get_ph_date()} {get_ph_time()}</p>
    </div>
    <button onclick="window.print()">Print Report</button>
    <script>
        fetch('/get-monthly-history?month={month}').then(r=>r.json()).then(d=>{
            let html='<table><tr><th>Date</th><th>Full Name</th><th>ID Number</th><th>Time In</th><th>Time Out</th></tr>';
            d.records.forEach(r=>html+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+r.id_number+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>');
            html+='</table>';document.body.innerHTML+=html;
        });
    </script>
</body>
</html>"""

# HTML Templates (Partial)
INVALID_CREDENTIALS_HTML = """
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
</html>
"""

LOGIN_HTML = """
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
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
