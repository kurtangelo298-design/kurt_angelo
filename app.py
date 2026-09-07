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

# ===================== MAIN PAGE — FIXED BUTTONS! =====================
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
        .logout{background:#dc3545;}
        .edit-form{background:#f8f9fa;padding:20px;border-radius:12px;margin-top:15px;}
        .hidden{display:none !important;}
        .dept-tabs{display:flex;gap:8px;margin:20px 0;flex-wrap:wrap;}
        .dept-tab{padding:8px 15px;background:#eee;color:#333;border:none;border-radius:8px;cursor:pointer;font-weight:600;transition:0.2s;font-size:14px;}
        .dept-tab:hover{background:#ddd;}
        .dept-tab.active{background:#667eea;color:white;}
        .search-box{margin-bottom:15px;}
        #search-input{max-width:400px;}
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Library Attendance — SLSU-JGE</h1>
        <div style="text-align:right;margin-bottom:15px;"><button class="logout" id="logout-btn">🚪 Logout</button></div>
        
        <!-- ✅ TABS — FIXED CLICK EVENT -->
        <div class="tabs">
            <button class="tab active" data-tab="scan" onclick="switchTab('scan')">📱 Scan / Attendance</button>
            <button class="tab" data-tab="register" onclick="switchTab('register')">📇 Register</button>
            <button class="tab" data-tab="students" onclick="switchTab('students')">👥 Students List</button>
            <button class="tab" data-tab="records" onclick="switchTab('records')">📋 Records</button>
            <button class="tab" data-tab="export" onclick="switchTab('export')">📄 Export</button>
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
                    <button class="dept-tab active" data-dept="ALL" onclick="switchDept('ALL')">📋 ALL</button>
                    {% for d in depts %}<button class="dept-tab" data-dept="{{d}}" onclick="switchDept('{{d}}')">{{d}}</button>{% endfor %}
                    <button class="dept-tab" data-dept="Visitor" onclick="switchDept('Visitor')">👤 VISITOR</button>
                </div>
                <button id="refresh-students" onclick="loadStudents()">🔄 Refresh</button>
                <div id="students-table"></div>
                <div id="edit-form-container" class="edit-form" style="display:none;">
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
                        <button type="button" class="btn-cancel" id="cancel-edit" onclick="hideEditForm()">❌ Cancel</button>
                    </form>
                </div>
            </div>
        </div>

        <!-- RECORDS TAB -->
        <div id="records" class="tab-content">
            <div class="card">
                <h2>📋 Attendance Records</h2>
                <button id="refresh-records" onclick="loadRecords()">🔄 Refresh</button>
                <div id="records-table"></div>
            </div>
        </div>

        <!-- EXPORT TAB -->
        <div id="export" class="tab-content">
            <div class="card">
                <h2>📄 Export Reports</h2>
                <p>Download today's attendance as Word Document</p>
                <button class="btn-download" id="download-btn" onclick="window.location.href='/download-word'">📄 Download Word File</button><br><br>
                <button class="btn-print" onclick="window.print()">🖨️ Print Page</button>
            </div>
        </div>
    </div>

<script>
const MAJORS = {
    "BSBA": ["Marketing Management", "Financial Management", "HRD", "Business Management", "Economics"],
    "BSED": ["English", "Math", "Science", "Filipino", "Social Studies", "Values Ed"],
    "CT": ["Computer Tech", "Electronics Tech", "Drafting Tech"]
};

let editingStudentId = null;
let currentDept = "ALL";

// ✅ SIMPLE & DIRECT TAB SWITCH — WALANG ERROR!
function switchTab(tabId){
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector([data-tab="${tabId}"]).classList.add('active');
    document.getElementById(tabId).classList.add('active');
    
    if(tabId === 'scan') setTimeout(()=>document.getElementById('scan-input')?.focus(), 100);
    if(tabId === 'students') loadStudents();
    if(tabId === 'records') loadRecords();
}

// ✅ DEPARTMENT SWITCH
function switchDept(dept){
    document.querySelectorAll('.dept-tab').forEach(t => t.classList.remove('active'));
    document.querySelector([data-dept="${dept}"]).classList.add('active');
    currentDept = dept;
    filterStudents();
}

// ========== SCAN ==========
document.addEventListener('DOMContentLoaded', function(){
    const scanInput = document.getElementById('scan-input');
    if(scanInput){
        scanInput.addEventListener('keypress', function(e){
            if(e.key === 'Enter') submitScan();
        });
    }

    // ========== REGISTER FORM ==========
    const regForm = document.getElementById('register-form');
    if(regForm){
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
                    e.target.reset();
                    updateFormFields();
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(err => alert('Error: ' + err));
        });
    }

    // ========== EDIT FORM ==========
    const editForm = document.getElementById('edit-form');
    if(editForm){
        editForm.addEventListener('submit', function(e){
            e.preventDefault();
            const form = new FormData(this);
            fetch('/update-student', {method: 'POST', body: form})
            .then(r => r.json())
            .then(d => {
                if(d.success){
                    alert('✅ Updated!');
                    hideEditForm();
                    loadStudents();
                } else {
                    alert('❌ Error: ' + d.error);
                }
            });
        });
    }

    // ========== LOGOUT ==========
    const logoutBtn = document.getElementById('logout-btn');
    if(logoutBtn){
        logoutBtn.addEventListener('click', ()=>window.location.href='/logout');
    }

    // ========== DROPDOWN LOGIC ==========
    const idTypeSelect = document.getElementById('id-type-select');
    if(idTypeSelect) idTypeSelect.addEventListener('change', updateFormFields);
    
    const deptSelect = document.getElementById('dept-select');
    if(deptSelect) deptSelect.addEventListener('change', updateMajorOptions);
    
    const editIdType = document.getElementById('edit-id-type');
    if(editIdType) editIdType.addEventListener('change', updateEditFormFields);
    
    const editDept = document.getElementById('edit-dept');
    if(editDept) editDept.addEventListener('change', updateEditMajorOptions);

    // INIT
    updateFormFields();
    loadRecords();
    loadStudents();
});

function submitScan(){
    const code = document.getElementById('scan-input').value.trim();
    if(!code) return;
    fetch('/scan', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'code=' + encodeURIComponent(code)
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('scan-input').value = '';
        document.getElementById('scan-input').focus();
        const box = document.getElementById('status-box');
        box.className = 'status ' + data.style;
        box.textContent = data.message;
    });
}

function updateFormFields(){
    const type = document.getElementById('id-type-select').value;
    if(type === 'Student'){
        document.getElementById('dept-group').classList.remove('hidden');
        document.getElementById('major-row').classList.remove('hidden');
        document.getElementById('year-group').classList.remove('hidden');
    } else {
        document.getElementById('dept-group').classList.add('hidden');
        document.getElementById('major-row').classList.add('hidden');
        document.getElementById('year-group').classList.add('hidden');
    }
    updateMajorOptions();
}

function updateMajorOptions(){
    const dept = document.getElementById('dept-select').value;
    const sel = document.getElementById('major-select');
    sel.innerHTML = '<option value="">-- Select --</option>';
    if(MAJORS[dept]){
        MAJORS[dept].forEach(m => {
            sel.innerHTML += <option value="${m}">${m}</option>;
        });
    }
}

function updateEditFormFields(){
    const type = document.getElementById('edit-id-type').value;
    if(type === 'Student'){
        document.getElementById('edit-dept-group').classList.remove('hidden');
        document.getElementById('edit-major-row').classList.remove('hidden');
    } else {
        document.getElementById('edit-dept-group').classList.add('hidden');
        document.getElementById('edit-major-row').classList.add('hidden');
    }
    updateEditMajorOptions();
}

function updateEditMajorOptions(){
    const dept = document.getElementById('edit-dept').value;
    const sel = document.getElementById('edit-major');
    sel.innerHTML = '<option value="">-- Select --</option>';
    if(MAJORS[dept]){
        MAJORS[dept].forEach(m => {
            sel.innerHTML += <option value="${m}">${m}</option>;
        });
    }
}

function loadStudents(){
    fetch('/students')
    .then(r => r.text())
    .then(h => {
        document.getElementById('students-table').innerHTML = h;
        filterStudents();
    });
}

function filterStudents(){
    const search = document.getElementById('search-input').value.toLowerCase().trim();
    const table = document.getElementById('students-table').querySelector('table');
    if(!table) return;
    const rows = table.tBodies[0]?.rows || [];
    for(let row of rows){
        const name = (row.cells[1]?.textContent || '').toLowerCase();
        const id = (row.cells[4]?.textContent || '').toLowerCase();
        const dept = row.getAttribute('data-dept') || '';
        const matchSearch = !search || name.includes(search) || id.includes(search);
        const matchDept = currentDept === 'ALL' || dept.includes(currentDept);
        row.style.display = (matchSearch && matchDept) ? '' : 'none';
    }
}

function showEditForm(id, type, name, num, dept, major, year, contact, addr){
    editingStudentId = id;
    document.getElementById('edit-id').value = id;
    document.getElementById('edit-id-type').value = type;
    document.getElementById('edit-fullname').value = name;
    document.getElementById('edit-idnum').value = num;
    document.getElementById('edit-dept').value = dept || '';
    document.getElementById('edit-major').value = major || '';
    document.getElementById('edit-year').value = year || '';
    document.getElementById('edit-contact').value = contact || '';
    document.getElementById('edit-address').value = addr || '';
    updateEditFormFields();
    document.getElementById('edit-form-container').style.display = 'block';
}

function hideEditForm(){
    editingStudentId = null;
    document.getElementById('edit-form-container').style.display = 'none';
}

function loadRecords(){
    fetch('/records')
    .then(r => r.text())
    .then(h => document.getElementById('records-table').innerHTML = h);
}
</script>
</body>
</html>
    """, id_types=ID_TYPES, depts=DEPARTMENTS, years=YEAR_LEVELS)

# ===================== LOGOUT =====================
@app.route('/logout')
def logout():
    resp = make_response("<script>window.location='/login';</script>")
    resp.set_cookie('logged_in', '', expires=0)
    return resp

# ===================== SCAN — TIME IN / OUT =====================
@app.route('/scan', methods=['POST'])
def scan():
    if not is_logged_in():
        return jsonify({"message":"Unauthorized","style":"error"})
    code = request.form.get('code', '').strip()
    conn = get_db_connection()
    if not conn:
        return jsonify({"message":"❌ DB Error","style":"error"})
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    c.execute("SELECT id,id_type,full_name,department FROM users WHERE LOWER(id_number) = LOWER(%s)", (code,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"message":f"❌ Not Found: {code}","style":"error"})
    uid, id_type, name, dept = user
    c.execute("SELECT id FROM attendance WHERE user_id = %s AND scan_date = %s AND time_out IS NULL", (uid, today))
    active = c.fetchone()
    now_time = datetime.datetime.now().strftime("%I:%M %p")
    if active:
        c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now_time, active[0]))
        msg = f"⏰ TIME OUT — {name} ({dept or id_type}) at {now_time}"
        style = "info"
    else:
        c.execute("INSERT INTO attendance (user_id, time_in, scan_date) VALUES (%s, %s, %s)", (uid, now_time, today))
        msg = f"✅ TIME IN — {name} ({dept or id_type}) at {now_time}"
        style = "success"
    conn.commit()
    conn.close()
    return jsonify({"message":msg,"style":style})

# ===================== REGISTER =====================
@app.route('/register', methods=['POST'])
def register():
    if not is_logged_in():
        return jsonify({"success":False,"error":"Unauthorized"})
    try:
        id_type = request.form.get('id_type','')
        id_number = request.form.get('id_number','').strip()
        full_name = request.form.get('full_name','').strip()
        department = request.form.get('department','') if id_type == 'Student' else None
        major = request.form.get('major','') if id_type == 'Student' else None
        year_level = request.form.get('year_level','') if id_type == 'Student' else None
        contact_number = request.form.get('contact_number','')
        address = request.form.get('address','')
        registered_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not full_name or not id_number or not id_type:
            return jsonify({"success":False,"error":"Fill all required fields!"})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success":False,"error":"DB Connection Failed!"})
        c = conn.cursor()
        c.execute("""INSERT INTO users 
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                  (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at))
        conn.commit()
        conn.close()
        barcode_b64 = generate_barcode_b64(id_number)
        return jsonify({"success":True,"info":f"{full_name} | {id_type} | {id_number}","barcode":barcode_b64})
    except psycopg2.IntegrityError:
        return jsonify({"success":False,"error":"ID Number already exists!"})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

# ===================== STUDENTS LIST =====================
@app.route('/students')
def students_list():
    if not is_logged_in(): return "Unauthorized"
    conn = get_db_connection()
    if not conn: return "DB Connection Failed"
    c = conn.cursor()
    c.execute("SELECT id, id_type, full_name, department, major, year_level, id_number, contact_number, address FROM users ORDER BY full_name")
    students = c.fetchall()
    conn.close()
    html = """<table><thead><tr><th>Type</th><th>Name</th><th>Dept/Major</th><th>Year</th><th>ID No.</th><th>Contact</th><th>Action</th></tr></thead><tbody>"""
    for s in students:
        dept_major = f"{s[3]} — {s[4]}" if s[4] else (s[3] or '-')
        html += f"""<tr data-dept="{s[3] or s[1]}">
            <td>{s[1]}</td>
            <td>{s[2]}</td>
            <td>{dept_major}</td>
            <td>{s[5] or '-'}</td>
            <td>{s[6]}</td>
            <td>{s[7] or '-'}</td>
            <td><button class="btn-edit" onclick="showEditForm({s[0]}, '{s[1]}', '{s[2].replace("'","\\'")}', '{s[6]}', '{s[3] or ""}', '{s[4] or ""}', '{s[5] or ""}', '{s[7] or ""}', '{s[8] or ""}')">✏️ Edit</button></td>
            </tr>"""
    html += "</tbody></table>"
    return html

# ===================== UPDATE STUDENT =====================
@app.route('/update-student', methods=['POST'])
def update_student():
    if not is_logged_in():
        return jsonify({"success":False,"error":"Unauthorized"})
    try:
        sid = request.form.get('id')
        id_type = request.form.get('id_type','')
        id_number = request.form.get('id_number','').strip()
        full_name = request.form.get('full_name','').strip()
        department = request.form.get('department','') if id_type == 'Student' else None
        major = request.form.get('major','') if id_type == 'Student' else None
        year_level = request.form.get('year_level','') if id_type == 'Student' else None
        contact_number = request.form.get('contact_number','')
        address = request.form.get('address','')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"success":False,"error":"DB Connection Failed!"})
        c = conn.cursor()
        c.execute("""UPDATE users SET id_type = %s, full_name = %s, id_number = %s, department = %s, major = %s, year_level = %s, contact_number = %s, address = %s WHERE id = %s""",
                  (id_type, full_name, id_number, department, major, year_level, contact_number, address, sid))
        conn.commit()
        conn.close()
        return jsonify({"success":True})
    except psycopg2.IntegrityError:
        return jsonify({"success":False,"error":"ID Number already exists!"})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

# ===================== ATTENDANCE RECORDS =====================
@app.route('/records')
def records():
    if not is_logged_in(): return "Unauthorized"
    today = datetime.date.today().isoformat()
    conn = get_db_connection()
    if not conn: return "DB Connection Failed"
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_type, u.department, a.time_in, a.time_out 
        FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.scan_date = %s ORDER BY a.id DESC""", (today,))
    recs = c.fetchall()
    conn.close()
    html = f"<h3>Today: {today}</h3><table><tr><th>Name</th><th>Type</th><th>Dept</th><th>Time In</th><th>Time Out</th></tr>"
    for r in recs:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2] or '-'}</td><td>{r[3]}</td><td>{r[4] or '-'}</td></tr>"
    html += "</table>"
    return html

# ===================== EXPORT TO WORD =====================
@app.route('/download-word')
def download_word():
    if not is_logged_in(): return "Unauthorized"
    today = datetime.date.today().isoformat()
    conn = get_db_connection()
    if not conn: return "DB Connection Failed"
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_type, u.department, a.time_in, a.time_out 
        FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.scan_date = %s ORDER BY a.id DESC""", (today,))
    recs = c.fetchall()
    conn.close()
    doc = Document()
    doc.add_heading(f'Library Attendance — {today}', 0)
    doc.add_paragraph(f'Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    doc.add_paragraph('')
    table = doc.add_table(rows=1, cols=5)
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    hdr[0].text='Name';hdr[1].text='Type';hdr[2].text='Department';hdr[3].text='Time In';hdr[4].text='Time Out'
    for r in recs:
        row = table.add_row().cells
        row[0].text=r[0];row[1].text=r[1];row[2].text=r[2] or '-';row[3].text=r[3];row[4].text=r[4] or '-'
    buffer = BytesIO()
    doc.save(buffer); buffer.seek(0)
    resp = make_response(buffer.read())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    resp.headers['Content-Disposition'] = f'attachment; filename=attendance_{today}.docx'
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
