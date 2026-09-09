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
    
    c.execute("""CREATE TABLE IF NOT EXISTS users (
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
    
    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
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

@app.route('/privacy-policy')
def privacy_policy():
    return render_template_string(PRIVACY_POLICY)

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
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;}
        .card{background:rgba(255,255,255,0.95);padding:50px 40px;border-radius:28px;box-shadow:0 25px 80px rgba(0,0,0,0.25);width:100%;max-width:440px;}
        h1{text-align:center;color:#1e1b4b;margin-bottom:10px;}
        .error{background:#fef2f2;color:#dc2626;padding:14px;border-radius:12px;margin-bottom:25px;text-align:center;}
        a{display:block;text-align:center;margin-top:20px;color:#6366f1;text-decoration:none;font-weight:600;}
    </style>
</head>
<body>
    <div class="card">
        <h1>❌ Invalid Credentials</h1>
        <p style="text-align:center;color:#6b7280;margin-bottom:25px;">Check your username and password</p>
        <a href="/login">← Try Again</a>
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
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;}
        .card{background:rgba(255,255,255,0.95);padding:50px 40px;border-radius:28px;box-shadow:0 25px 80px rgba(0,0,0,0.25);width:100%;max-width:440px;}
        h1{text-align:center;color:#1e1b4b;margin-bottom:8px;}
        .subtitle{text-align:center;color:#6b7280;margin-bottom:40px;}
        .form-group{margin-bottom:24px;}
        label{display:block;margin-bottom:10px;color:#374151;font-weight:600;}
        input{width:100%;padding:16px;border:2px solid #e5e7eb;border-radius:14px;font-size:16px;}
        input:focus{outline:none;border-color:#6366f1;}
        button{width:100%;padding:16px;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;border:none;border-radius:14px;font-size:18px;font-weight:700;cursor:pointer;}
        .hint{margin-top:25px;text-align:center;font-size:13px;color:#9ca3af;}
        .privacy{text-align:center;margin-top:20px;font-size:13px;}
        .privacy a{color:#6366f1;text-decoration:none;}
    </style>
</head>
<body>
    <div class="card">
        <h1>📚 Welcome Back</h1>
        <p class="subtitle">SLSU-JGE Library Attendance System</p>
        <form method="POST">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Sign In</button>
        </form>
        <p class="hint">Admin: slsu / jge<br>User: jge / slsu</p>
        <p class="privacy"><a href="/privacy-policy" target="_blank">📄 Privacy Policy</a></p>
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
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"success": False, "message": "Unauthorized — Admin only"}), 403
    
    data = request.get_json()
    id_number = data.get('id_number', '').strip()
    
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "❌ Database connection error"}), 500
    
    c = conn.cursor()
    today = get_ph_date()
    now = get_ph_time()
    
    c.execute("SELECT id, full_name, department, id_number FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({"success": False, "message": f"❌ ID {id_number} not found!"})
    
    user_id, full_name, department, _ = user
    
    c.execute("SELECT id, time_in, time_out FROM attendance WHERE user_id = %s AND scan_date = %s ORDER BY id DESC LIMIT 1", (user_id, today))
    last_attendance = c.fetchone()
    
    if not last_attendance or last_attendance[2]:
        c.execute("INSERT INTO attendance (user_id, time_in, scan_date) VALUES (%s, %s, %s)", (user_id, now, today))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"✅ TIME IN: {full_name} | {department or 'N/A'} — {now}"})
    else:
        c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"✅ TIME OUT: {full_name} | {department or 'N/A'} — {now}"})

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
        info = f"{full_name} | ID: {id_number} | {department or 'N/A'} | {id_type}"
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
    c.execute("""SELECT a.scan_date, u.full_name, u.department, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id
        ORDER BY a.scan_date DESC, a.id DESC LIMIT 100""")
    records = [{"scan_date": r[0], "full_name": r[1], "department": r[2], "time_in": r[3], "time_out": r[4]} for r in c.fetchall()]
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
    c.execute("""SELECT a.scan_date, u.full_name, u.department, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id
        WHERE a.scan_date LIKE %s
        ORDER BY a.scan_date DESC, a.id DESC""", (f"{month}%",))
    records = [{"scan_date": r[0], "full_name": r[1], "department": r[2], "time_in": r[3], "time_out": r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify({"records": records})

@app.route('/download-word')
def download_word():
    if not is_logged_in() or get_role() != 'admin':
        return "<script>window.location='/login';</script>"
    conn = get_db()
    if not conn:
        return "❌ Database error"
    today = get_ph_date()
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.department, a.time_in, a.time_out
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
    hdr[1].text = 'Department'
    hdr[2].text = 'Time In'
    hdr[3].text = 'Time Out'
    
    for rec in records:
        row = table.add_row().cells
        row[0].text = rec[0]
        row[1].text = rec[1] or '-'
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
    if not is_logged_in() or get_role() != 'admin':
        return "<script>window.location='/login';</script>"
    month = request.args.get('month', '').strip()
    conn = get_db()
    if not conn:
        return "❌ Database error"
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.department, a.scan_date, a.time_in, a.time_out
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
    hdr[2].text = 'Department'
    hdr[3].text = 'Time In'
    hdr[4].text = 'Time Out'
    
    for rec in records:
        row = table.add_row().cells
        row[0].text = rec[2]
        row[1].text = rec[0]
        row[2].text = rec[1] or '-'
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
    if not is_logged_in() or get_role() != 'admin':
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
let html='<table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>';
d.records.forEach(r=>html+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+(r.department||'-')+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>');
html+='</table>';document.body.innerHTML+=html;
}})</script>
</body></html>"""

PRIVACY_POLICY = """
<!DOCTYPE html>
<html>
<head>
    <title>Privacy Policy — SLSU-JGE Library Attendance System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:40px 20px;}
        .container{max-width:800px;margin:0 auto;}
        .card{background:white;padding:40px;border-radius:24px;box-shadow:0 20px 60px rgba(0,0,0,0.2);}
        h1{color:#1e1b4b;margin-bottom:30px;text-align:center;}
        h2{color:#4f46e5;margin-top:30px;margin-bottom:15px;}
        p,ul{color:#374151;line-height:1.8;margin-bottom:15px;}
        ul{padding-left:25px;}
        a{display:inline-block;margin-top:30px;color:#6366f1;text-decoration:none;font-weight:600;}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🔒 Privacy Policy</h1>
            <p><strong>Last Updated:</strong> September 9, 2026</p>
            
            <h2>1. Information We Collect</h2>
            <p>The SLSU-JGE Library Attendance System collects personal information including but not limited to your full name, ID number, department, contact number, and attendance time records. This information is collected solely for the purpose of managing library attendance and user registration.</p>
            
            <h2>2. How We Use Your Information</h2>
            <ul>
                <li>To record daily attendance (Time In / Time Out)</li>
                <li>To generate accurate attendance reports</li>
                <li>To identify registered users of the library system</li>
                <li>To generate barcode IDs for easy scanning</li>
            </ul>
            
            <h2>3. Data Protection & Security</h2>
            <p>Your personal data is stored in a secure database with restricted access. We do not sell, share, or distribute your personal information to third parties without your consent, except as required by law or university regulations.</p>
            
            <h2>4. Data Retention</h2>
            <p>Attendance records and user information are retained for university record-keeping purposes. You may request the deletion or update of your personal information by contacting the library administrator.</p>
            
            <h2>5. Your Rights</h2>
            <ul>
                <li>Access your personal data</li>
                <li>Request correction of inaccurate information</li>
                <li>Request deletion of your data where permitted by law</li>
                <li>Withdraw consent for data processing</li>
            </ul>
            
            <h2>6. Contact Us</h2>
            <p>For privacy-related inquiries, please contact:<br>
            📧 SLSU-JGE Library Administration<br>
            📍 Southern Luzon State University — JGE Campus</p>
            
            <a href="/login">← Back to Login</a>
        </div>
    </div>
</body>
</html>
"""

USER_FRONTEND = """
<!DOCTYPE html>
<html>
<head>
    <title>📇 User Registration — SLSU-JGE</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;padding:30px;}
        .container{width:100%;max-width:520px;}
        .card{background:rgba(255,255,255,0.95);padding:45px 40px;border-radius:28px;box-shadow:0 25px 80px rgba(0,0,0,0.25);}
        h1{text-align:center;color:#1e1b4b;margin-bottom:8px;}
        .subtitle{text-align:center;color:#6b7280;margin-bottom:35px;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:9px;color:#374151;font-weight:600;}
        input,select{width:100%;padding:14px;border:2px solid #e5e7eb;border-radius:12px;font-size:15px;}
        input:focus,select:focus{outline:none;border-color:#6366f1;}
        button{width:100%;padding:15px;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;border:none;border-radius:12px;font-size:17px;font-weight:700;cursor:pointer;margin-top:8px;}
        #barcode-result{display:none;margin-top:30px;text-align:center;padding:30px;background:linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 100%);border-radius:20px;border:2px solid #bae6fd;}
        .barcode-img{max-width:280px;margin:20px auto;display:block;padding:15px;background:white;border-radius:12px;}
        .btn-print{background:linear-gradient(135deg,#10b981 0%,#059669 100%);width:auto;padding:12px 28px;margin-top:20px;}
        .logout-link{display:block;text-align:center;margin-top:25px;color:#6b7280;text-decoration:none;font-size:14px;}
        @media(max-width:600px){.form-row{grid-template-columns:1fr;}}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📇 User Registration</h1>
            <p class="subtitle">Fill in all fields to generate your barcode ID</p>
            <form id="register-form">
                <div class="form-row">
                    <div class="form-group">
                        <label>ID Type *</label>
                        <select name="id_type" required>
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
                        <select name="department">
                            <option value="">-- Select Department --</option>
                            <option value="CT">BSIT / Computer Technology</option>
                            <option value="BSED">BSED</option>
                            <option value="BEED">BEED</option>
                            <option value="BSFI">BSFI / BSAF</option>
                            <option value="BSBA">BSBA</option>
                            <option value="BPA">BPA</option>
                            <option value="BSFAS">BSFAS — Food & Service Management</option>
                            <option value="EMPLOYEE">EMPLOYEE</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Year Level</label>
                        <select name="year_level">
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
                        <label>Major / Specialization</label>
                        <input type="text" name="major" placeholder="Optional">
                    </div>
                    <div class="form-group">
                        <label>Contact Number</label>
                        <input type="text" name="contact_number" placeholder="09XX-XXX-XXXX">
                    </div>
                </div>
                <div class="form-group">
                    <label>Complete Address</label>
                    <input type="text" name="address" placeholder="City, Province">
                </div>
                <button type="submit">✅ Register & Generate Barcode</button>
            </form>
            <div id="barcode-result">
                <h3>✅ Registration Successful!</h3>
                <p id="student-info"></p>
                <img id="barcode-img" class="barcode-img"><br>
                <button class="btn-print" onclick="window.print()">🖨️ Print Barcode</button>
            </div>
            <a href="/login" class="logout-link">← Logout</a>
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
        body{background:linear-gradient(135deg,#1e1b4b 0%,#312e81 100%);min-height:100vh;}
        .app-container{display:flex;height:100vh;position:relative;}
        .sidebar{width:280px;background:linear-gradient(180deg,rgba(30,27,75,0.98) 0%,rgba(49,46,129,0.98) 100%);display:flex;flex-direction:column;padding:25px 0;position:relative;z-index:100;}
        .sidebar.collapsed{width:72px;}
        .toggle-btn{position:absolute;right:-16px;top:30px;width:34px;height:34px;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);border:none;border-radius:50%;color:white;cursor:pointer;z-index:101;pointer-events:auto !important;}
        .sidebar-header{padding:0 20px 30px 20px;border-bottom:1px solid rgba(129,140,248,0.15);}
        .sidebar-header h2{color:white;font-size:20px;}
        .sidebar-menu{display:flex;flex-direction:column;gap:6px;padding:0 12px;position:relative;z-index:100;}
        .menu-item{display:flex;align-items:center;gap:12px;padding:14px 18px;color:#c7d2fe;border-radius:12px;cursor:pointer;transition:all 0.3s;pointer-events:auto !important;position:relative;z-index:100;user-select:none;}
        .menu-item:hover{background:rgba(99,102,241,0.25);color:#fff;}
        .menu-item.active{background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;box-shadow:0 4px 12px rgba(99,102,241,0.3);}
        .sidebar-footer{padding:20px;border-top:1px solid rgba(129,140,248,0.15);margin-top:auto;position:relative;z-index:100;}
        .logout-btn{width:100%;padding:14px;background:linear-gradient(135deg,#dc2626 0%,#b91c1c 100%);color:white;border:none;border-radius:12px;cursor:pointer;pointer-events:auto !important;position:relative;z-index:100;font-size:16px;}
        .logout-btn:hover{filter:brightness(1.1);}
        .main-content{flex:1;padding:30px;overflow-y:auto;position:relative;z-index:10;}
        .content-card{background:rgba(255,255,255,0.95);border-radius:24px;padding:35px;min-height:calc(100vh - 120px);position:relative;z-index:10;}
        h2{color:#1e1b4b;margin-bottom:25px;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:8px;color:#374151;font-weight:600;}
        input,select{width:100%;padding:13px;border:2px solid #e5e7eb;border-radius:12px;font-size:15px;}
        input:focus,select:focus{outline:none;border-color:#6366f1;}
        button{background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;border:none;padding:13px 20px;border-radius:12px;font-weight:600;cursor:pointer;transition:transform 0.2s;}
        button:active{transform:scale(0.97);}
        .scan-area{text-align:center;padding:40px;background:linear-gradient(135deg,#eef2ff 0%,#e0e7ff 100%);border-radius:20px;margin-bottom:20px;}
        #scan-input{font-size:24px;padding:18px;width:100%;max-width:480px;border-radius:12px;border:2px solid #a5b4fc;}
        .status{font-size:20px;font-weight:bold;margin-top:20px;padding:18px;border-radius:12px;}
        .success{background:#dcfce7;color:#166534;border:2px solid #86efac;}
        .info{background:#e0f2fe;color:#075985;border:2px solid #7dd3fc;}
        .error{background:#fee2e2;color:#991b1b;border:2px solid #fca5a5;}
        table{width:100%;border-collapse:collapse;margin-top:20px;border-radius:16px;overflow:hidden;}
        th,td{padding:16px;text-align:left;border-bottom:1px solid #f1f5f9;}
        th{background:#f8fafc;font-weight:700;color:#1e1b4b;}
        .tab-content{display:none;}
        .tab-content.active{display:block;}
        .btn-print{background:linear-gradient(135deg,#10b981 0%,#059669 100%);}
        .btn-download{background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);}
        .btn-edit{background:linear-gradient(135deg,#8b5cf6 0%,#7c3aed 100%);padding:8px 16px;font-size:13px;}
        .btn-save{background:linear-gradient(135deg,#10b981 0%,#059669 100%);}
        .btn-cancel{background:linear-gradient(135deg,#64748b 0%,#475569 100%);}
        .edit-form{background:#f8fafc;padding:25px;border-radius:20px;margin-top:20px;border:2px solid #e2e8f0;}
        .hidden{display:none !important;}
        .dept-tabs{display:flex;gap:8px;margin:20px 0;flex-wrap:wrap;}
        .dept-tab{padding:10px 16px;background:#f1f5f9;color:#475569;border:none;border-radius:10px;cursor:pointer;font-weight:600;pointer-events:auto;}
        .dept-tab.active{background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:white;}
        .month-filter{display:flex;gap:12px;align-items:center;margin-bottom:20px;flex-wrap:wrap;}
        .btn-month-print{background:linear-gradient(135deg,#ec4899 0%,#db2777 100%);color:white;}
        .barcode-img{max-width:320px;margin:20px auto;display:block;padding:15px;background:white;border-radius:16px;}
        .search-box{margin-bottom:15px;}
        .search-box input{max-width:400px;}
        @media(max-width:900px){.sidebar{width:72px;}.form-row{grid-template-columns:1fr;}.main-content{padding:15px;}}
    </style>
</head>
<body>
    <div class="app-container">
        <div class="sidebar" id="sidebar">
            <button class="toggle-btn" onclick="toggleSidebar()">◀</button>
            <div class="sidebar-header">
                <h2>📚 Library System</h2>
                <p style="color:#a5b4fc;font-size:13px;margin-top:5px;">SLSU-JGE Attendance — Admin</p>
            </div>
            <div class="sidebar-menu">
                <div class="menu-item active" onclick="showTab('scan')">📱 Scan / Attendance</div>
                <div class="menu-item" onclick="showTab('register')">📇 Register User</div>
                <div class="menu-item" onclick="showTab('students')">👥 Students List</div>
                <div class="menu-item" onclick="showTab('records')">📋 Daily Records</div>
                <div class="menu-item" onclick="showTab('history')">📅 Monthly History</div>
                <div class="menu-item" onclick="showTab('export')">📄 Export Reports</div>
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
                <!-- SCAN TAB -->
                <div id="scan" class="tab-content active">
                    <h2>📱 Scan Barcode — Time In / Time Out</h2>
                    <div class="scan-area">
                        <input type="text" id="scan-input" placeholder="👉 Scan barcode or type ID number..." autofocus>
                        <div id="status-box" class="status info">⏳ Waiting for scan...</div>
                    </div>
                </div>

                <!-- REGISTER TAB -->
                <div id="register" class="tab-content">
                    <h2>📇 Register New User</h2>
                    <form id="register-form">
                        <div class="form-row">
                            <div class="form-group">
                                <label>ID Type *</label>
                                <select name="id_type" required>
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
                                    <option value="BSFAS">BSFAS — Food & Service Management</option>
                                    <option value="EMPLOYEE">EMPLOYEE</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Major / Specialization</label>
                                <input type="text" name="major" placeholder="Optional">
                            </div>
                            <div class="form-group">
                                <label>Year Level</label>
                                <select name="year_level">
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
                        <button type="submit">✅ Register & Generate Barcode</button>
                    </form>
                    <div id="barcode-result" style="display:none;margin-top:30px;text-align:center;padding:30px;background:linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 100%);border-radius:20px;border:2px solid #bae6fd;">
                        <h3>✅ Registration Successful!</h3>
                        <p id="student-info" style="font-size:18px;margin:15px 0;"></p>
                        <img id="barcode-img" class="barcode-img"><br>
                        <button class="btn-print" onclick="window.print()">🖨️ Print Barcode</button>
                    </div>
                </div>

                <!-- STUDENTS TAB -->
                <div id="students" class="tab-content">
                    <h2>👥 Registered Users</h2>
                    <div class="search-box">
                        <input type="text" id="search-input" placeholder="🔍 Search by Name or ID..." oninput="filterStudents()">
                    </div>
                    <div class="dept-tabs">
                        <button class="dept-tab active" onclick="switchDept('ALL')">📋 ALL</button>
                        <button class="dept-tab" onclick="switchDept('CT')">CT</button>
                        <button class="dept-tab" onclick="switchDept('BSED')">BSED</button>
                        <button class="dept-tab" onclick="switchDept('BEED')">BEED</button>
                        <button class="dept-tab" onclick="switchDept('BSFI')">BSFI</button>
                        <button class="dept-tab" onclick="switchDept('BSBA')">BSBA</button>
                        <button class="dept-tab" onclick="switchDept('BSFAS')">BSFAS</button>
                        <button class="dept-tab" onclick="switchDept('BPA')">BPA</button>
                        <button class="dept-tab" onclick="switchDept('EMPLOYEE')">EMPLOYEE</button>
                    </div>
                    <div id="students-table-container">
                        <table id="students-table">
                            <thead>
                                <tr>
                                    <th>ID Type</th>
                                    <th>Full Name</th>
                                    <th>Department</th>
                                    <th>ID Number</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="students-tbody"></tbody>
                        </table>
                    </div>
                    <div id="edit-form-container" class="edit-form hidden">
                        <h3>✏️ Edit Student / User</h3>
                        <form id="edit-form">
                            <input type="hidden" id="edit-id">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>ID Type *</label>
                                    <select id="edit-id-type" required>
                                        <option value="Student">🎓 Student</option>
                                        <option value="Employee">👨‍🏫 Employee</option>
                                        <option value="Visitor">👤 Visitor</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>ID Number *</label>
                                    <input type="text" id="edit-id-number" required>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Full Name *</label>
                                    <input type="text" id="edit-full-name" required>
                                </div>
                                <div class="form-group">
                                    <label>Department</label>
                                    <select id="edit-department">
                                        <option value="">-- Select --</option>
                                        <option value="CT">BSIT / Computer Technology</option>
                                        <option value="BSED">BSED</option>
                                        <option value="BEED">BEED</option>
                                        <option value="BSFI">BSFI / BSAF</option>
                                        <option value="BSBA">BSBA</option>
                                        <option value="BPA">BPA</option>
                                        <option value="BSFAS">BSFAS</option>
                                        <option value="EMPLOYEE">EMPLOYEE</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Major</label>
                                    <input type="text" id="edit-major">
                                </div>
                                <div class="form-group">
                                    <label>Year Level</label>
                                    <select id="edit-year-level">
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
                                    <input type="text" id="edit-contact">
                                </div>
                                <div class="form-group">
                                    <label>Address</label>
                                    <input type="text" id="edit-address">
                                </div>
                            </div>
                            <div style="display:flex;gap:12px;margin-top:15px;">
                                <button type="submit" class="btn-save">💾 Save Changes</button>
                                <button type="button" class="btn-cancel" onclick="closeEditForm()">❌ Cancel</button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- RECORDS TAB -->
                <div id="records" class="tab-content">
                    <h2>📋 Daily Attendance Records — Today</h2>
                    <button class="btn-download" onclick="window.location='/download-word'">📄 Download Word Report</button>
                    <table id="records-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Full Name</th>
                                <th>Department</th>
                                <th>Time In</th>
                                <th>Time Out</th>
                            </tr>
                        </thead>
                        <tbody id="records-tbody"></tbody>
                    </table>
                </div>

                <!-- HISTORY TAB -->
                <div id="history" class="tab-content">
                    <h2>📅 Monthly History</h2>
                    <div class="month-filter">
                        <label>Select Month:</label>
                        <input type="month" id="month-input" onchange="loadMonthlyHistory()">
                        <button class="btn-month-print" onclick="printMonthly()">🖨️ Print This Month</button>
                        <button class="btn-download" onclick="downloadMonthlyWord()">📄 Download Word</button>
                    </div>
                    <table id="history-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Full Name</th>
                                <th>Department</th>
                                <th>Time In</th>
                                <th>Time Out</th>
                            </tr>
                        </thead>
                        <tbody id="history-tbody"></tbody>
                    </table>
                </div>

                <!-- EXPORT TAB -->
                <div id="export" class="tab-content">
                    <h2>📄 Export Reports</h2>
                    <div style="display:flex;flex-direction:column;gap:20px;margin-top:25px;">
                        <button class="btn-download" onclick="window.location='/download-word'" style="padding:18px;font-size:16px;">📄 Download Today's Report (Word)</button>
                        <button class="btn-month-print" onclick="document.getElementById('month-input-export').style.display='flex'" style="padding:18px;font-size:16px;">📅 Download Monthly Report</button>
                        <div id="month-input-export" style="display:none;gap:12px;align-items:center;margin-top:10px;">
                            <input type="month" id="month-export" style="padding:12px;border-radius:8px;border:1px solid #ccc;">
                            <button class="btn-download" onclick="downloadMonthlyWord()" style="padding:12px 20px;">Go</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

<script>
let currentDept = 'ALL';
let sidebarCollapsed = false;

// ✅ PINAKA-IMPORTANTENG FIX — GINAMIT KO ANG IBANG PANGALAN NG FUNCTION PARA HINDI CONFLICT
function showTab(tabId) {
    console.log('🖱️ Clicked tab:', tabId); // Makikita mo sa browser console kung gumagana!
    
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    // Remove active from all menu items
    document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active'));
    
    // Show selected tab
    const tab = document.getElementById(tabId);
    if (tab) tab.classList.add('active');
    event.currentTarget.classList.add('active');
    
    // Update title
    const titles = {
        scan: '📱 Scan / Attendance',
        register: '📇 Register User',
        students: '👥 Students List',
        records: '📋 Daily Records',
        history: '📅 Monthly History',
        export: '📄 Export Reports'
    };
    document.getElementById('page-title').textContent = titles[tabId] || '📚 Library System';
    
    // Load data if needed
    if (tabId === 'students') loadStudents();
    if (tabId === 'records') loadRecords();
}

function toggleSidebar() {
    const sb = document.getElementById('sidebar');
    sidebarCollapsed = !sidebarCollapsed;
    sb.classList.toggle('collapsed');
    sb.querySelector('.toggle-btn').textContent = sidebarCollapsed ? '▶' : '◀';
}

function logout() {
    document.cookie = 'logged_in=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
    document.cookie = 'role=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
    window.location.href = '/login';
}

// SCAN FUNCTION
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Admin Panel Loaded');

    const scanInput = document.getElementById('scan-input');
    if (scanInput) {
        scanInput.focus();
        scanInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const id = this.value.trim();
                if (!id) return;
                fetch('/scan', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id_number: id})
                })
                .then(res => res.json())
                .then(data => {
                    const box = document.getElementById('status-box');
                    box.textContent = data.message || data.error;
                    box.className = 'status ' + (data.success ? 'success' : 'error');
                    this.value = '';
                    this.focus();
                })
                .catch(err => {
                    document.getElementById('status-box').textContent = '❌ Server Error';
                    document.getElementById('status-box').className = 'status error';
                });
            }
        });
    }

    // REGISTER FORM
    const regForm = document.getElementById('register-form');
    if (regForm) {
        regForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const fd = new FormData(this);
            fetch('/register', {method: 'POST', body: fd})
            .then(r => r.json())
            .then(d => {
                if (d.success) {
                    document.getElementById('barcode-result').style.display = 'block';
                    document.getElementById('student-info').textContent = d.info;
                    document.getElementById('barcode-img').src = 'data:image/png;base64,' + d.barcode;
                    regForm.reset();
                } else {
                    alert('❌ ' + d.error);
                }
            })
            .catch(err => alert('❌ Error: ' + err));
        });
    }

    // EDIT FORM
    const editForm = document.getElementById('edit-form');
    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const fd = new FormData();
            fd.append('id', document.getElementById('edit-id').value);
            fd.append('id_type', document.getElementById('edit-id-type').value);
            fd.append('id_number', document.getElementById('edit-id-number').value);
            fd.append('full_name', document.getElementById('edit-full-name').value);
            fd.append('department', document.getElementById('edit-department').value);
            fd.append('major', document.getElementById('edit-major').value);
            fd.append('year_level', document.getElementById('edit-year-level').value);
            fd.append('contact_number', document.getElementById('edit-contact').value);
            fd.append('address', document.getElementById('edit-address').value);
            
            fetch('/update-student', {method: 'POST', body: fd})
            .then(r => r.json())
            .then(d => {
                if (d.success) {
                    alert('✅ Saved!');
                    closeEditForm();
                    loadStudents();
                } else {
                    alert('❌ ' + d.error);
                }
            })
            .catch(err => alert('❌ Error: ' + err));
        });
    }
});

// STUDENTS FUNCTIONS
function loadStudents() {
    fetch('/get-students')
    .then(r => r.json())
    .then(d => {
        window.allStudents = d.students;
        filterStudents();
    });
}

function switchDept(dept) {
    currentDept = dept;
    document.querySelectorAll('.dept-tab').forEach(t => t.classList.remove('active'));
    event.currentTarget.classList.add('active');
    filterStudents();
}

function filterStudents() {
    const q = document.getElementById('search-input')?.value.toLowerCase() || '';
    const tbody = document.getElementById('students-tbody');
    if (!window.allStudents) return;
    tbody.innerHTML = '';
    window.allStudents.forEach(s => {
        const matchDept = currentDept === 'ALL' || s.department === currentDept;
        const matchSearch = q === '' || s.full_name.toLowerCase().includes(q) || s.id_number.toLowerCase().includes(q);
        if (matchDept && matchSearch) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${s.id_type}</td>
                <td>${s.full_name}</td>
                <td>${s.department || '-'}</td>
                <td>${s.id_number}</td>
                <td><button class="btn-edit" onclick="openEditForm(${s.id}, '${s.id_type}', '${s.id_number}', '${s.full_name.replace(/'/g, "\\'")}', '${s.department||''}', '${s.major||''}', '${s.year_level||''}', '${s.contact_number||''}', '${s.address||''}')">✏️ Edit</button></td>
            `;
            tbody.appendChild(tr);
        }
    });
}

function openEditForm(id, type, idnum, name, dept, major, year, contact, addr) {
    document.getElementById('edit-form-container').classList.remove('hidden');
    document.getElementById('edit-id').value = id;
    document.getElementById('edit-id-type').value = type;
    document.getElementById('edit-id-number').value = idnum;
    document.getElementById('edit-full-name').value = name;
    document.getElementById('edit-department').value = dept;
    document.getElementById('edit-major').value = major;
    document.getElementById('edit-year-level').value = year;
    document.getElementById('edit-contact').value = contact;
    document.getElementById('edit-address').value = addr;
}

function closeEditForm() {
    document.getElementById('edit-form-container').classList.add('hidden');
}

// RECORDS
function loadRecords() {
    fetch('/get-records')
    .then(r => r.json())
    .then(d => {
        const tb = document.getElementById('records-tbody');
        tb.innerHTML = '';
        d.records.forEach(r => {
            tb.innerHTML += <tr><td>${r.scan_date}</td><td>${r.full_name}</td><td>${r.department||'-'}</td><td>${r.time_in||'-'}</td><td>${r.time_out||'-'}</td></tr>;
        });
    });
}

// MONTHLY
function loadMonthlyHistory() {
    const m = document.getElementById('month-input').value;
    if (!m) return;
    fetch(/get-monthly-history?month=${m})
    .then(r => r.json())
    .then(d => {
        const tb = document.getElementById('history-tbody');
        tb.innerHTML = '';
        d.records.forEach(r => {
            tb.innerHTML += <tr><td>${r.scan_date}</td><td>${r.full_name}</td><td>${r.department||'-'}</td><td>${r.time_in||'-'}</td><td>${r.time_out||'-'}</td></tr>;
        });
    });
}

function printMonthly() {
    const m = document.getElementById('month-input').value;
    if (!m) { alert('Pumili ng buwan'); return; }
    window.open(/print-monthly?month=${m}, '_blank');
}

function downloadMonthlyWord() {
    const m = (document.getElementById('month-input')?.value) || (document.getElementById('month-export')?.value);
    if (!m) { alert('Pumili ng buwan'); return; }
    window.location.href = /download-monthly-word?month=${m};
}
</script>
</body>
</html>
"""

# ✅ RUN THE APP
if __name__ == "_+main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
