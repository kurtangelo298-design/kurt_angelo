
from flask import Flask, render_template_string, request, jsonify, make_response
import psycopg2
import os
import datetime
from html import escape as html_escape
import barcode
from barcode.writer import ImageWriter
import base64
from io import BytesIO
import re
import secrets
from PIL import Image, ImageDraw, ImageFont
from docx import Document
import qrcode
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:10000").strip().rstrip("/")

ADMIN_USER = "library"
ADMIN_PASS = "slsu"
USER_USER = "slsu"
USER_PASS = "library"
STUDENT_USER = "student"
STUDENT_PASS = "student"
SCANNER_API_KEY = os.environ.get("SCANNER_API_KEY", "").strip()
CRON_API_KEY = os.environ.get("CRON_API_KEY", "").strip()

# ---- SMTP / Email notification config ----
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
try:
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "465").strip())
except Exception:
    SMTP_PORT = 465
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "library@slsu-jge.edu.ph").strip() or SMTP_USER or "library@slsu-jge.edu.ph"
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "SLSU-JGE Library").strip()
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# ---- Outside borrow: due date & late fine policy ----
OUTSIDE_BORROW_DAYS = int(os.environ.get("OUTSIDE_BORROW_DAYS", "7"))
LATE_FINE_PER_DAY = float(os.environ.get("LATE_FINE_PER_DAY", "5.0"))  # pesos/day late
OVERDUE_PENALTY_POINTS_PER_DAY = int(os.environ.get("OVERDUE_PENALTY_POINTS_PER_DAY", "1"))
OVERDUE_REMINDER_INTERVAL_DAYS = int(os.environ.get("OVERDUE_REMINDER_INTERVAL_DAYS", "7"))
OVERDUE_SCHEDULER_HOUR = int(os.environ.get("OVERDUE_SCHEDULER_HOUR", "8"))  # 8 AM PH

SLSU_LOGO_DATA_URI = ("data:image/jpeg;base64,"
    "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"
    "+LRaa1BoGjyPDeaZGun2ehQGKO6tEFsQs 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")


# ---------------- Time helpers (PH, UTC+8) ----------------
def get_ph_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def get_ph_time():
    return get_ph_now().strftime("%I:%M %p")

def get_ph_date():
    return get_ph_now().strftime("%Y-%m-%d")

def add_days(date_str, days):
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d") + datetime.timedelta(days=days)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return date_str

def days_between(d1, d2):
    try:
        a = datetime.datetime.strptime(d1, "%Y-%m-%d")
        b = datetime.datetime.strptime(d2, "%Y-%m-%d")
        return (b - a).days
    except Exception:
        return 0

def compute_fine(due_date, return_date=None):
    if not due_date:
        return 0, 0.0
    ref = return_date if return_date else get_ph_date()
    late = days_between(due_date, ref)
    if late <= 0:
        return 0, 0.0
    return late, round(late * LATE_FINE_PER_DAY, 2)

def display_status(return_time, borrow_type, email_confirmed):
    """Human-readable status per the NEW flow."""
    if return_time:
        return "Returned"
    if (borrow_type or "Inside") == "Outside":
        return "Borrowed (Confirmed)" if email_confirmed else "Pending Email Confirmation"
    return "Borrowed"


DEPARTMENT_CODES = {"CT": "CPT", "BSED": "BSED", "BEED": "BEED", "BSFAS": "BSFAS", "BSBA": "BSBA", "BPA": "BPA"}

def get_student_code(id_type, department, year_level):
    if id_type != "Student" or not department or not year_level:
        return "-"
    year_match = re.search(r"([1-4])", year_level)
    department_code = DEPARTMENT_CODES.get(department, department.upper())
    return f"{department_code}{year_match.group(1)}" if year_match else "-"

def _generate_next_id(prefix):
    conn = get_db()
    if not conn:
        return f"{prefix}-{secrets.token_hex(2).upper()}"
    c = conn.cursor()
    try:
        c.execute("SELECT id_number FROM users WHERE id_number LIKE %s", (f"{prefix}-%",))
        max_n = 0
        for (val,) in c.fetchall():
            m = re.search(r"-(\d+)$", val or "")
            if m:
                try:
                    max_n = max(max_n, int(m.group(1)))
                except Exception:
                    pass
    finally:
        conn.close()
    return f"{prefix}-{str(max_n + 1).zfill(4)}"


def get_db():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"DB Connect Error: {e}")
        return None


def init_db():
    conn = get_db()
    if not conn:
        print("Cannot connect to database")
        return
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, id_type TEXT NOT NULL, full_name TEXT NOT NULL,
        department TEXT, major TEXT, contact_number TEXT, address TEXT,
        year_level TEXT, id_number TEXT NOT NULL UNIQUE, registered_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
        time_in TEXT, time_out TEXT, scan_date TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS books (
        id SERIAL PRIMARY KEY, access_code TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
        author TEXT, isbn TEXT, category TEXT, shelf_location TEXT,
        quantity INTEGER DEFAULT 1, times_borrowed INTEGER DEFAULT 0,
        last_borrowed_date TEXT, created_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS borrow_records (
        id SERIAL PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id),
        user_id INTEGER NOT NULL REFERENCES users(id), borrow_date TEXT NOT NULL,
        borrow_time TEXT NOT NULL, return_date TEXT, return_time TEXT,
        status TEXT DEFAULT 'Borrowed')""")
    for stmt in [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS penalty_points INTEGER DEFAULT 0",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS borrow_type TEXT DEFAULT 'Inside'",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS borrower_email TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS email_sent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS barcode_number TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS due_date TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS fine_amount REAL DEFAULT 0",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS last_reminder_date TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS last_penalty_date TEXT",
        # NEW: email-confirmation workflow for Outside borrow
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS confirmation_token TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS email_confirmed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS confirmed_at TEXT",
    ]:
        try:
            c.execute(stmt)
        except Exception as e:
            print(f"ALTER skipped: {e}")
    conn.commit()
    conn.close()
    print("DATABASE READY")


init_db()


# ---------------- Email ----------------
def _send_email(to_email, subject, html_body):
    if not to_email or not EMAIL_RE.match(to_email):
        return False, "Invalid email address."
    if not SMTP_USER or not SMTP_PASS:
        return False, "SMTP not configured. Set SMTP_USER and SMTP_PASS environment variables."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        context = ssl.create_default_context()
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=20) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        return True, "Email sent."
    except Exception as e:
        print(f"SEND EMAIL ERROR: {e}")
        return False, f"Email not sent: {str(e)}"


def _email_shell(title, inner_html):
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;color:#1b2a41;">
    <div style="background:#1b2a41;color:#fff;padding:18px 22px;border-radius:8px 8px 0 0;">
      <strong>SLSU-JGE Library</strong> &nbsp;|&nbsp; {html_escape(title)}</div>
    <div style="padding:20px 22px;border:1px solid #e2e8f0;border-top:0;border-radius:0 0 8px 8px;">
    {inner_html}
    <p style="font-size:12px;color:#64748b;margin-top:18px;">SLSU-JGE Library Management System<br>
    Southern Luzon State University — Judge Guillermo Eleazar</p></div></div>"""


def send_borrow_notification(to_email, borrower_name, book_title, book_author, access_code,
                             borrow_date, borrow_time, borrow_type, due_date=None, confirm_link=None):
    borrower_name = html_escape(str(borrower_name))
    book_title = html_escape(str(book_title))
    book_author = html_escape(str(book_author or "Not provided"))
    access_code = html_escape(str(access_code))
    borrow_date = html_escape(str(borrow_date))
    borrow_time = html_escape(str(borrow_time))
    borrow_type = html_escape(str(borrow_type))
    due_date = html_escape(str(due_date or "Not specified"))
    rows = f"""
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Full Name of Borrower</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;font-weight:600;">{borrower_name}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Book Title</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;font-weight:600;">{book_title}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Author</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;">{book_author}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Access Code</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;">{access_code}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Date &amp; Time Borrowed</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;">{borrow_date} {borrow_time}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Borrowed Type</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;">{borrow_type}</td></tr>
      <tr><td style="padding:6px;color:#64748b;">Due Date for Return</td><td style="padding:6px;font-weight:600;">{due_date}</td></tr>
    </table>"""
    if confirm_link:
        link = html_escape(confirm_link)
        inner = (
            "<p>Your outside borrow has been recorded. <strong>Please check your email to confirm your "
            "borrow transaction</strong> — click the button below to confirm:</p>"
            '<p style="text-align:center;margin:22px 0;">'
            '<a href="' + link + '" style="background:#1b6b3a;color:#fff;padding:12px 26px;'
            'text-decoration:none;border-radius:6px;font-weight:600;">Confirm My Borrow</a></p>'
            '<p style="font-size:12px;color:#64748b;">Or open this link: ' + link + '</p>'
            + rows +
            '<p style="font-size:13px;color:#374151;margin-top:14px;">Until confirmed, your borrow shows as '
            '<em>Pending Email Confirmation</em>. A late fine of &#8369;' + ("%.2f" % LATE_FINE_PER_DAY) +
            '/day applies after the due date, and ' + str(OVERDUE_PENALTY_POINTS_PER_DAY) +
            ' penalty point(s)/day are deducted once 7+ days overdue.</p>')
        subject = "Confirm your book borrow — SLSU-JGE Library"
    else:
        inner = (f"<p>This is to confirm your book borrowing:</p>{rows}"
                 f"<p style=\"font-size:13px;color:#374151;margin-top:14px;\">Please return on or before the due date. "
                 f"A late fine of &#8369;{LATE_FINE_PER_DAY:.2f}/day applies after the due date. Please take good care of the book.</p>")
        subject = "Book Borrowed — Confirmation from SLSU-JGE Library"
    return _send_email(to_email, subject, _email_shell(subject, inner))


def send_overdue_reminder(to_email, borrower_name, book_title, access_code, borrow_date, due_date,
                          days_late, fine_amount, penalty_points=0):
    inner = f"""<p>Hello {html_escape(str(borrower_name))},</p>
    <p>This is a friendly reminder that the book you borrowed is now <strong>OVERDUE</strong>.
    Please return it to the SLSU-JGE Library as soon as possible.</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Book Title</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;font-weight:600;">{html_escape(str(book_title))}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Access Code</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;">{html_escape(str(access_code))}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Date Borrowed</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;">{html_escape(str(borrow_date))}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Due Date</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;">{html_escape(str(due_date))}</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Days Late</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;">{days_late} day(s)</td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #e2e8f0;color:#64748b;">Accumulated Fine</td><td style="padding:6px;border-bottom:1px solid #e2e8f0;font-weight:600;">&#8369;{fine_amount:.2f} (&#8369;{LATE_FINE_PER_DAY:.2f}/day)</td></tr>
      <tr><td style="padding:6px;color:#64748b;">Penalty Points Deducted</td><td style="padding:6px;">{penalty_points} point(s) on your student record</td></tr>
    </table>
    <p style="font-size:13px;color:#374151;margin-top:14px;">The fine continues to increase by &#8369;{LATE_FINE_PER_DAY:.2f} each day until the book is returned. Damage or loss must also be paid in full.</p>"""
    return _send_email(to_email, f"OVERDUE — Return '{book_title}' — SLSU-JGE Library",
                       _email_shell("OVERDUE BOOK REMINDER", inner))


# ---------------- Overdue scheduler ----------------
def run_overdue_check():
    today = get_ph_date()
    conn = get_db()
    if not conn:
        return {"success": False, "error": "Database connection failed."}
    c = conn.cursor()
    c.execute("""SELECT br.id, b.title, b.access_code, u.full_name, u.id, br.borrower_email,
                 br.borrow_date, br.due_date, br.last_reminder_date, u.penalty_points, u.email
                 FROM borrow_records br JOIN books b ON br.book_id = b.id
                 JOIN users u ON br.user_id = u.id
                 WHERE br.return_time IS NULL AND br.borrow_type = 'Outside'
                 AND br.due_date IS NOT NULL AND br.due_date < %s ORDER BY br.due_date ASC""", (today,))
    rows = c.fetchall()
    penalties_applied = reminders_sent = reminders_failed = 0
    for row in rows:
        borrow_id, title, access_code, borrower_name, user_id, borrower_email, borrow_date, due_date, last_reminder, user_penalty, user_email = row
        days_late, fine = compute_fine(due_date)
        email = (borrower_email or "").strip() or (user_email or "").strip()
        if days_late >= OVERDUE_REMINDER_INTERVAL_DAYS:
            c.execute("SELECT last_penalty_date FROM borrow_records WHERE id = %s", (borrow_id,))
            last_pen = c.fetchone()[0]
            if last_pen != today:
                c.execute("UPDATE users SET penalty_points = COALESCE(penalty_points,0) + %s WHERE id = %s",
                          (OVERDUE_PENALTY_POINTS_PER_DAY, user_id))
                c.execute("UPDATE borrow_records SET last_penalty_date = %s, fine_amount = %s WHERE id = %s",
                          (today, fine, borrow_id))
                penalties_applied += 1
                conn.commit()
            should_send = (not last_reminder) or (days_between(last_reminder, today) >= OVERDUE_REMINDER_INTERVAL_DAYS)
            if should_send:
                if email and EMAIL_RE.match(email):
                    c.execute("SELECT penalty_points FROM users WHERE id = %s", (user_id,))
                    current_penalty = c.fetchone()[0] or 0
                    ok, _ = send_overdue_reminder(email, borrower_name, title, access_code, borrow_date, due_date, days_late, fine, current_penalty)
                    if ok:
                        c.execute("UPDATE borrow_records SET last_reminder_date = %s, reminder_sent = TRUE WHERE id = %s", (today, borrow_id))
                        reminders_sent += 1
                    else:
                        reminders_failed += 1
                else:
                    reminders_failed += 1
                conn.commit()
        else:
            c.execute("UPDATE borrow_records SET fine_amount = %s WHERE id = %s", (fine, borrow_id))
            conn.commit()
    conn.close()
    return {"success": True, "checked": len(rows), "penalties_applied": penalties_applied,
            "reminders_sent": reminders_sent, "reminders_failed": reminders_failed,
            "ran_at": today + " " + get_ph_time()}


_overdue_scheduler_started = False

def _overdue_scheduler_loop():
    while True:
        try:
            now = get_ph_now()
            target = now.replace(hour=OVERDUE_SCHEDULER_HOUR, minute=0, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            sleep_seconds = (target - now).total_seconds()
            print(f"[OVERDUE SCHEDULER] next run at {target.strftime('%Y-%m-%d %I:%M %p')} PH (in {sleep_seconds/3600:.1f}h)")
            time.sleep(min(sleep_seconds, 24 * 3600))
            print(f"[OVERDUE SCHEDULER] daily check done: {run_overdue_check()}")
        except Exception as e:
            print(f"[OVERDUE SCHEDULER] error: {e}")
            time.sleep(3600)

def start_overdue_scheduler():
    global _overdue_scheduler_started
    if _overdue_scheduler_started:
        return
    if os.environ.get("DISABLE_OVERDUE_SCHEDULER", "").strip() == "1":
        print("[OVERDUE SCHEDULER] disabled via DISABLE_OVERDUE_SCHEDULER=1 (use /api/cron/overdue instead).")
        return
    _overdue_scheduler_started = True
    threading.Thread(target=_overdue_scheduler_loop, daemon=True).start()
    print("[OVERDUE SCHEDULER] started (daily at %02d:00 PH time)." % OVERDUE_SCHEDULER_HOUR)

start_overdue_scheduler()


# ---------------- Barcode / QR generators ----------------
def generate_barcode_b64(id_number):
    code128 = barcode.get_barcode_class("code128")
    code = code128(str(id_number), writer=ImageWriter())
    module_count = len(code.build()[0])
    image = code.render({
        "module_width": 38.0 / module_count, "module_height": 20.0, "quiet_zone": 5.0,
        "center_text": True, "write_text": False, "dpi": 300,
    }).convert("RGB")
    buffered = BytesIO()
    image.save(buffered, format="PNG", dpi=(300, 300), optimize=True)
    return base64.b64encode(buffered.getvalue()).decode()

def generate_qr_b64(data):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def book_status_info(book_id, quantity):
    conn = get_db()
    if not conn:
        return 0, quantity, "Available"
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM borrow_records WHERE book_id = %s AND return_time IS NULL", (book_id,))
    active = c.fetchone()[0]
    conn.close()
    available = max(0, int(quantity) - active)
    return active, available, ("Available" if available > 0 else "Borrowed")

def active_borrowers_of(book_id):
    conn = get_db()
    if not conn:
        return []
    c = conn.cursor()
    c.execute("""SELECT br.id, u.full_name, u.id_number, br.borrow_date, br.borrow_time, br.borrow_type, br.email_confirmed
                 FROM borrow_records br JOIN users u ON br.user_id = u.id
                 WHERE br.book_id = %s AND br.return_time IS NULL ORDER BY br.id""", (book_id,))
    rows = [{"borrow_id": r[0], "borrower_name": r[1], "borrower_id": r[2], "borrow_date": r[3],
             "borrow_time": r[4], "borrow_type": r[5] or "Inside", "email_confirmed": bool(r[6])} for r in c.fetchall()]
    conn.close()
    return rows

# ============================================================
# AUTH HELPERS
# ============================================================
def is_logged_in():
    return request.cookies.get('logged_in') == 'true'

def get_role():
    return request.cookies.get('role', 'user')

def is_scan_authorized():
    if is_logged_in():
        return True
    if not SCANNER_API_KEY:
        return False
    provided_key = request.headers.get('X-Scanner-Key', '').strip()
    return bool(provided_key) and secrets.compare_digest(provided_key, SCANNER_API_KEY)

def is_cron_authorized():
    if is_logged_in() and get_role() == 'admin':
        return True
    if not CRON_API_KEY:
        return False
    provided = request.headers.get('X-Cron-Key', '').strip() or request.args.get('key', '').strip()
    return bool(provided) and secrets.compare_digest(provided, CRON_API_KEY)


# ============================================================
# BARCODE / QR IMAGE ROUTES & DOWNLOADS
# ============================================================
@app.route('/barcode/<path:id_number>')
def barcode_image(id_number):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        image_data = base64.b64decode(generate_barcode_b64(id_number))
        response = make_response(image_data)
        response.headers['Content-Type'] = 'image/png'
        response.headers['Content-Disposition'] = f'attachment; filename="barcode_{id_number}.png"'
        response.headers['Cache-Control'] = 'no-store'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/book-barcode/<path:barcode_number>')
def book_barcode_image(barcode_number):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        image_data = base64.b64decode(generate_barcode_b64(barcode_number))
        response = make_response(image_data)
        response.headers['Content-Type'] = 'image/png'
        response.headers['Content-Disposition'] = f'attachment; filename="book_barcode_{barcode_number}.png"'
        response.headers['Cache-Control'] = 'no-store'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 400

def _font_path():
    for p in ["C:/Windows/Fonts/arial.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(p):
            return p
    return None

@app.route('/download-book-barcodes', methods=['POST'])
def download_book_barcodes():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True, force=True) or {}
        book_ids = [int(v) for v in payload.get('book_ids', []) if str(v).strip()]
        if not book_ids:
            return jsonify({"error": "Please select at least one book."}), 400
        conn = get_db()
        if not conn:
            return jsonify({"error": "Database connection failed."}), 500
        c = conn.cursor()
        c.execute("SELECT id, access_code, title, barcode_number FROM books WHERE id = ANY(%s) ORDER BY id", (book_ids,))
        books = c.fetchall()
        conn.close()
        if not books:
            return jsonify({"error": "No selected books were found."}), 404
        items = []
        for bid, access_code, title, bc in books:
            code = (bc or "").strip() or access_code
            items.append((code, title or ""))
        DPI = 300
        page_size = (round(210 / 25.4 * DPI), round(297 / 25.4 * DPI))
        columns, rows = 3, 5
        box_width = round(62 / 25.4 * DPI)
        box_height = round(52 / 25.4 * DPI)
        gap = round(2 / 25.4 * DPI)
        grid_width = columns * box_width + (columns - 1) * gap
        grid_height = rows * box_height + (rows - 1) * gap
        grid_left = (page_size[0] - grid_width) // 2
        grid_top = (page_size[1] - grid_height) // 2
        barcode_size = (round(58 / 25.4 * DPI), round(36 / 25.4 * DPI))
        fp = _font_path()
        title_font = ImageFont.truetype(fp, round(8 * DPI / 72)) if fp else ImageFont.load_default()
        code_font = ImageFont.truetype(fp, round(9 * DPI / 72)) if fp else ImageFont.load_default()
        pages = []
        labels_per_page = columns * rows
        for page_start in range(0, len(items), labels_per_page):
            page = Image.new('RGB', page_size, 'white')
            draw = ImageDraw.Draw(page)
            page_items = items[page_start:page_start + labels_per_page]
            for index, (code, title) in enumerate(page_items):
                column = index % columns
                row = index // columns
                cell_left = grid_left + column * (box_width + gap)
                cell_top = grid_top + row * (box_height + gap)
                bc_img = Image.open(BytesIO(base64.b64decode(generate_barcode_b64(code))))
                bc_img.thumbnail(barcode_size, Image.Resampling.LANCZOS)
                bc_left = cell_left + (box_width - bc_img.width) // 2
                bc_top = cell_top + round(15 / 25.4 * DPI)
                page.paste(bc_img, (bc_left, bc_top))
                title_label = title if len(title) <= 48 else title[:45] + "..."
                for label, font, y in ((title_label, title_font, cell_top + round(2 / 25.4 * DPI)),
                                       ("Code: " + code, code_font, cell_top + round(8 / 25.4 * DPI))):
                    while fp and draw.textlength(label, font=font) > box_width - round(4 / 25.4 * DPI) and font.size > 18:
                        font = ImageFont.truetype(fp, font.size - 2)
                    bounds = draw.textbbox((0, 0), label, font=font)
                    label_width = bounds[2] - bounds[0]
                    draw.text((cell_left + (box_width - label_width) // 2 - bounds[0], y - bounds[1]), label, fill='black', font=font)
                draw.rectangle((cell_left, cell_top, cell_left + box_width, cell_top + box_height), outline='black', width=3)
            pages.append(page)
        output = BytesIO()
        pages[0].save(output, format='PDF', resolution=300.0, save_all=True, append_images=pages[1:])
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename="book_barcodes.pdf"'
        return response
    except Exception as e:
        print(f"DOWNLOAD BOOK BARCODES ERROR: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/download-barcodes', methods=['POST'])
def download_barcodes():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True, force=True) or {}
        id_numbers = list(dict.fromkeys(str(v).strip() for v in payload.get('id_numbers', []) if str(v).strip()))
        if not id_numbers:
            return jsonify({"error": "Please select at least one student."}), 400
        DPI = 300
        IN = DPI
        page_w, page_h = int(8.5 * IN), int(11 * IN)
        margin = int(0.5 * IN)
        label_w, label_h = int(2.4 * IN), int(1.9 * IN)
        gap = int(0.1 * IN)
        columns, rows = 3, 5
        labels_per_page = columns * rows
        grid_w = columns * label_w + (columns - 1) * gap
        grid_h = rows * label_h + (rows - 1) * gap
        grid_left = (page_w - grid_w) // 2
        grid_top = (page_h - grid_h) // 2
        fp = _font_path()
        font_px = int(round(10 * DPI / 72))
        base_font = ImageFont.truetype(fp, font_px) if fp else ImageFont.load_default()
        bc_box_w, bc_box_h = int(2.2 * IN), int(1.4 * IN)
        text_top = int(0.12 * IN)
        bc_top = int(0.38 * IN)
        pages = []
        for page_start in range(0, len(id_numbers), labels_per_page):
            page = Image.new('RGB', (page_w, page_h), 'white')
            draw = ImageDraw.Draw(page)
            page_ids = id_numbers[page_start:page_start + labels_per_page]
            for i, id_number in enumerate(page_ids):
                column = i % columns
                row = i // columns
                x0 = grid_left + column * (label_w + gap)
                y0 = grid_top + row * (label_h + gap)
                x1, y1 = x0 + label_w, y0 + label_h
                text = "Student Number: " + id_number
                f = base_font
                max_text_w = label_w - int(0.2 * IN)
                while fp and draw.textlength(text, font=f) > max_text_w and f.size > 18:
                    f = ImageFont.truetype(fp, f.size - 2)
                tbox = draw.textbbox((0, 0), text, font=f)
                text_w = tbox[2] - tbox[0]
                tx = x0 + (label_w - text_w) // 2 - tbox[0]
                ty = y0 + text_top - tbox[1]
                draw.text((tx, ty), text, fill='black', font=f)
                bc_img = Image.open(BytesIO(base64.b64decode(generate_barcode_b64(id_number))))
                bc_img.thumbnail((bc_box_w, bc_box_h), Image.Resampling.LANCZOS)
                bcx = x0 + (label_w - bc_img.width) // 2
                bcy = y0 + bc_top + (bc_box_h - bc_img.height) // 2
                page.paste(bc_img, (bcx, bcy))
                draw.rectangle((x0, y0, x1, y1), outline='black', width=3)
            pages.append(page)
        output = BytesIO()
        pages[0].save(output, format='PDF', resolution=float(DPI), save_all=True, append_images=pages[1:])
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename="student_id_labels.pdf"'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/delete-students', methods=['POST'])
def delete_students():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"error": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True, force=True) or {}
        id_numbers = list(dict.fromkeys(str(v).strip() for v in payload.get('id_numbers', []) if str(v).strip()))
        if not id_numbers:
            return jsonify({"error": "Please select at least one student."}), 400
        conn = get_db()
        if not conn:
            return jsonify({"error": "Database connection failed."}), 500
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance WHERE user_id IN (SELECT id FROM users WHERE id_number = ANY(%s))", (id_numbers,))
            cursor.execute("DELETE FROM borrow_records WHERE user_id IN (SELECT id FROM users WHERE id_number = ANY(%s))", (id_numbers,))
            cursor.execute("DELETE FROM users WHERE id_number = ANY(%s)", (id_numbers,))
            deleted_count = cursor.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return jsonify({"success": True, "deleted_count": deleted_count})
    except Exception as e:
        print(f"DELETE STUDENTS ERROR: {e}")
        return jsonify({"error": "Unable to delete selected students."}), 500

@app.route('/delete-daily-history', methods=['POST'])
def delete_daily_history():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"error": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True, force=True) or {}
        selected_date = str(payload.get('date', '')).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", selected_date):
            return jsonify({"error": "Please select a valid specific date."}), 400
        conn = get_db()
        if not conn:
            return jsonify({"error": "Database connection failed."}), 500
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance WHERE scan_date = %s", (selected_date,))
            deleted_count = cursor.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return jsonify({"success": True, "deleted_count": deleted_count, "date": selected_date})
    except Exception as e:
        print(f"DELETE DAILY HISTORY ERROR: {e}")
        return jsonify({"error": "Unable to delete daily history."}), 500


# ============================================================
# BOOK MANAGEMENT ROUTES (Admin)
# ============================================================
@app.route('/api/scan-book-barcode', methods=['POST'])
def scan_book_barcode():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form
    code = str(data.get('code', '')).strip()
    if not code:
        return jsonify({"success": False, "error": "No barcode scanned."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed."}), 500
    c = conn.cursor()
    c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location, quantity, barcode_number
                 FROM books WHERE UPPER(barcode_number) = UPPER(%s) OR UPPER(access_code) = UPPER(%s) LIMIT 1""", (code, code))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({"success": True, "exists": True, "book": {
            "id": row[0], "access_code": row[1], "title": row[2], "author": row[3], "isbn": row[4],
            "category": row[5], "shelf_location": row[6], "quantity": row[7], "barcode_number": row[8] or ""}})
    return jsonify({"success": True, "exists": False, "barcode_number": code, "barcode_img": generate_barcode_b64(code),
                    "message": f"Barcode '{code}' not yet registered. Fill in the book details below."})

@app.route('/register-book', methods=['POST'])
def register_book():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip() or None
        isbn = request.form.get('isbn', '').strip() or None
        category = request.form.get('category', '').strip() or None
        shelf_location = request.form.get('shelf_location', '').strip() or None
        quantity = request.form.get('quantity', '1').strip()
        barcode_number = request.form.get('barcode_number', '').strip() or None
        if not title:
            return jsonify({"success": False, "error": "Book title is required."}), 400
        try:
            qty = max(1, int(quantity))
        except ValueError:
            qty = 1
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database connection failed."}), 500
        c = conn.cursor()
        created_at = get_ph_date() + " " + get_ph_time()
        c.execute("""INSERT INTO books (access_code, title, author, isbn, category, shelf_location, quantity, created_at, barcode_number)
                     VALUES ('PENDING', %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                  (title, author, isbn, category, shelf_location, qty, created_at, barcode_number))
        book_id = c.fetchone()[0]
        access_code = barcode_number if barcode_number else f"BK{str(book_id).zfill(6)}"
        c.execute("UPDATE books SET access_code = %s WHERE id = %s", (access_code, book_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "book_id": book_id, "access_code": access_code, "title": title,
                        "barcode": generate_barcode_b64(access_code),
                        "message": f"Book registered: {title} (Code: {access_code})"})
    except Exception as e:
        print(f"REGISTER BOOK ERROR: {e}")
        return jsonify({"success": False, "error": f"An error occurred: {str(e)}"}), 500

@app.route('/get-books')
def get_books():
    if not is_logged_in():
        return jsonify({"books": []})
    conn = get_db()
    if not conn:
        return jsonify({"books": []})
    c = conn.cursor()
    c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location, quantity,
                 times_borrowed, last_borrowed_date, created_at, barcode_number FROM books ORDER BY title""")
    books = []
    for r in c.fetchall():
        active, available, status = book_status_info(r[0], r[7])
        books.append({"id": r[0], "access_code": r[1], "title": r[2], "author": r[3], "isbn": r[4],
                      "category": r[5], "shelf_location": r[6], "quantity": r[7], "times_borrowed": r[8] or 0,
                      "last_borrowed_date": r[9] or "-", "created_at": r[10], "barcode_number": r[11] or "",
                      "active_borrows": active, "available_qty": available, "status": status})
    conn.close()
    return jsonify({"books": books})

@app.route('/api/search-books')
def search_books():
    if not is_logged_in():
        return jsonify({"books": []})
    q = request.args.get('q', '').strip()
    only_available = request.args.get('available', '').strip() == '1'
    conn = get_db()
    if not conn:
        return jsonify({"books": []})
    c = conn.cursor()
    if q:
        like = f"%{q}%"
        c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location, quantity, barcode_number
                     FROM books WHERE UPPER(title) LIKE UPPER(%s) OR UPPER(author) LIKE UPPER(%s)
                     OR UPPER(category) LIKE UPPER(%s) OR UPPER(access_code) LIKE UPPER(%s)
                     OR UPPER(COALESCE(barcode_number,'')) LIKE UPPER(%s) ORDER BY title""", (like, like, like, like, like))
    else:
        c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location, quantity, barcode_number
                     FROM books ORDER BY title""")
    results = []
    for r in c.fetchall():
        active, available, status = book_status_info(r[0], r[7])
        if only_available and available <= 0:
            continue
        results.append({"id": r[0], "access_code": r[1], "title": r[2], "author": r[3] or "-", "isbn": r[4] or "-",
                        "category": r[5] or "-", "shelf_location": r[6] or "-", "quantity": r[7],
                        "barcode_number": r[8] or "-", "available_qty": available, "status": status,
                        "current_borrowers": active_borrowers_of(r[0])})
    conn.close()
    return jsonify({"books": results, "query": q})

@app.route('/update-book', methods=['POST'])
def update_book():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        book_id = request.form.get('id', '').strip()
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip() or None
        isbn = request.form.get('isbn', '').strip() or None
        category = request.form.get('category', '').strip() or None
        shelf_location = request.form.get('shelf_location', '').strip() or None
        quantity = request.form.get('quantity', '1').strip()
        barcode_number = request.form.get('barcode_number', '').strip() or None
        if not book_id or not title:
            return jsonify({"success": False, "error": "Book ID and title are required."}), 400
        try:
            qty = max(1, int(quantity))
        except ValueError:
            qty = 1
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database error."}), 500
        c = conn.cursor()
        c.execute("""UPDATE books SET title=%s, author=%s, isbn=%s, category=%s, shelf_location=%s,
                     quantity=%s, barcode_number=%s WHERE id=%s""",
                  (title, author, isbn, category, shelf_location, qty, barcode_number, int(book_id)))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(f"UPDATE BOOK ERROR: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/delete-book', methods=['POST'])
def delete_book():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True, force=True) or {}
        book_ids = [int(v) for v in payload.get('book_ids', []) if str(v).strip()]
        if not book_ids:
            return jsonify({"success": False, "error": "Please select at least one book."}), 400
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database connection failed."}), 500
        try:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM borrow_records WHERE book_id = ANY(%s) AND return_time IS NULL", (book_ids,))
            if c.fetchone()[0] > 0:
                conn.close()
                return jsonify({"success": False, "error": "Cannot delete a book that is currently borrowed. Return it first."}), 400
            c.execute("DELETE FROM borrow_records WHERE book_id = ANY(%s)", (book_ids,))
            c.execute("DELETE FROM books WHERE id = ANY(%s)", (book_ids,))
            deleted = c.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return jsonify({"success": True, "deleted_count": deleted})
    except Exception as e:
        print(f"DELETE BOOK ERROR: {e}")
        return jsonify({"success": False, "error": "Unable to delete selected books."}), 500


# ============================================================
# OVERDUE / FINE / REMINDER ROUTES
# ============================================================
@app.route('/api/overdue-list')
def overdue_list():
    if not is_logged_in():
        return jsonify({"records": []})
    conn = get_db()
    if not conn:
        return jsonify({"records": []})
    c = conn.cursor()
    c.execute("""SELECT br.id, b.title, b.access_code, u.full_name, u.id_number, br.borrower_email,
                 br.borrow_date, br.borrow_time, br.due_date, br.reminder_sent, u.penalty_points, br.email_confirmed
                 FROM borrow_records br JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
                 WHERE br.return_time IS NULL AND br.borrow_type = 'Outside'
                 AND br.due_date IS NOT NULL AND br.due_date < %s ORDER BY br.due_date ASC""", (get_ph_date(),))
    records = []
    for r in c.fetchall():
        days_late, fine = compute_fine(r[8])
        records.append({"id": r[0], "title": r[1], "access_code": r[2], "borrower": r[3], "borrower_id": r[4],
                        "email": r[5] or "-", "borrow_date": r[6], "borrow_time": r[7], "due_date": r[8],
                        "days_late": days_late, "fine_amount": fine, "reminder_sent": bool(r[9]),
                        "penalty_points": r[10] or 0, "status": display_status(None, "Outside", bool(r[11]))})
    conn.close()
    return jsonify({"records": records})

@app.route('/api/cron/overdue', methods=['GET', 'POST'])
def cron_overdue():
    if not is_cron_authorized():
        return jsonify({"success": False, "error": "Unauthorized. Set CRON_API_KEY and pass X-Cron-Key header."}), 401
    return jsonify(run_overdue_check())

@app.route('/api/send-overdue-reminder', methods=['POST'])
def send_overdue_reminder_route():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form
    borrow_id = str(data.get('borrow_id', '')).strip()
    if not borrow_id:
        return jsonify({"success": False, "error": "borrow_id required."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "error": "Database error."}), 500
    c = conn.cursor()
    c.execute("""SELECT br.id, b.title, b.access_code, u.full_name, br.borrower_email, br.borrow_date,
                 br.due_date, u.id, u.email, u.penalty_points FROM borrow_records br
                 JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
                 WHERE br.id = %s AND br.return_time IS NULL""", (int(borrow_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Overdue record not found."}), 404
    days_late, fine = compute_fine(row[6])
    email = (row[4] or "").strip() or (row[8] or "").strip()
    ok, msg = send_overdue_reminder(email, row[3], row[1], row[2], row[5], row[6], days_late, fine, row[9] or 0)
    if ok:
        c.execute("UPDATE borrow_records SET reminder_sent = TRUE, fine_amount = %s, last_reminder_date = %s WHERE id = %s",
                  (fine, get_ph_date(), row[0]))
        conn.commit()
    conn.close()
    return jsonify({"success": ok, "message": msg, "fine_amount": fine, "days_late": days_late})

@app.route('/api/send-all-overdue-reminders', methods=['POST'])
def send_all_overdue_reminders():
    if not is_logged_in() or get_role() != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "error": "Database error."}), 500
    c = conn.cursor()
    c.execute("""SELECT br.id, b.title, b.access_code, u.full_name, br.borrower_email, br.borrow_date,
                 br.due_date, u.id, u.email, u.penalty_points FROM borrow_records br
                 JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
                 WHERE br.return_time IS NULL AND br.borrow_type = 'Outside'
                 AND br.due_date IS NOT NULL AND br.due_date < %s""", (get_ph_date(),))
    rows = c.fetchall()
    sent = failed = 0
    for row in rows:
        email = (row[4] or "").strip() or (row[8] or "").strip()
        if not email or not EMAIL_RE.match(email):
            failed += 1
            continue
        days_late, fine = compute_fine(row[6])
        ok, _ = send_overdue_reminder(email, row[3], row[1], row[2], row[5], row[6], days_late, fine, row[9] or 0)
        if ok:
            c.execute("UPDATE borrow_records SET reminder_sent = TRUE, fine_amount = %s, last_reminder_date = %s WHERE id = %s",
                      (fine, get_ph_date(), row[0]))
            sent += 1
        else:
            failed += 1
    conn.commit()
    conn.close()
    return jsonify({"success": True, "sent": sent, "failed": failed,
                    "message": f"Sent {sent} overdue reminder(s). {failed} failed (no valid email on profile)."})


# ============================================================
# NEW FAST BORROW / RETURN / LOOKUP — no side-effect lookups
# ============================================================
@app.route('/api/lookup-book', methods=['POST'])
def lookup_book():
    """Side-effect-free book lookup used by the borrow/return scanner."""
    if not is_scan_authorized():
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    data = request.get_json(silent=True) or request.form
    code = str(data.get('code', '')).strip()
    if not code:
        return jsonify({"success": False, "message": "No code scanned."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
    c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location, quantity,
                 times_borrowed, last_borrowed_date FROM books
                 WHERE UPPER(access_code) = UPPER(%s) OR UPPER(COALESCE(barcode_number,'')) = UPPER(%s) LIMIT 1""", (code, code))
    book = c.fetchone()
    if not book:
        conn.close()
        return jsonify({"success": False, "message": f"Code '{code}' not found as a book."})
    book_id = book[0]
    active, available, status = book_status_info(book_id, book[7])
    borrowers = active_borrowers_of(book_id)
    conn.close()
    return jsonify({"success": True, "type": "book", "book": {
        "id": book_id, "access_code": book[1], "title": book[2], "author": book[3], "isbn": book[4],
        "category": book[5], "shelf_location": book[6], "quantity": book[7],
        "times_borrowed": book[8] or 0, "last_borrowed_date": book[9] or "-"},
        "available_qty": available, "active_borrows": active, "current_borrowers": borrowers, "status": status})

@app.route('/api/lookup-user', methods=['POST'])
def lookup_user():
    if not is_scan_authorized():
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    data = request.get_json(silent=True) or request.form
    id_number = str(data.get('id_number', '')).strip()
    if not id_number:
        return jsonify({"success": False, "message": "id_number is required."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
    c.execute("""SELECT u.id, u.full_name, u.id_number, u.id_type, u.email, u.department, u.year_level, u.penalty_points
                 FROM users u WHERE UPPER(id_number) = UPPER(%s)""", (id_number,))
    user = c.fetchone()
    conn.close()
    if not user:
        return jsonify({"success": False, "message": f"User ID '{id_number}' not found. Scan a registered Student/Employee/Visitor ID."})
    return jsonify({"success": True, "user": {"id": user[0], "full_name": user[1], "id_number": user[2], "id_type": user[3],
        "email": user[4] or "", "department": user[5] or "", "year_level": user[6] or "", "penalty_points": user[7] or 0}})

@app.route('/api/borrow-book', methods=['POST'])
def borrow_book():
    """NEW FLOW: auto-record after book + user scan.
       Inside (default): status='Borrowed', email confirmation sent silently if online.
       Outside: requires privacy_agreed=true; status='Pending Email Confirmation', email
       contains a confirmation link; borrower clicks it -> 'Borrowed (Confirmed)'."""
    if not is_scan_authorized():
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    data = request.get_json(silent=True) or request.form
    book_id = str(data.get('book_id', '')).strip()
    id_number = str(data.get('id_number', '')).strip()
    borrow_type = str(data.get('borrow_type', 'Inside')).strip()
    privacy_agreed = str(data.get('privacy_agreed', '')).strip().lower() in ("true", "1", "yes")
    due_date = str(data.get('due_date', '')).strip() or None
    if borrow_type.lower() not in ("inside", "outside"):
        borrow_type = "Inside"
    else:
        borrow_type = borrow_type.capitalize()
    if not book_id or not id_number:
        return jsonify({"success": False, "message": "book_id and id_number are required."}), 400
    if borrow_type == "Outside" and not privacy_agreed:
        return jsonify({"success": False, "message": "Please tick 'Outside Borrow' and click AGREE on the Privacy Policy popup."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
    try:
        c.execute("SELECT id, title, access_code, author, quantity FROM books WHERE id = %s", (int(book_id),))
        book = c.fetchone()
        if not book:
            conn.close()
            return jsonify({"success": False, "message": "Book not found."})
        active, available, _ = book_status_info(book[0], book[4])
        if available <= 0:
            conn.close()
            return jsonify({"success": False, "message": f"'{book[1]}' is fully borrowed. No copies available."})
        c.execute("SELECT id, full_name, email FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
        user = c.fetchone()
        if not user:
            conn.close()
            return jsonify({"success": False, "message": f"User ID '{id_number}' not found. Scan a registered Student/Employee/Visitor ID."})
        user_id, full_name, user_email = user
        email = (user_email or "").strip() or None
        today = get_ph_date()
        now = get_ph_time()
        token = None
        email_confirmed = True
        status = "Borrowed"
        if borrow_type == "Outside":
            if not due_date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
                due_date = add_days(today, OUTSIDE_BORROW_DAYS)
            token = secrets.token_urlsafe(24)
            email_confirmed = False
            status = "Pending Email Confirmation"
        else:
            due_date = None
        c.execute("""INSERT INTO borrow_records (book_id, user_id, borrow_date, borrow_time, status, borrow_type,
                     borrower_email, due_date, confirmation_token, email_confirmed)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                  (book[0], user_id, today, now, status, borrow_type, email, due_date, token, email_confirmed))
        borrow_id = c.fetchone()[0]
        c.execute("UPDATE books SET times_borrowed = times_borrowed + 1, last_borrowed_date = %s WHERE id = %s", (today, book[0]))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"BORROW ERROR: {e}")
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500
    conn.close()

    email_ok = False
    email_note = ""
    if email and EMAIL_RE.match(email):
        confirm_link = f"{BASE_URL}/confirm/{token}" if token else None
        email_ok, email_note = send_borrow_notification(
            email, full_name, book[1], book[3], book[2], today, now, borrow_type, due_date, confirm_link)
        if email_ok:
            conn2 = get_db()
            if conn2:
                try:
                    c2 = conn2.cursor()
                    c2.execute("UPDATE borrow_records SET email_sent = TRUE WHERE id = %s", (borrow_id,))
                    conn2.commit()
                except Exception:
                    conn2.rollback()
                finally:
                    conn2.close()

    base_msg = f"BORROWED ({borrow_type}): '{book[1]}' by {full_name} at {now}"
    if borrow_type == "Outside":
        due_txt = f". Due date: {due_date} ({OUTSIDE_BORROW_DAYS} days). Late fine \u20b1{LATE_FINE_PER_DAY:.2f}/day."
        if email_ok:
            full_msg = base_msg + due_txt + f" Confirmation email sent to {email}. Status: Pending Email Confirmation."
        else:
            note = email_note if email_note else "No email on profile — borrower cannot confirm by email."
            full_msg = base_msg + due_txt + f" NOTE: {note}"
    else:
        email_txt = f" Confirmation email sent to {email}." if email_ok else ""
        full_msg = base_msg + " (in-library use)." + email_txt
    return jsonify({"success": True, "message": full_msg, "book_title": book[1], "borrower": full_name,
                    "date": today, "time": now, "borrow_type": borrow_type, "due_date": due_date,
                    "email_sent": email_ok, "email_note": email_note, "status": status})

@app.route('/confirm/<token>')
def confirm_borrow(token):
    """Public link from the Outside-borrow confirmation email."""
    token = (token or "").strip()
    if not token:
        return render_template_string(CONFIRM_PAGE, result="error",
            msg="Invalid confirmation link.", book="-", borrower="-")
    conn = get_db()
    if not conn:
        return render_template_string(CONFIRM_PAGE, result="error",
            msg="Database unavailable. Please try again later.", book="-", borrower="-")
    c = conn.cursor()
    c.execute("""SELECT br.id, br.email_confirmed, b.title, u.full_name, br.due_date
                 FROM borrow_records br JOIN books b ON br.book_id = b.id
                 JOIN users u ON br.user_id = u.id WHERE br.confirmation_token = %s""", (token,))
    row = c.fetchone()
    if not row:
        conn.close()
        return render_template_string(CONFIRM_PAGE, result="error",
            msg="Confirmation link not found. It may have been used already or is invalid.", book="-", borrower="-")
    borrow_id, already, title, full_name, due_date = row
    if already:
        conn.close()
        return render_template_string(CONFIRM_PAGE, result="already", book=title, borrower=full_name,
            msg=f"'{title}' borrowed by {full_name} was already confirmed. Status: Borrowed (Confirmed).")
    c.execute("""UPDATE borrow_records SET email_confirmed = TRUE, status = 'Borrowed (Confirmed)',
                 confirmed_at = %s WHERE id = %s""", (get_ph_date() + " " + get_ph_time(), borrow_id))
    conn.commit()
    conn.close()
    return render_template_string(CONFIRM_PAGE, result="ok", book=title, borrower=full_name,
        msg=f"Thank you, {full_name}! Your borrow of '{title}' is now confirmed. "
            f"Status: Borrowed (Confirmed). Due date: {due_date or '-'}.")

@app.route('/api/return-book', methods=['POST'])
def return_book():
    """NEW FLOW: scan-based return. Send {book_id, id_number} and the matching active
       borrow is auto-returned. {borrow_id} still accepted for backward compatibility."""
    if not is_scan_authorized():
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    data = request.get_json(silent=True) or request.form
    borrow_id = str(data.get('borrow_id', '')).strip()
    book_id = str(data.get('book_id', '')).strip()
    id_number = str(data.get('id_number', '')).strip()
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
    if not borrow_id:
        if not book_id or not id_number:
            conn.close()
            return jsonify({"success": False, "message": "Scan the book, then scan the User ID to confirm return."}), 400
        c.execute("""SELECT br.id, b.title, u.full_name, br.due_date, br.borrow_type
                     FROM borrow_records br JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
                     WHERE br.book_id = %s AND br.return_time IS NULL
                     AND UPPER(u.id_number) = UPPER(%s) ORDER BY br.id ASC LIMIT 1""", (int(book_id), id_number))
        rec = c.fetchone()
        if not rec:
            conn.close()
            return jsonify({"success": False, "message": "No active borrow found for this book + user. Check that the right person scanned their ID."})
        borrow_id = rec[0]
    else:
        c.execute("""SELECT br.id, b.title, u.full_name, br.due_date, br.borrow_type
                     FROM borrow_records br JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
                     WHERE br.id = %s AND br.return_time IS NULL""", (int(borrow_id),))
        rec = c.fetchone()
        if not rec:
            conn.close()
            return jsonify({"success": False, "message": "This borrow record was already returned or not found."})
    today = get_ph_date()
    now = get_ph_time()
    days_late, fine = compute_fine(rec[3])
    c.execute("""UPDATE borrow_records SET return_date = %s, return_time = %s, status = 'Returned',
                 fine_amount = %s WHERE id = %s""", (today, now, fine, int(borrow_id)))
    conn.commit()
    conn.close()
    fine_txt = f" — {days_late} day(s) late, fine \u20b1{fine:.2f}" if days_late > 0 else ""
    return jsonify({"success": True, "message": f"RETURNED: '{rec[1]}' (borrowed by {rec[2]}) at {now}{fine_txt}",
                    "book_title": rec[1], "borrower": rec[2], "date": today, "time": now,
                    "days_late": days_late, "fine_amount": fine})

@app.route('/api/smart-scan', methods=['POST'])
def smart_scan():
    """Unified scan for ATTENDANCE only (Time In/Out). Borrow/return use /api/lookup-book + /api/lookup-user."""
    if not is_scan_authorized():
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    data = request.get_json(silent=True) or request.form
    code = str(data.get('code', '')).strip()
    if not code:
        return jsonify({"success": False, "message": "No code scanned."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
    today = get_ph_date()
    now = get_ph_time()
    c.execute("SELECT id, full_name, id_number FROM users WHERE UPPER(id_number) = UPPER(%s)", (code,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False, "message": f"Code '{code}' not found as a User ID (attendance mode)."})
    user_id, full_name, _ = user
    c.execute("SELECT id, time_in, time_out FROM attendance WHERE user_id = %s AND scan_date = %s ORDER BY id DESC LIMIT 1", (user_id, today))
    last_attendance = c.fetchone()
    if not last_attendance or last_attendance[2]:
        c.execute("INSERT INTO attendance (user_id, time_in, scan_date) VALUES (%s, %s, %s)", (user_id, now, today))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "type": "attendance", "action": "time_in",
                        "message": f"TIME IN recorded — {full_name} — {now}",
                        "user": {"full_name": full_name, "id_number": code, "date": today, "time_in": now, "time_out": "-"}})
    c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "type": "attendance", "action": "time_out",
                    "message": f"TIME OUT recorded — {full_name} — {now}",
                    "user": {"full_name": full_name, "id_number": code, "date": today, "time_in": last_attendance[1], "time_out": now}})

@app.route('/get-borrow-records')
def get_borrow_records():
    if not is_logged_in():
        return jsonify({"records": []})
    book_id = request.args.get('book_id', '').strip()
    borrower = request.args.get('borrower', '').strip()
    status = request.args.get('status', '').strip()
    date_filter = request.args.get('date', '').strip()
    conn = get_db()
    if not conn:
        return jsonify({"records": []})
    c = conn.cursor()
    query = """SELECT br.id, b.title, b.access_code, u.full_name, u.id_number, br.borrow_date, br.borrow_time,
               br.return_date, br.return_time, br.status, br.borrow_type, br.borrower_email, br.email_sent,
               br.due_date, br.fine_amount, br.email_confirmed
               FROM borrow_records br JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id WHERE 1=1"""
    params = []
    if book_id:
        query += " AND b.id = %s"
        params.append(int(book_id))
    if borrower:
        query += " AND (UPPER(u.full_name) LIKE UPPER(%s) OR UPPER(u.id_number) LIKE UPPER(%s))"
        params.extend([f"%{borrower}%", f"%{borrower}%"])
    if status in ("Borrowed", "Returned"):
        if status == "Borrowed":
            query += " AND br.return_time IS NULL"
        else:
            query += " AND br.return_time IS NOT NULL"
    if date_filter and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_filter):
        query += " AND br.borrow_date = %s"
        params.append(date_filter)
    query += " ORDER BY br.id DESC"
    c.execute(query, params)
    records = []
    for r in c.fetchall():
        days_late, fine = compute_fine(r[13], r[7])
        records.append({"id": r[0], "title": r[1], "access_code": r[2], "borrower": r[3], "borrower_id": r[4],
                        "borrow_date": r[5], "borrow_time": r[6], "return_date": r[7] or "-", "return_time": r[8] or "-",
                        "status": display_status(r[8], r[10], bool(r[15])), "borrow_type": r[10] or "Inside",
                        "borrower_email": r[11] or "-", "email_sent": bool(r[12]), "due_date": r[13] or "-",
                        "fine_amount": r[14] or fine, "days_late": days_late})
    conn.close()
    return jsonify({"records": records})

# ============================================================
# REGISTER / UPDATE / GET USERS + RECORDS + DOWNLOADS
# ============================================================
@app.route('/register', methods=['POST'])
def register():
    if not is_logged_in():
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        id_type = request.form.get('id_type', '').strip()
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip() or None
        major = request.form.get('major', '').strip() or None
        contact_number = request.form.get('contact_number', '').strip()
        address = request.form.get('address', '').strip()
        year_level = request.form.get('year_level', '').strip() or None
        id_number = request.form.get('id_number', '').strip().upper()
        email = request.form.get('email', '').strip() or None
        if id_type not in {"Student", "Employee", "Visitor"}:
            return jsonify({"success": False, "error": "Please select a valid ID type."}), 400
        if id_type in {"Employee", "Visitor"} and not id_number:
            id_number = _generate_next_id("EMP" if id_type == "Employee" else "VIS")
        if not full_name or not id_number or not contact_number or not address:
            return jsonify({"success": False, "error": "Full name, contact number, and address are required."}), 400
        if email and not EMAIL_RE.match(email):
            return jsonify({"success": False, "error": "Invalid email address format."}), 400
        if id_type == "Employee":
            department, major, year_level = "EMPLOYEE", None, None
        elif id_type == "Visitor":
            department, major, year_level = None, None, None
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database connection failed."}), 500
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
        if c.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "This ID number is already registered."}), 400
        registered_at = get_ph_date() + " " + get_ph_time()
        c.execute("""INSERT INTO users (id_type, full_name, department, major, contact_number, address,
                     year_level, id_number, registered_at, email) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at, email))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "info": f"{full_name} | ID: {id_number} | {id_type}",
                        "barcode": generate_barcode_b64(id_number), "id_number": id_number})
    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        return jsonify({"success": False, "error": f"An error occurred: {str(e)}"}), 500

@app.route('/get-students')
def get_students():
    if not is_logged_in():
        return jsonify({"students": []})
    conn = get_db()
    if not conn:
        return jsonify({"students": []})
    c = conn.cursor()
    c.execute("""SELECT id, id_type, full_name, department, major, contact_number, address, year_level,
                 id_number, email, penalty_points FROM users ORDER BY full_name""")
    students = [{"id": r[0], "id_type": r[1], "full_name": r[2], "department": r[3], "major": r[4],
                 "contact_number": r[5], "address": r[6], "year_level": r[7], "id_number": r[8],
                 "email": r[9] or "", "penalty_points": r[10] or 0,
                 "department_display": get_student_code(r[1], r[3], r[7])} for r in c.fetchall()]
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
        email = request.form.get('email', '').strip() or None
        if id_type not in {"Student", "Employee", "Visitor"}:
            return jsonify({"success": False, "error": "Please select a valid ID type."}), 400
        if not all([student_id, id_number, full_name, contact_number, address]):
            return jsonify({"success": False, "error": "Full name, ID number, contact number, and address are required."}), 400
        if email and not EMAIL_RE.match(email):
            return jsonify({"success": False, "error": "Invalid email address format."}), 400
        if id_type == "Employee":
            department, major, year_level = "EMPLOYEE", None, None
        elif id_type == "Visitor":
            department, major, year_level = None, None, None
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database error."}), 500
        c = conn.cursor()
        c.execute("""UPDATE users SET id_type=%s, id_number=%s, full_name=%s, department=%s, major=%s,
                     contact_number=%s, address=%s, year_level=%s, email=%s WHERE id=%s""",
                  (id_type, id_number, full_name, department, major, contact_number, address, year_level, email, int(student_id)))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(f"UPDATE ERROR: {e}")
        return jsonify({"success": False, "error": f"An error occurred: {str(e)}"}), 500

@app.route('/get-records')
def get_records():
    if not is_logged_in():
        return jsonify({"records": []})
    conn = get_db()
    if not conn:
        return jsonify({"records": []})
    c = conn.cursor()
    c.execute("""SELECT a.scan_date, u.full_name, u.id_type, u.department, u.year_level, a.time_in, a.time_out
                 FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.scan_date = %s ORDER BY a.id DESC""", (get_ph_date(),))
    records = [{"scan_date": r[0], "full_name": r[1], "department": get_student_code(r[2], r[3], r[4]),
                "time_in": r[5], "time_out": r[6]} for r in c.fetchall()]
    conn.close()
    return jsonify({"records": records})

@app.route('/get-monthly-history')
def get_monthly_history():
    if not is_logged_in():
        return jsonify({"records": []})
    month = request.args.get('month', '').strip()
    selected_date = request.args.get('date', '').strip()
    conn = get_db()
    if not conn:
        return jsonify({"records": []})
    c = conn.cursor()
    query = """SELECT a.scan_date, u.full_name, u.id_type, u.department, u.year_level, u.id_number, a.time_in, a.time_out
               FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.scan_date LIKE %s"""
    params = (f"{month}%",)
    if selected_date:
        query += " AND a.scan_date = %s"
        params = (f"{month}%", selected_date)
    query += " ORDER BY a.scan_date DESC, a.id DESC"
    c.execute(query, params)
    records = [{"scan_date": r[0], "full_name": r[1], "department": get_student_code(r[2], r[3], r[4]),
                "id_number": r[5], "time_in": r[6], "time_out": r[7]} for r in c.fetchall()]
    conn.close()
    return jsonify({"records": records})

@app.route('/download-word')
def download_word():
    if not is_logged_in():
        return ""
    conn = get_db()
    if not conn:
        return "Database error"
    today = get_ph_date()
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_number, u.id_type, u.department, u.year_level, a.time_in, a.time_out
                 FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.scan_date = %s ORDER BY a.id""", (today,))
    records = c.fetchall()
    conn.close()
    doc = Document()
    doc.add_heading(f'Library Attendance Report — {today}', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('SLSU–JGE Library Management System')
    table = doc.add_table(rows=1, cols=5)
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text, hdr[4].text = 'Full Name', 'Department', 'ID Number', 'Time In', 'Time Out'
    for rec in records:
        row = table.add_row().cells
        row[0].text = rec[0]; row[1].text = get_student_code(rec[2], rec[3], rec[4]); row[2].text = rec[1]
        row[3].text = rec[5] or '-'; row[4].text = rec[6] or '-'
    buffer = BytesIO(); doc.save(buffer); buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Disposition'] = f'attachment; filename=attendance_report_{today}.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp

@app.route('/download-monthly-word')
def download_monthly_word():
    if not is_logged_in():
        return ""
    month = request.args.get('month', '').strip()
    conn = get_db()
    if not conn:
        return "Database error"
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_type, u.department, u.year_level, a.scan_date, a.time_in, a.time_out
                 FROM attendance a JOIN users u ON a.user_id = u.id WHERE a.scan_date LIKE %s ORDER BY a.scan_date, a.id""", (f"{month}%",))
    records = c.fetchall()
    conn.close()
    doc = Document()
    doc.add_heading(f'Monthly Attendance Report — {month}', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('SLSU–JGE Library Management System')
    current_date = None; table = None
    for rec in records:
        if rec[4] != current_date:
            current_date = rec[4]
            doc.add_heading(current_date, level=2)
            table = doc.add_table(rows=1, cols=5); table.style = 'Table Grid'
            hdr = table.rows[0].cells
            hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text, hdr[4].text = 'Date', 'Full Name', 'Department', 'Time In', 'Time Out'
        row = table.add_row().cells
        row[0].text = rec[4]; row[1].text = rec[0]; row[2].text = get_student_code(rec[1], rec[2], rec[3])
        row[3].text = rec[5] or '-'; row[4].text = rec[6] or '-'
    buffer = BytesIO(); doc.save(buffer); buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Disposition'] = f'attachment; filename=monthly_attendance_{month}.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp

@app.route('/download-borrow-word')
def download_borrow_word():
    if not is_logged_in():
        return ""
    conn = get_db()
    if not conn:
        return "Database error"
    c = conn.cursor()
    c.execute("""SELECT b.title, b.access_code, u.full_name, u.id_number, br.borrow_date, br.borrow_time,
                 br.return_date, br.return_time, br.borrow_type, br.due_date, br.fine_amount, br.email_confirmed
                 FROM borrow_records br JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id ORDER BY br.id DESC""")
    records = c.fetchall()
    conn.close()
    doc = Document()
    doc.add_heading('Library Book Borrow & Return Records', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('SLSU–JGE Library Management System')
    table = doc.add_table(rows=1, cols=8); table.style = 'Table Grid'
    hdr = table.rows[0].cells
    for i, h in enumerate(['Book Title / Book ID', 'Borrower Name & ID', 'Borrow Type', 'Date & Time Borrowed',
                           'Due Date', 'Date & Time Returned', 'Overdue Fine (\u20b1)', 'Current Status']):
        hdr[i].text = h
    for rec in records:
        row = table.add_row().cells
        row[0].text = f"{rec[0]} ({rec[1]})"; row[1].text = f"{rec[2]} ({rec[3]})"; row[2].text = rec[8] or 'Inside'
        row[3].text = f"{rec[4]} {rec[5]}"; row[4].text = rec[9] or '-'
        row[5].text = f"{rec[6]} {rec[7]}" if rec[6] else '-'
        fine = rec[10] or 0
        row[6].text = f"\u20b1{float(fine):.2f}" if float(fine) > 0 else '-'
        row[7].text = display_status(rec[7], rec[8], bool(rec[11]))
    buffer = BytesIO(); doc.save(buffer); buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Disposition'] = 'attachment; filename=book_borrow_records.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp

@app.route('/print-monthly')
def print_monthly():
    if not is_logged_in():
        return ""
    month = request.args.get('month', '').strip()
    return f"""<html><head><title>Monthly Attendance — {month}</title></head><body>
    <h2>Monthly Attendance Report — {month}</h2>
    <p>SLSU–JGE Library Management System &bull; Generated: {get_ph_date()} {get_ph_time()}</p>
    <div id="print-area"></div>
    <script>window.onload=function(){{fetch('/get-monthly-history?month={month}').then(r=>r.json()).then(d=>{{
      var h='<table border=1 cellpadding=6><tr><th>Date</th><th>Name</th><th>Dept</th><th>ID</th><th>In</th><th>Out</th></tr>';
      d.records.forEach(r=>{{h+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+r.department+'</td><td>'+r.id_number+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>';}});
      document.getElementById('print-area').innerHTML=h+'</table>'; window.print();}});}};</script>
    </body></html>"""

@app.route('/print-daily')
def print_daily():
    if not is_logged_in():
        return ""
    selected_date = request.args.get('date', '').strip() or get_ph_date()
    return f"""<html><head><title>Daily Attendance — {selected_date}</title></head><body>
    <h2>Daily Attendance Report — {selected_date}</h2>
    <p>SLSU–JGE Library Management System &bull; Generated: {get_ph_date()} {get_ph_time()}</p>
    <div id="print-area"></div>
    <script>window.onload=function(){{fetch('/get-monthly-history?month={selected_date[:7]}&date={selected_date}').then(r=>r.json()).then(d=>{{
      var h='<table border=1 cellpadding=6><tr><th>Name</th><th>Dept</th><th>ID</th><th>In</th><th>Out</th></tr>';
      d.records.forEach(r=>{{h+='<tr><td>'+r.full_name+'</td><td>'+r.department+'</td><td>'+r.id_number+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>';}});
      document.getElementById('print-area').innerHTML=h+'</table>'; window.print();}});}};</script>
    </body></html>"""

@app.route('/print-borrow-records')
def print_borrow_records():
    if not is_logged_in():
        return ""
    return f"""<html><head><title>Borrow Records</title></head><body>
    <h2>Book Borrow & Return Records</h2>
    <p>SLSU–JGE Library Management System &bull; Generated: {get_ph_date()} {get_ph_time()}</p>
    <div id="print-area"></div>
    <script>window.onload=function(){{fetch('/get-borrow-records').then(r=>r.json()).then(d=>{{
      var h='<table border=1 cellpadding=6><tr><th>Book</th><th>Borrower</th><th>Type</th><th>Borrowed</th><th>Due</th><th>Returned</th><th>Fine</th><th>Status</th></tr>';
      d.records.forEach(r=>{{h+='<tr><td>'+r.title+'</td><td>'+r.borrower+'</td><td>'+r.borrow_type+'</td><td>'+r.borrow_date+' '+r.borrow_time+'</td><td>'+r.due_date+'</td><td>'+(r.return_date!=='-'?r.return_date+' '+r.return_time:'-')+'</td><td>'+(r.fine_amount>0?'\\u20b1'+r.fine_amount.toFixed(2):'-')+'</td><td>'+r.status+'</td></tr>';}});
      document.getElementById('print-area').innerHTML=h+'</table>'; window.print();}});}};</script>
    </body></html>"""

@app.route('/scan', methods=['POST'])
@app.route('/api/scan', methods=['POST'])
def scan():
    if not is_scan_authorized():
        message = "Unauthorized. Log in or provide the X-Scanner-Key header."
        if not SCANNER_API_KEY and not is_logged_in():
            message = "Scanner API is not configured. Set the SCANNER_API_KEY environment variable."
        return jsonify({"success": False, "message": message}), 401
    data = request.get_json(silent=True) or request.form
    id_number = str(data.get('id_number', '')).strip()
    if not id_number:
        return jsonify({"success": False, "message": "id_number is required."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
    today = get_ph_date(); now = get_ph_time()
    c.execute("SELECT id, full_name, id_number FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False, "message": f"ID {id_number} was not found in the records."})
    user_id, full_name, _ = user
    c.execute("SELECT id, time_in, time_out FROM attendance WHERE user_id = %s AND scan_date = %s ORDER BY id DESC LIMIT 1", (user_id, today))
    last_attendance = c.fetchone()
    if not last_attendance or last_attendance[2]:
        c.execute("INSERT INTO attendance (user_id, time_in, scan_date) VALUES (%s, %s, %s)", (user_id, now, today))
        conn.commit(); conn.close()
        return jsonify({"success": True, "message": f"TIME IN recorded — {full_name} — {now}"})
    c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
    conn.commit(); conn.close()
    return jsonify({"success": True, "message": f"TIME OUT recorded — {full_name} — {now}"})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "email_configured": bool(SMTP_USER and SMTP_PASS),
                    "outside_borrow_days": OUTSIDE_BORROW_DAYS,
                    "overdue_scheduler": os.environ.get("DISABLE_OVERDUE_SCHEDULER", "").strip() != "1"})


# ============================================================
# LOGIN / PRIVACY / CONFIRM PAGES
# ============================================================
PRIVACY_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Privacy Policy - SLSU Library Management System</title><style>
body{font-family:Arial,Helvetica,sans-serif;max-width:860px;margin:30px auto;padding:0 20px;color:#1b2a41;line-height:1.6;}
h1{color:#1b2a41;border-bottom:3px solid #1b2a41;padding-bottom:8px;} h2{color:#1b4a7a;margin-top:28px;}
table{border-collapse:collapse;width:100%;margin:12px 0;} td,th{border:1px solid #cbd5e1;padding:8px 10px;font-size:14px;text-align:left;}
th{background:#eef2f7;} .foot{margin-top:30px;font-size:13px;color:#64748b;border-top:1px solid #e2e8f0;padding-top:14px;}</style></head><body>
<h1>Privacy Policy — SLSU Library Management System</h1>
<p><em>Last Updated: November 2026</em></p>
<h2>1. Who We Are</h2>
<p>This system — SLSU Library Management System — is designed exclusively for Southern Luzon State University (SLSU), Judge Guillermo Eleazar campus, to manage library entry/exit records and book borrowing (inside and outside).</p>
<h2>2. Exactly What Information We Collect</h2>
<p>Only the fields you enter during registration: Full Name, ID Type, ID Number (your barcode), Email Address (collected once; auto-used for outside-borrow confirmations and overdue reminders), Department, Year Level, Major, Contact Number, Complete Address, and auto-tracked Penalty Points. Attendance (Time In/Out/Date) and book-borrow data are recorded automatically on scan. We do <strong>not</strong> collect passwords, photos, biometrics, location, browsing history, or financial information.</p>
<h2>3. How We Use Your Information</h2>
<p>Only to verify identity, record attendance, manage book borrows, generate staff reports, and send borrow/overdue notifications to your email on file. We never sell, rent, or share your data, nor send commercial ads.</p>
<h2>4. Data Storage and Security</h2>
<p>PostgreSQL on Render/Supabase Cloud (encrypted, password-protected); all transmission over HTTPS; only the System Administrator has full database access.</p>
<h2>5. Who Can See Your Data</h2>
<table><tr><th>Role</th><th>Access</th></tr>
<tr><td>System Administrator (library/slsu)</td><td>Full access: manage books, attendance, borrows, reports; edit/print/delete/download; send overdue reminders; run daily overdue checks.</td></tr>
<tr><td>Library Staff (slsu/library)</td><td>Register users, scan attendance, process borrows/returns, view daily &amp; borrow records, search books.</td></tr>
<tr><td>Individual User (student/student)</td><td>Registration form and barcode generation only.</td></tr>
<tr><td>Public / Visitors</td><td>No access — login required.</td></tr></table>
<h2>6. Your Rights</h2>
<p>Register and create your own barcode; request correction of incorrect info; request data deletion on graduation/resignation/separation; scan your printed barcode for entry/exit and book borrows; know your data is protected and never shared or sold.</p>
<h2>7. Outside Borrow Liability</h2>
<p>Outside (take-home) borrows are due 7 days from borrow. You tick "Outside Borrow", click <strong>AGREE</strong> on the privacy popup, then scan your Student ID — the transaction records automatically. A confirmation email is sent; until you click its confirmation link, the borrow shows as <em>Pending Email Confirmation</em>, then <em>Borrowed (Confirmed)</em>. You are fully liable for damage and must pay full replacement cost if lost. A late fine of &#8369;5.00/day applies after the due date, and penalty points are deducted daily once 7+ days overdue. Confirmation emails and overdue reminders are sent automatically to your profile email.</p>
<h2>8. About the System</h2>
<p>Created for SLSU — Judge Guillermo Eleazar campus to streamline library attendance and book borrowing while prioritizing privacy and data security.</p>
<h2>9. Changes to This Policy</h2><p>Updates will be posted here with a revised date.</p>
<h2>10. Contact</h2><p>SLSU-JGE Library, Southern Luzon State University — Judge Guillermo Eleazar.</p>
<p class="foot">By registering, generating your barcode, scanning your ID, and borrowing books, you confirm you have read, understood, and agree to this Privacy Policy.</p>
</body></html>"""

@app.route('/privacy')
def privacy_policy():
    return render_template_string(PRIVACY_PAGE)

CONFIRM_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Borrow Confirmation — SLSU-JGE Library</title><style>
body{font-family:Arial,Helvetica,sans-serif;background:#eef2f7;display:flex;align-items:center;justify-content:center;min-height:90vh;margin:0;}
.box{background:#fff;padding:36px 40px;border-radius:12px;max-width:520px;box-shadow:0 8px 30px rgba(27,42,65,.15);text-align:center;}
.ok{color:#1b6b3a;} .already{color:#8a6d1f;} .error{color:#a12622;}
h2{margin-top:0;} p{color:#374151;line-height:1.6;} .logo{font-weight:800;color:#1b2a41;letter-spacing:1px;margin-bottom:14px;}</style></head>
<body><div class="box"><div class="logo">SLSU-JGE LIBRARY</div>
{% if result == "ok" %}<h2 class="ok">Borrow Confirmed</h2>{% elif result == "already" %}<h2 class="already">Already Confirmed</h2>{% else %}<h2 class="error">Confirmation Failed</h2>{% endif %}
<p>{{ msg }}</p><p style="font-size:13px;color:#64748b;">Southern Luzon State University — Judge Guillermo Eleazar</p></div></body></html>"""

LOGIN_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SLSU-JGE Library Management System — Log In</title><style>
*{box-sizing:border-box;} body{margin:0;font-family:Arial,Helvetica,sans-serif;background:linear-gradient(135deg,#1b2a41,#2c4a6e);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
.login-wrap{background:#fff;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.35);width:100%;max-width:400px;overflow:hidden;}
.header{background:#1b2a41;color:#fff;padding:26px 24px;text-align:center;} .header img{width:72px;height:72px;border-radius:50%;background:#fff;padding:4px;}
.header h1{margin:10px 0 4px;font-size:18px;} .header p{margin:0;font-size:12px;opacity:.85;}
form{padding:26px 24px;} label{display:block;font-size:13px;font-weight:600;color:#374151;margin:12px 0 6px;}
input{width:100%;padding:11px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;}
button{width:100%;margin-top:20px;padding:12px;background:#1b6b3a;color:#fff;border:0;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;}
button:hover{background:#15572f;} .error{background:#fde8e8;color:#a12622;padding:10px 12px;border-radius:8px;font-size:13px;margin-bottom:8px;}
.links{text-align:center;padding:0 24px 22px;font-size:12px;} .links a{color:#1b4a7a;text-decoration:none;margin:0 6px;}</style></head><body>
<div class="login-wrap"><div class="header"><img src="__SLSU_LOGO__" alt="SLSU Seal"><h1>Southern Luzon State University</h1><p>Judge Guillermo Eleazar &bull; Library Management System</p></div>
<form method="POST" action="/login">__ERROR__
<label>Username</label><input type="text" name="username" required autofocus>
<label>Password</label><input type="password" name="password" required>
<button type="submit">Log In</button></form>
<div class="links"><a href="/privacy" target="_blank">Privacy Policy</a></div></div></body></html>"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form.get('username', '').strip()
        pword = request.form.get('password', '').strip()
        role = None
        if uname == ADMIN_USER and pword == ADMIN_PASS:
            role = 'admin'
        elif uname == USER_USER and pword == USER_PASS:
            role = 'user'
        elif uname == STUDENT_USER and pword == STUDENT_PASS:
            role = 'student'
        if role:
            resp = make_response("")
            resp.set_cookie('logged_in', 'true', max_age=31536000)
            resp.set_cookie('role', role, max_age=31536000)
            return resp
        error_html = '<div class="error">The username or password you entered is incorrect. Please try again.</div>'
        return LOGIN_PAGE.replace("__ERROR__", error_html).replace("__SLSU_LOGO__", SLSU_LOGO_DATA_URI)
    return LOGIN_PAGE.replace("__ERROR__", "").replace("__SLSU_LOGO__", SLSU_LOGO_DATA_URI)

# ============================================================
# SHARED CSS + JAVASCRIPT + FAST-BORROW SCANNER
# ============================================================
APP_CSS = """*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Segoe UI',Arial,Helvetica,sans-serif;background:#eef2f7;color:#1b2a41;font-size:14px;}
a{color:#1b4a7a;} .hidden{display:none!important;}
.brand-mark{width:52px;height:52px;border-radius:50%;background:#1b2a41;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;text-align:center;line-height:1.1;flex-shrink:0;}
.btn-primary,.btn-save,.btn-cancel,.btn-print,.btn-download,.btn-download-barcode,.btn-barcode,.btn-delete,.btn-remind,.btn-month-print,.btn-delete-daily{padding:10px 18px;border:0;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;margin:4px 4px 4px 0;}
.btn-primary,.btn-save{background:#1b6b3a;color:#fff;} .btn-primary:hover,.btn-save:hover{background:#15572f;}
.btn-cancel{background:#64748b;color:#fff;} .btn-print{background:#1b4a7a;color:#fff;}
.btn-download,.btn-download-barcode{background:#2c4a6e;color:#fff;} .btn-barcode{background:#8a6d1f;color:#fff;}
.btn-delete,.btn-delete-daily{background:#a12622;color:#fff;} .btn-remind{background:#1b6b3a;color:#fff;} .btn-month-print{background:#1b4a7a;color:#fff;}
.status{padding:12px 16px;border-radius:8px;margin:12px 0;font-size:14px;font-weight:600;}
.status.info{background:#e3edf9;color:#1b4a7a;border:1px solid #bcd3ee;}
.status.success{background:#e3f4ea;color:#1b6b3a;border:1px solid #b7e0c6;}
.status.error{background:#fde8e8;color:#a12622;border:1px solid #f3c2c0;}
#toast{position:fixed;top:18px;right:18px;z-index:9999;max-width:360px;}
.toast-msg{padding:12px 16px;border-radius:8px;margin-bottom:8px;color:#fff;font-weight:600;box-shadow:0 6px 18px rgba(0,0,0,.25);animation:slidein .25s ease;}
.toast-msg.ok{background:#1b6b3a;} .toast-msg.err{background:#a12622;} .toast-msg.info{background:#1b4a7a;}
@keyframes slidein{from{transform:translateX(40px);opacity:0;}to{transform:translateX(0);opacity:1;}}
table{width:100%;border-collapse:collapse;font-size:13px;} th,td{padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:middle;}
th{background:#1b2a41;color:#fff;position:sticky;top:0;} tr:hover td{background:#f6f9fc;}
.table-wrap{overflow:auto;max-height:520px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;margin-top:10px;}
input,select,textarea{padding:9px 10px;border:1px solid #cbd5e1;border-radius:7px;font-size:13px;width:100%;background:#fff;}
label{display:block;font-size:12px;font-weight:700;color:#475569;margin-bottom:5px;text-transform:uppercase;letter-spacing:.3px;}
.form-group{margin-bottom:12px;} .form-row{display:flex;gap:14px;} .form-row .form-group{flex:1;}
.panel-card{background:#fff;border-radius:12px;padding:22px;box-shadow:0 4px 14px rgba(27,42,65,.08);margin-bottom:20px;}
.panel-title{font-size:17px;color:#1b2a41;margin-bottom:14px;border-left:4px solid #1b6b3a;padding-left:10px;}
.filter-row,.search-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px;}
.filter-row input,.filter-row select{width:auto;max-width:180px;} .search-box{margin-bottom:12px;}
.scan-input{font-size:16px;padding:14px 16px;border:2px solid #1b4a7a;border-radius:10px;letter-spacing:.5px;}
.scan-input:focus{outline:none;border-color:#1b6b3a;box-shadow:0 0 0 3px rgba(27,107,58,.18);}
/* ---- Fast borrow scanner ---- */
.mode-toggle{display:flex;gap:8px;margin-bottom:14px;}
.mode-btn{flex:1;max-width:160px;padding:11px;border:2px solid #cbd5e1;background:#fff;border-radius:9px;font-weight:700;font-size:14px;cursor:pointer;color:#64748b;}
.mode-btn.active{border-color:#1b6b3a;background:#1b6b3a;color:#fff;}
.outside-row{margin:0 0 14px;font-size:14px;font-weight:600;color:#1b2a41;display:flex;align-items:center;gap:8px;}
.outside-row input{width:auto;margin:0;transform:scale(1.2);}
.detail-card{background:#f6f9fc;border:1px solid #d6e2f0;border-left:5px solid #1b4a7a;border-radius:9px;padding:14px 18px;margin:12px 0;}
.detail-card h4{margin-bottom:8px;color:#1b2a41;} .detail-card .kv{display:grid;grid-template-columns:160px 1fr;gap:4px 12px;font-size:13px;}
.detail-card .kv .k{color:#64748b;font-weight:600;}
.modal-overlay{position:fixed;inset:0;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;z-index:10000;padding:20px;}
.modal-box{background:#fff;border-radius:12px;max-width:440px;width:100%;padding:26px;box-shadow:0 20px 60px rgba(0,0,0,.35);}
.modal-box h3{color:#1b2a41;margin-bottom:12px;} .modal-box p{color:#374151;line-height:1.6;margin-bottom:18px;font-size:14px;}
/* ---- Staff topnav ---- */
.topnav{background:#1b2a41;color:#fff;display:flex;align-items:center;gap:18px;padding:10px 22px;flex-wrap:wrap;}
.brand{display:flex;align-items:center;gap:12px;} .brand-text h1{font-size:16px;} .brand-text p{font-size:11px;opacity:.8;}
.nav-tabs{display:flex;gap:4px;flex:1;flex-wrap:wrap;} .nav-tab{padding:9px 14px;border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;opacity:.8;}
.nav-tab:hover{background:rgba(255,255,255,.1);} .nav-tab.active{background:#1b6b3a;opacity:1;}
.logout-btn{background:#a12622;color:#fff;border:0;padding:9px 16px;border-radius:7px;font-weight:700;cursor:pointer;}
.staff-content{padding:22px;max-width:1200px;margin:0 auto;} .staff-tab{display:none;} .staff-tab.active{display:block;}
/* ---- Registration card ---- */
.container{max-width:720px;margin:24px auto;padding:0 16px;}
.card{background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 8px 30px rgba(27,42,65,.12);}
.card-top{height:8px;background:linear-gradient(90deg,#1b6b3a,#1b4a7a);}
.card-body{padding:26px 28px;} .card-body h1{font-size:22px;margin-bottom:4px;} .subtitle{color:#64748b;font-size:13px;margin-bottom:18px;}
.reg-brand-mark{width:56px;height:56px;border-radius:50%;background:#1b2a41;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;margin-bottom:12px;text-align:center;line-height:1.1;}
.barcode-result{margin-top:20px;padding:18px;background:#e3f4ea;border-radius:10px;text-align:center;display:none;}
.barcode-id{font-weight:700;color:#1b6b3a;margin:8px 0;} .barcode-img{max-width:260px;height:auto;margin:10px 0;}
.privacy-link,.logout-link{display:inline-block;margin-top:14px;font-size:13px;margin-right:14px;}
/* ---- Admin sidebar ---- */
.app-container{display:flex;min-height:100vh;}
.sidebar{width:250px;background:#1b2a41;color:#fff;position:fixed;top:0;left:0;height:100vh;overflow-y:auto;transition:transform .25s;z-index:100;padding:16px 0;}
.sidebar.collapsed{transform:translateX(-100%);}
.sidebar-overlay{position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:90;display:none;} .sidebar-overlay.show{display:block;}
.toggle-btn{position:absolute;top:14px;right:-14px;background:#1b6b3a;color:#fff;border:0;width:28px;height:28px;border-radius:50%;cursor:pointer;z-index:110;}
.sidebar-header{text-align:center;padding:10px 16px 18px;border-bottom:1px solid rgba(255,255,255,.12);}
.sidebar-header .brand-mark{margin:0 auto 10px;} .full-title{font-size:16px;} .sidebar-header p{font-size:11px;opacity:.75;}
.sidebar-menu{padding:10px 0;} .menu-item{display:flex;align-items:center;gap:12px;padding:12px 18px;cursor:pointer;font-size:13px;font-weight:600;opacity:.85;}
.menu-item:hover{background:rgba(255,255,255,.08);opacity:1;} .menu-item.active{background:#1b6b3a;opacity:1;}
.menu-item .badge{background:rgba(255,255,255,.18);padding:2px 7px;border-radius:5px;font-size:11px;}
.sidebar-footer{padding:16px;text-align:center;border-top:1px solid rgba(255,255,255,.12);}
.main-content{flex:1;margin-left:250px;transition:margin .25s;min-width:0;} .main-content.expanded{margin-left:0;}
.content-header{background:#fff;padding:14px 24px;display:flex;align-items:center;gap:14px;box-shadow:0 2px 6px rgba(0,0,0,.06);position:sticky;top:0;z-index:50;}
.content-header h1{font-size:18px;} .hamburger{background:#1b2a41;color:#fff;border:0;padding:8px 14px;border-radius:7px;cursor:pointer;font-weight:700;}
.content-card{padding:22px;max-width:1280px;margin:0 auto;} .tab-content{display:none;} .tab-content.active{display:block;}
.dept-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0;}
.dept-tab{padding:7px 14px;border:1px solid #cbd5e1;background:#fff;border-radius:20px;cursor:pointer;font-size:12px;font-weight:700;color:#64748b;}
.dept-tab.active{background:#1b4a7a;color:#fff;border-color:#1b4a7a;}
.student-actions{margin:10px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
.edit-modal{position:fixed;inset:0;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;z-index:10000;padding:20px;}
.edit-dialog{background:#fff;border-radius:12px;max-width:640px;width:100%;max-height:92vh;overflow-y:auto;padding:24px;}
.edit-dialog-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;}
.edit-close{background:none;border:0;font-size:26px;cursor:pointer;color:#64748b;}
.qr-result{margin-top:18px;padding:18px;background:#e3f4ea;border-radius:10px;text-align:center;display:none;}
.action-row{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:10px;}
.overdue-summary{background:#fde8e8;border:1px solid #f3c2c0;border-radius:9px;padding:14px;margin-bottom:12px;font-weight:600;color:#a12622;}
.cron-result{margin:12px 0;padding:12px;border-radius:8px;background:#e3edf9;color:#1b4a7a;font-size:13px;display:none;}
.privacy-frame{width:100%;height:75vh;border:1px solid #cbd5e1;border-radius:8px;background:#fff;}
.barcode-scan-box{background:#f6f9fc;border:1px dashed #94a3b8;border-radius:9px;padding:14px;margin-bottom:16px;}
.student-check{width:auto;margin-right:6px;}
@media(max-width:860px){.sidebar{transform:translateX(-100%);} .sidebar.open{transform:translateX(0);} .main-content{margin-left:0;} .form-row{flex-direction:column;}}
"""

COMMON_JS = """
function postJSON(url, data){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).then(r=>r.json());}
function toast(msg,type){type=type||'ok';var t=document.createElement('div');t.className='toast-msg '+type;t.textContent=msg;document.getElementById('toast').appendChild(t);setTimeout(function(){t.remove();},3500);}
function logout(){document.cookie='logged_in=;max-age=0';document.cookie='role=;max-age=0';window.location.href='/login';}
function downloadUserBarcode(){var id=document.getElementById('barcode-id').textContent;if(id)window.location.href='/barcode/'+encodeURIComponent(id);}
function printBookBarcode(){window.print();}
function downloadBookBarcode(){var code=document.getElementById('book-qr-code').textContent.replace(/^Code:\\s*/i,'');if(code)window.location.href='/book-barcode/'+encodeURIComponent(code);}
var MAJORS={'CT':['Programming','Networking','Web Development','Database Systems','Multimedia'],
'BSED':['English','Mathematics','Science','Filipino','Social Studies','Values Education'],
'BEED':['General Elementary','Preschool Education'],
'BSFAS':['Fisheries','Aquaculture','Marine Biology'],
'BSBA':['Financial Management','Marketing Management','Human Resource Management','Operations Management'],
'BPA':['Public Administration','Office Administration']};
function wireMajor(deptSelId, majorSelId){var d=document.getElementById(deptSelId),m=document.getElementById(majorSelId);if(!d||!m)return;
 d.addEventListener('change',function(){m.innerHTML='<option value="">-- Select Major --</option>';(MAJORS[d.value]||[]).forEach(function(x){var o=document.createElement('option');o.value=x;o.textContent=x;m.appendChild(o);});});}
function wireIdType(typeSelId, studentFieldsId){var t=document.getElementById(typeSelId),sf=document.getElementById(studentFieldsId);if(!t||!sf)return;
 t.addEventListener('change',function(){sf.style.display=(t.value==='Student')?'':'none';});}
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
"""

# ---- Fast borrow scanner: markup (used by both staff & admin) ----
SCANNER_PANEL_HTML = """
<div class="panel-card">
  <h2 class="panel-title">Fast Borrow / Return Scanner — auto-record, no extra clicks</h2>
  <div class="mode-toggle">
    <button type="button" class="mode-btn active" data-mode="borrow" onclick="setScanMode('borrow')">Borrow</button>
    <button type="button" class="mode-btn" data-mode="return" onclick="setScanMode('return')">Return</button>
    <button type="button" class="mode-btn" data-mode="attendance" onclick="setScanMode('attendance')">Attendance (In/Out)</button>
  </div>
  <div class="outside-row" id="outside-row">
    <label style="text-transform:none;font-size:14px;margin:0;display:flex;align-items:center;gap:8px;">
      <input type="checkbox" id="outside-checkbox" onchange="onOutsideToggle(this)"> Outside Borrow (take home &mdash; 7 days, email confirmation required)
    </label>
  </div>
  <input type="text" class="scan-input" id="borrow-scan-input" placeholder="Step 1: Scan Book barcode/QR..." autofocus onkeydown="if(event.key==='Enter')handleBorrowScan()">
  <div id="borrow-status" class="status info">Step 1: Scan the Book barcode/QR. Details appear automatically.</div>
  <div id="book-card" class="detail-card" style="display:none;"></div>
  <div id="user-card" class="detail-card" style="display:none;"></div>
  <button type="button" class="btn-cancel" onclick="resetBorrowScanner()">Cancel / Start Over</button>
</div>
<div id="privacy-modal" class="modal-overlay" style="display:none;">
  <div class="modal-box">
    <h3>Privacy Policy</h3>
    <p>Your email will be used to send borrow confirmation and due date reminders. Data is kept secure and only for library purposes.</p>
    <button type="button" class="btn-primary" onclick="agreePrivacy()">AGREE</button>
    <button type="button" class="btn-cancel" onclick="declinePrivacy()">Cancel</button>
  </div>
</div>
"""

# ---- Fast borrow scanner: state machine ----
SCANNER_JS = """
var scanState = {mode:'borrow', step:'book', book:null, user:null, outsideAgreed:false, busy:false};
function setScanMode(m){
  scanState.mode=m;
  document.querySelectorAll('.mode-btn').forEach(function(b){b.classList.toggle('active', b.dataset.mode===m);});
  document.getElementById('outside-row').style.display = (m==='borrow') ? '' : 'none';
  resetBorrowScanner();
}
function onOutsideToggle(cb){
  if(cb.checked){ scanState.outsideAgreed=false; document.getElementById('privacy-modal').style.display='flex'; }
  else { scanState.outsideAgreed=false; }
}
function agreePrivacy(){ scanState.outsideAgreed=true; document.getElementById('privacy-modal').style.display='none'; document.getElementById('outside-checkbox').checked=true; document.getElementById('borrow-scan-input').focus(); }
function declinePrivacy(){ scanState.outsideAgreed=false; document.getElementById('privacy-modal').style.display='none'; document.getElementById('outside-checkbox').checked=false; document.getElementById('borrow-scan-input').focus(); }
function setBorrowStatus(msg, cls){ var s=document.getElementById('borrow-status'); s.className='status '+(cls||'info'); s.textContent=msg; }
function showBookCard(res){
  var b=res.book; var html='<h4>Book: '+esc(b.title)+'</h4><div class="kv">'+
    '<span class="k">Access Code</span><span>'+esc(b.access_code)+'</span>'+
    '<span class="k">Author</span><span>'+esc(b.author||'-')+'</span>'+
    '<span class="k">Category</span><span>'+esc(b.category||'-')+'</span>'+
    '<span class="k">Shelf</span><span>'+esc(b.shelf_location||'-')+'</span>'+
    '<span class="k">Available</span><span>'+(res.available_qty)+' of '+b.quantity+'</span>';
  if(res.current_borrowers && res.current_borrowers.length){
    html+='<span class="k">Current borrower(s)</span><span>'+res.current_borrowers.map(function(x){return esc(x.borrower_name)+' ('+esc(x.borrower_id)+')';}).join(', ')+'</span>';
  }
  html+='</div>';
  var c=document.getElementById('book-card'); c.innerHTML=html; c.style.display='block';
}
function showUserCard(res){
  var u=res.user; var html='<h4>Borrower: '+esc(u.full_name)+'</h4><div class="kv">'+
    '<span class="k">ID Number</span><span>'+esc(u.id_number)+'</span>'+
    '<span class="k">Type</span><span>'+esc(u.id_type)+'</span>'+
    '<span class="k">Department</span><span>'+esc(u.department||'-')+'</span>'+
    '<span class="k">Year Level</span><span>'+esc(u.year_level||'-')+'</span>'+
    '<span class="k">Email on file</span><span>'+(u.email?esc(u.email):'<em>none &mdash; no email notifications</em>')+'</span>'+
    '<span class="k">Penalty points</span><span>'+(u.penalty_points||0)+'</span></div>';
  var c=document.getElementById('user-card'); c.innerHTML=html; c.style.display='block';
}
function resetBorrowScanner(){
  scanState.step='book'; scanState.book=null; scanState.user=null; scanState.busy=false;
  document.getElementById('book-card').style.display='none';
  document.getElementById('user-card').style.display='none';
  var inp=document.getElementById('borrow-scan-input'); inp.value='';
  if(scanState.mode==='attendance'){ inp.placeholder='Scan User ID for Time In / Out...'; setBorrowStatus('Scan a User ID barcode. Time In/Out records automatically.','info'); }
  else { inp.placeholder='Step 1: Scan Book barcode/QR...'; setBorrowStatus('Step 1: Scan the Book barcode/QR. Details appear automatically.','info'); }
  inp.focus();
}
async function handleBorrowScan(){
  if(scanState.busy) return;
  var inp=document.getElementById('borrow-scan-input'); var code=inp.value.trim(); inp.value='';
  if(!code) return;
  if(scanState.mode==='attendance'){
    scanState.busy=true;
    try{ var r=await postJSON('/api/smart-scan',{code:code}); if(r.success){toast(r.message,'ok'); setBorrowStatus(r.message,'success');} else {toast(r.message,'err'); setBorrowStatus(r.message,'error');} }
    catch(e){toast('Scan failed: '+e,'err');}
    scanState.busy=false; inp.focus(); return;
  }
  // Try book first (side-effect-free lookup)
  scanState.busy=true;
  var bookRes=null;
  try{ bookRes=await postJSON('/api/lookup-book',{code:code}); }catch(e){}
  if(bookRes && bookRes.success){
    scanState.book=bookRes.book; showBookCard(bookRes); scanState.user=null; document.getElementById('user-card').style.display='none';
    if(scanState.mode==='return'){
      if(!bookRes.active_borrows || bookRes.active_borrows===0){
        setBorrowStatus("This book is not currently borrowed — nothing to return. Scan another book.","error");
        scanState.book=null; scanState.busy=false; inp.focus(); return;
      }
      scanState.step='user'; setBorrowStatus("Step 2: Scan the borrower's User ID to confirm return. Auto-returns on match.","info");
    } else {
      if(bookRes.available_qty<=0){ setBorrowStatus("'"+bookRes.book.title+"' is fully borrowed. No copies available.","error"); scanState.book=null; scanState.busy=false; inp.focus(); return; }
      scanState.step='user'; setBorrowStatus("Step 2: Scan the User ID. Transaction records automatically — no button to click.","info");
    }
    scanState.busy=false; inp.focus(); return;
  }
  // Not a book -> try user
  var userRes=null;
  try{ userRes=await postJSON('/api/lookup-user',{id_number:code}); }catch(e){}
  if(userRes && userRes.success){
    if(scanState.step!=='user' || !scanState.book){ setBorrowStatus("Scan the BOOK first, then the User ID.","error"); scanState.busy=false; inp.focus(); return; }
    scanState.user=userRes.user; showUserCard(userRes);
    if(scanState.mode==='return'){ await doReturnScan(); } else { await doBorrowScan(); }
    scanState.busy=false; inp.focus(); return;
  }
  setBorrowStatus("Code '"+code+"' not recognized as a Book or User ID.","error");
  scanState.busy=false; inp.focus();
}
async function doBorrowScan(){
  var outside=document.getElementById('outside-checkbox').checked;
  if(outside && !scanState.outsideAgreed){ setBorrowStatus("Please tick 'Outside Borrow' and click AGREE on the Privacy Policy popup.","error"); document.getElementById('privacy-modal').style.display='flex'; return; }
  setBorrowStatus("Recording transaction...","info");
  try{
    var r=await postJSON('/api/borrow-book',{book_id:scanState.book.id, id_number:scanState.user.id_number,
      borrow_type: outside?'Outside':'Inside', privacy_agreed: outside});
    if(r.success){
      toast(r.message,'ok'); setBorrowStatus(r.message,'success');
      if(typeof loadBorrowHistory==='function'){ try{loadBorrowHistory();}catch(e){} }
      setTimeout(resetBorrowScanner, 3000);
    } else { toast(r.message,'err'); setBorrowStatus(r.message,'error'); }
  }catch(e){ toast('Borrow failed: '+e,'err'); setBorrowStatus('Borrow failed.','error'); }
}
async function doReturnScan(){
  setBorrowStatus("Processing return...","info");
  try{
    var r=await postJSON('/api/return-book',{book_id:scanState.book.id, id_number:scanState.user.id_number});
    if(r.success){ toast(r.message,'ok'); setBorrowStatus(r.message,'success'); setTimeout(resetBorrowScanner, 3000); }
    else { toast(r.message,'err'); setBorrowStatus(r.message,'error'); }
  }catch(e){ toast('Return failed: '+e,'err'); setBorrowStatus('Return failed.','error'); }
}
"""

# ============================================================
# STUDENT FRONTEND (registration only)
# ============================================================
STUDENT_BODY = """
<div class="container"><div class="card"><div class="card-top"></div><div class="card-body">
  <div class="reg-brand-mark">SLSU<br>JGE</div>
  <h1>User Registration</h1>
  <p class="subtitle">Complete the form to generate an attendance barcode</p>
  <form id="register-form">
    <div class="form-row">
      <div class="form-group"><label>ID Type *</label>
        <select name="id_type" id="id-type-select" required><option value="Student">Student</option><option value="Employee">Employee</option><option value="Visitor">Visitor</option></select></div>
      <div class="form-group"><label>ID Number *</label><input type="text" name="id_number" required placeholder="e.g. 2024-0001"></div>
    </div>
    <div class="form-group"><label>Full Name *</label><input type="text" name="full_name" required placeholder="Last, First Middle"></div>
    <div id="student-fields">
      <div class="form-row">
        <div class="form-group"><label>Department</label>
          <select name="department" id="dept-select"><option value="">-- Select Department --</option><option value="CT">BSIT</option><option value="BSED">BSED</option><option value="BEED">BEED</option><option value="BSFAS">BSFAS</option><option value="BSBA">BSBA</option><option value="BPA">BPA</option></select></div>
        <div class="form-group"><label>Major / Specialization</label><select name="major" id="major-select"><option value="">-- Select Department First --</option></select></div>
      </div>
      <div class="form-row"><div class="form-group"><label>Year Level</label>
        <select name="year_level" id="year-select"><option value="1st Year">1st Year</option><option value="2nd Year">2nd Year</option><option value="3rd Year">3rd Year</option><option value="4th Year">4th Year</option><option value="N/A">N/A</option></select></div></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Contact Number *</label><input type="text" name="contact_number" required placeholder="09XX-XXX-XXXX"></div>
      <div class="form-group"><label>Address *</label><input type="text" name="address" required placeholder="City, Province"></div>
    </div>
    <div class="form-group"><label>Email (saved once — auto-used for outside-borrow confirmations)</label><input type="email" name="email" placeholder="you@example.com"></div>
    <button type="submit" class="btn-primary">Register &amp; Generate Barcode</button>
  </form>
  <div id="barcode-result"><h3>Registration Successful</h3><p id="barcode-id" class="barcode-id"></p>
    <img id="barcode-img" class="barcode-img"><br>
    <button type="button" class="btn-print" onclick="window.print()">Print Barcode</button>
    <button type="button" class="btn-download-barcode" onclick="downloadUserBarcode()">Download Barcode</button></div>
  <a href="/privacy" class="privacy-link" target="_blank">Privacy Policy</a>
  <a href="/login" class="logout-link" onclick="logout(event)">← Back to Sign In</a>
</div></div></div>
<div id="toast"></div>
"""

STUDENT_JS = COMMON_JS + """
wireMajor('dept-select','major-select'); wireIdType('id-type-select','student-fields');
document.getElementById('register-form').addEventListener('submit', async function(e){
  e.preventDefault();
  var fd=new FormData(this);
  try{
    var r=await fetch('/register',{method:'POST',body:fd}).then(x=>x.json());
    if(r.success){ document.getElementById('barcode-id').textContent=r.id_number;
      document.getElementById('barcode-img').src='data:image/png;base64,'+r.barcode;
      document.getElementById('barcode-result').style.display='block'; toast(r.info,'ok'); this.reset(); }
    else { toast(r.error||'Registration failed','err'); }
  }catch(err){ toast('Error: '+err,'err'); }
});
"""

STUDENT_FRONTEND = ("<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                    "<title>Register — SLSU-JGE Library</title><style>" + APP_CSS + "</style></head><body>"
                    + STUDENT_BODY + "<script>" + STUDENT_JS + "</script></body></html>")

# ============================================================
# STAFF (USER) FRONTEND
# ============================================================
STAFF_BODY = """
<div class="topnav">
  <div class="brand"><div class="brand-mark">SLSU<br>JGE</div>
    <div class="brand-text"><h1>Library System — Staff</h1><p>Library Management System</p></div></div>
  <div class="nav-tabs">
    <div class="nav-tab active" onclick="showStaffTab('scan')">Scanner</div>
    <div class="nav-tab" onclick="showStaffTab('daily')">Daily Record</div>
    <div class="nav-tab" onclick="showStaffTab('borrowed')">Borrowed Books</div>
    <div class="nav-tab" onclick="showStaffTab('search')">Search Books</div>
    <div class="nav-tab" onclick="showStaffTab('register')">Register User</div>
  </div>
  <button type="button" class="logout-btn" onclick="logout()">Log Out</button>
</div>
<div id="toast"></div>
<div class="staff-content">
  <div id="tab-scan" class="staff-tab active">
    __SCANNER_PANEL__
    <div class="panel-card">
      <h2 class="panel-title">Recent Borrow Transactions</h2>
      <button type="button" class="btn-cancel" style="background:#1b2a41;" onclick="loadBorrowHistory()">Refresh</button>
      <div class="table-wrap" id="borrow-history-table"></div>
    </div>
  </div>
  <div id="tab-daily" class="staff-tab"><div class="panel-card">
    <h2 class="panel-title">Daily Attendance Records</h2>
    <div class="filter-row"><input type="date" id="daily-date" onchange="loadTodayRecords()">
      <button type="button" class="btn-cancel" style="background:#1b2a41;margin:0;" onclick="loadTodayRecords()">Refresh</button>
      <button type="button" class="btn-print" style="margin:0;" onclick="printDaily()">Print</button>
      <button type="button" class="btn-download-barcode" style="margin:0;" onclick="downloadDaily()">Download Word</button></div>
    <div class="table-wrap" id="today-records-table"></div>
  </div></div>
  <div id="tab-borrowed" class="staff-tab"><div class="panel-card">
    <h2 class="panel-title">Borrow &amp; Return Records</h2>
    <div class="filter-row">
      <label style="margin-bottom:0;">Date:</label><input type="date" id="br-date" onchange="loadBorrowHistoryFull()">
      <label style="margin-bottom:0;">Borrower:</label><input type="text" id="br-borrower" placeholder="Name or ID" style="max-width:160px;" oninput="loadBorrowHistoryFull()">
      <label style="margin-bottom:0;">Status:</label><select id="br-status" onchange="loadBorrowHistoryFull()"><option value="">All</option><option value="Borrowed">Currently Borrowed</option><option value="Returned">Returned</option></select>
      <button type="button" class="btn-cancel" style="background:#1b2a41;margin:0;" onclick="loadBorrowHistoryFull()">Refresh</button>
      <button type="button" class="btn-print" style="margin:0;" onclick="window.open('/print-borrow-records','_blank')">Print</button>
      <button type="button" class="btn-download-barcode" style="margin:0;" onclick="window.location.href='/download-borrow-word'">Download Word</button></div>
    <div class="table-wrap" id="borrow-full-table"></div>
  </div></div>
  <div id="tab-search" class="staff-tab"><div class="panel-card">
    <h2 class="panel-title">Search Books — Availability &amp; Current Borrowers</h2>
    <div class="search-row"><input type="text" id="book-search-input" placeholder="Type book title, author, category, or code..." onkeypress="if(event.key==='Enter')doBookSearch()">
      <button type="button" class="btn-primary" style="width:auto;margin:0;" onclick="doBookSearch()">Search</button>
      <button type="button" class="btn-cancel" style="margin:0;" onclick="listAvailableBooks()">List All Available</button></div>
    <p style="font-size:13px;color:#64748b;margin-bottom:14px;">When a book is borrowed, you can see here who borrowed it and when.</p>
    <div class="table-wrap" id="search-results-table"></div>
  </div></div>
  <div id="tab-register" class="staff-tab">__STUDENT_BODY__</div>
</div>
""".replace("__SCANNER_PANEL__", SCANNER_PANEL_HTML).replace("__STUDENT_BODY__", STUDENT_BODY)

STAFF_JS = COMMON_JS + SCANNER_JS + """
function showStaffTab(t){document.querySelectorAll('.nav-tab').forEach(function(x,i){x.classList.toggle('active', ['scan','daily','borrowed','search','register'][i]===t);});
  document.querySelectorAll('.staff-tab').forEach(function(x){x.classList.remove('active');});
  document.getElementById('tab-'+t).classList.add('active');
  if(t==='scan'){setTimeout(function(){document.getElementById('borrow-scan-input').focus();},50);}
  if(t==='daily')loadTodayRecords(); if(t==='borrowed')loadBorrowHistoryFull();}
function borrowRow(r){return '<tr><td>'+esc(r.title)+'</td><td>'+esc(r.borrower)+'</td><td>'+esc(r.borrow_type)+'</td><td>'+esc(r.borrow_date)+' '+esc(r.borrow_time)+'</td><td>'+esc(r.due_date)+'</td><td>'+(r.return_date!=='-'?esc(r.return_date)+' '+esc(r.return_time):'-')+'</td><td>'+(r.fine_amount>0?'\\u20b1'+Number(r.fine_amount).toFixed(2):'-')+'</td><td>'+esc(r.status)+'</td></tr>';}
function borrowHead(){return '<table><thead><tr><th>Book</th><th>Borrower</th><th>Type</th><th>Borrowed</th><th>Due</th><th>Returned</th><th>Fine</th><th>Status</th></tr></thead><tbody>';}
async function loadBorrowHistory(){
  try{var d=await fetch('/get-borrow-records').then(r=>r.json());
    var h=borrowHead(); (d.records||[]).slice(0,12).forEach(function(r){h+=borrowRow(r);});
    document.getElementById('borrow-history-table').innerHTML=h+'</tbody></table>';}catch(e){}
}
async function loadBorrowHistoryFull(){
  var date=document.getElementById('br-date').value, bor=document.getElementById('br-borrower').value, st=document.getElementById('br-status').value;
  try{var d=await fetch('/get-borrow-records?date='+encodeURIComponent(date)+'&borrower='+encodeURIComponent(bor)+'&status='+encodeURIComponent(st)).then(r=>r.json());
    var h=borrowHead(); (d.records||[]).forEach(function(r){h+=borrowRow(r);});
    document.getElementById('borrow-full-table').innerHTML=h+'</tbody></table>';}catch(e){}
}
async function loadTodayRecords(){
  var date=document.getElementById('daily-date').value;
  var url=date?('/get-monthly-history?month='+date.slice(0,7)+'&date='+date):'/get-records';
  try{var d=await fetch(url).then(r=>r.json());
    var h='<table><thead><tr><th>Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr></thead><tbody>';
    (d.records||[]).forEach(function(r){h+='<tr><td>'+esc(r.full_name)+'</td><td>'+esc(r.department)+'</td><td>'+esc(r.time_in||'-')+'</td><td>'+esc(r.time_out||'-')+'</td></tr>';});
    document.getElementById('today-records-table').innerHTML=h+'</tbody></table>';}catch(e){}
}
function printDaily(){var d=document.getElementById('daily-date').value; window.open('/print-daily?date='+encodeURIComponent(d||''),'_blank');}
function downloadDaily(){window.location.href='/download-word';}
async function doBookSearch(){var q=document.getElementById('book-search-input').value; renderBookSearch('/api/search-books?q='+encodeURIComponent(q));}
async function listAvailableBooks(){renderBookSearch('/api/search-books?available=1');}
async function renderBookSearch(url){
  try{var d=await fetch(url).then(r=>r.json());
    var h='<table><thead><tr><th>Title</th><th>Author</th><th>Category</th><th>Shelf</th><th>Available</th><th>Current Borrower(s)</th></tr></thead><tbody>';
    (d.books||[]).forEach(function(b){h+='<tr><td>'+esc(b.title)+'</td><td>'+esc(b.author)+'</td><td>'+esc(b.category)+'</td><td>'+esc(b.shelf_location)+'</td><td>'+b.available_qty+'/'+b.quantity+'</td><td>'+(b.current_borrowers||[]).map(function(x){return esc(x.borrower_name);}).join(', ')||'-'+'</td></tr>';});
    document.getElementById('search-results-table').innerHTML=h+'</tbody></table>';}catch(e){}
}
// register form (in Register tab)
var regForm=document.getElementById('register-form');
if(regForm){wireMajor('dept-select','major-select'); wireIdType('id-type-select','student-fields');
  regForm.addEventListener('submit', async function(e){e.preventDefault();
    try{var r=await fetch('/register',{method:'POST',body:new FormData(this)}).then(x=>x.json());
      if(r.success){document.getElementById('barcode-id').textContent=r.id_number;
        document.getElementById('barcode-img').src='data:image/png;base64,'+r.barcode;
        document.getElementById('barcode-result').style.display='block'; toast(r.info,'ok'); this.reset();}
      else toast(r.error||'Registration failed','err');
    }catch(err){toast('Error: '+err,'err');}
  });
}
loadBorrowHistory();
"""

USER_FRONTEND = ("<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                 "<title>Staff — SLSU-JGE Library</title><style>" + APP_CSS + "</style></head><body>"
                 + STAFF_BODY + "<script>" + STAFF_JS + "</script></body></html>")


# ============================================================
# ADMIN FRONTEND
# ============================================================
ADMIN_BODY = """
<div class="app-container">
  <div class="sidebar-overlay" id="sidebar-overlay" onclick="toggleSidebar()"></div>
  <div class="sidebar" id="sidebar">
    <button type="button" class="toggle-btn" onclick="toggleSidebar()">&#9664;</button>
    <div class="sidebar-header"><div class="brand-mark" style="margin:0 auto 10px;">SLSU<br>JGE</div>
      <h2 class="full-title">Library System</h2><p>Full Administration</p></div>
    <div class="sidebar-menu">
      <div class="menu-item active" onclick="showContent('scan')"><span class="badge">01</span><span class="label">Scan / Borrow</span></div>
      <div class="menu-item" onclick="showContent('students')"><span class="badge">02</span><span class="label">Users List</span></div>
      <div class="menu-item" onclick="showContent('records')"><span class="badge">03</span><span class="label">Daily Records</span></div>
      <div class="menu-item" onclick="showContent('history')"><span class="badge">04</span><span class="label">Monthly History</span></div>
      <div class="menu-item" onclick="showContent('books')"><span class="badge">05</span><span class="label">Manage Books</span></div>
      <div class="menu-item" onclick="showContent('bookrecords')"><span class="badge">06</span><span class="label">Book Records</span></div>
      <div class="menu-item" onclick="showContent('overdue')"><span class="badge">07</span><span class="label">Overdue Reminders</span></div>
      <div class="menu-item" onclick="showContent('export')"><span class="badge">08</span><span class="label">Export Reports</span></div>
      <div class="menu-item" onclick="showContent('privacy')"><span class="badge">09</span><span class="label">Privacy Policy</span></div>
    </div>
    <div class="sidebar-footer"><button type="button" class="logout-btn" onclick="logout()">Log Out</button></div>
  </div>
  <div class="main-content" id="main-content">
    <div class="content-header"><button type="button" class="hamburger" onclick="toggleSidebar()">&#9776; Menu</button><h1 id="page-title">Scan / Borrow</h1></div>
    <div class="content-card">
      <div id="scan" class="tab-content active">__SCANNER_PANEL__</div>

      <div id="students" class="tab-content">
        <h2>Registered Users — Edit / Print / Delete / Download</h2>
        <div class="search-box"><input type="text" id="search-input" placeholder="Search by name, contact, address, email, or ID..." oninput="filterStudents()"></div>
        <div class="dept-tabs user-role-tabs">
          <button type="button" class="dept-tab active" id="user-type-Student" onclick="switchUserType('Student')">Students</button>
          <button type="button" class="dept-tab" id="user-type-Employee" onclick="switchUserType('Employee')">Employees</button>
          <button type="button" class="dept-tab" id="user-type-Visitor" onclick="switchUserType('Visitor')">Visitors</button></div>
        <div class="dept-tabs" id="student-dept-tabs">
          <button type="button" class="dept-tab active" id="dept-ALL" onclick="switchDept('ALL')">ALL</button>
          <button type="button" class="dept-tab" id="dept-CT" onclick="switchDept('CT')">CT</button>
          <button type="button" class="dept-tab" id="dept-BSED" onclick="switchDept('BSED')">BSED</button>
          <button type="button" class="dept-tab" id="dept-BEED" onclick="switchDept('BEED')">BEED</button>
          <button type="button" class="dept-tab" id="dept-BSFAS" onclick="switchDept('BSFAS')">BSFAS</button>
          <button type="button" class="dept-tab" id="dept-BSBA" onclick="switchDept('BSBA')">BSBA</button>
          <button type="button" class="dept-tab" id="dept-BPA" onclick="switchDept('BPA')">BPA</button></div>
        <div class="filter-row"><label style="margin-bottom:0;">Sort:</label>
          <select id="user-sort" onchange="filterStudents()"><option value="full_name-asc">Full Name A-Z</option><option value="full_name-desc">Full Name Z-A</option><option value="contact_number-asc">Contact Number</option><option value="address-asc">Address</option><option value="email-asc">Email</option><option value="penalty_points-desc">Penalty Points (high&rarr;low)</option></select>
          <button type="button" class="btn-cancel" onclick="loadStudents()">Refresh List</button></div>
        <div class="student-actions">
          <button type="button" class="btn-barcode" id="choose-barcode-btn" onclick="enableBarcodeSelection()">Select Users</button>
          <div id="barcode-selection-actions" class="hidden">
            <label style="text-transform:none;font-size:13px;margin:0;font-weight:600;"><input class="student-check" type="checkbox" id="select-all-students" onchange="toggleAllStudents(this.checked)"> Select All</label>
            <button type="button" class="btn-print" onclick="printSelectedBarcodes()">Print Selected</button>
            <button type="button" class="btn-download" onclick="downloadSelectedBarcodes()">Download Selected</button>
            <button type="button" class="btn-delete" onclick="deleteSelectedStudents()">Delete Selected</button>
            <button type="button" class="btn-cancel" onclick="disableBarcodeSelection()">Cancel</button></div></div>
        <div class="table-wrap" id="students-table"></div>
        <div id="edit-form-container" class="edit-modal hidden" onclick="if(event.target===this)hideEditForm()">
          <div class="edit-dialog"><div class="edit-dialog-header"><h3>Edit User Information</h3><button type="button" class="edit-close" onclick="hideEditForm()">&times;</button></div>
            <form id="edit-form">
              <input type="hidden" id="edit-id" name="id">
              <div class="form-row"><div class="form-group"><label>ID Type</label><select id="edit-id-type" name="id_type" onchange="updateEditFieldsByIdType()"><option value="Student">Student</option><option value="Employee">Employee</option><option value="Visitor">Visitor</option></select></div>
                <div class="form-group"><label>ID Number</label><input type="text" id="edit-idnum" name="id_number" required></div></div>
              <div class="form-group"><label>Full Name</label><input type="text" id="edit-fullname" name="full_name" required></div>
              <div class="form-row" id="edit-student-extra"><div class="form-group"><label>Department</label><select id="edit-dept" name="department"><option value="">-- Select --</option><option value="CT">BSIT</option><option value="BSED">BSED</option><option value="BEED">BEED</option><option value="BSFAS">BSFAS</option><option value="BSBA">BSBA</option><option value="BPA">BPA</option></select></div>
                <div class="form-group"><label>Major</label><select id="edit-major" name="major"></select></div></div>
              <div class="form-row"><div class="form-group" id="edit-year-group"><label>Year Level</label><select id="edit-year" name="year_level"><option value="1st Year">1st Year</option><option value="2nd Year">2nd Year</option><option value="3rd Year">3rd Year</option><option value="4th Year">4th Year</option><option value="N/A">N/A</option></select></div>
                <div class="form-group"><label>Contact Number</label><input type="text" id="edit-contact" name="contact_number"></div></div>
              <div class="form-group"><label>Complete Address</label><input type="text" id="edit-address" name="address"></div>
              <div class="form-group"><label>Email (auto-used for outside-borrow confirmations)</label><input type="email" id="edit-email" name="email" placeholder="you@example.com"></div>
              <button type="submit" class="btn-save">Save Changes</button>
              <button type="button" class="btn-cancel" onclick="hideEditForm()">Cancel</button></form></div></div>
      </div>

      <div id="records" class="tab-content">
        <h2>Today's Attendance Records</h2>
        <button type="button" class="btn-cancel" onclick="loadRecords()">Refresh</button>
        <button type="button" class="btn-print" onclick="window.open('/print-daily','_blank')">Print</button>
        <button type="button" class="btn-download" onclick="window.location.href='/download-word'">Download Word</button>
        <div class="table-wrap" id="records-table"></div></div>

      <div id="history" class="tab-content">
        <h2>Attendance History</h2>
        <div class="filter-row">
          <label style="margin-bottom:0;">Month:</label><select id="month-select" onchange="loadMonthlyHistory()">
            <option value="2026-01">Jan 2026</option><option value="2026-02">Feb 2026</option><option value="2026-03">Mar 2026</option><option value="2026-04">Apr 2026</option><option value="2026-05">May 2026</option><option value="2026-06">Jun 2026</option><option value="2026-07">Jul 2026</option><option value="2026-08">Aug 2026</option><option value="2026-09">Sep 2026</option><option value="2026-10">Oct 2026</option><option value="2026-11" selected>Nov 2026</option><option value="2026-12">Dec 2026</option><option value="2027-01">Jan 2027</option></select>
          <label style="margin-bottom:0;">Day:</label><input type="date" id="history-date" onchange="loadMonthlyHistory()">
          <button type="button" class="btn-print" onclick="printDailyReport()">Print Daily</button>
          <button type="button" class="btn-print" onclick="printMonthlyReport()">Print Monthly</button>
          <button type="button" class="btn-download" onclick="downloadMonthlyReport()">Download Word</button>
          <select id="delete-history-date"><option value="">Select day to delete</option></select>
          <button type="button" class="btn-delete-daily" onclick="deleteDailyHistory()">Delete Daily History</button></div>
        <button type="button" class="btn-cancel" onclick="loadMonthlyHistory()">Load Records</button>
        <div class="table-wrap" id="history-table"></div></div>

      <div id="books" class="tab-content">
        <h2>Register New Book</h2>
        <div class="barcode-scan-box">
          <label style="text-transform:none;font-size:13px;">Scan existing printed barcode (optional — leave blank, a barcode is auto-generated):</label>
          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">
            <input type="text" id="book-barcode-scan" placeholder="Scan or type the printed barcode number..." style="flex:1 1 260px;max-width:none;" onkeypress="if(event.key==='Enter')scanBookBarcode()">
            <button type="button" class="btn-barcode" style="margin:0;" onclick="scanBookBarcode()">Scan / Lookup</button></div>
          <div id="barcode-scan-status" style="font-size:13px;margin-top:10px;"></div></div>
        <form id="book-form">
          <div class="form-row"><div class="form-group"><label>Barcode Number (auto if blank)</label><input type="text" name="barcode_number" id="book-barcode-number" placeholder="Auto-generated if blank"></div>
            <div class="form-group"><label>Quantity</label><input type="number" name="quantity" value="1" min="1"></div></div>
          <div class="form-row"><div class="form-group"><label>Title *</label><input type="text" name="title" id="book-title-input" required placeholder="Book title"></div>
            <div class="form-group"><label>Author</label><input type="text" name="author" placeholder="Author name"></div></div>
          <div class="form-row"><div class="form-group"><label>ISBN</label><input type="text" name="isbn" placeholder="ISBN (optional)"></div>
            <div class="form-group"><label>Category</label><input type="text" name="category" placeholder="e.g. Fiction, Science"></div></div>
          <div class="form-row"><div class="form-group"><label>Shelf / Location *</label><input type="text" name="shelf_location" placeholder="e.g. Shelf A-3" required></div></div>
          <button type="submit" class="btn-save">Register Book &amp; Generate Barcode</button></form>
        <div id="book-qr-result" class="qr-result"><h3>Book Registered — Barcode Generated</h3>
          <p id="book-qr-title" style="font-weight:600;color:#1b2a41;margin-top:8px;"></p>
          <p id="book-qr-code" style="font-size:13px;color:#64748b;"></p>
          <img id="book-barcode-img" class="barcode-img" style="width:48mm;height:auto;">
          <div class="action-row"><button type="button" class="btn-print" onclick="window.print()">Print Barcode</button>
            <button type="button" class="btn-download-barcode" onclick="downloadBookBarcode()">Download Barcode</button></div></div>
        <h2 style="margin-top:32px;">All Books</h2>
        <div class="search-box"><input type="text" id="book-search" placeholder="Search by title, author, ISBN, or code..." oninput="filterBooks()"></div>
        <div class="filter-row">
          <label style="margin-bottom:0;">Status:</label><select id="book-status-filter" onchange="filterBooks()"><option value="">All</option><option value="Available">Available</option><option value="Borrowed">Fully Borrowed</option></select>
          <label style="margin-bottom:0;">Sort:</label><select id="book-sort" onchange="filterBooks()"><option value="title">Title A-Z</option><option value="most_borrowed">Most Borrowed</option><option value="recent">Recently Added</option></select>
          <button type="button" class="btn-cancel" onclick="loadBooks()">Refresh</button>
          <button type="button" class="btn-barcode" id="choose-book-qr-btn" onclick="enableBookQRSelection()">Select Books</button>
          <div id="book-qr-actions" class="hidden">
            <label style="text-transform:none;font-size:13px;margin:0;font-weight:600;"><input class="student-check" type="checkbox" id="select-all-books" onchange="toggleAllBooks(this.checked)"> Select All</label>
            <button type="button" class="btn-print" onclick="printSelectedBookBarcodes()">Print Selected</button>
            <button type="button" class="btn-download" onclick="downloadSelectedBookBarcodes()">Download Selected</button>
            <button type="button" class="btn-delete" onclick="deleteSelectedBooks()">Delete Selected</button>
            <button type="button" class="btn-cancel" onclick="disableBookQRSelection()">Cancel</button></div></div>
        <div class="table-wrap" id="books-table"></div>
        <div id="book-edit-modal" class="edit-modal hidden" onclick="if(event.target===this)hideBookEdit()">
          <div class="edit-dialog"><div class="edit-dialog-header"><h3>Edit Book</h3><button type="button" class="edit-close" onclick="hideBookEdit()">&times;</button></div>
            <form id="book-edit-form">
              <input type="hidden" id="book-edit-id" name="id">
              <div class="form-row"><div class="form-group"><label>Title *</label><input type="text" id="book-edit-title" name="title" required></div><div class="form-group"><label>Author</label><input type="text" id="book-edit-author" name="author"></div></div>
              <div class="form-row"><div class="form-group"><label>ISBN</label><input type="text" id="book-edit-isbn" name="isbn"></div><div class="form-group"><label>Category</label><input type="text" id="book-edit-category" name="category"></div></div>
              <div class="form-row"><div class="form-group"><label>Shelf / Location</label><input type="text" id="book-edit-shelf" name="shelf_location"></div><div class="form-group"><label>Quantity</label><input type="number" id="book-edit-qty" name="quantity" min="1"></div></div>
              <div class="form-row"><div class="form-group"><label>Barcode Number</label><input type="text" id="book-edit-barcode" name="barcode_number"></div></div>
              <button type="submit" class="btn-save">Save Changes</button>
              <button type="button" class="btn-cancel" onclick="hideBookEdit()">Cancel</button></form></div></div>
      </div>

      <div id="bookrecords" class="tab-content">
        <h2>Borrow &amp; Return Records</h2>
        <div class="filter-row">
          <label style="margin-bottom:0;">Date:</label><input type="date" id="br-date" onchange="loadBorrowRecords()">
          <label style="margin-bottom:0;">Borrower:</label><input type="text" id="br-borrower" placeholder="Name or ID" style="max-width:180px;" oninput="loadBorrowRecords()">
          <label style="margin-bottom:0;">Status:</label><select id="br-status" onchange="loadBorrowRecords()"><option value="">All</option><option value="Borrowed">Currently Borrowed</option><option value="Returned">Returned</option></select>
          <button type="button" class="btn-cancel" onclick="loadBorrowRecords()">Refresh</button>
          <button type="button" class="btn-print" onclick="window.open('/print-borrow-records','_blank')">Print</button>
          <button type="button" class="btn-download" onclick="window.location.href='/download-borrow-word'">Download Word</button></div>
        <div class="table-wrap" id="borrow-records-table"></div></div>

      <div id="overdue" class="tab-content">
        <h2>Overdue Books — Daily Auto Check + Reminder Email + Penalty Points</h2>
        <div class="overdue-summary" id="overdue-summary">Loading overdue list...</div>
        <p style="font-size:13px;color:#374151;margin-bottom:12px;">A background scheduler runs the overdue check daily at 8:00 AM PH time. You can also trigger it manually below, or set an external cron to hit <code>/api/cron/overdue</code> with <code>X-Cron-Key</code>.</p>
        <button type="button" class="btn-remind" onclick="runOverdueCheckNow()">Run Daily Overdue Check Now</button>
        <button type="button" class="btn-remind" style="background:#8a6d1f;" onclick="sendAllOverdueReminders()">Send Reminder Email to ALL Overdue Borrowers</button>
        <button type="button" class="btn-cancel" onclick="loadOverdue()">Refresh</button>
        <div id="cron-result" class="cron-result"></div>
        <div class="table-wrap" id="overdue-table"></div></div>

      <div id="export" class="tab-content">
        <h2>Export &amp; Print Reports</h2>
        <p style="font-size:15px;color:#64748b;margin-bottom:22px;">Download reports as Microsoft Word documents or print directly.</p>
        <button type="button" class="btn-download" onclick="window.location.href='/download-word'">Download Today's Attendance (Word)</button><br><br>
        <button type="button" class="btn-download" onclick="window.location.href='/download-borrow-word'">Download Book Borrow Records (Word)</button><br><br>
        <button type="button" class="btn-print" onclick="window.open('/print-borrow-records','_blank')">Print Borrow Records</button>
        <button type="button" class="btn-print" onclick="window.print()">Print Page</button></div>

      <div id="privacy" class="tab-content"><iframe class="privacy-frame" src="/privacy" title="Privacy Policy"></iframe></div>
    </div>
  </div>
</div>
""".replace("__SCANNER_PANEL__", SCANNER_PANEL_HTML)

ADMIN_JS = COMMON_JS + SCANNER_JS + """
var ALL_STUDENTS=[], ALL_BOOKS=[], curUserType='Student', curDept='ALL', barcodeSelect=false, bookSelect=false;
function toggleSidebar(){var sb=document.getElementById('sidebar'), mc=document.getElementById('main-content'), ov=document.getElementById('sidebar-overlay');
  sb.classList.toggle('collapsed'); mc.classList.toggle('expanded'); ov.classList.toggle('show');}
var TITLES={scan:'Scan / Borrow',students:'Users List',records:'Daily Records',history:'Monthly History',books:'Manage Books',bookrecords:'Book Records',overdue:'Overdue Reminders',export:'Export Reports',privacy:'Privacy Policy'};
function showContent(t){document.querySelectorAll('.menu-item').forEach(function(x,i){x.classList.toggle('active',['scan','students','records','history','books','bookrecords','overdue','export','privacy'][i]===t);});
  document.querySelectorAll('.tab-content').forEach(function(x){x.classList.remove('active');});
  document.getElementById(t).classList.add('active'); document.getElementById('page-title').textContent=TITLES[t]||'';
  if(t==='scan')setTimeout(function(){document.getElementById('borrow-scan-input').focus();},50);
  if(t==='students')loadStudents(); if(t==='records')loadRecords(); if(t==='history')loadMonthlyHistory();
  if(t==='books')loadBooks(); if(t==='bookrecords')loadBorrowRecords(); if(t==='overdue')loadOverdue();}
// ---- Users ----
function switchUserType(t){curUserType=t; document.querySelectorAll('.user-role-tab').forEach(function(x){x.classList.toggle('active', x.id==='user-type-'+t);});
  document.getElementById('student-dept-tabs').style.display=(t==='Student')?'':'none'; filterStudents();}
function switchDept(d){curDept=d; document.querySelectorAll('#student-dept-tabs .dept-tab').forEach(function(x){x.classList.toggle('active', x.id==='dept-'+d);}); filterStudents();}
async function loadStudents(){try{var d=await fetch('/get-students').then(r=>r.json()); ALL_STUDENTS=d.students||[]; filterStudents();}catch(e){}}
function filterStudents(){
  var q=(document.getElementById('search-input').value||'').toLowerCase();
  var sort=document.getElementById('user-sort').value;
  var list=ALL_STUDENTS.filter(function(s){return s.id_type===curUserType;});
  if(curUserType==='Student' && curDept!=='ALL') list=list.filter(function(s){return s.department===curDept;});
  if(q) list=list.filter(function(s){return (s.full_name+s.contact_number+s.address+s.email+s.id_number).toLowerCase().indexOf(q)>=0;});
  var sk=sort.split('-'); list.sort(function(a,b){var av=a[sk[0]]||'', bv=b[sk[0]]||''; return (sk[1]==='desc'?String(bv).localeCompare(String(av)):String(av).localeCompare(String(bv)));});
  var h='<table><thead><tr>'+(barcodeSelect?'<th></th>':'')+'<th>Name</th><th>ID</th><th>Type</th><th>Dept</th><th>Year</th><th>Contact</th><th>Email</th><th>Penalty</th><th></th></tr></thead><tbody>';
  list.forEach(function(s){h+='<tr>'+(barcodeSelect?'<td><input class="student-check" type="checkbox" value="'+esc(s.id_number)+'"></td>':'')+
    '<td>'+esc(s.full_name)+'</td><td>'+esc(s.id_number)+'</td><td>'+esc(s.id_type)+'</td><td>'+esc(s.department_display)+'</td><td>'+esc(s.year_level||'-')+'</td><td>'+esc(s.contact_number)+'</td><td>'+esc(s.email||'-')+'</td><td>'+(s.penalty_points||0)+'</td>'+
    '<td><button class="btn-print" style="padding:5px 10px;margin:0;" onclick="editStudent('+s.id+')">Edit</button></td></tr>';});
  document.getElementById('students-table').innerHTML=h+'</tbody></table>';
}
function enableBarcodeSelection(){barcodeSelect=true; document.getElementById('choose-barcode-btn').classList.add('hidden'); document.getElementById('barcode-selection-actions').classList.remove('hidden'); filterStudents();}
function disableBarcodeSelection(){barcodeSelect=false; document.getElementById('choose-barcode-btn').classList.remove('hidden'); document.getElementById('barcode-selection-actions').classList.add('hidden'); filterStudents();}
function toggleAllStudents(ch){document.querySelectorAll('#students-table .student-check').forEach(function(c){c.checked=ch;});}
function selectedStudentIds(){return Array.from(document.querySelectorAll('#students-table .student-check:checked')).map(function(c){return c.value;});}
function printSelectedBarcodes(){var ids=selectedStudentIds(); if(!ids.length){toast('Select at least one user.','err');return;} toast('Preparing print sheet...','info');
  fetch('/download-barcodes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id_numbers:ids})}).then(function(r){return r.blob();}).then(function(b){var u=URL.createObjectURL(b); var w=window.open(u);});}
function downloadSelectedBarcodes(){var ids=selectedStudentIds(); if(!ids.length){toast('Select at least one user.','err');return;}
  fetch('/download-barcodes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id_numbers:ids})}).then(function(r){return r.blob();}).then(function(b){var a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='student_id_labels.pdf'; a.click();});}
async function deleteSelectedStudents(){var ids=selectedStudentIds(); if(!ids.length){toast('Select at least one user.','err');return;}
  if(!confirm('Delete '+ids.length+' selected user(s)? This also deletes their attendance and borrow records.'))return;
  try{var r=await postJSON('/delete-students',{id_numbers:ids}); if(r.success){toast('Deleted '+r.deleted_count+' user(s).','ok'); loadStudents();} else toast(r.error,'err');}catch(e){toast('Delete failed','err');}}
function editStudent(id){var s=ALL_STUDENTS.find(function(x){return x.id===id;}); if(!s)return;
  document.getElementById('edit-id').value=s.id; document.getElementById('edit-id-type').value=s.id_type;
  document.getElementById('edit-idnum').value=s.id_number; document.getElementById('edit-fullname').value=s.full_name;
  document.getElementById('edit-dept').value=s.department||''; document.getElementById('edit-year').value=s.year_level||'N/A';
  document.getElementById('edit-contact').value=s.contact_number||''; document.getElementById('edit-address').value=s.address||'';
  document.getElementById('edit-email').value=s.email||''; updateEditFieldsByIdType();
  document.getElementById('edit-form-container').classList.remove('hidden');}
function hideEditForm(){document.getElementById('edit-form-container').classList.add('hidden');}
function updateEditFieldsByIdType(){var t=document.getElementById('edit-id-type').value;
  document.getElementById('edit-student-extra').style.display=(t==='Student')?'':'none';
  document.getElementById('edit-year-group').style.display=(t==='Student')?'':'none';}
document.getElementById('edit-form').addEventListener('submit', async function(e){e.preventDefault();
  try{var r=await fetch('/update-student',{method:'POST',body:new FormData(this)}).then(x=>x.json());
    if(r.success){toast('User updated.','ok'); hideEditForm(); loadStudents();} else toast(r.error,'err');}catch(err){toast('Error: '+err,'err');}});
// ---- Attendance records ----
async function loadRecords(){try{var d=await fetch('/get-records').then(r=>r.json());
  var h='<table><thead><tr><th>Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr></thead><tbody>';
  (d.records||[]).forEach(function(r){h+='<tr><td>'+esc(r.full_name)+'</td><td>'+esc(r.department)+'</td><td>'+esc(r.time_in||'-')+'</td><td>'+esc(r.time_out||'-')+'</td></tr>';});
  document.getElementById('records-table').innerHTML=h+'</tbody></table>';}catch(e){}}
async function loadMonthlyHistory(){var m=document.getElementById('month-select').value, day=document.getElementById('history-date').value;
  try{var d=await fetch('/get-monthly-history?month='+m+(day?'&date='+day:'')).then(r=>r.json());
    var h='<table><thead><tr><th>Date</th><th>Name</th><th>Dept</th><th>ID</th><th>In</th><th>Out</th></tr></thead><tbody>';
    var days=new Set(); (d.records||[]).forEach(function(r){h+='<tr><td>'+esc(r.scan_date)+'</td><td>'+esc(r.full_name)+'</td><td>'+esc(r.department)+'</td><td>'+esc(r.id_number)+'</td><td>'+esc(r.time_in||'-')+'</td><td>'+esc(r.time_out||'-')+'</td></tr>'; days.add(r.scan_date);});
    document.getElementById('history-table').innerHTML=h+'</tbody></table>';
    var sel=document.getElementById('delete-history-date'); sel.innerHTML='<option value="">Select day to delete</option>';
    Array.from(days).sort().reverse().forEach(function(dy){var o=document.createElement('option');o.value=dy;o.textContent=dy;sel.appendChild(o);});
  }catch(e){}}
function printDailyReport(){var d=document.getElementById('history-date').value; window.open('/print-daily?date='+encodeURIComponent(d||''),'_blank');}
function printMonthlyReport(){window.open('/print-monthly?month='+encodeURIComponent(document.getElementById('month-select').value),'_blank');}
function downloadMonthlyReport(){window.location.href='/download-monthly-word?month='+encodeURIComponent(document.getElementById('month-select').value);}
async function deleteDailyHistory(){var d=document.getElementById('delete-history-date').value; if(!d){toast('Select a day first.','err');return;}
  if(!confirm('Delete ALL attendance records for '+d+'? This cannot be undone.'))return;
  try{var r=await postJSON('/delete-daily-history',{date:d}); if(r.success){toast('Deleted '+r.deleted_count+' records.','ok'); loadMonthlyHistory();} else toast(r.error,'err');}catch(e){toast('Delete failed','err');}}
// ---- Books ----
async function scanBookBarcode(){var code=document.getElementById('book-barcode-scan').value.trim(); if(!code)return;
  try{var r=await postJSON('/api/scan-book-barcode',{code:code});
    var st=document.getElementById('barcode-scan-status');
    if(r.success && r.exists){st.innerHTML='<span style="color:#1b6b3a;font-weight:600;">Already registered: '+esc(r.book.title)+' ('+esc(r.book.access_code)+')</span>';}
    else if(r.success){document.getElementById('book-barcode-number').value=r.barcode_number;
      st.innerHTML='<span style="color:#8a6d1f;font-weight:600;">'+esc(r.message)+'</span><br><img src="data:image/png;base64,'+r.barcode_img+'" style="max-width:220px;margin-top:8px;">';}
    else st.innerHTML='<span style="color:#a12622;">'+esc(r.error)+'</span>';
  }catch(e){toast('Scan failed','err');}}
document.getElementById('book-form').addEventListener('submit', async function(e){e.preventDefault();
  try{var r=await fetch('/register-book',{method:'POST',body:new FormData(this)}).then(x=>x.json());
    if(r.success){document.getElementById('book-qr-title').textContent=r.title; document.getElementById('book-qr-code').textContent='Code: '+r.access_code;
      document.getElementById('book-barcode-img').src='data:image/png;base64,'+r.barcode;
      document.getElementById('book-qr-result').style.display='block'; toast(r.message,'ok'); this.reset(); loadBooks();}
    else toast(r.error,'err');}catch(err){toast('Error: '+err,'err');}});
async function loadBooks(){try{var d=await fetch('/get-books').then(r=>r.json()); ALL_BOOKS=d.books||[]; filterBooks();}catch(e){}}
function filterBooks(){var q=(document.getElementById('book-search').value||'').toLowerCase();
  var st=document.getElementById('book-status-filter').value, sort=document.getElementById('book-sort').value;
  var list=ALL_BOOKS.slice();
  if(q) list=list.filter(function(b){return (b.title+b.author+b.isbn+b.access_code+(b.category||'')).toLowerCase().indexOf(q)>=0;});
  if(st) list=list.filter(function(b){return b.status===st;});
  if(sort==='most_borrowed') list.sort(function(a,b){return b.times_borrowed-a.times_borrowed;});
  else if(sort==='recent') list.sort(function(a,b){return String(b.created_at).localeCompare(String(a.created_at));});
  else list.sort(function(a,b){return String(a.title).localeCompare(String(b.title));});
  var h='<table><thead><tr>'+(bookSelect?'<th></th>':'')+'<th>Title</th><th>Author</th><th>Category</th><th>Shelf</th><th>Qty</th><th>Available</th><th>Status</th><th>Borrowed</th><th></th></tr></thead><tbody>';
  list.forEach(function(b){h+='<tr>'+(bookSelect?'<td><input class="student-check" type="checkbox" value="'+b.id+'"></td>':'')+
    '<td>'+esc(b.title)+'</td><td>'+esc(b.author||'-')+'</td><td>'+esc(b.category||'-')+'</td><td>'+esc(b.shelf_location||'-')+'</td><td>'+b.quantity+'</td><td>'+b.available_qty+'</td><td>'+esc(b.status)+'</td><td>'+b.times_borrowed+'</td>'+
    '<td><button class="btn-print" style="padding:5px 10px;margin:0;" onclick="editBook('+b.id+')">Edit</button></td></tr>';});
  document.getElementById('books-table').innerHTML=h+'</tbody></table>';}
function enableBookQRSelection(){bookSelect=true; document.getElementById('choose-book-qr-btn').classList.add('hidden'); document.getElementById('book-qr-actions').classList.remove('hidden'); filterBooks();}
function disableBookQRSelection(){bookSelect=false; document.getElementById('choose-book-qr-btn').classList.remove('hidden'); document.getElementById('book-qr-actions').classList.add('hidden'); filterBooks();}
function toggleAllBooks(ch){document.querySelectorAll('#books-table .student-check').forEach(function(c){c.checked=ch;});}
function selectedBookIds(){return Array.from(document.querySelectorAll('#books-table .student-check:checked')).map(function(c){return Number(c.value);});}
function printSelectedBookBarcodes(){var ids=selectedBookIds(); if(!ids.length){toast('Select at least one book.','err');return;}
  fetch('/download-book-barcodes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({book_ids:ids})}).then(r=>r.blob()).then(b=>{window.open(URL.createObjectURL(b));});}
function downloadSelectedBookBarcodes(){var ids=selectedBookIds(); if(!ids.length){toast('Select at least one book.','err');return;}
  fetch('/download-book-barcodes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({book_ids:ids})}).then(r=>r.blob()).then(b=>{var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='book_barcodes.pdf';a.click();});}
async function deleteSelectedBooks(){var ids=selectedBookIds(); if(!ids.length){toast('Select at least one book.','err');return;}
  if(!confirm('Delete '+ids.length+' selected book(s)?'))return;
  try{var r=await postJSON('/delete-book',{book_ids:ids}); if(r.success){toast('Deleted '+r.deleted_count+' book(s).','ok'); loadBooks();} else toast(r.error,'err');}catch(e){toast('Delete failed','err');}}
function editBook(id){var b=ALL_BOOKS.find(function(x){return x.id===id;}); if(!b)return;
  document.getElementById('book-edit-id').value=b.id; document.getElementById('book-edit-title').value=b.title;
  document.getElementById('book-edit-author').value=b.author||''; document.getElementById('book-edit-isbn').value=b.isbn||'';
  document.getElementById('book-edit-category').value=b.category||''; document.getElementById('book-edit-shelf').value=b.shelf_location||'';
  document.getElementById('book-edit-qty').value=b.quantity; document.getElementById('book-edit-barcode').value=b.barcode_number||'';
  document.getElementById('book-edit-modal').classList.remove('hidden');}
function hideBookEdit(){document.getElementById('book-edit-modal').classList.add('hidden');}
document.getElementById('book-edit-form').addEventListener('submit', async function(e){e.preventDefault();
  try{var r=await fetch('/update-book',{method:'POST',body:new FormData(this)}).then(x=>x.json());
    if(r.success){toast('Book updated.','ok'); hideBookEdit(); loadBooks();} else toast(r.error,'err');}catch(err){toast('Error: '+err,'err');}});
// ---- Borrow records + overdue ----
function borrowRow(r){return '<tr><td>'+esc(r.title)+'</td><td>'+esc(r.borrower)+'</td><td>'+esc(r.borrow_type)+'</td><td>'+esc(r.borrow_date)+' '+esc(r.borrow_time)+'</td><td>'+esc(r.due_date)+'</td><td>'+(r.return_date!=='-'?esc(r.return_date)+' '+esc(r.return_time):'-')+'</td><td>'+(r.fine_amount>0?'\\u20b1'+Number(r.fine_amount).toFixed(2):'-')+'</td><td>'+esc(r.status)+'</td></tr>';}
async function loadBorrowRecords(){var date=document.getElementById('br-date').value, bor=document.getElementById('br-borrower').value, st=document.getElementById('br-status').value;
  try{var d=await fetch('/get-borrow-records?date='+encodeURIComponent(date)+'&borrower='+encodeURIComponent(bor)+'&status='+encodeURIComponent(st)).then(r=>r.json());
    var h='<table><thead><tr><th>Book</th><th>Borrower</th><th>Type</th><th>Borrowed</th><th>Due</th><th>Returned</th><th>Fine</th><th>Status</th></tr></thead><tbody>';
    (d.records||[]).forEach(function(r){h+=borrowRow(r);});
    document.getElementById('borrow-records-table').innerHTML=h+'</tbody></table>';}catch(e){}}
async function loadOverdue(){try{var d=await fetch('/api/overdue-list').then(r=>r.json());
  var recs=d.records||[];
  document.getElementById('overdue-summary').textContent=recs.length? (recs.length+' overdue outside borrow(s). Total fine potential shown below.') : 'No overdue books at the moment.';
  var h='<table><thead><tr><th>Book</th><th>Borrower</th><th>Email</th><th>Due</th><th>Days Late</th><th>Fine</th><th>Penalty Pts</th><th>Status</th><th>Reminder</th></tr></thead><tbody>';
  recs.forEach(function(r){h+='<tr><td>'+esc(r.title)+'</td><td>'+esc(r.borrower)+'</td><td>'+esc(r.email)+'</td><td>'+esc(r.due_date)+'</td><td>'+r.days_late+'</td><td>\\u20b1'+Number(r.fine_amount).toFixed(2)+'</td><td>'+r.penalty_points+'</td><td>'+esc(r.status)+'</td><td>'+(r.reminder_sent?'Sent':'Not yet')+'</td></tr>';});
  document.getElementById('overdue-table').innerHTML=h+'</tbody></table>';}catch(e){}}
async function runOverdueCheckNow(){try{var r=await postJSON('/api/cron/overdue',{});
  var c=document.getElementById('cron-result'); c.style.display='block';
  c.textContent=r.success? ('Check done: '+r.checked+' checked, '+r.penalties_applied+' penalty(ies) applied, '+r.reminders_sent+' reminder(s) sent, '+r.reminders_failed+' failed. Ran at '+r.ran_at) : ('Error: '+r.error);
  loadOverdue();}catch(e){toast('Cron failed','err');}}
async function sendAllOverdueReminders(){try{var r=await postJSON('/api/send-all-overdue-reminders',{});
  toast(r.message||'Done', r.success?'ok':'err'); loadOverdue();}catch(e){toast('Failed','err');}}
loadStudents();
"""

ADMIN_FRONTEND = ("<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                  "<title>Admin — SLSU-JGE Library</title><style>" + APP_CSS + "</style></head><body>"
                  + ADMIN_BODY + "<div id='toast'></div><script>" + ADMIN_JS + "</script></body></html>")


# ============================================================
# ROUTES: panels + entry point
# ============================================================
@app.route('/user')
def user_panel():
    if not is_logged_in() or get_role() != 'user':
        return ""
    return render_template_string(USER_FRONTEND)

@app.route('/student')
def student_panel():
    if not is_logged_in() or get_role() != 'student':
        return ""
    return render_template_string(STUDENT_FRONTEND)

@app.route('/')
def home():
    if not is_logged_in():
        return LOGIN_PAGE.replace("__ERROR__", "").replace("__SLSU_LOGO__", SLSU_LOGO_DATA_URI)
    role = get_role()
    if role == 'user':
        return render_template_string(USER_FRONTEND)
    if role == 'student':
        return render_template_string(STUDENT_FRONTEND)
    return render_template_string(ADMIN_FRONTEND)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
