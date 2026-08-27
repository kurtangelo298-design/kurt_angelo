from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey12345"

DATABASE_URL = os.environ.get("DATABASE_URL")

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
        body { font-family: Arial; background: #f0f4f8; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 350px; text-align: center; }
        h1 { color: #2c3e50; margin-bottom: 25px; }
        button { width: 100%; padding: 12px; margin: 8px 0; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; }
        .btn-login { background: #3498db; color: white; }
        .btn-register { background: #2ecc71; color: white; }
        button:hover { opacity: 0.9; }
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
            conn = psycopg2.connect(DATABASE_URL)
            c = conn.cursor()
            
            c.execute("SELECT id FROM users WHERE username = %s OR student_number = %s",
                     (data['username'], data['student_number']))
            if c.fetchone():
                conn.close()
                return "❌ Username or Student Number already exists!"
            
            c.execute("""
                INSERT INTO users 
                (username, password, full_name, department, contact_number, year_level, student_number)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                data['username'], data['password'], data['full_name'],
                data['department'], data['contact_number'], data['year_level'],
                data['student_number']
            ))
            
            conn.commit()
            conn.close()
            return "✅ Registration Successful! <a href='/login'>Go to Login</a>"
        
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Register</title>
    <style>
        body { font-family: Arial; background: #f0f4f8; padding: 30px; }
        .box { background: white; padding: 25px; border-radius: 12px; max-width: 400px; margin: 0 auto; }
        h2 { text-align: center; color: #2c3e50; }
        input, select { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #2ecc71; color: white; border: none; border-radius: 6px; font-size: 16px; margin-top: 10px; cursor: pointer; }
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
        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute("SELECT id, full_name, department FROM users WHERE username = %s AND password = %s",
                 (data['username'], data['password']))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['full_name'] = user[1]
            session['department'] = user[2]
            return redirect(url_for('dashboard'))
        return "❌ Invalid username or password! <a href='/login'>Try again</a>"
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <style>
        body { font-family: Arial; background: #f0f4f8; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); width: 350px; }
        h2 { text-align: center; color: #2c3e50; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #3498db; color: white; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; }
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
    
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    
    c.execute("SELECT id, barcode_id, in_time, out_time, created_at FROM attendance WHERE user_id = %s ORDER BY created_at DESC LIMIT 20",
             (session['user_id'],))
    records = c.fetchall()
    
    c.execute("SELECT COUNT(*) FROM attendance WHERE user_id = %s", (session['user_id'],))
    total_visits = c.fetchone()[0]
    
    conn.close()
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard</title>
    <style>
        body { font-family: Arial; background: #f0f4f8; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; text-align: center; }
        .info { background: #e8f4f8; padding: 15px; border-radius: 8px; margin: 15px 0; }
        .btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 15px; cursor: pointer; margin: 5px; text-decoration: none; display: inline-block; }
        .btn-in { background: #2ecc71; color: white; }
        .btn-out { background: #e74c3c; color: white; }
        .btn-logout { background: #95a5a6; color: white; float: right; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #2c3e50; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <a href='/logout' class='btn btn-logout'>🚪 Logout</a>
        <h1>📚 Library Attendance</h1>
        
        <div class="info">
            <h3>Welcome, {{ session['full_name'] }}! 🎓</h3>
            <p><strong>Department:</strong> {{ session['department'] }}</p>
            <p><strong>Total Visits:</strong> """ + str(total_visits) + """</p>
        </div>
        
        <div style="text-align: center; margin: 25px 0;">
            <a href='/scan-in' class='btn btn-in'>✅ Time IN</a>
            <a href='/scan-out' class='btn btn-out'>🚪 Time OUT</a>
        </div>
        
        <h3>📋 Recent Records</h3>
        <table>
            <tr><th>Barcode ID</th><th>Time IN</th><th>Time OUT</th><th>Date</th></tr>
            {% for r in records %}
            <tr>
                <td>{{ r[1] }}</td>
                <td>{{ r[2] or '-' }}</td>
                <td>{{ r[3] or '-' }}</td>
                <td>{{ r[4].strftime('%Y-%m-%d') if r[4] else '-' }}</td>
            </tr>
            {% else %}
            <tr><td colspan="4" style="text-align:center;">No records yet.</td></tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
    """, session=session, records=records, total_visits=total_visits)

@app.route('/scan-in')
def scan_in():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    
    c.execute("SELECT student_number FROM users WHERE id = %s", (session['user_id'],))
    barcode_id = c.fetchone()[0]
    
    now = datetime.datetime.now()
    c.execute("INSERT INTO attendance (user_id, barcode_id, in_time) VALUES (%s, %s, %s)",
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
    
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    
    c.execute("""
        SELECT id FROM attendance 
        WHERE user_id = %s AND out_time IS NULL 
        ORDER BY in_time DESC LIMIT 1
    """, (session['user_id'],))
    record = c.fetchone()
    
    if record:
        now = datetime.datetime.now()
        c.execute("UPDATE attendance SET out_time = %s WHERE id = %s", (now, record[0]))
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
