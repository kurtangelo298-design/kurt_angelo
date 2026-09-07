from flask import Flask, render_template_string, request, jsonify, make_response
import psycopg2
from psycopg2 import OperationalError
import os
import datetime
import barcode
from barcode.writer import ImageWriter
import base64
from io import BytesIO
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

app = Flask(__name__)

# ===================== DATABASE URL =====================
DATABASE_URL = os.environ.get("DATABASE_URL")

# ===================== LOGIN CREDENTIALS =====================
USERNAME = "slsu"
PASSWORD = "jge"

# ===================== DATABASE CONNECTION =====================
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except OperationalError as e:
        print(f"DB Error: {e}")
        return None

# ===================== DATABASE INIT =====================
def init_db():
    conn = get_db_connection()
    if not conn:
        print("❌ No DB connection")
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
    print("✅ DB Ready")

init_db()

ID_TYPES = ["Student", "Employee", "Visitor"]
DEPARTMENTS = ["CT", "FBT", "BSED", "BEED", "BSFI", "BSBA", "EMPLOYEE"]
YEAR_LEVELS = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "N/A"]

MAJORS = {
    "BSBA": ["Marketing Management", "Financial Management", "Human Resource Development", "Business Management", "Economics"],
    "BSED": ["English", "Mathematics", "Science", "Filipino", "Social Studies", "Values Education"],
    "CT": ["Computer Technology", "Electronics Technology", "Drafting Technology"]
}

def generate_barcode_b64(id_number):
    code128 = barcode.get_barcode_class("code128")
    writer = ImageWriter()
    writer.set_options({"module_width":0.3, "module_height":10, "font_size":8, "text_distance":2})
    img = code128(id_number, writer=writer).render()
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def normalize_text(text):
    return text.strip().lower() if text else ""

def is_logged_in():
    return request.cookies.get('logged_in') == 'true'

# ===================== LOGIN =====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = normalize_text(request.form.get('username', ''))
        pword = request.form.get('password', '').strip()
        if uname == normalize_text(USERNAME) and pword == PASSWORD:
            resp = make_response("<script>window.location='/';</script>")
            resp.set_cookie('logged_in', 'true', max_age=31536000)
            return resp
        return """<html><body style="font-family:Arial;text-align:center;padding-top:100px;background:#f5f5f5;"><h2 style="color:red;">❌ Wrong Credentials!</h2><a href="/login" style="font-size:18px;">Try Again</a></body></html>"""
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
        input,select{width:100%;padding:14px;border:2px solid #eee;border-radius:10px;font-size:16px;}
        button{width:100%;padding:14px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;border-radius:10px;font-size:18px;font-weight:bold;cursor:pointer;}
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
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📚 Library Attendance — SLSU-JGE</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif;}
        body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:20px;}
        .container{max-width:1200px;margin:0 auto;}
        .tabs{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;}
        .tab{padding:12px 20px;background:rgba(255,255,255,0.3);color:white;border:none;border-radius:10px;cursor:pointer;font-weight:bold;transition:0.3s;font-size:16px;}
        .tab:hover{background:rgba(255,255,255,0.5);}
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
        table{width:100%;border-collapse:collapse;margin-top:15px;}
        th,td{padding:10px;text-align:left;border-bottom:1px solid #eee;font-size:14px;}
        th{background:#f8f9fa;font-weight:bold;color:#667eea;}
        .tab-content{display:none;}
        .tab-content.active{display:block;}
        .barcode-img{max-width:300px;margin:15px auto;display:block;}
        .btn-print{background:#28a745;}
        .btn-download{background:#ffc107;color:#333;}
        .btn-edit{background:#f39c12;color:white;padding:5px 10px;font-size:13px;}
        .btn-save{background:#2ecc71;color:white;}
        .btn-cancel{background:#95a5a6;color:white;}
        .logout-btn{background:#dc3545;}
        .edit-form{background:#f8f9fa;padding:20px;border-radius:12px;margin-top:15px;}
        .hidden{display:none !important;}
        .dept-tabs{display:flex;gap:8px;margin:20px 0;flex-wrap:wrap;}
        .dept-tab{padding:8px 15px;background:#eee;color:#333;border:none;border-radius:8px;cursor:pointer;font-weight:600;transition:0.2s;font-size:14px;}
        .dept-tab:hover{background:#ddd;}
        .dept-tab.active{background:#667eea;color:white;}
        .search-box{margin-bottom:15px;}
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Library Attendance — SLSU-JGE</h1>
        <div style="text-align:right;margin-bottom:15px;">
            <button class="logout-btn" onclick="logout()">🚪 Logout</button>
        </div>
        
        <!-- ✅ TABS — ALL WORKING -->
        <div class="tabs">
            <button class="tab active" id="tab-scan" onclick="switchTab('scan')">📱 Scan / Attendance</button>
            <button class="tab" id="tab-register" onclick="switchTab('register')">📇 Register</button>
            <button class="tab" id="tab-students" onclick="switchTab('students')">👥 Students List</button>
            <button class="tab" id="tab-records" onclick="switchTab('records')">📋 Records</button>
            <button class="tab" id="tab-export" onclick="switchTab('export')">📄 Export</button>
        </div>

        <!-- SCAN TAB -->
        <div id="scan" class="tab-content active">
            <div class="card">
                <h2>📱 Scan Barcode</h2>
                <div class="scan-area">
                    <input type="text" id="scan-input" placeholder="Scan or type ID..." autofocus>
                    <div id="status-box" class="status info">Waiting...</div>
                </div>
            </div>
        </div>

        <!-- REGISTER TAB -->
        <div id="register" class="tab-content">
            <div class="card">
                <h2>📇 Register New Student/Visitor</h2>
                <form id="register-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>ID Type</label>
                            <select name="id_type" id="id-type-select">
                                {% for t in id_types %}<option value="{{t}}">{{t}}</option>{% endfor %}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>ID Number</label>
                            <input type="text" name="id_number" required placeholder="ID Number">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group"><label>Full Name</label><input type="text" name="full_name" required></div>
                        <div class="form-group" id="dept-group">
                            <label>Department</label>
                            <select name="department" id="dept-select">
                                {% for d in depts %}<option value="{{d}}">{{d}}</option>{% endfor %}
                            </select>
                        </div>
                    </div>
                    <div class="form-row" id="major-row">
                        <div class="form-group">
                            <label>Major</label>
                            <select name="major" id="major-select"><option value="">-- Select Dept First --</option></select>
                        </div>
                        <div class="form-group" id="year-group">
                            <label>Year Level</label>
                            <select name="year_level" id="year-select">
                                {% for y in years %}<option>{{y}}</option>{% endfor %}
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group"><label>Contact Number</label><input type="text" name="contact_number"></div>
                        <div class="form-group"><label>Address</label><input type="text" name="address"></div>
                    </div>
                    <button type="submit">✅ Register & Generate Barcode</button>
                </form>
                <div id="barcode-result" style="display:none;margin-top:25px;text-align:center;padding:20px;background:#f0f4ff;border-radius:15px;">
                    <h3>✅ Registered!</h3>
                    <p><strong id="student-info"></strong></p>
                    <img id="barcode-img" class="barcode-img"><br>
                    <button class="btn-print" onclick="window.print()">🖨️ Print Barcode</button>
                </div>
            </div>
        </div>

        <!-- STUDENTS LIST TAB -->
        <div id="students" class="tab-content">
            <div class="card">
                <h2>👥 Students List — By Department</h2>
                <div class="search-box">
                    <input type="text" id="search-input" placeholder="🔍 Search Name or ID..." oninput="filterStudents()">
                </div>
                <div class="dept-tabs">
                    <button class="dept-tab active" id="dept-ALL" onclick="switchDept('ALL')">📋 ALL</button>
                    {% for d in depts %}<button class="dept-tab" id="dept-{{d}}" onclick="switchDept('{{d}}')">{{d}}</button>{% endfor %}
                    <button class="dept-tab" id="dept-Visitor" onclick="switchDept('Visitor')">👤 VISITOR</button>
                </div>
                <button onclick="loadStudents()">🔄 Refresh</button>
                <div id="students-table"></div>
                <div id="edit-form-container" class="edit-form hidden">
                    <h3>✏️ Edit Info</h3>
                    <form id="edit-form">
                        <input type="hidden" id="edit-id" name="id">
                        <div class="form-row">
                            <div class="form-group"><label>ID Type</label>
                                <select id="edit-id-type" name="id_type">
                                    {% for t in id_types %}<option value="{{t}}">{{t}}</option>{% endfor %}
                                </select>
                            </div>
                            <div class="form-group"><label>ID Number</label><input type="text" id="edit-idnum" name="id_number" required></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>Full Name</label><input type="text" id="edit-fullname" name="full_name" required></div>
                            <div class="form-group" id="edit-dept-group">
                                <label>Department</label>
                                <select id="edit-dept" name="department">
                                    {% for d in depts %}<option value="{{d}}">{{d}}</option>{% endfor %}
                                </select>
                            </div>
                        </div>
                        <div class="form-row" id="edit-major-row">
                            <div class="form-group"><label>Major</label><select id="edit-major" name="major"></select></div>
                            <div class="form-group"><label>Year Level</label>
                                <select id="edit-year" name="year_level">{% for y in years %}<option>{{y}}</option>{% endfor %}</select>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>Contact</label><input type="text" id="edit-contact" name="contact_number"></div>
                            <div class="form-group"><label>Address</label><input type="text" id="edit-address" name="address"></div>
                        </div>
                        <button type="submit" class="btn-save">💾 Save</button>
                        <button type="button" class="btn-cancel" onclick="hideEditForm()">❌ Cancel</button>
                    </form>
                </div>
            </div>
        </div>

        <!-- RECORDS TAB -->
        <div id="records" class="tab-content">
            <div class="card">
                <h2>📋 Attendance Records</h2>
                <button onclick="loadRecords()">🔄 Refresh</button>
                <div id="records-table"></div>
            </div>
        </div>

        <!-- EXPORT TAB -->
        <div id="export" class="tab-content">
            <div class="card">
                <h2>📄 Export Reports</h2>
                <p>Download today's attendance as Word Document</p>
                <button class="btn-download" onclick="window.location.href='/download-word'">📄 Download Word File</button><br><br>
                <button class="btn-print" onclick="window.print()">🖨️ Print Page</button>
            </div>
        </div>
    </div>

<script>
const ID_TYPES = {{ id_types|tojson }};
const DEPARTMENTS = {{ depts|tojson }};
const YEAR_LEVELS = {{ years|tojson }};
const MAJORS = {
    "BSBA": ["Marketing Management", "Financial Management", "Human Resource Development", "Business Management", "Economics"],
    "BSED": ["English", "Mathematics", "Science", "Filipino", "Social Studies", "Values Education"],
    "CT": ["Computer Technology", "Electronics Technology", "Drafting Technology"]
};

let editingStudentId = null;
let currentDept = "ALL";
let allStudents = [];

// ✅ LOGOUT FUNCTION
function logout(){
    document.cookie = "logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    window.location.href = "/login";
}

// ✅ TAB SWITCH — FULLY FIXED!
function switchTab(tabId){
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');
    document.getElementById(tabId).classList.add('active');
    
    if(tabId === 'scan') setTimeout(()=>document.getElementById('scan-input')?.focus(), 100);
    if(tabId === 'students') loadStudents();
    if(tabId === 'records') loadRecords();
}

// ✅ DEPARTMENT SWITCH
function switchDept(dept){
    document.querySelectorAll('.dept-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('dept-' + dept).classList.add('active');
    currentDept = dept;
    filterStudents();
}

// ✅ UPDATE MAJOR OPTIONS
function updateMajorOptions(deptSelectId, majorSelectId, yearSelectId){
    const dept = document.getElementById(deptSelectId).value;
    const majorSelect = document.getElementById(majorSelectId);
    const yearSelect = document.getElementById(yearSelectId);
    majorSelect.innerHTML = '<option value="">-- Select --</option>';
    
    if(dept === 'Visitor' || dept === 'EMPLOYEE'){
        yearSelect.value = 'N/A';
        yearSelect.disabled = true;
    } else {
        yearSelect.disabled = false;
        if(MAJORS[dept]){
            MAJORS[dept].forEach(m => {
                const opt = document.createElement('option');
                opt.value = m; opt.textContent = m;
                majorSelect.appendChild(opt);
            });
        }
    }
}

// ✅ SCAN FUNCTIONS
function submitScan(){
    const idNumber = document.getElementById('scan-input').value.trim();
    if(!idNumber) return;
    
    fetch('/scan', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id_number: idNumber})
    })
    .then(r => r.json())
    .then(data => {
        const box = document.getElementById('status-box');
        box.className = 'status ' + (data.success ? 'success' : 'error');
        box.textContent = data.message;
        document.getElementById('scan-input').value = '';
    })
    .catch(err => {
        document.getElementById('status-box').className = 'status error';
        document.getElementById('status-box').textContent = 'Error: ' + err;
    });
}

// ✅ LOAD STUDENTS
function loadStudents(){
    fetch('/get-students')
    .then(r => r.json())
    .then(data => {
        allStudents = data.students || [];
        filterStudents();
    });
}

// ✅ FILTER STUDENTS
function filterStudents(){
    const search = document.getElementById('search-input')?.value.toLowerCase() || '';
    let filtered = allStudents;
    
    if(currentDept !== 'ALL'){
        filtered = filtered.filter(s => s.department === currentDept || (currentDept === 'Visitor' && s.id_type === 'Visitor'));
    }
    if(search){
        filtered = filtered.filter(s => 
            s.full_name.toLowerCase().includes(search) || 
            s.id_number.toLowerCase().includes(search)
        );
    }
    
    const table = document.getElementById('students-table');
    if(!filtered.length){
        table.innerHTML = '<p style="text-align:center;color:#666;padding:20px;">No records found.</p>';
        return;
    }
    
    table.innerHTML = '<table><tr><th>ID No.</th><th>Name</th><th>Type</th><th>Dept</th><th>Action</th></tr>' +
        filtered.map(s => `
            <tr>
                <td>${s.id_number}</td>
                <td>${s.full_name}</td>
                <td>${s.id_type}</td>
                <td>${s.department || '-'}</td>
                <td><button class="btn-edit" onclick="editStudent(${s.id})">✏️ Edit</button></td>
            </tr>
        `).join('') + '</table>';
}

// ✅ EDIT STUDENT
function editStudent(id){
    const student = allStudents.find(s => s.id === id);
    if(!student) return;
    editingStudentId = id;
    
    document.getElementById('edit-id').value = student.id;
    document.getElementById('edit-id-type').value = student.id_type;
    document.getElementById('edit-idnum').value = student.id_number;
    document.getElementById('edit-fullname').value = student.full_name;
    document.getElementById('edit-dept').value = student.department || '';
    document.getElementById('edit-major').value = student.major || '';
    document.getElementById('edit-year').value = student.year_level || '';
    document.getElementById('edit-contact').value = student.contact_number || '';
    document.getElementById('edit-address').value = student.address || '';
    
    document.getElementById('edit-form-container').classList.remove('hidden');
    window.scrollTo(0, document.getElementById('edit-form-container').offsetTop);
}

// ✅ HIDE EDIT FORM
function hideEditForm(){
    document.getElementById('edit-form-container').classList.add('hidden');
    editingStudentId = null;
    document.getElementById('edit-form').reset();
}

// ✅ LOAD RECORDS
function loadRecords(){
    fetch('/get-records')
    .then(r => r.json())
    .then(data => {
        const records = data.records || [];
        const table = document.getElementById('records-table');
        if(!records.length){
            table.innerHTML = '<p style="text-align:center;color:#666;padding:20px;">No attendance records yet.</p>';
            return;
        }
        table.innerHTML = '<table><tr><th>Date</th><th>Name</th><th>ID No.</th><th>Time In</th><th>Time Out</th></tr>' +
            records.map(r => `
                <tr>
                    <td>${r.scan_date}</td>
                    <td>${r.full_name}</td>
                    <td>${r.id_number}</td>
                    <td>${r.time_in || '-'}</td>
                    <td>${r.time_out || '-'}</td>
                </tr>
            `).join('') + '</table>';
    });
}

// ✅ INITIALIZE EVERYTHING ON PAGE LOAD
document.addEventListener('DOMContentLoaded', function(){
    // Scan input Enter key
    const scanInput = document.getElementById('scan-input');
    if(scanInput){
        scanInput.addEventListener('keypress', function(e){
            if(e.key === 'Enter') submitScan();
        });
    }

    // Register form submit
    const regForm = document.getElementById('register-form');
    if(regForm){
        document.getElementById('dept-select').addEventListener('change', function(){
            updateMajorOptions('dept-select', 'major-select', 'year-select');
        });
        
        regForm.addEventListener('submit', function(e){
            e.preventDefault();
            const form = new FormData(this);
            fetch('/register', {method: 'POST', body: form})
            .then(r => r.json())
            .then(data => {
                if(data.success){
                    document.getElementById('barcode-result').style.display = 'block';
                    document.getElementById('student-info').textContent = data.info;
                    document.getElementById('barcode-img').src = 'data:image/png;base64,' + data.barcode;
                    regForm.reset();
                    document.getElementById('major-select').innerHTML = '<option value="">-- Select Dept First --</option>';
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(err => alert('Error: ' + err));
        });
    }

    // Edit form submit
    const editForm = document.getElementById('edit-form');
    if(editForm){
        document.getElementById('edit-dept').addEventListener('change', function(){
            updateMajorOptions('edit-dept', 'edit-major', 'edit-year');
        });
        
        editForm.addEventListener('submit', function(e){
            e.preventDefault();
            const form = new FormData(this);
            fetch('/update-student', {method: 'POST', body: form})
            .then(r => r.json())
            .then(d => {
                if(d.success){
                    alert('✅ Updated successfully!');
                    hideEditForm();
                    loadStudents();
                } else {
                    alert('❌ Error: ' + d.error);
                }
            })
            .catch(err => alert('Error: ' + err));
        });
    }
});
</script>
</body>
</html>
    """, id_types=ID_TYPES, depts=DEPARTMENTS, years=YEAR_LEVELS)

# ===================== SCAN ENDPOINT =====================
@app.route('/scan', methods=['POST'])
def scan():
    if not is_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.get_json()
    id_number = data.get('id_number', '').strip()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database error"}), 500
    
    c = conn.cursor()
    today = datetime.date.today().strftime("%Y-%m-%d")
    now = datetime.datetime.now().strftime("%I:%M:%S %p")
    
    c.execute("SELECT id, full_name, id_number FROM users WHERE LOWER(id_number) = LOWER(%s)", (id_number,))
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
        return jsonify({"success": True, "message": f"✅ IN: {full_name} — {now}"})
    else:
        c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"✅ OUT: {full_name} — {now}"})

# ===================== REGISTER ENDPOINT =====================
@app.route('/register', methods=['POST'])
def register():
    if not is_logged_in():
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    id_type = request.form.get('id_type', '').strip()
    full_name = request.form.get('full_name', '').strip()
    department = request.form.get('department', '').strip() or None
    major = request.form.get('major', '').strip() or None
    contact_number = request.form.get('contact_number', '').strip() or None
    address = request.form.get('address', '').strip() or None
    year_level = request.form.get('year_level', '').strip() or None
    id_number = request.form.get('id_number', '').strip().upper()
    registered_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not all([id_type, full_name, id_number]):
        return jsonify({"success": False, "error": "Missing required fields"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    
    c = conn.cursor()
    try:
        c.execute("""INSERT INTO users 
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at))
        conn.commit()
        
        barcode_b64 = generate_barcode_b64(id_number)
        info = f"{full_name} | ID: {id_number} | {id_type}"
        
        return jsonify({"success": True, "info": info, "barcode": barcode_b64})
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({"success": False, "error": "ID Number already exists!"}), 400
    finally:
        conn.close()

# ===================== GET STUDENTS =====================
@app.route('/get-students')
def get_students():
    if not is_logged_in():
        return jsonify({"students": []})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"students": []})
    
    c = conn.cursor()
    c.execute("SELECT id, id_type, full_name, department, id_number FROM users ORDER BY full_name")
    students = [
        {
            "id": row[0],
            "id_type": row[1],
            "full_name": row[2],
            "department": row[3],
            "id_number": row[4]
        }
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify({"students": students})

# ===================== UPDATE STUDENT =====================
@app.route('/update-student', methods=['POST'])
def update_student():
    if not is_logged_in():
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
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
        return jsonify({"success": False, "error": "Missing required fields"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database error"}), 500
    
    c = conn.cursor()
    try:
        c.execute("""UPDATE users SET 
            id_type = %s, id_number = %s, full_name = %s, department = %s, 
            major = %s, contact_number = %s, address = %s, year_level = %s
            WHERE id = %s""",
            (id_type, id_number, full_name, department, major, contact_number, address, year_level, student_id))
        conn.commit()
        return jsonify({"success": True})
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({"success": False, "error": "ID Number already exists!"}), 400
    finally:
        conn.close()

# ===================== GET RECORDS =====================
@app.route('/get-records')
def get_records():
    if not is_logged_in():
        return jsonify({"records": []})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"records": []})
    
    c = conn.cursor()
    c.execute("""
        SELECT a.scan_date, u.full_name, u.id_number, a.time_in, a.time_out
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.scan_date DESC, a.id DESC LIMIT 100
    """)
    records = [
        {
            "scan_date": row[0],
            "full_name": row[1],
            "id_number": row[2],
            "time_in": row[3],
            "time_out": row[4]
        }
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify({"records": records})

# ===================== DOWNLOAD WORD =====================
@app.route('/download-word')
def download_word():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    
    conn = get_db_connection()
    if not conn:
        return "Database error"
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    c = conn.cursor()
    c.execute("""
        SELECT u.full_name, u.id_number, a.time_in, a.time_out
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.scan_date = %s
        ORDER BY a.id
    """, (today,))
    records = c.fetchall()
    conn.close()
    
    doc = Document()
    doc.add_heading(f'Library Attendance Report — {today}', 0)
    doc.add_paragraph(f'Generated on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    doc.add_paragraph('=' * 50)
    
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Name'
    hdr_cells[1].text = 'ID Number'
    hdr_cells[2].text = 'Time In'
    hdr_cells[3].text = 'Time Out'
    
    for rec in records:
        row_cells = table.add_row().cells
        row_cells[0].text = rec[0]
        row_cells[1].text = rec[1]
        row_cells[2].text = rec[2] or '-'
        row_cells[3].text = rec[3] or '-'
    
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Disposition'] = f'attendance_report_{today}.docx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return response

if __name__ == '__main__':
    app.run(debug=True)
