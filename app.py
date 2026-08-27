from flask import Flask, render_template_string, request, jsonify, make_response
import sqlite3
import datetime
import barcode
from barcode.writer import ImageWriter
import base64
from io import BytesIO

app = Flask(__name__)
DB_FILE = "library_attendance.db"

def ph_now():
    utc_now = datetime.datetime.utcnow()
    ph_offset = datetime.timedelta(hours=8)
    return utc_now + ph_offset

def ph_date():
    return ph_now().date().isoformat()

def ph_datetime_str():
    return ph_now().isoformat(timespec="seconds")

USERNAME = "slsu"
PASSWORD = "jge"

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

DEPARTMENTS = ["CT", "FBT", "BSED", "BEED", "BSFI", "BSBA", "EMPLOYEE"]
YEAR_LEVELS = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "N/A"]

def generate_barcode_b64(student_number):
    code128 = barcode.get_barcode_class("code128")
    writer = ImageWriter()
    writer.set_options({"module_width":0.25, "module_height":6, "font_size":10, "text_distance":1.5})
    img = code128(student_number, writer=writer).render()
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def is_logged_in():
    return request.cookies.get('logged_in') == 'true'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form.get('username', '').strip()
        pword = request.form.get('password', '').strip()
        if uname == USERNAME and pword == PASSWORD:
            resp = make_response("""<script>window.location='/';</script>""")
            resp.set_cookie('logged_in', 'true', max_age=86400)
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

@app.route('/')
def home():
    if not is_logged_in():
        return """<script>window.location='/login';</script>"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📚 Library Attendance System</title>
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
        .barcode-img{max-width:220px;margin:15px auto;display:block;}
        .btn-print{background:#28a745;}
        .btn-download{background:#ffc107;color:#333;}
        .logout{background:#dc3545;}
        @media print{
            body *{visibility:hidden;}
            .print-barcode-area, .print-barcode-area *{visibility:visible;}
            .print-barcode-area{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);text-align:center;}
            .barcode-img{max-width:180px !important;}
            @page{size:3in 1in;margin:0;}
        }
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
                    <div class="print-barcode-area">
                        <img id="barcode-img" class="barcode-img">
                    </div>
                    <br>
                    <button class="btn-print" onclick="window.print()">🖨️ Print Barcode</button>
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
function showTab(name){
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById(name).classList.add('active');
    if(name==='scan') setTimeout(()=>document.getElementById('scan-input').focus(),100);
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

function loadRecords(){
    fetch('/records').then(r=>r.text()).then(html=>{
        document.getElementById('records-table').innerHTML = html;
    });
}
document.addEventListener('DOMContentLoaded', loadRecords);

function downloadWord(){
    window.location.href = '/download-word';
}
</script>
</body>
</html>
    """, depts=DEPARTMENTS, years=YEAR_LEVELS)

@app.route('/logout')
def logout():
    resp = make_response("""<script>window.location='/login';</script>""")
    resp.set_cookie('logged_in', '', expires=0)
    return resp

@app.route('/scan', methods=['POST'])
def scan():
    if not is_logged_in():
        return jsonify({"message":"Unauthorized","style":"error"})
    code = request.form.get('code', '').strip()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    today = ph_date()
    
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
                 (ph_datetime_str(), active[0]))
        msg = f"⏰ TIME OUT — {name} ({dept} | {year})"
        style = "info"
    else:
        c.execute("INSERT INTO attendance (user_id,time_in,scan_date) VALUES (?,?,?)",
                 (uid, ph_datetime_str(), today))
        msg = f"✅ TIME IN — {name} ({dept} | {year})"
        style = "success"
    conn.commit()
    conn.close()
    return jsonify({"message":msg,"style":style})

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
        c.execute("INSERT INTO users (full_name,department,contact_number,year_level,student_number,registered_at) VALUES (?,?,?,?,?,?)",
                 (full_name, department, contact_number, year_level, student_number, ph_datetime_str()))
        conn.commit()
        conn.close()
        
        barcode_b64 = generate_barcode_b64(student_number)
        return jsonify({"success":True,
                       "info":f"{full_name} | {department} | {year_level} | ID: {student_number}",
                       "barcode":barcode_b64})
    except sqlite3.IntegrityError:
        return jsonify({"success":False,"error":"Student Number already exists!"})

@app.route('/records')
def records():
    if not is_logged_in():
        return "<h2>Unauthorized</h2>"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT users.full_name, users.department, attendance.time_in, attendance.time_out, attendance.scan_date
                 FROM attendance JOIN users ON users.id = attendance.user_id
                 ORDER BY attendance.id DESC LIMIT 100""")
    rows = c.fetchall()
    conn.close()
    html = "<table><tr><th>Name</th><th>Dept</th><th>Time In</th><th>Time Out</th><th>Date</th></tr>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2] or '-'}</td><td>{r[3] or '-'}</td><td>{r[4]}</td></tr>"
    html += "</table>"
    return html

@app.route('/download-word')
def download_word():
    if not is_logged_in():
        return "Unauthorized"
    
    try:
        from docx import Document
    except ImportError:
        return "⚠️ python-docx not installed."
    
    today = ph_date()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT users.full_name, users.department, attendance.time_in, attendance.time_out
                 FROM attendance JOIN users ON users.id = attendance.user_id
                 WHERE attendance.scan_date = ? ORDER BY attendance.id DESC""", (today,))
    rows = c.fetchall()
    conn.close()
    
    doc = Document()
    doc.add_heading(f'Library Attendance Report — {today}', 0)
    doc.add_paragraph(f'Generated on: {ph_datetime_str()}')
    doc.add_paragraph('=' * 50)
    
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Name'
    hdr_cells[1].text = 'Department'
    hdr_cells[2].text = 'Time In'
    hdr_cells[3].text = 'Time Out'
    
    for r in rows:
        row_cells = table.add_row().cells
        row_cells[0].text = r[0]
        row_cells[1].text = r[1]
        row_cells[2].text = r[2] or '-'
        row_cells[3].text = r[3] or '-'
    
    filename = f"attendance_{today}.docx"
    from io import BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
