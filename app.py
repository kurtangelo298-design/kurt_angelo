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

ADMIN_USER = "slsu"
ADMIN_PASS = "jge"
USER_USER = "jge"
USER_PASS = "slsu"

def get_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ DB Connect Error: {e}")
        return None

def get_ph_time():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return now.strftime("%I:%M %p")

def get_ph_date():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")

def init_db():
    conn = get_db()
    if not conn:
        print("❌ Cannot connect to database")
        return
    c = conn.cursor()
    
    c.execute("DROP TABLE IF EXISTS attendance;")
    c.execute("DROP TABLE IF EXISTS users;")
    
    c.execute("""CREATE TABLE users (
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
    )""")
    
    c.execute("""CREATE TABLE attendance (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        time_in TEXT,
        time_out TEXT,
        scan_date TEXT NOT NULL
    )""")
    
    conn.commit()
    conn.close()
    print("✅ DATABASE READY!")

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
    <title>Login — Library Attendance</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;position:relative;}
        body::before{content:'';position:absolute;top:0;left:0;width:100%;height:100%;background:radial-gradient(circle at 20% 50%,rgba(255,255,255,0.1) 0%,transparent 50%),radial-gradient(circle at 80% 80%,rgba(255,255,255,0.1) 0%,transparent 50%);z-index:0;}
        .card{background:rgba(255,255,255,0.95);padding:50px 40px;border-radius:28px;box-shadow:0 25px 80px rgba(0,0,0,0.25);width:100%;max-width:440px;position:relative;z-index:1;backdrop-filter:blur(20px);animation:slideUp 0.5s ease;}
        @keyframes slideUp{from{opacity:0;transform:translateY(30px);}to{opacity:1;transform:translateY(0);}}
        h1{text-align:center;color:#1e1b4b;margin-bottom:10px;font-size:30px;font-weight:700;}
        .subtitle{text-align:center;color:#6b7280;margin-bottom:35px;font-size:15px;}
        .form-group{margin-bottom:24px;}
        label{display:block;margin-bottom:10px;color:#374151;font-weight:600;font-size:15px;}
        input{width:100%;padding:16px 18px;border:2px solid #e5e7eb;border-radius:14px;font-size:16px;transition:all 0.3s ease;background:#f9fafb;}
        input:focus{outline:none;border-color:#6366f1;background:#fff;box-shadow:0 0 0 5px rgba(99,102,241,0.15);}
        button{width:100%;padding:16px;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;border:none;border-radius:14px;font-size:18px;font-weight:700;cursor:pointer;transition:all 0.3s ease;box-shadow:0 8px 24px rgba(99,102,241,0.3);}
        button:hover{transform:translateY(-3px);box-shadow:0 12px 32px rgba(99,102,241,0.4);}
        .error{background:#fef2f2;color:#dc2626;padding:14px;border-radius:12px;margin-bottom:25px;text-align:center;border:1px solid #fecaca;}
    </style>
</head>
<body>
    <div class="card">
        <h1>❌ Invalid Credentials</h1>
        <p class="subtitle">Please check your username and password</p>
        <a href="/login" style="display:block;text-align:center;padding:14px;background:#f3f4f6;color:#374151;border-radius:12px;text-decoration:none;font-weight:600;transition:all 0.2s;">← Try Again</a>
    </div>
</body>
</html>"""
    
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Login — Library Attendance System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;position:relative;overflow:hidden;}
        body::before{content:'';position:absolute;top:0;left:0;width:100%;height:100%;background:radial-gradient(circle at 10% 20%,rgba(255,255,255,0.12) 0%,transparent 50%),radial-gradient(circle at 90% 80%,rgba(255,255,255,0.12) 0%,transparent 50%);z-index:0;}
        .card{background:rgba(255,255,255,0.95);padding:50px 40px;border-radius:28px;box-shadow:0 25px 80px rgba(0,0,0,0.25);width:100%;max-width:440px;position:relative;z-index:1;backdrop-filter:blur(20px);animation:slideUp 0.6s ease;}
        @keyframes slideUp{from{opacity:0;transform:translateY(40px);}to{opacity:1;transform:translateY(0);}}
        .icon{text-align:center;font-size:48px;margin-bottom:10px;}
        h1{text-align:center;color:#1e1b4b;margin-bottom:8px;font-size:30px;font-weight:800;}
        .subtitle{text-align:center;color:#6b7280;margin-bottom:40px;font-size:15px;}
        .form-group{margin-bottom:24px;}
        label{display:block;margin-bottom:10px;color:#374151;font-weight:600;font-size:15px;}
        input{width:100%;padding:16px 18px;border:2px solid #e5e7eb;border-radius:14px;font-size:16px;transition:all 0.3s ease;background:#f9fafb;}
        input:focus{outline:none;border-color:#6366f1;background:#fff;box-shadow:0 0 0 5px rgba(99,102,241,0.15);transform:scale(1.02);}
        button{width:100%;padding:16px;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;border:none;border-radius:14px;font-size:18px;font-weight:700;cursor:pointer;transition:all 0.3s ease;box-shadow:0 8px 24px rgba(99,102,241,0.3);}
        button:hover{transform:translateY(-3px);box-shadow:0 14px 36px rgba(99,102,241,0.4);}
        .hint{margin-top:25px;text-align:center;font-size:13px;color:#9ca3af;line-height:1.6;}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">📚</div>
        <h1>Welcome Back</h1>
        <p class="subtitle">SLSU-JGE Library Attendance System</p>
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
        <p class="hint">Admin: slsu / jge<br>User: jge / slsu</p>
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
        return jsonify({"success": False, "message": "❌ Database connection error"}), 500
    
    c = conn.cursor()
    today = get_ph_date()
    now = get_ph_time()
    
    c.execute("SELECT id, full_name, id_number FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({"success": False, "message": f"❌ ID {id_number} not found!"})
    
    user_id, full_name, _ = user
    
    c.execute("SELECT id, time_in, time_out FROM attendance WHERE user_id = %s AND scan_date = %s ORDER BY id DESC LIMIT 1", (user_id, today))
    last_attendance = c.fetchone()
    
    if not last_attendance or last_attendance[2]:
        c.execute("INSERT INTO attendance (user_id, time_in, scan_date) VALUES (%s, %s, %s)", (user_id, now, today))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"✅ TIME IN: {full_name} — {now}"})
    else:
        c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"✅ TIME OUT: {full_name} — {now}"})

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
            return jsonify({"success": False, "error": "⚠️ Fill up all required fields!"}), 400
        
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "❌ Database connection failed"}), 500
        
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
        if c.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "⚠️ ID Number already exists!"}), 400
        
        c.execute("""INSERT INTO users 
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at))
        conn.commit()
        conn.close()
        
        barcode_b64 = generate_barcode_b64(id_number)
        info = f"{full_name} | ID: {id_number} | {id_type}"
        return jsonify({"success": True, "info": info, "barcode": barcode_b64})
    
    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        return jsonify({"success": False, "error": f"❌ Error: {str(e)}"}), 500

@app.route('/get-students')
def get_students():
    if not is_logged_in():
        return jsonify({"students": []})
    conn = get_db()
    if not conn:
        return jsonify({"students": []})
    c = conn.cursor()
    c.execute("SELECT id, id_type, full_name, department, id_number FROM users ORDER BY full_name")
    students = [{"id": r[0], "id_type": r[1], "full_name": r[2], "department": r[3], "id_number": r[4]} for r in c.fetchall()]
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
            return jsonify({"success": False, "error": "⚠️ Missing required fields"}), 400
        
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "❌ Database error"}), 500
        
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
        return jsonify({"success": False, "error": f"❌ Error: {str(e)}"}), 500

@app.route('/get-records')
def get_records():
    if not is_logged_in():
        return jsonify({"records": []})
    conn = get_db()
    if not conn:
        return jsonify({"records": []})
    c = conn.cursor()
    c.execute("""SELECT a.scan_date, u.full_name, u.id_number, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id
        ORDER BY a.scan_date DESC, a.id DESC LIMIT 100""")
    records = [{"scan_date": r[0], "full_name": r[1], "id_number": r[2], "time_in": r[3], "time_out": r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify({"records": records})

@app.route('/get-monthly-history')
def get_monthly_history():
    if not is_logged_in():
        return jsonify({"records": []})
    month = request.args.get('month', '').strip()
    conn = get_db()
    if not conn:
        return jsonify({"records": []})
    c = conn.cursor()
    c.execute("""SELECT a.scan_date, u.full_name, u.id_number, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id
        WHERE a.scan_date LIKE %s
        ORDER BY a.scan_date DESC, a.id DESC""", (f"{month}%",))
    records = [{"scan_date": r[0], "full_name": r[1], "id_number": r[2], "time_in": r[3], "time_out": r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify({"records": records})

@app.route('/download-word')
def download_word():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    conn = get_db()
    if not conn:
        return "❌ Database error"
    today = get_ph_date()
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_number, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.scan_date = %s ORDER BY a.id""", (today,))
    records = c.fetchall()
    conn.close()
    
    doc = Document()
    doc.add_heading(f'📚 Library Attendance Report — {today}', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('=' * 50)
    
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
    resp.headers['Content-Disposition'] = f'attendance_report_{today}.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp

@app.route('/download-monthly-word')
def download_monthly_word():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    month = request.args.get('month', '').strip()
    conn = get_db()
    if not conn:
        return "❌ Database error"
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_number, a.scan_date, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id
        WHERE a.scan_date LIKE %s ORDER BY a.scan_date, a.id""", (f"{month}%",))
    records = c.fetchall()
    conn.close()
    
    doc = Document()
    doc.add_heading(f'📚 Monthly Attendance Report — {month}', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('=' * 60)
    
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
    resp.headers['Content-Disposition'] = f'monthly_attendance_{month}.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp

@app.route('/print-monthly')
def print_monthly():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    month = request.args.get('month', '').strip()
    return f"""
<!DOCTYPE html><html><head><title>Monthly Report — {month}</title>
<style>body{{font-family:'Segoe UI',sans-serif;padding:40px;max-width:1200px;margin:0 auto;}}h1{{text-align:center;color:#1e1b4b;margin-bottom:10px;}}table{{width:100%;border-collapse:collapse;margin-top:30px;}}th,td{{border:1px solid #e5e7eb;padding:14px;text-align:left;}}th{{background:#f9fafb;font-weight:700;color:#1e1b4b;}}tr:nth-child(even){{background:#f9fafb;}}@media print{{button{{display:none;}}body{{padding:0;}}}}</style>
</head><body>
<h1>📚 Monthly Attendance Report — {month}</h1>
<p style="text-align:center;color:#6b7280;margin-bottom:20px;">Generated: {get_ph_date()} {get_ph_time()}</p>
<button onclick="window.print()" style="padding:12px 30px;font-size:16px;cursor:pointer;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;border:none;border-radius:12px;font-weight:600;">🖨️ Print Report</button>
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
    <title>📇 User Registration — SLSU-JGE</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;padding:30px;position:relative;}
        body::before{content:'';position:absolute;top:0;left:0;width:100%;height:100%;background:radial-gradient(circle at 10% 20%,rgba(255,255,255,0.1) 0%,transparent 50%),radial-gradient(circle at 90% 80%,rgba(255,255,255,0.1) 0%,transparent 50%);z-index:0;}
        .container{width:100%;max-width:520px;position:relative;z-index:1;}
        .card{background:rgba(255,255,255,0.95);padding:45px 40px;border-radius:28px;box-shadow:0 25px 80px rgba(0,0,0,0.25);backdrop-filter:blur(20px);animation:slideUp 0.6s ease;}
        @keyframes slideUp{from{opacity:0;transform:translateY(40px);}to{opacity:1;transform:translateY(0);}}
        .icon{text-align:center;font-size:52px;margin-bottom:10px;}
        h1{text-align:center;color:#1e1b4b;margin-bottom:8px;font-size:28px;font-weight:800;}
        .subtitle{text-align:center;color:#6b7280;margin-bottom:35px;font-size:15px;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:9px;color:#374151;font-weight:600;font-size:14px;}
        input,select{width:100%;padding:14px 16px;border:2px solid #e5e7eb;border-radius:12px;font-size:15px;transition:all 0.3s ease;background:#f9fafb;}
        input:focus,select:focus{outline:none;border-color:#6366f1;background:#fff;box-shadow:0 0 0 4px rgba(99,102,241,0.15);transform:scale(1.01);}
        button{width:100%;padding:15px;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;border:none;border-radius:12px;font-size:17px;font-weight:700;cursor:pointer;transition:all 0.3s ease;box-shadow:0 8px 24px rgba(99,102,241,0.3);margin-top:8px;}
        button:hover{transform:translateY(-2px);box-shadow:0 12px 32px rgba(99,102,241,0.4);}
        #barcode-result{display:none;margin-top:30px;text-align:center;padding:30px;background:linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 100%);border-radius:20px;border:2px solid #bae6fd;animation:fadeIn 0.4s ease;}
        @keyframes fadeIn{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:translateY(0);}}
        #barcode-result h3{color:#0369a1;margin-bottom:15px;}
        #student-info{font-size:17px;color:#1e293b;}
        .barcode-img{max-width:280px;margin:20px auto;display:block;padding:15px;background:white;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);}
        .btn-print{background:linear-gradient(135deg,#10b981 0%,#059669 100%);width:auto;padding:12px 28px;margin-top:20px;}
        .btn-print:hover{box-shadow:0 8px 24px rgba(16,185,129,0.3);}
        .logout-link{display:block;text-align:center;margin-top:25px;color:#6b7280;text-decoration:none;font-size:14px;transition:color 0.2s;}
        .logout-link:hover{color:#6366f1;}
        @media(max-width:600px){.form-row{grid-template-columns:1fr;}.card{padding:30px 24px;}}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="icon">📇</div>
            <h1>User Registration</h1>
            <p class="subtitle">Fill in the form to generate your barcode</p>
            <form id="register-form">
                <div class="form-row">
                    <div class="form-group">
                        <label>ID Type *</label>
                        <select name="id_type" id="id-type-select" required>
                            <option value="Student">🎓 Student</option>
                            <option value="Employee">👨‍🏫 Employee</option>
                            <option value="Visitor">👤 Visitor</option>
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
                <button type="submit">✅ Register & Generate Barcode</button>
            </form>
            <div id="barcode-result">
                <h3>✅ Registration Successful!</h3>
                <p id="student-info"></p>
                <img id="barcode-img" class="barcode-img"><br>
                <button class="btn-print" onclick="window.print()">🖨️ Print Barcode</button>
            </div>
            <a href="/login" class="logout-link">← Back to Login</a>
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
                alert("❌ "+data.error);
            }
        })
        .catch(err=>alert("❌ Error: "+err));
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
    <title>📚 Library Attendance — SLSU-JGE Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#1e1b4b 0%,#312e81 100%);min-height:100vh;position:relative;overflow:hidden;}
        body::before{content:'';position:fixed;top:0;left:0;width:100%;height:100%;background:radial-gradient(circle at 15% 30%,rgba(129,140,248,0.08) 0%,transparent 50%),radial-gradient(circle at 85% 70%,rgba(167,139,250,0.08) 0%,transparent 50%);z-index:0;pointer-events:none;}
        .app-container{display:flex;height:100vh;position:relative;z-index:1;}
        .sidebar{width:280px;background:linear-gradient(180deg,rgba(30,27,75,0.95) 0%,rgba(49,46,129,0.95) 100%);backdrop-filter:blur(24px);display:flex;flex-direction:column;padding:25px 0;box-shadow:4px 0 30px rgba(0,0,0,0.3);border-right:1px solid rgba(129,140,248,0.15);position:relative;transition:all 0.4s cubic-bezier(0.4,0,0.2,1);}
        .sidebar.collapsed{width:72px;padding:25px 0;}
        .toggle-btn{position:absolute;right:-16px;top:30px;width:34px;height:34px;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);border:none;border-radius:50%;color:white;font-size:16px;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 15px rgba(99,102,241,0.4);z-index:10;transition:all 0.3s ease;}
        .toggle-btn:hover{transform:scale(1.15);box-shadow:0 6px 20px rgba(99,102,241,0.5);}
        .sidebar.collapsed .toggle-btn{transform:rotate(180deg);}
        .sidebar-header{padding:0 20px 30px 20px;border-bottom:1px solid rgba(129,140,248,0.15);margin-bottom:20px;transition:opacity 0.3s;}
        .sidebar.collapsed .sidebar-header h2 span,.sidebar.collapsed .sidebar-header p{opacity:0;visibility:hidden;position:absolute;}
        .sidebar-header h2{color:white;font-size:20px;display:flex;align-items:center;gap:10px;}
        .sidebar-header p{color:#a5b4fc;font-size:13px;margin-top:5px;}
        .sidebar-menu{display:flex;flex-direction:column;gap:6px;padding:0 12px;flex:1;}
        .menu-item{display:flex;align-items:center;gap:12px;padding:14px 18px;color:#c7d2fe;border-radius:12px;cursor:pointer;transition:all 0.3s cubic-bezier(0.4,0,0.2,1);font-size:15px;font-weight:500;border:2px solid transparent;white-space:nowrap;position:relative;}
        .sidebar.collapsed .menu-item{justify-content:center;padding:14px 0;}
        .sidebar.collapsed .menu-item span:nth-child(2){display:none;}
        .menu-item:hover{background:rgba(99,102,241,0.15);color:#e0e7ff;transform:translateX(4px);}
        .sidebar.collapsed .menu-item:hover{transform:scale(1.05);}
        .menu-item.active{background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;box-shadow:0 4px 20px rgba(99,102,241,0.35);border-color:transparent;}
        .menu-item i{font-size:20px;width:24px;text-align:center;}
        .sidebar-footer{padding:20px;border-top:1px solid rgba(129,140,248,0.15);margin-top:auto;}
        .sidebar.collapsed .sidebar-footer{padding:20px 8px;}
        .logout-btn{width:100%;display:flex;align-items:center;justify-content:center;gap:8px;padding:14px;background:linear-gradient(135deg,#dc2626 0%,#b91c1c 100%);color:white;border:none;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;transition:all 0.3s;}
        .logout-btn:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(220,38,38,0.35);}
        .main-content{flex:1;padding:30px;overflow-y:auto;position:relative;transition:padding 0.3s;}
        .content-header{margin-bottom:25px;display:flex;justify-content:space-between;align-items:center;}
        .content-header h1{color:white;font-size:28px;font-weight:700;}
        .content-card{background:rgba(255,255,255,0.95);border-radius:24px;padding:35px;box-shadow:0 10px 50px rgba(0,0,0,0.3);min-height:calc(100vh - 120px);animation:fadeIn 0.5s ease;position:relative;backdrop-filter:blur(20px);}
        @keyframes fadeIn{from{opacity:0;transform:translateY(20px);}to{opacity:1;transform:translateY(0);}}
        h2{color:#1e1b4b;margin-bottom:25px;font-size:24px;font-weight:700;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:8px;color:#374151;font-weight:600;font-size:14px;}
        input,select{width:100%;padding:13px 16px;border:2px solid #e5e7eb;border-radius:12px;font-size:15px;transition:all 0.3s ease;background:#f9fafb;}
        input:focus,select:focus{outline:none;border-color:#6366f1;background:white;box-shadow:0 0 0 4px rgba(99,102,241,0.15);transform:translateY(-1px);}
        button{background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;border:none;padding:13px 28px;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;transition:all 0.3s ease;margin:5px;}
        button:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(99,102,241,0.35);}
        .scan-area{text-align:center;padding:40px;background:linear-gradient(135deg,#eef2ff 0%,#e0e7ff 100%);border-radius:20px;margin-bottom:20px;border:2px solid #c7d2fe;}
        #scan-input{font-size:24px;text-align:center;padding:18px;width:100%;max-width:480px;border-radius:12px;border:2px solid #a5b4fc;}
        .status{font-size:20px;font-weight:bold;margin-top:20px;padding:18px;border-radius:12px;animation:popIn 0.3s ease;}
        @keyframes popIn{from{transform:scale(0.9);opacity:0;}to{transform:scale(1);opacity:1;}}
        .success{background:#dcfce7;color:#166534;border:2px solid #86efac;}
        .info{background:#e0f2fe;color:#075985;border:2px solid #7dd3fc;}
        .error{background:#fee2e2;color:#991b1b;border:2px solid #fca5a5;}
        table{width:100%;border-collapse:collapse;margin-top:20px;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);}
        th,td{padding:16px;text-align:left;border-bottom:1px solid #f1f5f9;font-size:14px;}
        th{background:linear-gradient(135deg,#f8fafc 0%,#f1f5f9 100%);font-weight:700;color:#1e1b4b;}
        tr:hover{background:#f8fafc;}
        .tab-content{display:none;}
        .tab-content.active{display:block;animation:fadeIn 0.3s ease;}
        .barcode-img{max-width:320px;margin:20px auto;display:block;padding:15px;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.08);}
        .btn-print{background:linear-gradient(135deg,#10b981 0%,#059669 100%);}
        .btn-download{background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);color:white;}
        .btn-edit{background:linear-gradient(135deg,#8b5cf6 0%,#7c3aed 100%);color:white;padding:8px 16px;font-size:13px;border-radius:10px;}
        .btn-save{background:linear-gradient(135deg,#10b981 0%,#059669 100%);}
        .btn-cancel{background:linear-gradient(135deg,#64748b 0%,#475569 100%);}
        .edit-form{background:linear-gradient(135deg,#f8fafc 0%,#f1f5f9 100%);padding:25px;border-radius:20px;margin-top:20px;border:2px solid #e2e8f0;}
        .hidden{display:none !important;}
        .dept-tabs{display:flex;gap:8px;margin:20px 0;flex-wrap:wrap;}
        .dept-tab{padding:10px 16px;background:#f1f5f9;color:#475569;border:none;border-radius:10px;cursor:pointer;font-weight:600;transition:all 0.2s;font-size:14px;}
        .dept-tab:hover{background:#e2e8f0;transform:translateY(-1px);}
        .dept-tab.active{background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;box-shadow:0 4px 12px rgba(99,102,241,0.3);}
        .search-box{margin-bottom:20px;}
        .search-box input{font-size:15px;padding:12px 16px;}
        .month-filter{display:flex;gap:12px;align-items:center;margin-bottom:20px;flex-wrap:wrap;}
        .month-filter select{max-width:200px;}
        .btn-month-print{background:linear-gradient(135deg,#ec4899 0%,#db2777 100%);color:white;}
        @media(max-width:900px){
            .sidebar{width:72px;padding:25px 0;}
            .sidebar-header h2 span,.sidebar-header p,.menu-item span:nth-child(2){display:none;}
            .menu-item{justify-content:center;padding:14px 0;}
            .form-row{grid-template-columns:1fr;}
            .main-content{padding:15px;}
            .content-card{padding:20px;}
        }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="sidebar" id="sidebar">
            <button class="toggle-btn" onclick="toggleSidebar()">◀</button>
            <div class="sidebar-header">
                <h2>📚 <span>Library System</span></h2>
                <p>SLSU-JGE Attendance — Admin</p>
            </div>
            <div class="sidebar-menu">
                <div class="menu-item active" onclick="showContent('scan')">
                    <span>📱</span> <span>Scan / Attendance</span>
                </div>
                <div class="menu-item" onclick="showContent('register')">
                    <span>📇</span> <span>Register User</span>
                </div>
                <div class="menu-item" onclick="showContent('students')">
                    <span>👥</span> <span>Students List</span>
                </div>
                <div class="menu-item" onclick="showContent('records')">
                    <span>📋</span> <span>Daily Records</span>
                </div>
                <div class="menu-item" onclick="showContent('history')">
                    <span>📅</span> <span>Monthly History</span>
                </div>
                <div class="menu-item" onclick="showContent('export')">
                    <span>📄</span> <span>Export Reports</span>
                </div>
            </div>
            <div class="sidebar-footer">
                <button class="logout-btn" onclick="logout()">🚪 Logout</button>
            </div>
        </div>
        <div class="main-content">
            <div class="content-header">
                <h1 id="page-title">📱 Scan / Attendance</h1>
            </div>
            <div class="content-card">
                <!-- ============= SCAN / ATTENDANCE ============= -->
                <div id="scan" class="tab-content active">
                    <h2>📱 Scan Barcode — Time In / Time Out</h2>
                    <div class="scan-area">
                        <input type="text" id="scan-input" placeholder="👉 Scan barcode or type ID number..." autofocus>
                        <div id="status-box" class="status info">⏳ Waiting for scan...</div>
                    </div>
                </div>
                <!-- ============= REGISTER USER ============= -->
                <div id="register" class="tab-content">
                    <h2>📇 Register New User</h2>
                    <form id="register-form">
                        <div class="form-row">
                            <div class="form-group">
                                <label>ID Type *</label>
                                <select name="id_type" id="id-type-select" required>
                                    <option value="Student">🎓 Student</option>
                                    <option value="Employee">👨‍🏫 Employee</option>
                                    <option value="Visitor">👤 Visitor</option>
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
                        <button type="submit" class="btn-primary">✅ Register & Generate Barcode</button>
                    </form>
                    <div id="barcode-result" style="display:none;margin-top:30px;text-align:center;padding:30px;background:linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 100%);border-radius:20px;border:2px solid #bae6fd;">
                        <h3>✅ Registration Successful!</h3>
                        <p style="font-size:18px;margin:15px 0;"><strong id="student-info"></strong></p>
                        <img id="barcode-img" class="barcode-img"><br><br>
                        <button class="btn-print" onclick="window.print()">🖨️ Print Barcode</button>
                    </div>
                </div>
                <!-- ============= STUDENTS LIST ============= -->
                <div id="students" class="tab-content">
                    <h2>👥 Registered Users — By Department</h2>
                    <div class="search-box">
                        <input type="text" id="search-input" placeholder="🔍 Search by Name or ID Number..." oninput="filterStudents()">
                    </div>
                    <div class="dept-tabs">
                        <button class="dept-tab active" id="dept-ALL" onclick="switchDept('ALL')">📋 ALL</button>
                        <button class="dept-tab" id="dept-CT" onclick="switchDept('CT')">CT</button>
                        <button class="dept-tab" id="dept-BSED" onclick="switchDept('BSED')">BSED</button>
                        <button class="dept-tab" id="dept-BEED" onclick="switchDept('BEED')">BEED</button>
                        <button class="dept-tab" id="dept-BSFI" onclick="switchDept('BSFI')">BSFI</button>
                        <button class="dept-tab" id="dept-BSBA" onclick="switchDept('BSBA')">BSBA</button>
                        <button class="dept-tab" id="dept-EMPLOYEE" onclick="switchDept('EMPLOYEE')">EMPLOYEE</button>
                        <button class="dept-tab" id="dept-Visitor" onclick="switchDept('Visitor')">👤 VISITOR</button>
                    </div>
                    <button class="btn-refresh" onclick="loadStudents()">🔄 Refresh List</button>
                    <div id="students-table"></div>

                    <div id="edit-form-container" class="edit-form hidden">
                        <h3>✏️ Edit User Information</h3>
                        <form id="edit-form">
                            <input type="hidden" id="edit-id" name="id">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>ID Type</label>
                                    <select id="edit-id-type" name="id_type">
                                        <option value="Student">🎓 Student</option>
                                        <option value="Employee">👨‍🏫 Employee</option>
                                        <option value="Visitor">👤 Visitor</option>
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
                            <button type="submit" class="btn-save">💾 Save Changes</button>
                            <button type="button" class="btn-cancel" onclick="hideEditForm()">❌ Cancel</button>
                        </form>
                    </div>
                </div>
                <!-- ============= DAILY RECORDS ============= -->
                <div id="records" class="tab-content">
                    <h2>📋 Today's Attendance Records</h2>
                    <button class="btn-refresh" onclick="loadRecords()">🔄 Refresh Records</button>
                    <div id="records-table"></div>
                </div>
                <!-- ============= MONTHLY HISTORY ============= -->
                <div id="history" class="tab-content">
                    <h2>📅 Monthly Attendance History</h2>
                    <div class="month-filter">
                        <label>Select Month:</label>
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
                        <button class="btn-month-print" onclick="printMonthlyReport()">🖨️ Print Monthly Report</button>
                        <button class="btn-download" onclick="downloadMonthlyReport()">📄 Download Word</button>
                    </div>
                    <button class="btn-refresh" onclick="loadMonthlyHistory()">🔄 Load Records</button>
                    <div id="history-table"></div>
                </div>
                <!-- ============= EXPORT REPORTS ============= -->
                <div id="export" class="tab-content">
                    <h2>📄 Export & Print Reports</h2>
                    <p style="font-size:16px;color:#64748b;margin-bottom:25px;">Download today's complete attendance as Microsoft Word Document or print directly.</p>
                    <button class="btn-download" onclick="window.location.href='/download-word'">📄 Download Today's Report</button><br><br>
                    <button class="btn-print" onclick="window.print()">🖨️ Print Page</button>
                </div>
            </div>
        </div>
    </div>
<script>
// ============= FIXED: ALL FUNCTIONS — BUTTONS NOW WORKING =============
const MAJORS = {
    "BSBA": ["Marketing Management", "Financial Management"],
    "BSED": ["English", "Mathematics", "Science"],
    "CT": ["Computer Technology", "Food Technology"],
    "BSFI": ["Food Service Management", "Hospitality Management"],
};
const PAGE_TITLES = {
    scan: "📱 Scan / Attendance",
    register: "📇 Register New User",
    students: "👥 Registered Users",
    records: "📋 Daily Attendance Records",
    history: "📅 Monthly Attendance History",
    export: "📄 Export & Print Reports"
};
let editingStudentId = null;
let currentDept = "ALL";
let allStudents = [];
// --- SIDEBAR TOGGLE ---
function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    sidebar.classList.toggle("collapsed");
    const btn = sidebar.querySelector(".toggle-btn");
    btn.textContent = sidebar.classList.contains("collapsed") ? "▶" : "◀";
}
// --- LOGOUT ---
function logout() {
    document.cookie = "logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    document.cookie = "role=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    window.location.href = "/login";
}
// ============= FIXED: MAIN NAVIGATION — BUTTONS NOW RESPOND =============
function showContent(pageId) {
    console.log("Switching to:", pageId); // ✅ Check console kung gumana
    // Remove active from all menu items
    document.querySelectorAll(".menu-item").forEach(item => item.classList.remove("active"));
    // Remove active from all tabs
    document.querySelectorAll(".tab-content").forEach(tab => tab.classList.remove("active"));
    // Activate selected menu
    const menuIndex = ["scan", "register", "students", "records", "history", "export"].indexOf(pageId);
    if (menuIndex !== -1) {
        document.querySelectorAll(".menu-item")[menuIndex].classList.add("active");
    }
    // Show selected content
    const targetTab = document.getElementById(pageId);
    if (targetTab) {
        targetTab.classList.add("active");
    }
    // Update page title
    document.getElementById("page-title").textContent = PAGE_TITLES[pageId] || "Library System";
    // Load data for pages
    if (pageId === "scan") {
        setTimeout(() => document.getElementById("scan-input")?.focus(), 100);
    }
    if (pageId === "students") loadStudents();
    if (pageId === "records") loadRecords();
    if (pageId === "history") loadMonthlyHistory();
}
// --- DEPARTMENT TABS ---
function switchDept(dept) {
    document.querySelectorAll(".dept-tab").forEach(tab => tab.classList.remove("active"));
    document.getElementById("dept-" + dept).classList.add("active");
    currentDept = dept;
    filterStudents();
}
// --- MAJOR OPTIONS ---
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
// --- SCAN SUBMIT ---
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
        document.getElementById("status-box").textContent = "❌ Error: " + err;
    });
}
// --- LOAD STUDENTS ---
function loadStudents() {
    fetch("/get-students")
        .then(res => res.json())
        .then(data => {
            allStudents = data.students || [];
            filterStudents();
        })
        .catch(err => alert("❌ Load Error: " + err));
}
// --- FILTER STUDENTS ---
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
                        <td><button class='btn-edit' onclick='editStudent(${s.id})'>✏️ Edit</button></td>
                    </tr>
                `).join("")}
            </table>
        `;
    } else {
        table.innerHTML = '<p style="text-align:center;color:#64748b;padding:30px;font-size:16px;">📭 No records found.</p>';
    }
}
// --- EDIT STUDENT ---
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
// --- LOAD DAILY RECORDS ---
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
                                <td style='color:#16a34a;font-weight:600;'>${r.time_in || "-"}</td>
                                <td style='color:#dc2626;font-weight:600;'>${r.time_out || "-"}</td>
                            </tr>
                        `).join("")}
                    </table>
                `;
            } else {
                table.innerHTML = '<p style="text-align:center;color:#64748b;padding:30px;font-size:16px;">📭 No attendance records yet.</p>';
            }
        })
        .catch(err => alert("❌ Load Error: " + err));
}
// --- LOAD MONTHLY HISTORY ---
function loadMonthlyHistory() {
    const month = document.getElementById("month-select").value;
    fetch("/get-monthly-history?month=" + month)
        .then(res => res.json())
        .then(data => {
            const records = data.records || [];
            const table = document.getElementById("history-table");

            if (records.length > 0) {
                table.innerHTML = `
                    <h3 style='margin:20px 0;color:#1e293b;'>📅 Records for ${month}</h3>
                    <table>
                        <tr><th>Date</th><th>Full Name</th><th>ID Number</th><th>Time In</th><th>Time Out</th></tr>
                        ${records.map(r => `
                            <tr>
                                <td><strong>${r.scan_date}</strong></td>
                                <td>${r.full_name}</td>
                                <td>${r.id_number}</td>
                                <td style='color:#16a34a;font-weight:600;'>${r.time_in || "-"}</td>
                                <td style='color:#dc2626;font-weight:600;'>${r.time_out || "-"}</td>
                            </tr>
                        `).join("")}
                    </table>
                `;
            } else {
                table.innerHTML = <p style="text-align:center;color:#64748b;padding:30px;font-size:16px;">📭 No records for ${month}.</p>;
            }
        })
        .catch(err => alert("❌ Load Error: " + err));
}
function printMonthlyReport() {
    const month = document.getElementById("month-select").value;
    window.open("/print-monthly?month=" + month, "_blank");
}
function downloadMonthlyReport() {
    const month = document.getElementById("month-select").value;
    window.location.href = "/download-monthly-word?month=" + month;
}
// ============= FIXED: FORM INITIALIZATION =============
document.addEventListener("DOMContentLoaded", function() {
    console.log("✅ Dashboard Loaded — Buttons Ready!");
    // Scan input — Enter key
    const scanInput = document.getElementById("scan-input");
    if (scanInput) {
        scanInput.addEventListener("keypress", e => {
            if (e.key === "Enter") submitScan();
        });
    }
    // Department → Major linkage
    const deptSelect = document.getElementById("dept-select");
    if (deptSelect) {
        deptSelect.addEventListener("change", () => updateMajorOptions("dept-select", "major-select", "year-select"));
    }
    const editDeptSelect = document.getElementById("edit-dept");
    if (editDeptSelect) {
        editDeptSelect.addEventListener("change", () => updateMajorOptions("edit-dept", "edit-major", "edit-year"));
    }
    // Register Form Submit
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
                    alert("❌ Error: " + data.error);
                }
            })
            .catch(err => alert("❌ Error: " + err));
        });
    }
    // Edit Form Submit
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
                    alert("✅ Updated successfully!");
                    hideEditForm();
                    loadStudents();
                } else {
                    alert("❌ Error: " + data.error);
                }
            })
            .catch(err => alert("❌ Error: " + err));
        });
    }
});
</script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
