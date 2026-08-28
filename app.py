from flask import Flask, render_template_string, request, session, redirect, url_for
import sqlite3
import datetime
import os

app = Flask(__name__)
app.secret_key = "supersecretkey12345"
DB_FILE = "library.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            department TEXT NOT NULL,
            contact_number TEXT,
            year_level TEXT,
            student_number TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            barcode_id TEXT NOT NULL,
            in_time TIMESTAMP,
            out_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

def normalize_text(text):
    if text:
        return text.strip().lower()
    return ""

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Library Attendance System</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f0f4f8; min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); width: 100%; max-width: 360px; text-align: center; }
        h1 { color: #2c3e50; margin-bottom: 30px; font-size: 24px; }
        button { width: 100%; padding: 14px; margin: 8px 0; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; transition: 0.2s; }
        .btn-login { background: #3498db; color: white; }
        .btn-register { background: #2ecc71; color: white; }
        button:hover { opacity: 0.9; transform: translateY(-1px); }
    </style>
</head>
<body>
    <div class="box">
        <h1>📚 Library Attendance</h1>
        <button class="btn-login" onclick="window.location.href='/login'">🔐 Login</button>
        <button class="btn-register" onclick="window.location.href='/register'">📝 Register</button>
    </div>
</body>
</html>
    """)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.form
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            norm_username = normalize_text(data['username'])
            norm_studentnum = normalize_text(data['student_number'])
            
            c.execute("SELECT id FROM users WHERE LOWER(username) = ? OR LOWER(student_number) = ?",
                     (norm_username, norm_studentnum))
            if c.fetchone():
                conn.close()
                return "<p style='color:red;text-align:center;'>❌ Username or Student Number already exists! <a href='/register'>Go back</a></p>"
            
            c.execute("""
                INSERT INTO users 
                (username, password, full_name, department, contact_number, year_level, student_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data['username'], data['password'], data['full_name'],
                data['department'], data['contact_number'], data['year_level'],
                data['student_number']
            ))
            
            conn.commit()
            conn.close()
            return "<p style='color:green;text-align:center;'>✅ Registration Successful! <a href='/login'>Go to Login</a></p>"
        
        except Exception as e:
            return f"<p style='color:red;'>❌ Error: {str(e)}</p>"
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Register</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f0f4f8; padding: 30px; }
        .box { background: white; padding: 25px; border-radius: 12px; max-width: 420px; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        h2 { text-align: center; color: #2c3e50; margin-bottom: 25px; }
        input, select { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; font-size: 15px; }
        button { width: 100%; padding: 13px; background: #2ecc71; color: white; border: none; border-radius: 6px; font-size: 16px; margin-top: 10px; cursor: pointer; }
        button:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="box">
        <h2>📝 Register Account</h2>
        <form method="POST">
            <input type="text" name="full_name" placeholder="Full Name" required>
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <select name="department" required>
                <option value="">-- Select Department --</option>
                <option>CT</option>
                <option>FBT</option>
                <option>BSED</option>
                <option>BEED</option>
                <option>BSFI</option>
                <option>BSBA</option>
            </select>
            <input type="text" name="year_level" placeholder="Year Level (e.g. 1st Year)" required>
            <input type="text" name="student_number" placeholder="Student Number (Barcode ID)" required>
            <input type="text" name="contact_number" placeholder="Contact Number">
            <button type="submit">✅ Register</button>
        </form>
    </div>
</body>
</html>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, full_name, department FROM users WHERE LOWER(username) = ? AND password = ?",
                 (normalize_text(data['username']), data['password']))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['full_name'] = user[1]
            session['department'] = user[2]
            return redirect(url_for('dashboard'))
        return "<p style='color:red;text-align:center;'>❌ Invalid username or password! <a href='/login'>Try again</a></p>"
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f0f4f8; min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); width: 100%; max-width: 360px; }
        h2 { text-align: center; color: #2c3e50; margin-bottom: 25px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 6px; font-size: 15px; }
        button { width: 100%; padding: 13px; background: #3498db; color: white; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; }
        button:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="box">
        <h2>🔐 Login</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
    """)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT id, barcode_id, in_time, out_time, created_at FROM attendance WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
             (session['user_id'],))
    records = c.fetchall()
    
    c.execute("SELECT COUNT(*) FROM attendance WHERE user_id = ?", (session['user_id'],))
    total_visits = c.fetchone()[0]
    
    conn.close()
    
    html_rows = ""
    for r in records:
        date_str = r[4][:10] if r[4] else "-"
        html_rows += f"<tr><td>{r[1]}</td><td>{r[2] or '-'}</td><td>{r[3] or '-'}</td><td>{date_str}</td></tr>"
    if len(records) == 0:
        html_rows = "<tr><td colspan='4' style='text-align:center;'>No records yet.</td></tr>"
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f0f4f8; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        h1 { color: #2c3e50; text-align: center; margin-bottom: 20px; font-size: 26px; }
        .info { background: #e8f4f8; padding: 18px; border-radius: 8px; margin: 15px 0; }
        .info h3 { margin-bottom: 8px; color: #2c3e50; }
        .btn { padding: 10px 18px; border: none; border-radius: 6px; font-size: 15px; cursor: pointer; margin: 5px; text-decoration: none; display: inline-block; transition: 0.2s; }
        .btn-in { background: #2ecc71; color: white; }
        .btn-out { background: #e74c3c; color: white; }
        .btn-logout { background: #95a5a6; color: white; float: right; }
        .btn-list { background: #9b59b6; color: white; }
        .btn-edit { background: #f39c12; color: white; }
        .btn:hover { opacity: 0.9; }
        .btn-group { text-align: center; margin: 25px 0; }
        h3 { color: #2c3e50; margin-top: 30px; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }
        th { background: #2c3e50; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <a href='/logout' class='btn btn-logout'>🚪 Logout</a>
        <h1>📚 Library Attendance</h1>
        <div class="info">
            <h3>Welcome, """ + session['full_name'] + """! 🎓</h3>
            <p><strong>Department:</strong> """ + session['department'] + """</p>
            <p><strong>Total Visits:</strong> """ + str(total_visits) + """</p>
        </div>
        <div class="btn-group">
            <a href='/scan-in' class='btn btn-in'>✅ Time IN</a>
            <a href='/scan-out' class='btn btn-out'>🚪 Time OUT</a>
            <a href='/user-list' class='btn btn-list'>👥 All Users</a>
            <a href='/edit-profile' class='btn btn-edit'>✏️ Edit My Info</a>
        </div>
        <h3>📋 Recent Records</h3>
        <table>
            <tr><th>Barcode ID</th><th>Time IN</th><th>Time OUT</th><th>Date</th></tr>
            """ + html_rows + """
        </table>
    </div>
</body>
</html>
    """)

@app.route('/user-list')
def user_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, full_name, username, department, year_level, student_number, contact_number FROM users ORDER BY full_name")
    users = c.fetchall()
    conn.close()
    
    html_rows = ""
    for u in users:
        contact = u[6] if u[6] else "-"
        html_rows += f"<tr><td>{u[1]}</td><td>{u[2]}</td><td>{u[3]}</td><td>{u[4]}</td><td>{u[5]}</td><td>{contact}</td><td><a href='/edit-user/{u[0]}' class='btn btn-edit'>Edit</a></td></tr>"
    if len(users) == 0:
        html_rows = "<tr><td colspan='7' style='text-align:center;'>No users registered yet.</td></tr>"
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>All Registered Users</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f0f4f8; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        h2 { color: #2c3e50; text-align: center; margin-bottom: 20px; }
        .btn { padding: 8px 15px; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; margin: 3px; font-size: 14px; }
        .btn-back { background: #95a5a6; color: white; margin-bottom: 15px; }
        .btn-edit { background: #f39c12; color: white; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }
        th { background: #2c3e50; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <a href='/dashboard' class='btn btn-back'>← Back to Dashboard</a>
        <h2>👥 All Registered Users</h2>
        <table>
            <tr>
                <th>Full Name</th>
                <th>Username</th>
                <th>Department</th>
                <th>Year Level</th>
                <th>Student Number</th>
                <th>Contact</th>
                <th>Action</th>
            </tr>
            """ + html_rows + """
        </table>
    </div>
</body>
</html>
    """)

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.form
        c.execute("""
            UPDATE users SET full_name=?, password=?, department=?, year_level=?, contact_number=?
            WHERE id = ?
        """, (data['full_name'], data['password'], data['department'], data['year_level'], data['contact_number'], session['user_id']))
        conn.commit()
        conn.close()
        return "<p style='color:green;text-align:center;'>✅ Profile Updated! <a href='/dashboard'>Go to Dashboard</a></p>"
    
    c.execute("SELECT full_name, username, department, year_level, contact_number FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    conn.close()
    
    dept_selected = {}
    for dept in ['CT', 'FBT', 'BSED', 'BEED', 'BSFI', 'BSBA']:
        dept_selected[dept] = "selected" if user[2] == dept else ""
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Edit My Profile</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f0f4f8; padding: 30px; }
        .box { background: white; padding: 25px; border-radius: 12px; max-width: 450px; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        h2 { text-align: center; color: #2c3e50; margin-bottom: 25px; }
        input, select { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; font-size: 15px; }
        input:disabled { background: #eee; color: #666; }
        button { width: 100%; padding: 13px; background: #f39c12; color: white; border: none; border-radius: 6px; font-size: 16px; margin-top: 10px; cursor: pointer; }
        .btn-back { background: #95a5a6; color: white; text-align: center; padding: 10px; border-radius: 6px; text-decoration: none; display: block; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="box">
        <a href='/dashboard' class='btn-back'>← Back</a>
        <h2>✏️ Edit My Profile</h2>
        <form method="POST">
            <input type="text" name="full_name" value='""" + user[0] + """' required>
            <input type="text" name="username" value='""" + user[1] + """' disabled>
            <input type="password" name="password" placeholder="New Password" required>
            <select name="department" required>
                <option value="">-- Select Department --</option>
                <option """ + dept_selected['CT'] + """>CT</option>
                <option """ + dept_selected['FBT'] + """>FBT</option>
                <option """ + dept_selected['BSED'] + """>BSED</option>
                <option """ + dept_selected['BEED'] + """>BEED</option>
                <option """ + dept_selected['BSFI'] + """>BSFI</option>
                <option """ + dept_selected['BSBA'] + """>BSBA</option>
            </select>
            <input type="text" name="year_level" value='""" + user[3] + """' required>
            <input type="text" name="contact_number" value='""" + (user[4] or "") + """'>
            <button type="submit">✅ Update Profile</button>
        </form>
    </div>
</body>
</html>
    """)

@app.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.form
        c.execute("""
            UPDATE users SET full_name=?, department=?, year_level=?, contact_number=?
            WHERE id = ?
        """, (data['full_name'], data['department'], data['year_level'], data['contact_number'], user_id))
        conn.commit()
        conn.close()
        return "<p style='color:green;text-align:center;'>✅ User Updated! <a href='/user-list'>Back to List</a></p>"
    
    c.execute("SELECT full_name, username, department, year_level, contact_number, student_number FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    dept_selected = {}
    for dept in ['CT', 'FBT', 'BSED', 'BEED', 'BSFI', 'BSBA']:
        dept_selected[dept] = "selected" if user[2] == dept else ""
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Edit User</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #f0f4f8; padding: 30px; }
        .box { background: white; padding: 25px; border-radius: 12px; max-width: 450px; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        h2 { text-align: center; color: #2c3e50; margin-bottom: 25px; }
        input, select { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; font-size: 15px; }
        input:disabled { background: #eee; color: #666; }
        button { width: 100%; padding: 13px; background: #f39c12; color: white; border: none; border-radius: 6px; font-size: 16px; margin-top: 10px; cursor: pointer; }
        .btn-back { background: #95a5a6; color: white; text-align: center; padding: 10px; border-radius: 6px; text-decoration: none; display: block; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="box">
        <a href='/user-list' class='btn-back'>← Back to User List</a>
        <h2>✏️ Edit User</h2>
        <form method="POST">
            <input type="text" name="full_name" value='""" + user[0] + """' required>
            <input type="text" name="username" value='""" + user[1] + """' disabled>
            <input type="text" name="student_number" value='""" + user[5] + """' disabled>
            <select name="department" required>
                <option value="">-- Select Department --</option>
                <option """ + dept_selected['CT'] + """>CT</option>
                <option """ + dept_selected['FBT'] + """>FBT</option>
                <option """ + dept_selected['BSED'] + """>BSED</option>
                <option """ + dept_selected['BEED'] + """>BEED</option>
                <option """ + dept_selected['BSFI'] + """>BSFI</option>
                <option """ + dept_selected['BSBA'] + """>BSBA</option>
            </select>
            <input type="text" name="year_level" value='""" + user[3] + """' required>
            <input type="text" name="contact_number" value='""" + (user[4] or "") + """'>
            <button type="submit">✅ Update User</button>
        </form>
    </div>
</body>
</html>
    """)

@app.route('/scan-in')
def scan_in():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT student_number FROM users WHERE id = ?", (session['user_id'],))
    barcode_id = c.fetchone()[0]
    
    now = datetime.datetime.now()
    c.execute("INSERT INTO attendance (user_id, barcode_id, in_time) VALUES (?, ?, ?)",
             (session['user_id'], barcode_id, now))
    
    conn.commit()
    conn.close()
    
    return f"""
    <script>alert('✅ TIME IN SUCCESS!\\nTime: {now.strftime('%Y-%m-%d %H:%M:%S')}'); window.location.href='/dashboard';</script>
    """

@app.route('/scan-out')
def scan_out():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        SELECT id FROM attendance 
        WHERE user_id = ? AND out_time IS NULL 
        ORDER BY in_time DESC LIMIT 1
    """, (session['user_id'],))
    record = c.fetchone()
    
    if record:
        now = datetime.datetime.now()
        c.execute("UPDATE attendance SET out_time = ? WHERE id = ?", (now, record[0]))
        msg = f"✅ TIME OUT SUCCESS!\\nTime: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        msg = "⚠️ No active Time In found!"
    
    conn.commit()
    conn.close()
    
    return f"""
    <script>alert('{msg}'); window.location.href='/dashboard';</script>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
