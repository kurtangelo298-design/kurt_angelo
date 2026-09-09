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

# ===================== DATABASE — POSTGRESQL =====================
DATABASE_URL = os.environ.get("DATABASE_URL")

# ===================== LOGIN =====================
USERNAME = "slsu"
PASSWORD = "jge"

# ===================== DB CONNECTION =====================
def get_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ DB Connect Error: {e}")
        return None

# ===================== PHILIPPINE TIME — UTC+8 =====================
def get_ph_time():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return now.strftime("%I:%M %p")

def get_ph_date():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")

# ===================== INIT DB =====================
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

# ===================== LOGIN PAGE =====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form.get('username', '').strip()
        pword = request.form.get('password', '').strip()
        if uname == USERNAME and pword == PASSWORD:
            resp = make_response("<script>window.location='/';</script>")
            resp.set_cookie('logged_in', 'true', max_age=31536000)
            return resp
        return """<html><body style="font-family:Arial;text-align:center;padding-top:100px;background:linear-gradient(135deg,#1e3a8a 0%,#312e81 100%);"><h2 style="color:#ff6b6b;">❌ Wrong Credentials!</h2><a href="/login" style="font-size:18px;color:white;">Try Again</a></body></html>"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Login — Library Attendance</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#1e3a8a 0%,#312e81 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;position:relative;}
        body::before{content:'';position:absolute;top:0;left:0;width:100%;height:100%;background:url('https://images.unsplash.com/photo-1507842273431-48ccb61e49b?w=1920&q=80') no-repeat center center;background-size:cover;opacity:0.15;z-index:0;}
        .card{background:rgba(255,255,255,0.95);padding:45px 35px;border-radius:24px;box-shadow:0 20px 60px rgba(0,0,0,0.3);width:100%;max-width:420px;position:relative;z-index:1;backdrop-filter:blur(10px);}
        h1{text-align:center;color:#1e3a8a;margin-bottom:35px;font-size:28px;}
        .form-group{margin-bottom:22px;}
        label{display:block;margin-bottom:8px;color:#374151;font-weight:600;font-size:15px;}
        input{width:100%;padding:15px;border:2px solid #e5e7eb;border-radius:12px;font-size:16px;transition:0.3s;}
        input:focus{outline:none;border-color:#3b82f6;box-shadow:0 0 0 4px rgba(59,130,246,0.2);}
        button{width:100%;padding:15px;background:linear-gradient(135deg,#1e3a8a 0%,#4f46e5 100%);color:white;border:none;border-radius:12px;font-size:18px;font-weight:bold;cursor:pointer;transition:0.3s;}
        button:hover{transform:translateY(-2px);box-shadow:0 10px 25px rgba(79,70,229,0.4);}
    </style>
</head>
<body>
    <div class="card">
        <h1>🔐 Admin Login</h1>
        <form method="POST">
            <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>"""

# ===================== MAIN DASHBOARD =====================
@app.route('/')
def home():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    return render_template_string(FRONTEND_HTML)

# ===================== SCAN ENDPOINT — TIME IN / TIME OUT =====================
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

# ===================== REGISTER ENDPOINT =====================
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

# ===================== GET STUDENTS =====================
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

# ===================== UPDATE STUDENT =====================
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

# ===================== GET RECORDS =====================
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

# ===================== MONTHLY HISTORY =====================
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

# ===================== DOWNLOAD DAILY WORD =====================
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

# ===================== DOWNLOAD MONTHLY WORD =====================
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

# ===================== PRINT MONTHLY PAGE =====================
@app.route('/print-monthly')
def print_monthly():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    month = request.args.get('month', '').strip()
    return f"""
<!DOCTYPE html><html><head><title>Monthly Report — {month}</title>
<style>body{{font-family:Arial;padding:30px;}}h1{{text-align:center;}}table{{width:100%;border-collapse:collapse;margin-top:20px;}}th,td{{border:1px solid #ccc;padding:10px;text-align:left;}}th{{background:#f0f0f0;}}@media print{{button{{display:none;}}}}</style>
</head><body>
<h1>📚 Monthly Attendance Report — {month}</h1>
<p>Generated: {get_ph_date()} {get_ph_time()}</p>
<button onclick="window.print()" style="padding:10px 20px;font-size:16px;cursor:pointer;">🖨️ Print</button>
<script>fetch('/get-monthly-history?month={month}').then(r=>r.json()).then(d=>{{
let html='<table><tr><th>Date</th><th>Full Name</th><th>ID Number</th><th>Time In</th><th>Time Out</th></tr>';
d.records.forEach(r=>html+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+r.id_number+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>');
html+='</table>';document.body.innerHTML+=html;
}})</script>
</body></html>"""
FRONTEND_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>📚 Library Attendance — SLSU-JGE</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 100%);min-height:100vh;position:relative;overflow:hidden;}
        body::before{content:'';position:fixed;top:0;left:0;width:100%;height:100%;background:url('https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=1920&q=80') no-repeat center center;background-size:cover;opacity:0.06;z-index:0;pointer-events:none;}
        .app-container{display:flex;height:100vh;position:relative;z-index:1;}
        .sidebar{width:280px;background:linear-gradient(180deg,rgba(30,41,59,0.95) 0%,rgba(15,23,42,0.95) 100%);backdrop-filter:blur(20px);display:flex;flex-direction:column;padding:25px 0;box-shadow:4px 0 24px rgba(0,0,0,0.2);border-right:1px solid rgba(255,255,255,0.05);position:relative;transition:all 0.4s cubic-bezier(0.4,0,0.2,1);}
        .sidebar.collapsed{width:72px;padding:25px 0;}
        .toggle-btn{position:absolute;right:-16px;top:30px;width:32px;height:32px;background:linear-gradient(135deg,#3b82f6 0%,#6366f1 100%);border:none;border-radius:50%;color:white;font-size:16px;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(59,130,246,0.3);z-index:10;transition:all 0.3s ease;}
        .toggle-btn:hover{transform:scale(1.1);box-shadow:0 6px 16px rgba(59,130,246,0.4);}
        .sidebar.collapsed .toggle-btn{transform:rotate(180deg);}
        .sidebar-header{padding:0 20px 30px 20px;border-bottom:1px solid rgba(255,255,255,0.08);margin-bottom:20px;transition:opacity 0.3s;}
        .sidebar.collapsed .sidebar-header h2 span,.sidebar.collapsed .sidebar-header p{opacity:0;visibility:hidden;position:absolute;}
        .sidebar-header h2{color:white;font-size:20px;display:flex;align-items:center;gap:10px;}
        .sidebar-header p{color:#94a3b8;font-size:13px;margin-top:5px;}
        .sidebar-menu{display:flex;flex-direction:column;gap:6px;padding:0 12px;flex:1;}
        .menu-item{display:flex;align-items:center;gap:12px;padding:14px 18px;color:#cbd5e1;border-radius:12px;cursor:pointer;transition:all 0.3s cubic-bezier(0.4,0,0.2,1);font-size:15px;font-weight:500;border:2px solid transparent;white-space:nowrap;pointer-events:auto;position:relative;z-index:2;}
        .sidebar.collapsed .menu-item{justify-content:center;padding:14px 0;}
        .sidebar.collapsed .menu-item span:nth-child(2){display:none;}
        .menu-item:hover{background:rgba(59,130,246,0.15);color:#93c5fd;transform:translateX(4px);}
        .sidebar.collapsed .menu-item:hover{transform:scale(1.05);}
        .menu-item.active{background:linear-gradient(135deg,#3b82f6 0%,#6366f1 100%);color:white;box-shadow:0 4px 15px rgba(59,130,246,0.3);border-color:transparent;}
        .menu-item i{font-size:20px;width:24px;text-align:center;}
        .sidebar-footer{padding:20px;border-top:1px solid rgba(255,255,255,0.08);margin-top:auto;}
        .sidebar.collapsed .sidebar-footer{padding:20px 8px;}
        .logout-btn{width:100%;display:flex;align-items:center;justify-content:center;gap:8px;padding:14px;background:linear-gradient(135deg,#dc2626 0%,#b91c1c 100%);color:white;border:none;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;transition:all 0.3s;pointer-events:auto;position:relative;z-index:2;}
        .logout-btn:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(220,38,38,0.35);}
        .main-content{flex:1;padding:30px;overflow-y:auto;position:relative;transition:padding 0.3s;}
        .content-header{margin-bottom:25px;display:flex;justify-content:space-between;align-items:center;}
        .content-header h1{color:white;font-size:28px;}
        .content-card{background:rgba(255,255,255,0.95);backdrop-filter:blur(20px);border-radius:24px;padding:35px;box-shadow:0 10px 40px rgba(0,0,0,0.2);min-height:calc(100vh - 120px);animation:fadeIn 0.4s ease;position:relative;z-index:1;}
        @keyframes fadeIn{from{opacity:0;transform:translateY(15px);}to{opacity:1;transform:translateY(0);}}
        h2{color:#1e293b;margin-bottom:25px;font-size:24px;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:7px;color:#475569;font-weight:600;font-size:14px;}
        input,select{width:100%;padding:13px;border:2px solid #e2e8f0;border-radius:12px;font-size:15px;transition:0.3s;background:#fafafa;pointer-events:auto;}
        input:focus,select:focus{outline:none;border-color:#3b82f6;background:white;box-shadow:0 0 0 4px rgba(59,130,246,0.15);transform:translateY(-1px);}
        button{background:linear-gradient(135deg,#3b82f6 0%,#6366f1 100%);color:white;border:none;padding:13px 28px;border-radius:12px;font-size:15px;font-weight:bold;cursor:pointer;transition:all 0.3s;margin:5px;pointer-events:auto;position:relative;z-index:2;}
        button:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(99,102,241,0.3);}
        .scan-area{text-align:center;padding:40px;background:linear-gradient(135deg,#eff6ff 0%,#eef2ff 100%);border-radius:20px;margin-bottom:20px;border:2px solid #bfdbfe;}
        #scan-input{font-size:24px;text-align:center;padding:18px;width:100%;max-width:450px;border-radius:12px;border:2px solid #93c5fd;pointer-events:auto;}
        .status{font-size:20px;font-weight:bold;margin-top:20px;padding:18px;border-radius:12px;animation:popIn 0.3s ease;}
        @keyframes popIn{from{transform:scale(0.9);opacity:0;}to{transform:scale(1);opacity:1;}}
        .success{background:#dcfce7;color:#166534;border:2px solid #86efac;}
        .info{background:#e0f2fe;color:#075985;border:2px solid #7dd3fc;}
        .error{background:#fee2e2;color:#991b1b;border:2px solid #fca5a5;}
        table{width:100%;border-collapse:collapse;margin-top:20px;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.05);}
        th,td{padding:16px;text-align:left;border-bottom:1px solid #f1f5f9;font-size:14px;}
        th{background:linear-gradient(135deg,#f8fafc 0%,#f1f5f9 100%);font-weight:bold;color:#1e293b;}
        tr:hover{background:#f8fafc;}
        .tab-content{display:none;}
        .tab-content.active{display:block;animation:fadeIn 0.3s ease;}
        .barcode-img{max-width:320px;margin:20px auto;display:block;padding:15px;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);}
        .btn-print{background:linear-gradient(135deg,#10b981 0%,#059669 100%);}
        .btn-download{background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);color:white;}
        .btn-edit{background:linear-gradient(135deg,#8b5cf6 0%,#7c3aed 100%);color:white;padding:8px 16px;font-size:13px;border-radius:10px;}
        .btn-save{background:linear-gradient(135deg,#10b981 0%,#059669 100%);}
        .btn-cancel{background:linear-gradient(135deg,#64748b 0%,#475569 100%);}
        .edit-form{background:linear-gradient(135deg,#f8fafc 0%,#f1f5f9 100%);padding:25px;border-radius:20px;margin-top:20px;border:2px solid #e2e8f0;}
        .hidden{display:none !important;}
        .dept-tabs{display:flex;gap:8px;margin:20px 0;flex-wrap:wrap;}
        .dept-tab{padding:10px 16px;background:#f1f5f9;color:#475569;border:none;border-radius:10px;cursor:pointer;font-weight:600;transition:all 0.2s;font-size:14px;pointer-events:auto;}
        .dept-tab:hover{background:#e2e8f0;transform:translateY(-1px);}
        .dept-tab.active{background:linear-gradient(135deg,#3b82f6 0%,#6366f1 100%);color:white;box-shadow:0 4px 12px rgba(59,130,246,0.3);}
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
                <p>SLSU-JGE Attendance</p>
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
                <div id="scan" class="tab-content active">
                    <h2>📱 Scan Barcode — Time In / Time Out</h2>
                    <div class="scan-area">
                        <input type="text" id="scan-input" placeholder="👉 Scan barcode or type ID number..." autofocus>
                        <div id="status-box" class="status info">⏳ Waiting for scan...</div>
                    </div>
                </div>
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
                            <div class="form-group"><label>Full Name *</label><input type="text" name="full_name" required placeholder="Last, First Middle"></div>
                            <div class="form-group">
                                <label>Department</label>
                                <select name="department" id="dept-select">
                                    <option value="">-- Select Department --</option>
                                    <option value="CT">Computer Technology (CT)</option>
                                    <option value="FBT">Food & Beverage Technology (FBT)</option>
                                    <option value="BSED">BSED</option>
                                    <option value="BEED">BEED</option>
                                    <option value="BSFI">BSFI</option>
                                    <option value="BSBA">BSBA</option>
                                    <option value="EMPLOYEE">EMPLOYEE</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-row" id="major-row">
                            <div class="form-group">
                                <label>Major / Specialization</label>
                                <select name="major" id="major-select"><option value="">-- Select Department First --</option></select>
                            </div>
                            <div class="form-group">
                                <label>Year Level</label>
                                <select name="year_level" id="year-select">
                                    <option value="1st Year">1st Year</option>
                                    <option value="2nd Year">2nd Year</option>
                                    <option value="3rd Year">3rd Year</option>
                                    <option value="4th Year">4th Year</option>
                                    <option value="5th Year">5th Year</option>
                                    <option value="N/A">N/A — Not Applicable</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>Contact Number</label><input type="text" name="contact_number" placeholder="09XX-XXX-XXXX"></div>
                            <div class="form-group"><label>Complete Address</label><input type="text" name="address" placeholder="City, Province"></div>
                        </div>
                        <button type="submit">✅ Register & Generate Barcode</button>
                    </form>
                    <div id="barcode-result" style="display:none;margin-top:30px;text-align:center;padding:30px;background:linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 100%);border-radius:20px;border:2px solid #bae6fd;">
                        <h3>✅ Registration Successful!</h3>
                        <p style="font-size:18px;margin:15px 0;"><strong id="student-info"></strong></p>
                        <img id="barcode-img" class="barcode-img"><br>
                        <button class="btn-print" onclick="window.print()">🖨️ Print Barcode</button>
                    </div>
                </div>
                <div id="students" class="tab-content">
                    <h2>👥 Registered Users — By Department</h2>
                    <div class="search-box">
                        <input type="text" id="search-input" placeholder="🔍 Search by Name or ID Number..." oninput="filterStudents()">
                    </div>
                    <div class="dept-tabs">
                        <button class="dept-tab active" id="dept-ALL" onclick="switchDept('ALL')">📋 ALL</button>
                        <button class="dept-tab" id="dept-CT" onclick="switchDept('CT')">CT</button>
                        <button class="dept-tab" id="dept-FBT" onclick="switchDept('FBT')">FBT</button>
                        <button class="dept-tab" id="dept-BSED" onclick="switchDept('BSED')">BSED</button>
                        <button class="dept-tab" id="dept-BEED" onclick="switchDept('BEED')">BEED</button>
                        <button class="dept-tab" id="dept-BSFI" onclick="switchDept('BSFI')">BSFI</button>
                        <button class="dept-tab" id="dept-BSBA" onclick="switchDept('BSBA')">BSBA</button>
                        <button class="dept-tab" id="dept-EMPLOYEE" onclick="switchDept('EMPLOYEE')">EMPLOYEE</button>
                        <button class="dept-tab" id="dept-Visitor" onclick="switchDept('Visitor')">👤 VISITOR</button>
                    </div>
                    <button onclick="loadStudents()">🔄 Refresh List</button>
                    <div id="students-table"></div>
                    <div id="edit-form-container" class="edit-form hidden">
                        <h3>✏️ Edit User Information</h3>
                        <form id="edit-form">
                            <input type="hidden" id="edit-id" name="id">
                            <div class="form-row">
                                <div class="form-group"><label>ID Type</label>
                                    <select id="edit-id-type" name="id_type">
                                        <option value="Student">🎓 Student</option>
                                        <option value="Employee">👨‍🏫 Employee</option>
                                        <option value="Visitor">👤 Visitor</option>
                                    </select>
                                </div>
                                <div class="form-group"><label>ID Number</label><input type="text" id="edit-idnum" name="id_number" required></div>
                            </div>
                            <div class="form-row">
                                <div class="form-group"><label>Full Name</label><input type="text" id="edit-fullname" name="full_name" required></div>
                                <div class="form-group">
                                    <label>Department</label>
                                    <select id="edit-dept" name="department">
                                        <option value="">-- Select --</option>
                                        <option value="CT">Computer Technology (CT)</option>
                                        <option value="FBT">Food & Beverage Technology (FBT)</option>
                                        <option value="BSED">BSED</option>
                                        <option value="BEED">BEED</option>
                                        <option value="BSFI">BSFI</option>
                                        <option value="BSBA">BSBA</option>
                                        <option value="EMPLOYEE">EMPLOYEE</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group"><label>Major / Specialization</label><select id="edit-major" name="major"></select></div>
                                <div class="form-group"><label>Year Level</label>
                                    <select id="edit-year" name="year_level">
                                        <option value="1st Year">1st Year</option>
                                        <option value="2nd Year">2nd Year</option>
                                        <option value="3rd Year">3rd Year</option>
                                        <option value="4th Year">4th Year</option>
                                        <option value="5th Year">5th Year</option>
                                        <option value="N/A">N/A</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group"><label>Contact Number</label><input type="text" id="edit-contact" name="contact_number"></div>
                                <div class="form-group"><label>Complete Address</label><input type="text" id="edit-address" name="address"></div>
                            </div>
                            <button type="submit" class="btn-save">💾 Save Changes</button>
                            <button type="button" class="btn-cancel" onclick="hideEditForm()">❌ Cancel</button>
                        </form>
                    </div>
                </div>
                <div id="records" class="tab-content">
                    <h2>📋 Today's Attendance Records</h2>
                    <button onclick="loadRecords()">🔄 Refresh Records</button>
                    <div id="records-table"></div>
                </div>
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
                    <button onclick="loadMonthlyHistory()">🔄 Load Records</button>
                    <div id="history-table"></div>
                </div>
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
const MAJORS = {
    "BSBA": ["Marketing Management", "Financial Management", "Human Resource Development", "Business Management", "Economics"],
    "BSED": ["English", "Mathematics", "Science", "Filipino", "Social Studies", "Values Education"],
    "CT": ["Computer Technology", "Electronics Technology", "Drafting Technology"],
    "FBT": ["Food Technology", "Baking & Pastry", "Culinary Arts"]
};
const PAGE_TITLES = {scan:"📱 Scan / Attendance",register:"📇 Register New User",students:"👥 Registered Users",records:"📋 Daily Attendance Records",history:"📅 Monthly Attendance History",export:"📄 Export & Print Reports"};
let editingStudentId=null,currentDept="ALL",allStudents=[];
function toggleSidebar(){const e=document.getElementById("sidebar");e.classList.toggle("collapsed");const t=e.querySelector(".toggle-btn");t.textContent=e.classList.contains("collapsed")?"▶":"◀";}
function logout(){document.cookie="logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";window.location.href="/login";}
function showContent(e){document.querySelectorAll(".menu-item").forEach(t=>t.classList.remove("active"));document.querySelectorAll(".tab-content").forEach(t=>t.classList.remove("active"));const t=["scan","register","students","records","history","export"].indexOf(e);-1!==t&&document.querySelectorAll(".menu-item")[t].classList.add("active");document.getElementById(e).classList.add("active");document.getElementById("page-title").textContent=PAGE_TITLES[e];if("scan"===e)setTimeout(()=>{var t;null===(t=document.getElementById("scan-input"))||void 0===t||t.focus()},100);if("students"===e)loadStudents();if("records"===e)loadRecords();if("history"===e)loadMonthlyHistory();}
function switchDept(e){document.querySelectorAll(".dept-tab").forEach(t=>t.classList.remove("active"));document.getElementById("dept-"+e).classList.add("active");currentDept=e;filterStudents();}
function updateMajorOptions(e,t,n){const s=document.getElementById(e).value;const a=document.getElementById(t);const i=document.getElementById(n);a.innerHTML='<option value="">-- Select Major --</option>',("Visitor"===s||"EMPLOYEE"===s||""===s)?(i&&(i.value="N/A",i.disabled=!0)):(i&&(i.disabled=!1),MAJORS[s]&&MAJORS[s].forEach(e=>{const t=document.createElement("option");t.value=e,t.textContent=e,a.appendChild(t)}));}
function submitScan(){const e=document.getElementById("scan-input").value.trim();if(!e)return;fetch("/scan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id_number:e})}).then(e=>e.json()).then(t=>{const n=document.getElementById("status-box");n.className="status "+(t.success?"success":"error"),n.textContent=t.message,document.getElementById("scan-input").value=""}).catch(e=>{document.getElementById("status-box").className="status error",document.getElementById("status-box").textContent="❌ Error: "+e});}
function loadStudents(){fetch("/get-students").then(e=>e.json()).then(e=>{allStudents=e.students||[],filterStudents()}).catch(e=>alert("❌ Load Error: "+e));}
function filterStudents(){const e=document.getElementById("search-input")?.value.toLowerCase()||"";let t=allStudents;"ALL"!==currentDept&&(t=t.filter(e=>e.department===currentDept||"Visitor"===currentDept&&"Visitor"===e.id_type)),e&&(t=t.filter(t=>t.full_name.toLowerCase().includes(e)||t.id_number.toLowerCase().includes(e)));const n=document.getElementById("students-table");t.length?n.innerHTML="<table><tr><th>ID Number</th><th>Full Name</th><th>Type</th><th>Department</th><th>Action</th></tr>"+t.map(e=>"<tr><td><strong>"+e.id_number+"</strong></td><td>"+e.full_name+"</td><td>"+e.id_type+"</td><td>"+(e.department||"-")+"</td><td><button class='btn-edit' onclick='editStudent("+e.id+")'>✏️ Edit</button></td></tr>").join("")+"</table>":n.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:16px;">📭 No records found.</p>';}
function editStudent(e){const t=allStudents.find(t=>t.id===e);if(!t)return;editingStudentId=e,document.getElementById("edit-id").value=t.id,document.getElementById("edit-id-type").value=t.id_type,document.getElementById("edit-idnum").value=t.id_number,document.getElementById("edit-fullname").value=t.full_name,document.getElementById("edit-dept").value=t.department||"",document.getElementById("edit-major").value=t.major||"",document.getElementById("edit-year").value=t.year_level||"",document.getElementById("edit-contact").value=t.contact_number||"",document.getElementById("edit-address").value=t.address||"",document.getElementById("edit-form-container").classList.remove("hidden"),document.getElementById("edit-form-container").scrollIntoView({behavior:"smooth"});}
function hideEditForm(){document.getElementById("edit-form-container").classList.add("hidden"),editingStudentId=null,document.getElementById("edit-form").reset();}
function loadRecords(){fetch("/get-records").then(e=>e.json()).then(e=>{const t=e.records||[],n=document.getElementById("records-table");t.length?n.innerHTML="<table><tr><th>Date</th><th>Full Name</th><th>ID Number</th><th>Time In</th><th>Time Out</th></tr>"+t.map(e=>"<tr><td><strong>"+e.scan_date+"</strong></td><td>"+e.full_name+"</td><td>"+e.id_number+"</td><td style='color:#16a34a;font-weight:600;'>"+(e.time_in||"-")+"</td><td style='color:#dc2626;font-weight:600;'>"+(e.time_out||"-")+"</td></tr>").join("")+"</table>":n.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:16px;">📭 No attendance records yet.</p>';}).catch(e=>alert("❌ Load Error: "+e));}
function loadMonthlyHistory(){const e=document.getElementById("month-select").value;fetch("/get-monthly-history?month="+e).then(e=>e.json()).then(t=>{const n=t.records||[],s=document.getElementById("history-table");n.length?s.innerHTML="<h3 style='margin:20px 0;color:#1e293b;'>📅 Records for "+e+"</h3><table><tr><th>Date</th><th>Full Name</th><th>ID Number</th><th>Time In</th><th>Time Out</th></tr>"+n.map(e=>"<tr><td><strong>"+e.scan_date+"</strong></td><td>"+e.full_name+"</td><td>"+e.id_number+"</td><td style='color:#16a34a;font-weight:600;'>"+(e.time_in||"-")+"</td><td style='color:#dc2626;font-weight:600;'>"+(e.time_out||"-")+"</td></tr>").join("")+"</table>":s.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:16px;">📭 No records for '+e+'.</p>';}).catch(e=>alert("❌ Load Error: "+e));}
function printMonthlyReport(){const e=document.getElementById("month-select").value;window.open("/print-monthly?month="+e,"_blank");}
function downloadMonthlyReport(){const e=document.getElementById("month-select").value;window.location.href="/download-monthly-word?month="+e;}
document.addEventListener("DOMContentLoaded",function(){const e=document.getElementById("scan-input");e&&e.addEventListener("keypress",e=>"Enter"===e.key&&submitScan());const t=document.getElementById("dept-select");t&&t.addEventListener("change",()=>updateMajorOptions("dept-select","major-select","year-select"));const n=document.getElementById("edit-dept");n&&n.addEventListener("change",()=>updateMajorOptions("edit-dept","edit-major","edit-year"));const s=document.getElementById("register-form");s&&s.addEventListener("submit",e=>{e.preventDefault();const t=new FormData(s);fetch("/register",{method:"POST",body:t}).then(e=>e.json()).then(t=>{t.success?(document.getElementById("barcode-result").style.display="block",document.getElementById("student-info").textContent=t.info,document.getElementById("barcode-img").src="data:image/png;base64,"+t.barcode,s.reset(),document.getElementById("major-select").innerHTML='<option value="">-- Select Department First --</option>'):alert("❌ Error: "+t.error);}).catch(e=>alert("❌ Error: "+e));});const a=document.getElementById("edit-form");a&&a.addEventListener("submit",e=>{e.preventDefault();const t=new FormData(a);fetch("/update-student",{method:"POST",body:t}).then(e=>e.json()).then(t=>{t.success?(alert("✅ Updated successfully!"),hideEditForm(),loadStudents()):alert("❌ Error: "+t.error);}).catch(e=>alert("❌ Error: "+e));});});
</script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
