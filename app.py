from flask import Flask, render_template_string, request, jsonify, make_response
import sqlite3
import datetime
import barcode
from barcode.writer import ImageWriter
import base64
from io import BytesIO
import os

app = Flask(__name__)

# ===================== PERMANENT DATABASE PATH =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "library_attendance.db")

# ===================== LOGIN CREDENTIALS =====================
USERNAME = "slsu"
PASSWORD = "jge"

# ===================== DATABASE INIT — PERMANENT! =====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        department TEXT NOT NULL,
        contact_number TEXT,
        year_level TEXT NOT NULL,
        student_number TEXT NOT NULL UNIQUE,
        registered_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        time_in TEXT,
        time_out TEXT,
        scan_date TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()

# Auto-create database on first run
init_db()

DEPARTMENTS = ["CT", "FBT", "BSED", "BEED", "BSFI", "BSBA", "EMPLOYEE"]
YEAR_LEVELS = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "N/A"]

def generate_barcode_b64(student_number):
    code128 = barcode.get_barcode_class("code128")
    writer = ImageWriter()
    writer.set_options({"module_width":0.3, "module_height":10, "font_size":8, "text_distance":2})
    img = code128(student_number, writer=writer).render()
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def normalize_text(text):
    if text:
        return text.strip().lower()
    return ""

def is_logged_in():
    return request.cookies.get('logged_in') == 'true'

# ===================== LOGIN PAGE =====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = normalize_text(request.form.get('username', ''))
        pword = request.form.get('password', '').strip()
        if uname == normalize_text(USERNAME) and pword == PASSWORD:
            resp = make_response("""<script>window.location='/';</script>""")
            resp.set_cookie('logged_in', 'true', max_age=31536000)
            return resp
        return """
        <html><body style="font-family:Arial;text-align:center;padding-top:100px;background:#f5f5f5;">
            <h2 style="color:red;">❌ Wrong Username or Password!</h2>
            <a href="/login" style="font-size:18px;">Try Again</a>
        </body></html>"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Login — Library Attendance</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;}
        .card{background:white;padding:40px 30px;border-radius:20px;box-shadow:0 15px 35px rgba(0,0,0,0.2);width:100%;max-width:400px;}
        h1{text-align:center;color:#2c3e50;margin-bottom:30px;}
        .form-group{margin-bottom:20px;}
        label{display:block;margin-bottom:8px;color:#555;font-weight:600;}
        input{width:100%;padding:14px;border:2px solid #eee;border-radius:10px;font-size:16px;}
        button{width:100%;padding:14px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;border-radius:10px;font-size:18px;font-weight:bold;cursor:pointer;}
    </style>
</head>
<body>
    <div class="card">
        <h1>🔐 Admin Login</h1>
        <form method="POST">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>"""

# ===================== MAIN PAGE =====================
@app.route('/')
def home():
    if not is_logged_in():
        return """<script>window.location='/login';</script>"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📚 Library Attendance System — SLSU-JGE</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:20px;}
        .container{max-width:1000px;margin:0 auto;}
        .tabs{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;}
        .tab{padding:12px 20px;background:rgba(255,255,255,0.3);color:white;border:none;border-radius:10px;cursor:pointer;font-weight:bold;transition:0.3s;}
        .tab.active{background:white;color:#667eea;box-shadow:0 4px 15px rgba(0,0,0,0.2);}
        .card{background:white;padding:30px;border-radius:20px;box-shadow:0 10px 30px rgba(0,0,0,0.2);margin-bottom:20px;}
        h1{text-align:center;color:white;text-shadow:0 2px 10px rgba(0,0,0,0.2);margin-bottom:20px;}
        h2{color:#667eea;margin-bottom:20px;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;}
        .form-group{margin-bottom:15px;}
        label{display:block;margin-bottom:5px;color:#555;font-weight:600;}
        input,select{width:100%;padding:12px;border:2px solid #eee;border-radius:8px;font-size:15px;}
        button{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;padding:13px 25px;border-radius:10px;font-size:16px;font-weight:bold;cursor:pointer;transition:0.3s;margin:5px;}
        button:hover{transform:translateY(-2px);box-shadow:0 5px 15px rgba(102,126,234,0.4);}
        .scan-area{text-align:center;padding:30px;background:#f8f9fa;border-radius:15px;margin-bottom:20px;}
        #scan-input{font-size:22px;text-align:center;padding:15px;width:100%;max-width:400px;}
        .status{font-size:20px;font-weight:bold;margin-top:15px;padding:15px;border-radius:10px;}
        .success{background:#d4edda;color:#155724;}
        .info{background:#d1ecf1;color:#0c5460;}
        .error{background:#f8d7da;color:#721c24;}
        table{width:100%;border-collapse:collapse;margin-top:20px;}
        th,td{padding:12px;text-align:left;border-bottom:1px solid #eee;}
        th{background:#f8f9fa;font-weight:bold;color:#667eea;}
        .tab-content{display:none;}
        .tab-content.active{display:block;}
        .barcode-img{max-width:300px;margin:15px auto;display:block;}
        .btn-print{background:#28a745;}
        .btn-download{background:#ffc107;color:#333;}
        .btn-edit{background:#f39c12;color:white;padding:5px 10px;font-size:13px;}
        .btn-save{background:#2ecc71;color:white;}
        .btn-cancel{background:#95a5a6;color:white;}
        .logout{background:#dc3545;}
        .edit-form{background:#f8f9fa;padding:20px;border-radius:12px;margin-top:15px;}
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Library Attendance System — SLSU-JGE</h1>
        <div style="text-align:right;margin-bottom:15px;">
            <button class="logout" onclick="window.location='/logout'">🚪 Logout</button>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('scan')">📱 Scan / Attendance</button>
            <button class="tab" onclick="showTab('register')">📇 Register</button>
            <button class="tab" onclick="showTab('students')">👥 Students List</button>
            <button class="tab" onclick="showTab('records')">📋 Records</button>
            <button class="tab" onclick="showTab('export')">📄 Export</button>
        </div>

        <div id="scan" class="tab-content active">
            <div class="card">
                <h2>📱 Scan Student Number Barcode</h2>
                <div class="scan-area">
                    <input type="text" id="scan-input" placeholder="Scan barcode or type student number..." autofocus>
                    <div id="status-box" class="status info">Waiting for scan...</div>
                </div>
            </div>
        </div>

        <div id="register" class="tab-content">
            <div class="card">
                <h2>📇 Register New Student — NO LIMIT!</h2>
                <form id="register-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Full Name</label>
                            <input type="text" name="full_name" required>
                        </div>
                        <div class="form-group">
                            <label>Student Number</label>
                            <input type="text" name="student_number" required>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Department</label>
                            <select name="department">
                                {% for d in depts %}<option>{{d}}</option>{% endfor %}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Year Level</label>
                            <select name="year_level">
                                {% for y in years %}<option>{{y}}</option>{% endfor %}
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Contact Number</label>
                        <input type="text" name="contact_number">
                    </div>
                    <button type="submit">✅ Register & Generate Barcode</button>
                </form>
                <div id="barcode-result" style="display:none;margin-top:25px;text-align:center;padding:20px;background:#f0f4ff;border-radius:15px;">
                    <h3>✅ Registered Successfully!</h3>
                    <p><strong id="student-info"></strong></p>
                    <img id="barcode-img" class="barcode-img">
                    <br>
                    <button class="btn-print" onclick="window.print()">🖨️ Print Barcode</button>
                </div>
            </div>
        </div>

        <div id="students" class="tab-content">
            <div class="card">
                <h2>👥 Registered Students — Edit Any Info</h2>
                <button onclick="loadStudents()">🔄 Refresh List</button>
                <div id="students-table"></div>
                
                <div id="edit-form-container" class="edit-form" style="display:none;">
                    <h3>✏️ Edit Student Info</h3>
                    <form id="edit-form">
                        <input type="hidden" id="edit-id" name="id">
                        <div class="form-row">
                            <div class="form-group">
                                <label>Full Name</label>
                                <input type="text" id="edit-fullname" name="full_name" required>
                            </div>
                            <div class="form-group">
                                <label>Student Number</label>
                                <input type="text" id="edit-studentnum" name="student_number" required>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Department</label>
                                <select id="edit-dept" name="department">
                                    {% for d in depts %}<option>{{d}}</option>{% endfor %}
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Year Level</label>
                                <select id="edit-year" name="year_level">
                                    {% for y in years %}<option>{{y}}</option>{% endfor %}
                                </select>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Contact Number</label>
                            <input type="text" id="edit-contact" name="contact_number">
                        </div>
                        <button type="submit" class="btn-save">💾 Save Changes</button>
                        <button type="button" class="btn-cancel" onclick="hideEditForm()">❌ Cancel</button>
                    </form>
                </div>
            </div>
        </div>

        <div id="records" class="tab-content">
            <div class="card">
                <h2>📋 Attendance Records</h2>
                <button onclick="loadRecords()">🔄 Refresh</button>
                <div id="records-table"></div>
            </div>
        </div>

        <div id="export" class="tab-content">
            <div class="card">
                <h2>📄 Download / Export Reports</h2>
                <p>Download today's attendance as Word Document (.docx)</p>
                <button class="btn-download" onclick="downloadWord()">📄 Download Today's Attendance</button>
                <br><br>
                <p>Print all records directly</p>
                <button class="btn-print" onclick="window.print()">🖨️ Print Page</button>
            </div>
        </div>
    </div>

<script>
let editingStudentId = null;

function showTab(name){
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById(name).classList.add('active');
    if(name==='scan') setTimeout(()=>document.getElementById('scan-input').focus(),100);
    if(name==='students') loadStudents();
}

const scanInput = document.getElementById('scan-input');
const statusBox = document.getElementById('status-box');
scanInput.addEventListener('keypress', function(e){
    if(e.key==='Enter') submitScan();
});
function submitScan(){
    const code = scanInput.value.trim();
    if(!code) return;
    fetch('/scan', {
        method:'POST',
        headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:'code='+encodeURIComponent(code)
    }).then(r=>r.json()).then(data=>{
        scanInput.value='';
        scanInput.focus();
        statusBox.className = 'status ' + data.style;
        statusBox.textContent = data.message;
    });
}

document.getElementById('register-form').addEventListener('submit', function(e){
    e.preventDefault();
    const form = new FormData(this);
    fetch('/register', {
        method:'POST',
        body:form
    }).then(r=>r.json()).then(data=>{
        if(data.success){
            document.getElementById('barcode-result').style.display='block';
            document.getElementById('student-info').textContent = data.info;
            document.getElementById('barcode-img').src = 'data:image/png;base64,' + data.barcode;
            this.reset();
        }else alert('Error: ' + data.error);
    });
});

function loadStudents(){
    fetch('/students').then(r=>r.text()).then(html=>{
        document.getElementById('students-table').innerHTML = html;
    });
}

function showEditForm(id, name, studentNum, dept, year, contact){
    editingStudentId = id;
    document.getElementById('edit-id').value = id;
    document.getElementById('edit-fullname').value = name;
    document.getElementById('edit-studentnum').value = studentNum;
    document.getElementById('edit-dept').value = dept;
    document.getElementById('edit-year').value = year;
    document.getElementById('edit-contact').value = contact || '';
    document.getElementById('edit-form-container').style.display = 'block';
    window.scrollTo({top:document.getElementById('edit-form-container').offsetTop - 20, behavior:'smooth'});
}

function hideEditForm(){
    editingStudentId = null;
    document.getElementById('edit-form-container').style.display = 'none';
    document.getElementById('edit-form').reset();
}

document.getElementById('edit-form').addEventListener('submit', function(e){
    e.preventDefault();
    const form = new FormData(this);
    fetch('/update-student', {
        method:'POST',
        body:form
    }).then(r=>r.json()).then(data=>{
        if(data.success){
            alert('✅ Student info updated!');
            hideEditForm();
            loadStudents();
        }else alert('❌ Error: ' + data.error);
    });
});

function loadRecords(){
    fetch('/records').then(r=>r.text()).then(html=>{
        document.getElementById('records-table').innerHTML = html;
    });
}
document.addEventListener('DOMContentLoaded', ()=>{ loadRecords(); loadStudents(); });

function downloadWord(){
    window.location.href = '/download-word';
}
</script>
</body>
</html>
    """, depts=DEPARTMENTS, years=YEAR_LEVELS)

# ===================== LOGOUT =====================
@app.route('/logout')
def logout():
    resp = make_response("""<script>window.location='/login';</script>""")
    resp.set_cookie('logged_in', '', expires=0)
    return resp

# ===================== SCAN ENDPOINT =====================
@app.route('/scan', methods=['POST'])
def scan():
    if not is_logged_in():
        return jsonify({"message":"Unauthorized","style":"error"})
    code = request.form.get('code', '').strip()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    
    c.execute("SELECT id,full_name,department,year_level FROM users WHERE student_number=?", (code,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"message":f"❌ Not Found: {code}","style":"error"})
    
    uid, name, dept, year = user
    c.execute("SELECT id FROM attendance WHERE user_id=? AND scan_date=? AND time_out IS NULL", (uid, today))
    active = c.fetchone()
    
    if active:
        c.execute("UPDATE attendance SET time_out=? WHERE id=?", 
                 (datetime.datetime.now().isoformat(timespec="seconds"), active[0]))
        msg = f"⏰ TIME OUT — {name} ({dept} | {year})"
        style = "info"
    else:
        c.execute("INSERT INTO attendance (user_id,time_in,scan_date) VALUES (?,?,?)",
                 (uid, datetime.datetime.now().isoformat(timespec="seconds"), today))
        msg = f"✅ TIME IN — {name} ({dept} | {year})"
        style = "success"
    conn.commit()
    conn.close()
    return jsonify({"message":msg,"style":style})

# ===================== REGISTER ENDPOINT =====================
@app.route('/register', methods=['POST'])
def register():
    if not is_logged_in():
        return jsonify({"success":False,"error":"Unauthorized"})
    try:
        data = request.form
        full_name = data.get('full_name','').strip()
        student_number = data.get('student_number','').strip()
        department = data.get('department','')
        year_level = data.get('year_level','')
        contact_number = data.get('contact_number','')
        
        if not full_name or not student_number:
            return jsonify({"success":False,"error":"Missing required fields"})
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE student_number=?", (student_number,))
        if c.fetchone():
            conn.close()
            return jsonify({"success":False,"error":"Student Number already registered!"})
        
        c.execute("""INSERT INTO users 
            (full_name, department, contact_number, year_level, student_number, registered_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (full_name, department, contact_number, year_level, student_number, 
             datetime.datetime.now().isoformat(timespec="seconds")))
        conn.commit()
        
        barcode_b64 = generate_barcode_b64(student_number)
        conn.close()
        
        return jsonify({
            "success": True,
            "info": f"{full_name} | {student_number} | {department} — {year_level}",
            "barcode": barcode_b64
        })
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

# ===================== STUDENTS LIST ENDPOINT =====================
@app.route('/students')
def students_list():
    if not is_logged_in():
        return "<p>Please login first.</p>"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, full_name, student_number, department, year_level, contact_number FROM users ORDER BY full_name")
    students = c.fetchall()
    conn.close()
    
    if not students:
        return "<p style='text-align:center;color:#888;'>No registered students yet.</p>"
    
    html = "<table><tr><th>Name</th><th>Student #</th><th>Dept</th><th>Year</th><th>Contact</th><th>Action</th></tr>"
    for s in students:
        sid, name, num, dept, year, contact = s
        html += f"""<tr>
            <td>{name}</td><td>{num}</td><td>{dept}</td><td>{year}</td>
            <td>{contact or '-'}</td>
            <td><button class='btn-edit' onclick="showEditForm({sid}, '{name}', '{num}', '{dept}', '{year}', '{contact or ''}')">✏️ Edit</button></td>
        </tr>"""
    html += "</table>"
    return html

# ===================== UPDATE STUDENT ENDPOINT =====================
@app.route('/update-student', methods=['POST'])
def update_student():
    if not is_logged_in():
        return jsonify({"success":False,"error":"Unauthorized"})
    try:
        data = request.form
        sid = data.get('id')
        full_name = data.get('full_name','').strip()
        student_number = data.get('student_number','').strip()
        department = data.get('department','')
        year_level = data.get('year_level','')
        contact_number = data.get('contact_number','')
        
        if not sid or not full_name or not student_number:
            return jsonify({"success":False,"error":"Missing required fields"})
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE student_number=? AND id!=?", (student_number, sid))
        if c.fetchone():
            conn.close()
            return jsonify({"success":False,"error":"Student Number already used by another!"})
        
        c.execute("""UPDATE users SET 
            full_name=?, student_number=?, department=?, year_level=?, contact_number=?
            WHERE id=?""",
            (full_name, student_number, department, year_level, contact_number, sid))
        conn.commit()
        conn.close()
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

# ===================== RECORDS ENDPOINT =====================
@app.route('/records')
def records():
    if not is_logged_in():
        return "<p>Please login first.</p>"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT u.full_name, a.scan_date, a.time_in, a.time_out, u.department
                 FROM attendance a JOIN users u ON a.user_id = u.id
                 ORDER BY a.scan_date DESC, a.time_in DESC LIMIT 200""")
    records = c.fetchall()
    conn.close()
    
    if not records:
        return "<p style='text-align:center;color:#888;'>No attendance records yet.</p>"
    
    html = "<table><tr><th>Name</th><th>Date</th><th>Time In</th><th>Time Out</th><th>Dept</th></tr>"
    for r in records:
        name, date, tin, tout, dept = r
        tin_short = tin.split('T')[1][:8] if tin else '-'
        tout_short = tout.split('T')[1][:8] if tout else '-'
        html += f"<tr><td>{name}</td><td>{date}</td><td>{tin_short}</td><td>{tout_short}</td><td>{dept}</td></tr>"
    html += "</table>"
    return html

# ===================== DOWNLOAD WORD ENDPOINT =====================
@app.route('/download-word')
def download_word():
    if not is_logged_in():
        return "Unauthorized", 401
    try:
        from docx import Document
        from docx.shared import Pt
        
        today = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""SELECT u.full_name, a.time_in, a.time_out, u.department
                     FROM attendance a JOIN users u ON a.user_id = u.id
                     WHERE a.scan_date = ? ORDER BY a.time_in""", (today,))
        records = c.fetchall()
        conn.close()
        
        doc = Document()
        doc.add_heading(f'Library Attendance — {today}', 0)
        doc.add_paragraph(f'Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        doc.add_paragraph('')
        
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = '#'
        hdr[1].text = 'Name'
        hdr[2].text = 'Time In'
        hdr[3].text = 'Time Out'
        hdr[4].text = 'Department'
        
        for i, r in enumerate(records, 1):
            name, tin, tout, dept = r
            row = table.add_row().cells
            row[0].text = str(i)
            row[1].text = name
            row[2].text = tin.split('T')[1][:8] if tin else '-'
            row[3].text = tout.split('T')[1][:8] if tout else '-'
            row[4].text = dept
        
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        resp = make_response(buffer.read())
        resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        resp.headers['Content-Disposition'] = f'attachment; filename=attendance_{today}.docx'
        return resp
    except ImportError:
        return "python-docx not installed. Add 'python-docx' to requirements.txt", 500

# ===================== RUN — FOR RENDER =====================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
