from flask import Flask, render_template_string, request, jsonify, make_response
import psycopg2
import os
import datetime
import barcode
from barcode.writer import ImageWriter
import base64
from io import BytesIO
import zipfile
import re
import secrets
from PIL import Image, ImageDraw
from docx import Document
import qrcode
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER = "library"
ADMIN_PASS = "slsu"
USER_USER = "slsu"
USER_PASS = "library"
STUDENT_USER = "student"
STUDENT_PASS = "student"
SCANNER_API_KEY = os.environ.get("SCANNER_API_KEY", "").strip()

# ---- SMTP / Email notification config (for OUTSIDE borrow) ----
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
try:
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "465").strip())
except Exception:
    SMTP_PORT = 465
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER).strip() or SMTP_USER
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "SLSU-JGE Library").strip()
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# ---- OUTSIDE BORROW: due date & late fine policy ----
OUTSIDE_BORROW_DAYS = int(os.environ.get("OUTSIDE_BORROW_DAYS", "3"))
LATE_FINE_PER_DAY = float(os.environ.get("LATE_FINE_PER_DAY", "5.0"))  # pesos per day late

# Embedded SLSU official seal (base64) — used on the login page header
SLSU_LOGO_DATA_URI = "data:image/jpeg;base64,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"


def get_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"DB Connect Error: {e}")
        return None


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
    """Return (days_late, fine_amount). If not returned, compare to today."""
    if not due_date:
        return 0, 0.0
    ref = return_date if return_date else get_ph_date()
    late = days_between(due_date, ref)
    if late <= 0:
        return 0, 0.0
    return late, round(late * LATE_FINE_PER_DAY, 2)


DEPARTMENT_CODES = {
    "CT": "CPT",
    "BSED": "BSED",
    "BEED": "BEED",
    "BSFAS": "BSFAS",
    "BSBA": "BSBA",
    "BPA": "BPA",
}


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


def init_db():
    conn = get_db()
    if not conn:
        print("Cannot connect to database")
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
    c.execute("""CREATE TABLE IF NOT EXISTS books (
        id SERIAL PRIMARY KEY,
        access_code TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        author TEXT,
        isbn TEXT,
        category TEXT,
        shelf_location TEXT,
        quantity INTEGER DEFAULT 1,
        times_borrowed INTEGER DEFAULT 0,
        last_borrowed_date TEXT,
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS borrow_records (
        id SERIAL PRIMARY KEY,
        book_id INTEGER NOT NULL REFERENCES books(id),
        user_id INTEGER NOT NULL REFERENCES users(id),
        borrow_date TEXT NOT NULL,
        borrow_time TEXT NOT NULL,
        return_date TEXT,
        return_time TEXT,
        status TEXT DEFAULT 'Borrowed'
    )""")
    # ---- New columns (safe: IF NOT EXISTS) ----
    for stmt in [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS borrow_type TEXT DEFAULT 'Inside'",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS borrower_email TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS email_sent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS barcode_number TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS due_date TEXT",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS fine_amount REAL DEFAULT 0",
        "ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN DEFAULT FALSE",
    ]:
        try:
            c.execute(stmt)
        except Exception as e:
            print(f"ALTER skipped: {e}")
    conn.commit()
    conn.close()
    print("DATABASE READY")


init_db()

# ============================================================
#  EMAIL NOTIFICATION (for OUTSIDE borrow + overdue reminder)
# ============================================================
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
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=20) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        return True, "Email sent."
    except Exception as e:
        print(f"SEND EMAIL ERROR: {e}")
        return False, f"Email not sent: {str(e)}"


def send_borrow_notification(to_email, borrower_name, book_title, access_code, borrow_date, borrow_time, borrow_type, due_date=None):
    due_line = ""
    if due_date:
        due_line = f"""<tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Due Date (Return On or Before)</strong></td>
            <td style="padding:10px;border:1px solid #d8dbe0;"><strong style="color:#8a1f1f;">{due_date}</strong></td></tr>"""
    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#1f2937;line-height:1.6;">
    <div style="max-width:560px;margin:0 auto;border:1px solid #d8dbe0;border-radius:6px;overflow:hidden;">
      <div style="background:#1b2a41;color:#e8c766;padding:18px 24px;font-family:Georgia,serif;font-size:18px;font-weight:700;">
        SLSU-JGE Library — Borrow Confirmation
      </div>
      <div style="padding:24px;">
        <p>Hello <strong>{borrower_name}</strong>,</p>
        <p>This is to confirm that you borrowed the following book
        <strong>{'for OUTSIDE use (take home)' if str(borrow_type).lower()=='outside' else 'for INSIDE use (in-library reading)'}</strong>
        today at the SLSU-JGE Library:</p>
        <table style="width:100%;border-collapse:collapse;margin:14px 0;">
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;width:40%;"><strong>Book Title</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{book_title}</td></tr>
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Access Code</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{access_code}</td></tr>
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Date Borrowed</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{borrow_date}</td></tr>
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Time Borrowed</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{borrow_time}</td></tr>
          {due_line}
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Borrow Type</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{borrow_type}</td></tr>
        </table>
        <p style="background:#fdf6e3;border-left:4px solid #c9a227;padding:12px 14px;font-size:13px;color:#8a6d1f;">
          <strong>Reminder:</strong> Please take good care of the book. For OUTSIDE borrows, you are fully
          responsible for any damage and must pay the replacement cost if the book is lost.
          A late fine of <strong>₱{LATE_FINE_PER_DAY:.2f} per day</strong> will be charged if returned after the due date.
        </p>
        <p style="font-size:12px;color:#64748b;margin-top:20px;">SLSU-JGE Library Management System<br>
        Southern Luzon State University — Judge Guillermo Eleazar</p>
      </div>
    </div>
    </body></html>
    """
    return _send_email(to_email, f"Book Borrow Confirmation — {book_title} — SLSU-JGE Library", html)


def send_overdue_reminder(to_email, borrower_name, book_title, access_code, borrow_date, due_date, days_late, fine_amount):
    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#1f2937;line-height:1.6;">
    <div style="max-width:560px;margin:0 auto;border:1px solid #d8dbe0;border-radius:6px;overflow:hidden;">
      <div style="background:#7a1f1f;color:#fff;padding:18px 24px;font-family:Georgia,serif;font-size:18px;font-weight:700;">
        SLSU-JGE Library — OVERDUE BOOK REMINDER
      </div>
      <div style="padding:24px;">
        <p>Hello <strong>{borrower_name}</strong>,</p>
        <p>This is a friendly reminder that the book you borrowed is now <strong style="color:#8a1f1f;">OVERDUE</strong>.
        Please return it to the SLSU-JGE Library as soon as possible.</p>
        <table style="width:100%;border-collapse:collapse;margin:14px 0;">
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;width:40%;"><strong>Book Title</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{book_title}</td></tr>
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Access Code</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{access_code}</td></tr>
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Date Borrowed</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{borrow_date}</td></tr>
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Due Date</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;">{due_date}</td></tr>
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Days Late</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;color:#8a1f1f;font-weight:700;">{days_late} day(s)</td></tr>
          <tr><td style="padding:10px;border:1px solid #d8dbe0;background:#f7f8fa;"><strong>Accumulated Fine</strong></td>
              <td style="padding:10px;border:1px solid #d8dbe0;color:#8a1f1f;font-weight:700;">₱{fine_amount:.2f} (₱{LATE_FINE_PER_DAY:.2f}/day)</td></tr>
        </table>
        <p style="background:#fbeaea;border-left:4px solid #c0392b;padding:12px 14px;font-size:13px;color:#8a1f1f;">
          <strong>Please return the book immediately.</strong> The fine continues to increase by ₱{LATE_FINE_PER_DAY:.2f} each day
          until the book is returned. Damage or loss must also be paid in full.
        </p>
        <p style="font-size:12px;color:#64748b;margin-top:20px;">SLSU-JGE Library Management System<br>
        Southern Luzon State University — Judge Guillermo Eleazar</p>
      </div>
    </div>
    </body></html>
    """
    return _send_email(to_email, f"OVERDUE — Return '{book_title}' — SLSU-JGE Library", html)


# ============================================================
#  BARCODE / QR GENERATORS  (high-contrast, scanner-friendly, 300 DPI)
# ============================================================
def generate_barcode_b64(id_number):
    """Code128 barcode — standard module width, tall bars, generous quiet zone, 300 DPI.
    Sized so any handheld/USB barcode scanner reads it reliably on screen and in print."""
    code128 = barcode.get_barcode_class("code128")
    writer = ImageWriter()
    writer.set_options({
        "module_width": 0.6,        # standard bar thickness (not too thin)
        "module_height": 18.0,      # tall bars for reliable scan
        "font_size": 12,            # readable human-readable digits below
        "text_distance": 4,         # space between bars and digits
        "quiet_zone": 4.0,          # generous white margin on both sides (quiet zone)
        "center_text": True,
        "dpi": 300,
    })
    img = code128(str(id_number), writer=writer).render().convert("RGB")
    pad = round(8 / 25.4 * 300)  # extra white padding around (>=5mm safe margin)
    canvas = Image.new("RGB", (img.width + 2 * pad, img.height + 2 * pad), "white")
    canvas.paste(img, (pad, pad))
    buffered = BytesIO()
    canvas.save(buffered, format="PNG", dpi=(300, 300), optimize=True)
    return base64.b64encode(buffered.getvalue()).decode()


def generate_qr_b64(data):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
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
    status = "Available" if available > 0 else "Borrowed"
    return active, available, status


def active_borrowers_of(book_id):
    conn = get_db()
    if not conn:
        return []
    c = conn.cursor()
    c.execute("""SELECT br.id, u.full_name, u.id_number, br.borrow_date, br.borrow_time, br.borrow_type
        FROM borrow_records br JOIN users u ON br.user_id = u.id
        WHERE br.book_id = %s AND br.return_time IS NULL ORDER BY br.id""", (book_id,))
    rows = [{"borrow_id": r[0], "borrower_name": r[1], "borrower_id": r[2],
             "borrow_date": r[3], "borrow_time": r[4],
             "borrow_type": r[5] or "Inside"} for r in c.fetchall()]
    conn.close()
    return rows


# ============================================================
#  BARCODE / QR IMAGE ROUTES & DOWNLOADS
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


@app.route('/download-book-barcodes', methods=['POST'])
def download_book_barcodes():
    """Bulk download selected books' barcodes as a print-ready PDF (A4 grid).
    Uses barcode_number if set, otherwise the access_code. Each cell shows the
    book title + code above the barcode, like the user barcode sheet."""
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
        # barcode to print = barcode_number if present, else access_code
        items = []
        for bid, access_code, title, bc in books:
            code = (bc or "").strip() or access_code
            items.append((code, title or ""))
        page_size = (round(210 / 25.4 * 300), round(297 / 25.4 * 300))
        columns = 4
        rows = 10
        box_width = round(48 / 25.4 * 300)
        box_height = round(32 / 25.4 * 300)
        gap = round(2 / 25.4 * 300)
        grid_width = columns * box_width + (columns - 1) * gap
        grid_height = rows * box_height + (rows - 1) * gap
        grid_left = (page_size[0] - grid_width) // 2
        grid_top = (page_size[1] - grid_height) // 2
        barcode_size = (round(44 / 25.4 * 300), round(16 / 25.4 * 300))
        pages = []
        for page_start in range(0, len(items), columns * rows):
            page = Image.new('RGB', page_size, 'white')
            draw = ImageDraw.Draw(page)
            page_items = items[page_start:page_start + columns * rows]
            for index, (code, title) in enumerate(page_items):
                column = index % columns
                row = index // columns
                cell_left = grid_left + column * (box_width + gap)
                cell_top = grid_top + row * (box_height + gap)
                bc_img = Image.open(BytesIO(base64.b64decode(generate_barcode_b64(code))))
                bc_img.thumbnail(barcode_size, Image.Resampling.LANCZOS)
                bc_left = cell_left + (box_width - bc_img.width) // 2
                bc_top = cell_top + round(12 / 25.4 * 300)
                page.paste(bc_img, (bc_left, bc_top))
                title_label = title if len(title) <= 26 else title[:23] + "..."
                code_label = "Code: " + code
                for li, lab in enumerate([title_label, code_label]):
                    lb = draw.textbbox((0, 0), lab)
                    lw = lb[2] - lb[0]
                    draw.text((cell_left + (box_width - lw) // 2, cell_top + round(2 / 25.4 * 300) + li * round(3.5 / 25.4 * 300)), lab, fill='black')
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
    """Print-ready Student ID Label Sheet.
    Page: Letter (8.5x11in) Portrait, 0.5in margins, 3 labels/page, 1 column, centered.
    Each label: 2.2in wide x 1.0in tall, HORIZONTAL layout — left 'Student Number: X'
    (Arial 11pt black), right Code-128 horizontal barcode (0.5in bar height, human-readable
    text below, generous quiet zone), 300 DPI. Thin black border per label, light gray
    dotted divider between labels, white background, black only."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True, force=True) or {}
        id_numbers = payload.get('id_numbers', [])
        id_numbers = list(dict.fromkeys(str(value).strip() for value in id_numbers if str(value).strip()))
        if not id_numbers:
            return jsonify({"error": "Please select at least one student."}), 400

        DPI = 300
        IN = DPI  # pixels per inch
        page_w, page_h = int(8.5 * IN), int(11 * IN)   # Letter, portrait
        margin = int(0.5 * IN)                          # 0.5in margins all sides
        label_w, label_h = int(2.2 * IN), int(1.0 * IN) # 2.2in x 1.0in per label
        gap = int(0.15 * IN)                            # equal small spacing between labels
        labels_per_page = 3                             # only 3 labels per page, 1 column
        strip_h = labels_per_page * label_h + (labels_per_page - 1) * gap
        usable_w = page_w - 2 * margin
        usable_h = page_h - 2 * margin
        strip_left = margin + (usable_w - label_w) // 2   # centered horizontally
        strip_top = margin + (usable_h - strip_h) // 2    # centered vertically

        # Font: Arial metric-compatible (Liberation Sans), 11pt
        from PIL import ImageFont
        font_paths = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font_path = next((p for p in font_paths if os.path.exists(p)), None)
        font_px = int(round(11 * DPI / 72))  # 11pt @300dpi ~ 46px
        base_font = ImageFont.truetype(font_path, font_px) if font_path else ImageFont.load_default()

        # Barcode box on the right of each label (1.25in wide x 0.85in tall; 0.5in bars + text below)
        bc_box_w = int(1.25 * IN)
        bc_box_h = int(0.85 * IN)
        bc_left_in_label = label_w - bc_box_w - int(0.08 * IN)
        bc_top_in_label = (label_h - bc_box_h) // 2

        pages = []
        for page_start in range(0, len(id_numbers), labels_per_page):
            page = Image.new('RGB', (page_w, page_h), 'white')
            draw = ImageDraw.Draw(page)
            page_ids = id_numbers[page_start:page_start + labels_per_page]
            for i, id_number in enumerate(page_ids):
                x0 = strip_left
                y0 = strip_top + i * (label_h + gap)
                x1 = x0 + label_w
                y1 = y0 + label_h
                # thin black border around each label (aligned edges form outer strip border)
                draw.rectangle((x0, y0, x1, y1), outline='black', width=3)
                # light gray dotted divider line in the gap between labels
                if i > 0:
                    dy = y0 - gap // 2
                    dash = int(0.06 * IN); spc = int(0.05 * IN)
                    dx = x0 + int(0.1 * IN)
                    while dx < x1 - int(0.1 * IN):
                        draw.line((dx, dy, min(dx + dash, x1 - int(0.1 * IN)), dy), fill=(180, 180, 180), width=3)
                        dx += dash + spc
                # Left side: "Student Number: [ID]" — Arial 11pt, black, vertically centered
                text = "Student Number: " + id_number
                f = base_font
                max_text_w = int(0.95 * IN)
                while font_path and draw.textlength(text, font=f) > max_text_w and f.size > 18:
                    f = ImageFont.truetype(font_path, f.size - 2)
                tbox = draw.textbbox((0, 0), text, font=f)
                th = tbox[3] - tbox[1]
                tx = x0 + int(0.12 * IN)
                ty = y0 + (label_h - th) // 2 - tbox[1]
                draw.text((tx, ty), text, fill='black', font=f)
                # Right side: Code-128 HORIZONTAL barcode (300 DPI, quiet zone, text below)
                bc_img = Image.open(BytesIO(base64.b64decode(generate_barcode_b64(id_number))))
                bc_img.thumbnail((bc_box_w, bc_box_h), Image.Resampling.LANCZOS)
                bcx = x0 + bc_left_in_label + (bc_box_w - bc_img.width) // 2
                bcy = y0 + bc_top_in_label + (bc_box_h - bc_img.height) // 2
                page.paste(bc_img, (bcx, bcy))
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
        id_numbers = list(dict.fromkeys(
            str(value).strip() for value in payload.get('id_numbers', []) if str(value).strip()
        ))
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


# ============================================================
#  BOOK MANAGEMENT ROUTES (Admin) — with barcode scan + generate
# ============================================================
@app.route('/api/scan-book-barcode', methods=['POST'])
def scan_book_barcode():
    """Admin book registration: scan an existing printed barcode. If book exists, return it;
    if not, return the scanned number so admin can fill the book info table."""
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
            "id": row[0], "access_code": row[1], "title": row[2], "author": row[3],
            "isbn": row[4], "category": row[5], "shelf_location": row[6],
            "quantity": row[7], "barcode_number": row[8] or ""
        }})
    barcode_b64 = generate_barcode_b64(code)
    return jsonify({"success": True, "exists": False, "barcode_number": code, "barcode_img": barcode_b64,
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
            qty = int(quantity)
            if qty < 1:
                qty = 1
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
        barcode_b64 = generate_barcode_b64(access_code)
        return jsonify({
            "success": True,
            "book_id": book_id,
            "access_code": access_code,
            "title": title,
            "barcode": barcode_b64,
            "message": f"Book registered: {title} (Code: {access_code})"
        })
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
    c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location,
        quantity, times_borrowed, last_borrowed_date, created_at, barcode_number FROM books ORDER BY title""")
    books = []
    for r in c.fetchall():
        active, available, status = book_status_info(r[0], r[7])
        books.append({
            "id": r[0], "access_code": r[1], "title": r[2], "author": r[3],
            "isbn": r[4], "category": r[5], "shelf_location": r[6],
            "quantity": r[7], "times_borrowed": r[8] or 0,
            "last_borrowed_date": r[9] or "-", "created_at": r[10],
            "barcode_number": r[11] or "",
            "active_borrows": active, "available_qty": available, "status": status,
        })
    conn.close()
    return jsonify({"books": books})


@app.route('/api/search-books')
def search_books():
    """Search available books; returns matches with current borrowers (who borrowed at this time)."""
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
            OR UPPER(COALESCE(barcode_number,'')) LIKE UPPER(%s) ORDER BY title""",
            (like, like, like, like, like))
    else:
        c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location, quantity, barcode_number
            FROM books ORDER BY title""")
    results = []
    for r in c.fetchall():
        active, available, status = book_status_info(r[0], r[7])
        if only_available and available <= 0:
            continue
        borrowers = active_borrowers_of(r[0])
        results.append({
            "id": r[0], "access_code": r[1], "title": r[2], "author": r[3] or "-",
            "isbn": r[4] or "-", "category": r[5] or "-", "shelf_location": r[6] or "-",
            "quantity": r[7], "barcode_number": r[8] or "-",
            "available_qty": available, "status": status,
            "current_borrowers": borrowers,
        })
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
            qty = int(quantity)
            if qty < 1:
                qty = 1
        except ValueError:
            qty = 1
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database error."}), 500
        c = conn.cursor()
        c.execute("""UPDATE books SET title=%s, author=%s, isbn=%s, category=%s,
            shelf_location=%s, quantity=%s, barcode_number=%s WHERE id=%s""",
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
#  OVERDUE / FINE / REMINDER ROUTES
# ============================================================
@app.route('/api/overdue-list')
def overdue_list():
    """List all OUTSIDE borrows that are past due_date and not yet returned, with computed fine."""
    if not is_logged_in():
        return jsonify({"records": []})
    conn = get_db()
    if not conn:
        return jsonify({"records": []})
    c = conn.cursor()
    c.execute("""SELECT br.id, b.title, b.access_code, u.full_name, u.id_number, br.borrower_email,
        br.borrow_date, br.borrow_time, br.due_date, br.reminder_sent
        FROM borrow_records br JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
        WHERE br.return_time IS NULL AND br.borrow_type = 'Outside' AND br.due_date IS NOT NULL
        AND br.due_date < %s ORDER BY br.due_date ASC""", (get_ph_date(),))
    records = []
    for r in c.fetchall():
        days_late, fine = compute_fine(r[8])
        records.append({
            "id": r[0], "title": r[1], "access_code": r[2], "borrower": r[3],
            "borrower_id": r[4], "email": r[5] or "-", "borrow_date": r[6],
            "borrow_time": r[7], "due_date": r[8], "days_late": days_late,
            "fine_amount": fine, "reminder_sent": bool(r[9]),
        })
    conn.close()
    return jsonify({"records": records})


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
    c.execute("""SELECT br.id, b.title, b.access_code, u.full_name, br.borrower_email,
        br.borrow_date, br.due_date FROM borrow_records br
        JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
        WHERE br.id = %s AND br.return_time IS NULL""", (int(borrow_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Overdue record not found."}), 404
    days_late, fine = compute_fine(row[6])
    ok, msg = send_overdue_reminder(row[4], row[3], row[1], row[2], row[5], row[6], days_late, fine)
    if ok:
        c.execute("UPDATE borrow_records SET reminder_sent = TRUE, fine_amount = %s WHERE id = %s", (fine, row[0]))
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
    c.execute("""SELECT br.id, b.title, b.access_code, u.full_name, br.borrower_email,
        br.borrow_date, br.due_date FROM borrow_records br
        JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
        WHERE br.return_time IS NULL AND br.borrow_type = 'Outside' AND br.due_date IS NOT NULL
        AND br.due_date < %s""", (get_ph_date(),))
    rows = c.fetchall()
    sent = 0
    failed = 0
    for row in rows:
        if not row[4] or not EMAIL_RE.match(row[4]):
            failed += 1
            continue
        days_late, fine = compute_fine(row[6])
        ok, _ = send_overdue_reminder(row[4], row[3], row[1], row[2], row[5], row[6], days_late, fine)
        if ok:
            c.execute("UPDATE borrow_records SET reminder_sent = TRUE, fine_amount = %s WHERE id = %s", (fine, row[0]))
            sent += 1
        else:
            failed += 1
    conn.commit()
    conn.close()
    return jsonify({"success": True, "sent": sent, "failed": failed,
                    "message": f"Sent {sent} overdue reminder(s). {failed} failed (no valid email on profile)."})


# ============================================================
#  BORROW / RETURN / SMART SCAN — with INSIDE / OUTSIDE flow
#  Email is NO LONGER asked at borrow time — it is auto-fetched
#  from the borrower's registered profile.
# ============================================================
@app.route('/api/smart-scan', methods=['POST'])
def smart_scan():
    """Unified scan: detect if code is a Book QR/barcode or a User ID (attendance)."""
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
    # 1) Try as BOOK (access_code OR barcode_number)
    c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location, quantity,
        times_borrowed, last_borrowed_date FROM books
        WHERE UPPER(access_code) = UPPER(%s) OR UPPER(COALESCE(barcode_number,'')) = UPPER(%s) LIMIT 1""", (code, code))
    book = c.fetchone()
    if book:
        book_id = book[0]
        active, available, status = book_status_info(book_id, book[7])
        active_borrows = active_borrowers_of(book_id)
        conn.close()
        return jsonify({
            "success": True, "type": "book",
            "book": {
                "id": book_id, "access_code": book[1], "title": book[2], "author": book[3],
                "isbn": book[4], "category": book[5], "shelf_location": book[6],
                "quantity": book[7], "times_borrowed": book[8] or 0,
                "last_borrowed_date": book[9] or "-",
            },
            "available_qty": available, "active_borrows": active_borrows, "status": status,
        })
    # 2) Try as USER ID (attendance)
    today = get_ph_date()
    now = get_ph_time()
    c.execute("SELECT id, full_name, id_number FROM users WHERE UPPER(id_number) = UPPER(%s)", (code,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False, "message": f"Code '{code}' not found as a Book QR/barcode or User ID."})
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
    else:
        c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "type": "attendance", "action": "time_out",
                        "message": f"TIME OUT recorded — {full_name} — {now}",
                        "user": {"full_name": full_name, "id_number": code, "date": today, "time_in": last_attendance[1], "time_out": now}})


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
    c.execute("SELECT id, full_name, id_number, id_type, email FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
    user = c.fetchone()
    conn.close()
    if not user:
        return jsonify({"success": False, "message": f"User ID '{id_number}' not found. Scan a registered Student/Employee/Visitor ID."})
    return jsonify({
        "success": True,
        "user": {"id": user[0], "full_name": user[1], "id_number": user[2],
                 "id_type": user[3], "email": user[4] or ""}
    })


@app.route('/api/borrow-book', methods=['POST'])
def borrow_book():
    """Record a borrow. Email is NOT required — it is auto-fetched from the
    borrower's registered user profile (used only for OUTSIDE borrow notifications)."""
    if not is_scan_authorized():
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    data = request.get_json(silent=True) or request.form
    book_id = str(data.get('book_id', '')).strip()
    id_number = str(data.get('id_number', '')).strip()
    borrow_type = str(data.get('borrow_type', 'Inside')).strip()
    due_date = str(data.get('due_date', '')).strip() or None
    if borrow_type.lower() not in ("inside", "outside"):
        borrow_type = "Inside"
    else:
        borrow_type = borrow_type.capitalize()
    if not book_id or not id_number:
        return jsonify({"success": False, "message": "book_id and id_number are required."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
    try:
        c.execute("SELECT id, title, access_code, quantity FROM books WHERE id = %s", (int(book_id),))
        book = c.fetchone()
        if not book:
            conn.close()
            return jsonify({"success": False, "message": "Book not found."})
        active, available, _ = book_status_info(book[0], book[3])
        if available <= 0:
            conn.close()
            return jsonify({"success": False, "message": f"'{book[1]}' is fully borrowed. No copies available."})
        # Auto-fetch borrower + email from profile (email no longer asked at scan time)
        c.execute("SELECT id, full_name, email FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
        user = c.fetchone()
        if not user:
            conn.close()
            return jsonify({"success": False, "message": f"User ID '{id_number}' not found. Scan a registered Student/Employee/Visitor ID."})
        user_id, full_name, user_email = user
        email = (user_email or "").strip() or None
        today = get_ph_date()
        now = get_ph_time()
        if borrow_type == "Outside":
            if not due_date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
                due_date = add_days(today, OUTSIDE_BORROW_DAYS)
        else:
            due_date = None
        c.execute("""INSERT INTO borrow_records
            (book_id, user_id, borrow_date, borrow_time, status, borrow_type, borrower_email, due_date)
            VALUES (%s, %s, %s, %s, 'Borrowed', %s, %s, %s) RETURNING id""",
            (book[0], user_id, today, now, borrow_type, email, due_date))
        borrow_id = c.fetchone()[0]
        c.execute("UPDATE books SET times_borrowed = times_borrowed + 1, last_borrowed_date = %s WHERE id = %s", (today, book[0]))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"BORROW ERROR: {e}")
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500
    conn.close()
    email_msg = ""
    email_ok = False
    if borrow_type == "Outside" and email and EMAIL_RE.match(email):
        email_ok, email_msg = send_borrow_notification(
            email, full_name, book[1], book[2], today, now, borrow_type, due_date
        )
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
        due_txt = f". Due date: {due_date}. Late fine ₱{LATE_FINE_PER_DAY:.2f}/day."
        if email_ok:
            full_msg = base_msg + due_txt + f" Email notification sent to {email} (from profile)."
        else:
            note = email_msg if email_msg else "No email on profile — notification skipped."
            full_msg = base_msg + due_txt + f" NOTE: {note}"
    else:
        full_msg = base_msg + " (in-library use)."
    return jsonify({"success": True,
                    "message": full_msg,
                    "book_title": book[1], "borrower": full_name,
                    "date": today, "time": now,
                    "borrow_type": borrow_type,
                    "due_date": due_date,
                    "email_sent": email_ok,
                    "email_note": email_msg})


@app.route('/api/return-book', methods=['POST'])
def return_book():
    if not is_scan_authorized():
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    data = request.get_json(silent=True) or request.form
    borrow_id = str(data.get('borrow_id', '')).strip()
    if not borrow_id:
        return jsonify({"success": False, "message": "borrow_id is required."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
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
    c.execute("UPDATE borrow_records SET return_date = %s, return_time = %s, status = 'Returned', fine_amount = %s WHERE id = %s",
              (today, now, fine, int(borrow_id)))
    conn.commit()
    conn.close()
    fine_txt = f" — {days_late} day(s) late, fine ₱{fine:.2f}" if days_late > 0 else ""
    return jsonify({"success": True,
                    "message": f"RETURNED: '{rec[1]}' (borrowed by {rec[2]}) at {now}{fine_txt}",
                    "book_title": rec[1], "borrower": rec[2], "date": today, "time": now,
                    "days_late": days_late, "fine_amount": fine})


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
    query = """SELECT br.id, b.title, b.access_code, u.full_name, u.id_number,
        br.borrow_date, br.borrow_time, br.return_date, br.return_time, br.status,
        br.borrow_type, br.borrower_email, br.email_sent, br.due_date, br.fine_amount
        FROM borrow_records br JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
        WHERE 1=1"""
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
        records.append({
            "id": r[0], "title": r[1], "access_code": r[2], "borrower": r[3],
            "borrower_id": r[4], "borrow_date": r[5], "borrow_time": r[6],
            "return_date": r[7] or "-", "return_time": r[8] or "-",
            "status": "Returned" if r[8] else "Borrowed",
            "borrow_type": r[9] or "Inside",
            "borrower_email": r[10] or "-",
            "email_sent": bool(r[11]),
            "due_date": r[13] or "-",
            "fine_amount": r[14] or fine,
            "days_late": days_late,
        })
    conn.close()
    return jsonify({"records": records})


# ============================================================
#  PRIVACY PAGE & LOGIN (redesigned — SLSU-JGE header + dark card)
# ============================================================
PRIVACY_PAGE = """
<!DOCTYPE html><html><head>
<title>Privacy Policy - SLSU Library Management System</title>
<link rel="icon" type="image/png" href="/static/app-icon.png">
<link rel="apple-touch-icon" href="/static/app-icon.png">
<meta name="theme-color" content="#006633">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}body{font-family:'Segoe UI',Arial,sans-serif;background:#eef0f3;color:#374151;margin:0;padding:24px;line-height:1.65;overflow-x:hidden}.policy{max-width:980px;margin:0 auto;background:#fff;border:1px solid #d8dbe0;padding:34px 42px;box-shadow:0 2px 12px rgba(15,25,43,.08)}h1,h2{font-family:Georgia,'Times New Roman',serif;color:#1b2a41}h1{font-size:26px;margin:0 0 6px}h2{font-size:18px;margin:28px 0 8px;border-bottom:1px solid #eef0f3;padding-bottom:8px}p{margin:8px 0 14px}li{margin:5px 0}.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}table{width:100%;border-collapse:collapse;margin:12px 0 20px;min-width:520px}th,td{border:1px solid #d8dbe0;padding:10px;text-align:left;vertical-align:top;word-break:break-word}th{background:#1b2a41;color:#fff}@media(max-width:600px){body{padding:10px}.policy{padding:22px 18px}table{font-size:12px}}
</style></head><body><main class="policy">
<h1>Privacy Policy - SLSU Library Management System</h1>
<p><strong>Last Updated:</strong> October 2026</p>
<h2>1. Who We Are</h2><p>This system - SLSU Library Management System - is designed exclusively for Southern Luzon State University (SLSU). It is created to simplify and manage library entry and exit records for students, employees, and authorized visitors, as well as book borrowing (inside and outside).</p>
<h2>2. Exactly What Information We Collect</h2><p>We collect only the specific fields you enter during registration:</p>
<div class="table-wrap"><table><tr><th>Field</th><th>Purpose</th></tr><tr><td>Full Name</td><td>Identification and record-keeping</td></tr><tr><td>ID Type</td><td>Student / Employee / Visitor categorization</td></tr><tr><td>ID Number</td><td>Unique identifier - this becomes your barcode</td></tr><tr><td>Email Address</td><td>Collected once at registration; auto-used for OUTSIDE book-borrow notifications (never asked again at scan time)</td></tr><tr><td>Department</td><td>CT, BSED, BEED, BSFAS, BSBA, BPA, EMPLOYEE - for reporting</td></tr><tr><td>Year Level</td><td>Students only - classification and demographic reporting</td></tr><tr><td>Major / Specialization</td><td>Program-specific reporting</td></tr><tr><td>Contact Number</td><td>Library-related announcements only</td></tr><tr><td>Complete Address</td><td>Required per university guidelines</td></tr></table></div>
<p><strong>Attendance Data (Automatically Recorded Upon Scan)</strong></p><ul><li>Time In - exact date and time you scan your ID upon entry</li><li>Time Out - exact date and time you scan your ID upon exit</li><li>Date of Visit - automatically recorded for daily and monthly reports</li></ul>
<p><strong>Book Borrow Data</strong></p><ul><li>Book title, access code, borrow date/time, borrow type (Inside/Outside)</li><li>For Outside borrows: your email on file is used automatically for confirmation and overdue reminders; due date and late fines are computed and emailed. A Privacy & Terms Agreement with an "I Agree" checkbox is presented before an Outside borrow is recorded.</li></ul>
<p><strong>We do not collect passwords, photos, biometrics, location data, browsing history, or financial information.</strong></p>
<h2>3. How We Use Your Information</h2><p>Your data is used only to verify identity, record attendance, manage book borrows, generate reports for library staff, and send borrow/overdue notifications to your email on file. We will never sell, rent, or share your data with any third party, nor send commercial advertisements.</p>
<h2>4. Data Storage and Security</h2><ul><li><strong>Database:</strong> PostgreSQL hosted on Render / Supabase Cloud - encrypted and password-protected</li><li><strong>Security:</strong> All data is transmitted over HTTPS. Only the System Administrator has full database access.</li></ul>
<h2>5. Who Can See Your Data</h2><div class="table-wrap"><table><tr><th>User Role</th><th>What They Can See and Do</th></tr><tr><td>System Administrator (library/slsu)</td><td>Full access to all records - manage books, attendance, borrows, reports; edit, print, delete, download; send overdue reminders</td></tr><tr><td>Library Staff (slsu/library)</td><td>Can register users, scan attendance, process book borrows/returns, view daily records, borrow records, and search books</td></tr><tr><td>Individual User (student/student)</td><td>Can access only the Registration Form and Barcode Generation</td></tr><tr><td>Public / Visitors</td><td>No access - login is required.</td></tr></table></div>
<h2>6. Your Rights</h2><ul><li>Register and create your own barcode</li><li>Request correction of incorrect information</li><li>Request data deletion upon graduation, resignation, or separation from SLSU</li><li>Scan your printed barcode for entry/exit and book borrows</li><li>Know that your information is protected and never shared or sold</li></ul>
<h2>7. Outside Borrow Liability</h2><p>When you borrow a book for OUTSIDE use (take home), you must check the "I Agree" box confirming that you are fully responsible for any damage to the book and must pay the full replacement cost if the book is lost. A late fine applies per day after the due date. A confirmation email and overdue reminders are sent automatically to the address on your profile.</p>
<h2>8. About the System</h2><p>This system was created for Southern Luzon State University (SLSU) - Judge Guillermo Eleazar campus to streamline library attendance and book borrowing while prioritizing user privacy and data security.</p>
<h2>9. Changes to This Policy</h2><p>We may update this Privacy Policy as needed. Changes will be posted here with an updated date.</p>
<h2>10. Contact Information</h2><p><strong>System:</strong> SLSU Library Management System<br><strong>Institution:</strong> Southern Luzon State University - Judge Guillermo Eleazar<br><strong>Office:</strong> SLSU Library - SLSU-JGE</p>
<p><strong>By registering, generating your barcode, scanning your ID, and borrowing books, you confirm that you have read, understood, and agree to this Privacy Policy.</strong></p>
</main></body></html>"""


@app.route('/privacy')
def privacy_policy():
    return render_template_string(PRIVACY_PAGE)


# ---- Shared login page markup (redesigned to match SLSU-JGE header + dark translucent card) ----
LOGIN_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>Sign In — Library Management System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <link rel="apple-touch-icon" href="/static/app-icon.png">
    <meta name="theme-color" content="#0b5d2b">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{
            background:#0f1c30 url('/static/jge.jpg') center/cover no-repeat fixed;
            min-height:100vh;display:flex;flex-direction:column;position:relative;overflow-x:hidden;
        }
        /* Dark overlay over background image so text stays readable */
        body:before{content:"";position:fixed;inset:0;background:rgba(8,16,28,.55);z-index:0;}
        /* ===== Top green institutional header (SLSU-JGE) ===== */
        .site-header{
            position:relative;z-index:2;background:linear-gradient(180deg,#0e6b34,#0a5227);
            color:#fff;padding:14px 18px;display:flex;align-items:center;justify-content:center;gap:16px;
            box-shadow:0 2px 10px rgba(0,0,0,.35);border-bottom:2px solid #e8c766;
        }
        .seal{
            width:52px;height:52px;flex:0 0 52px;object-fit:contain;
            border-radius:8px;background:#fff;padding:3px;
            box-shadow:0 1px 4px rgba(0,0,0,.25);
        }
        @media(max-width:520px){.seal{width:42px;height:42px;flex:0 0 42px;}}
        .header-text{text-align:center;max-width:720px;}
        .header-text h1{font-family:Georgia,'Times New Roman',serif;font-size:17px;font-weight:700;line-height:1.25;word-break:break-word;}
        .header-text p{font-size:12px;margin-top:3px;color:#d9e8dd;letter-spacing:.4px;}
        .login-wrap{flex:1;display:flex;align-items:center;justify-content:center;padding:34px 16px;position:relative;z-index:1;}
        /* ===== Dark translucent rounded card ===== */
        .login-card{
            width:100%;max-width:420px;background:rgba(15,23,42,.72);
            border:1px solid rgba(255,255,255,.18);border-radius:18px;
            backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
            padding:38px 32px 30px;box-shadow:0 14px 40px rgba(0,0,0,.45);
        }
        .login-card h2{
            color:#fff;font-family:Georgia,'Times New Roman',serif;font-size:34px;font-weight:700;
            margin-bottom:26px;letter-spacing:.5px;
        }
        .field{margin-bottom:18px;position:relative;}
        .field input{
            width:100%;padding:15px 16px;border-radius:10px;border:1px solid rgba(255,255,255,.28);
            background:rgba(255,255,255,.10);color:#fff;font-size:15px;transition:border-color .2s,background .2s;
        }
        .field input::placeholder{color:rgba(255,255,255,.65);}
        .field input:focus{outline:none;border-color:#e8c766;background:rgba(255,255,255,.16);}
        .field input[type="password"]{padding-right:48px;}
        .eye-btn{
            position:absolute;right:10px;top:50%;transform:translateY(-50%);
            background:transparent;border:none;cursor:pointer;padding:6px;color:rgba(255,255,255,.75);
            display:flex;align-items:center;justify-content:center;
        }
        .eye-btn:hover{color:#fff;}
        .forgot-row{text-align:right;margin:-6px 0 20px;}
        .forgot-row a{color:#e8c766;font-size:13px;text-decoration:underline;cursor:pointer;}
        .forgot-row a:hover{color:#fff;}
        .signin-btn{
            width:100%;padding:14px;background:#3b82f6;border:none;border-radius:10px;color:#fff;
            font-size:16px;font-weight:700;cursor:pointer;letter-spacing:.4px;transition:background .2s,transform .1s;
        }
        .signin-btn:hover{background:#2563eb;}
        .signin-btn:active{transform:scale(.99);}
        .create-row{text-align:center;margin-top:18px;}
        .create-row a{color:#fff;font-size:14px;text-decoration:underline;cursor:pointer;}
        .create-row a:hover{color:#e8c766;}
        .error-box{
            background:rgba(192,57,43,.18);border:1px solid rgba(231,76,60,.5);color:#ffd7d0;
            padding:12px 14px;border-radius:8px;margin-bottom:18px;font-size:13px;word-break:break-word;
        }
        .footer-note{
            position:relative;z-index:2;text-align:center;color:rgba(255,255,255,.75);
            font-size:12px;padding:14px 16px 22px;
        }
        .footer-note a{color:#e8c766;text-decoration:none;margin:0 6px;}
        .footer-note a:hover{text-decoration:underline;}
        @media(max-width:520px){
            .seal{width:42px;height:42px;flex:0 0 42px;font-size:8px;}
            .header-text h1{font-size:14px;}
            .header-text p{font-size:11px;}
            .login-card{padding:30px 22px 24px;}
            .login-card h2{font-size:28px;}
            .field input{font-size:16px;}
        }
    </style>
</head>
<body>

    <div class="site-header">
        <img class="seal" src="__SLSU_LOGO__" alt="SLSU Official Seal">
        <div class="header-text">
            <h1>Southern Luzon State University – Judge Guillermo Eleazar</h1>
            <p>Library Management System</p>
        </div>
        <img class="seal" src="__SLSU_LOGO__" alt="SLSU-JGE Campus Seal">
    </div>
    <div class="login-wrap">
        <form class="login-card" method="POST" action="/login">
            <h2>Sign In</h2>
            __ERROR__
            <div class="field">
                <input type="text" name="username" required placeholder="Username" autocomplete="username">
            </div>
            <div class="field">
                <input type="password" name="password" id="login-password" required placeholder="Password" autocomplete="current-password">
                <button type="button" class="eye-btn" onclick="togglePassword()" aria-label="Show password">
                    <svg id="eye-open" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    <svg id="eye-closed" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                </button>
            </div>
            <div class="forgot-row"><a href="javascript:void(0)" onclick="alert('Please approach the SLSU-JGE Librarian to reset your account.')">Forgot password?</a></div>
            <button type="submit" class="signin-btn">Sign In</button>
            <div class="create-row"><a href="javascript:void(0)" onclick="alert('Account creation is done at the library. Please approach the SLSU-JGE Librarian to register.')">Create an account</a></div>
        </form>
    </div>
    <div class="footer-note">
        <a href="/privacy" target="_blank">Privacy Policy</a> ·
        <a href="javascript:void(0)" onclick="alert('Please approach the SLSU-JGE Librarian.')">Terms and Conditions</a>
        <br>SLSU-JGE Library Management System © 2026
    </div>
    <script>
window.onerror=function(msg,src,line,col,err){var b=document.createElement('div');b.style.cssText='position:fixed;top:0;left:0;right:0;z-index:99999;background:#a52b2b;color:#fff;padding:12px 18px;font-family:Arial;font-size:13px;line-height:1.5;box-shadow:0 2px 10px rgba(0,0,0,.4);word-break:break-word;';b.innerHTML='<strong>JS ERROR (screenshot & send to dev):</strong><br>'+msg+' (line '+line+')';document.body.appendChild(b);return false;};
        function togglePassword(){
            const p = document.getElementById('login-password');
            const open = document.getElementById('eye-open');
            const closed = document.getElementById('eye-closed');
            if(p.type === 'password'){ p.type = 'text'; open.style.display='none'; closed.style.display='block'; }
            else { p.type = 'password'; open.style.display='block'; closed.style.display='none'; }
        }
    </script>
</body>
</html>"""


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
        if uname == STUDENT_USER and pword == STUDENT_PASS:
            resp = make_response("<script>window.location='/student';</script>")
            resp.set_cookie('logged_in', 'true', max_age=31536000)
            resp.set_cookie('role', 'student', max_age=31536000)
            return resp
        error_html = '<div class="error-box">The username or password you entered is incorrect. Please try again.</div>'
        return LOGIN_PAGE.replace("__ERROR__", error_html).replace("__SLSU_LOGO__", SLSU_LOGO_DATA_URI)
    return LOGIN_PAGE.replace("__ERROR__", "").replace("__SLSU_LOGO__", SLSU_LOGO_DATA_URI)


@app.route('/user')
def user_panel():
    if not is_logged_in() or get_role() != 'user':
        return "<script>window.location='/login';</script>"
    return render_template_string(USER_FRONTEND)


@app.route('/student')
def student_panel():
    if not is_logged_in() or get_role() != 'student':
        return "<script>window.location='/login';</script>"
    return render_template_string(STUDENT_FRONTEND)


@app.route('/')
def home():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    if get_role() != 'admin':
        return "<script>window.location='/user';</script>"
    return render_template_string(ADMIN_FRONTEND)


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
    today = get_ph_date()
    now = get_ph_time()
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
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"TIME IN recorded — {full_name} — {now}"})
    else:
        c.execute("UPDATE attendance SET time_out = %s WHERE id = %s", (now, last_attendance[0]))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"TIME OUT recorded — {full_name} — {now}"})


@app.route('/health')
def health():
    return jsonify({"status": "ok", "email_configured": bool(SMTP_USER and SMTP_PASS)})


# ============================================================
#  REGISTER / UPDATE / GET USERS
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
            department = "EMPLOYEE"
            major = None
            year_level = None
        elif id_type == "Visitor":
            department = None
            major = None
            year_level = None
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database connection failed."}), 500
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
        if c.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "This ID number is already registered."}), 400
        registered_at = get_ph_date() + " " + get_ph_time()
        c.execute("""INSERT INTO users
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at, email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at, email))
        conn.commit()
        conn.close()
        barcode_b64 = generate_barcode_b64(id_number)
        info = f"{full_name}  |  ID: {id_number}  |  {id_type}"
        return jsonify({"success": True, "info": info, "barcode": barcode_b64, "id_number": id_number})
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
    c.execute("""SELECT id, id_type, full_name, department, major, contact_number,
        address, year_level, id_number, email FROM users ORDER BY full_name""")
    students = [{"id": r[0], "id_type": r[1], "full_name": r[2], "department": r[3],
                 "major": r[4], "contact_number": r[5], "address": r[6],
                 "year_level": r[7], "id_number": r[8], "email": r[9] or "",
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
            department = "EMPLOYEE"
            major = None
            year_level = None
        elif id_type == "Visitor":
            department = None
            major = None
            year_level = None
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database error."}), 500
        c = conn.cursor()
        c.execute("""UPDATE users SET
            id_type = %s, id_number = %s, full_name = %s, department = %s,
            major = %s, contact_number = %s, address = %s, year_level = %s, email = %s
            WHERE id = %s""",
            (id_type, id_number, full_name, department, major, contact_number, address, year_level, email, student_id))
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
        FROM attendance a JOIN users u ON a.user_id = u.id
        WHERE a.scan_date = %s
        ORDER BY a.id DESC""", (get_ph_date(),))
    records = [{"scan_date": r[0], "full_name": r[1],
                "department": get_student_code(r[2], r[3], r[4]),
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
    query = """SELECT a.scan_date, u.full_name, u.id_type, u.department, u.year_level,
        u.id_number, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id
        WHERE a.scan_date LIKE %s"""
    params = (f"{month}%",)
    if selected_date:
        query += " AND a.scan_date = %s"
        params = (f"{month}%", selected_date)
    query += " ORDER BY a.scan_date DESC, a.id DESC"
    c.execute(query, params)
    records = [{"scan_date": r[0], "full_name": r[1],
                "department": get_student_code(r[2], r[3], r[4]),
                "id_number": r[5], "time_in": r[6], "time_out": r[7]} for r in c.fetchall()]
    conn.close()
    return jsonify({"records": records})


@app.route('/download-word')
def download_word():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    conn = get_db()
    if not conn:
        return "Database error"
    today = get_ph_date()
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_number, u.id_type, u.department, u.year_level,
        a.time_in, a.time_out
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
    hdr[0].text = 'Full Name'
    hdr[1].text = 'Department'
    hdr[2].text = 'ID Number'
    hdr[3].text = 'Time In'
    hdr[4].text = 'Time Out'
    for rec in records:
        row = table.add_row().cells
        row[0].text = rec[0]
        row[1].text = get_student_code(rec[2], rec[3], rec[4])
        row[2].text = rec[1]
        row[3].text = rec[5] or '-'
        row[4].text = rec[6] or '-'
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Disposition'] = f'attachment; filename=attendance_report_{today}.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp


@app.route('/download-monthly-word')
def download_monthly_word():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    month = request.args.get('month', '').strip()
    conn = get_db()
    if not conn:
        return "Database error"
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.id_type, u.department, u.year_level,
        a.scan_date, a.time_in, a.time_out
        FROM attendance a JOIN users u ON a.user_id = u.id
        WHERE a.scan_date LIKE %s ORDER BY a.scan_date, a.id""", (f"{month}%",))
    records = c.fetchall()
    conn.close()
    doc = Document()
    doc.add_heading(f'Monthly Attendance Report — {month}', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('SLSU–JGE Library Management System')
    current_date = None
    table = None
    for rec in records:
        if rec[4] != current_date:
            current_date = rec[4]
            doc.add_heading(current_date, level=2)
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            hdr = table.rows[0].cells
            hdr[0].text = 'Date'
            hdr[1].text = 'Full Name'
            hdr[2].text = 'Department'
            hdr[3].text = 'Time In'
            hdr[4].text = 'Time Out'
        row = table.add_row().cells
        row[0].text = rec[4]
        row[1].text = rec[0]
        row[2].text = get_student_code(rec[1], rec[2], rec[3])
        row[3].text = rec[5] or '-'
        row[4].text = rec[6] or '-'
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Disposition'] = f'attachment; filename=monthly_attendance_{month}.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp


@app.route('/download-borrow-word')
def download_borrow_word():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    conn = get_db()
    if not conn:
        return "Database error"
    c = conn.cursor()
    c.execute("""SELECT b.title, b.access_code, u.full_name, u.id_number,
        br.borrow_date, br.borrow_time, br.return_date, br.return_time, br.borrow_type, br.due_date, br.fine_amount, br.status
        FROM borrow_records br JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
        ORDER BY br.id DESC""")
    records = c.fetchall()
    conn.close()
    doc = Document()
    doc.add_heading('Library Book Borrow & Return Records', 0)
    doc.add_paragraph(f'Generated on: {get_ph_date()} {get_ph_time()}')
    doc.add_paragraph('SLSU–JGE Library Management System')
    table = doc.add_table(rows=1, cols=8)
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    headers = ['Book Title / Book ID', 'Borrower Name & ID', 'Borrow Type',
               'Date & Time Borrowed', 'Due Date', 'Date & Time Returned',
               'Overdue Fine (₱)', 'Current Status']
    for i, h in enumerate(headers):
        hdr[i].text = h
    for rec in records:
        row = table.add_row().cells
        row[0].text = f"{rec[0]} ({rec[1]})"
        row[1].text = f"{rec[2]} ({rec[3]})"
        row[2].text = rec[8] or 'Inside'
        row[3].text = f"{rec[4]} {rec[5]}"
        row[4].text = rec[9] or '-'
        row[5].text = f"{rec[6]} {rec[7]}" if rec[6] else '-'
        fine = rec[10] or 0
        row[6].text = f"₱{float(fine):.2f}" if float(fine) > 0 else '-'
        row[7].text = 'Returned' if rec[7] else 'Borrowed'
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    resp = make_response(buffer.getvalue())
    resp.headers['Content-Disposition'] = 'attachment; filename=book_borrow_records.docx'
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return resp


@app.route('/print-monthly')
def print_monthly():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    month = request.args.get('month', '').strip()
    return f"""
<!DOCTYPE html><html><head><title>Monthly Report — {month}</title>
<link rel="icon" type="image/png" href="/static/app-icon.png">
<link rel="apple-touch-icon" href="/static/app-icon.png">
<meta name="theme-color" content="#006633">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{{box-sizing:border-box;}}
body{{font-family:'Segoe UI',Arial,sans-serif;padding:40px;max-width:1100px;margin:0 auto;color:#1f2937;overflow-x:hidden;}}
.report-header{{border-bottom:3px solid #1b2a41;padding-bottom:16px;margin-bottom:24px;}}
h1{{color:#1b2a41;font-family:Georgia,'Times New Roman',serif;font-size:24px;margin-bottom:6px;word-break:break-word;}}
.meta{{color:#64748b;font-size:13px;}}
.table-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;}}
table{{width:100%;border-collapse:collapse;margin-top:10px;min-width:560px;}}
th,td{{border:1px solid #d8dbe0;padding:10px 12px;text-align:left;font-size:13px;word-break:break-word;}}
th{{background:#1b2a41;color:#fff;font-weight:600;}}
tr:nth-child(even){{background:#f7f8fa;}}
button{{padding:11px 26px;font-size:14px;cursor:pointer;background:#1b2a41;color:white;border:none;border-radius:4px;font-weight:600;margin-bottom:20px;}}
@media(max-width:600px){{body{{padding:14px;}}h1{{font-size:19px;}}table{{font-size:12px;}}}}
@media print{{button{{display:none;}}body{{padding:0;}}}}
</style>
</head><body>

<div class="report-header">
<h1>Monthly Attendance Report — {month}</h1>
<p class="meta">SLSU–JGE Library Management System &nbsp;•&nbsp; Generated: {get_ph_date()} {get_ph_time()}</p>
</div>
<button type="button" onclick="window.print()">Print Report</button>
<div id="report-area"></div>
<script>fetch('/get-monthly-history?month={month}').then(r=>r.json()).then(d=>{{
 const grouped = d.records.reduce((days, record) => {{
     (days[record.scan_date] ||= []).push(record);
     return days;
 }}, {{}});
 let html='';
 Object.entries(grouped).forEach(([date, records]) => {{
     html+='<h2 style="margin-top:28px;word-break:break-word;">'+date+'</h2><div class="table-wrap"><table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>';
     records.forEach(r=>html+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+r.department+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>');
     html+='</table></div>';
 }});
 document.getElementById('report-area').innerHTML=html || '<p style="color:#64748b;padding:20px;">No records.</p>';
}})</script>
</body></html>"""


@app.route('/print-daily')
def print_daily():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    selected_date = request.args.get('date', '').strip() or get_ph_date()
    return f"""
<!DOCTYPE html><html><head><title>Daily Attendance Report - {selected_date}</title>
<link rel="icon" type="image/png" href="/static/app-icon.png">
<link rel="apple-touch-icon" href="/static/app-icon.png">
<meta name="theme-color" content="#006633">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>*{{box-sizing:border-box;}}body{{font-family:'Segoe UI',Arial,sans-serif;padding:40px;max-width:1100px;margin:0 auto;color:#1f2937;overflow-x:hidden;}}h1{{color:#1b2a41;font-family:Georgia,'Times New Roman',serif;word-break:break-word;}}.meta{{color:#64748b;font-size:13px;}}.table-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;}}table{{width:100%;border-collapse:collapse;margin-top:24px;min-width:560px;}}th,td{{border:1px solid #d8dbe0;padding:10px 12px;text-align:left;font-size:13px;word-break:break-word;}}th{{background:#1b2a41;color:#fff;}}tr:nth-child(even){{background:#f7f8fa;}}button{{padding:11px 26px;font-size:14px;cursor:pointer;background:#1b2a41;color:white;border:0;border-radius:4px;font-weight:600;margin-bottom:20px;}}@media(max-width:600px){{body{{padding:14px;}}table{{font-size:12px;}}}}@media print{{button{{display:none;}}body{{padding:0;}}}}</style>
</head><body><button type="button" onclick="window.print()">Print Daily Report</button><h1>Daily Attendance Report - {selected_date}</h1><p class="meta">SLSU-JGE Library Management System</p>
<div class="table-wrap" id="daily-table-wrap"></div>
<script>fetch('/get-monthly-history?month={selected_date[:7]}&date={selected_date}').then(r=>r.json()).then(d=>{{let html='<table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>';d.records.forEach(r=>html+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+r.department+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>');html+='</table>';document.getElementById('daily-table-wrap').innerHTML=html;}})</script></body></html>"""


@app.route('/print-borrow-records')
def print_borrow_records():
    if not is_logged_in():
        return "<script>window.location='/login';</script>"
    return """
<!DOCTYPE html><html><head><title>Book Borrow & Return Records</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>*{box-sizing:border-box;}body{font-family:'Segoe UI',Arial,sans-serif;padding:40px;max-width:1200px;margin:0 auto;color:#1f2937;overflow-x:hidden;}h1{color:#1b2a41;font-family:Georgia,serif;}.meta{color:#64748b;font-size:13px;}.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;}table{width:100%;border-collapse:collapse;margin-top:20px;min-width:860px;}th,td{border:1px solid #d8dbe0;padding:10px 12px;text-align:left;font-size:13px;word-break:break-word;vertical-align:top;}th{background:#1b2a41;color:#fff;}tr:nth-child(even){background:#f7f8fa;}button{padding:11px 26px;font-size:14px;cursor:pointer;background:#1b2a41;color:white;border:0;border-radius:4px;font-weight:600;margin-bottom:20px;}@media print{button{display:none;}body{padding:0;}}</style>
</head><body><button type="button" onclick="window.print()">Print Borrow Records</button>
<h1>Book Borrow & Return Records</h1><p class="meta">SLSU-JGE Library Management System</p>
<div class="table-wrap" id="area"></div>
<script>fetch('/get-borrow-records').then(r=>r.json()).then(d=>{
let html='<table><tr><th>Book Title / Book ID</th><th>Borrower Name &amp; ID</th><th>Borrow Type</th><th>Date &amp; Time Borrowed</th><th>Due Date</th><th>Date &amp; Time Returned</th><th>Overdue Fine (₱)</th><th>Current Status</th></tr>';
d.records.forEach(r=>{
  const fine = (r.fine_amount>0)?('₱'+Number(r.fine_amount).toFixed(2)):'-';
  const status = (r.status==="Returned")?'Returned':'Borrowed';
  html+='<tr><td><strong>'+r.title+'</strong><br><span style="color:#64748b;font-size:11px;">'+r.access_code+'</span></td>'+
        '<td>'+r.borrower+'<br><span style="color:#64748b;font-size:11px;">'+r.borrower_id+'</span></td>'+
        '<td>'+r.borrow_type+'</td>'+
        '<td>'+r.borrow_date+' '+r.borrow_time+'</td>'+
        '<td>'+r.due_date+'</td>'+
        '<td>'+(r.return_date!=="-"?r.return_date+' '+r.return_time:'-')+'</td>'+
        '<td>'+fine+'</td>'+
        '<td>'+status+'</td></tr>';
});
html+='</table>';
document.getElementById('area').innerHTML=html;
})</script>
</body></html>"""


# ============================================================
#  LEGAL TERMS (shared string for OUTSIDE borrow — with "I Agree" checkbox)
# ============================================================
LEGAL_TERMS_HTML = """
<div style="text-align:left;font-size:13px;line-height:1.7;color:#374151;">
<p style="margin-bottom:10px;"><strong style="color:#8a1f1f;">OUTSIDE BORROW — PRIVACY &amp; TERMS AGREEMENT</strong></p>
<p style="margin-bottom:8px;">By choosing <strong>OUTSIDE</strong> (taking the book home), the borrower acknowledges and agrees to the following:</p>
<ol style="padding-left:20px;margin-bottom:10px;">
<li style="margin-bottom:6px;"><strong>LIABILITY FOR DAMAGE:</strong> The borrower is fully responsible for any damage, destruction, missing pages, or alteration to the book while it is in their care outside the library. They must pay the cost of repair or replacement.</li>
<li style="margin-bottom:6px;"><strong>PAYMENT IF LOST:</strong> If the book is lost, the borrower must <strong>pay the full current replacement cost</strong> of the book, or replace it with an identical copy within thirty (30) days.</li>
<li style="margin-bottom:6px;"><strong>TIMELY RETURN:</strong> The book must be returned within three (3) working days from the date of borrowing, or by the due date set by the librarian. A late fine of <strong>₱5.00 per day</strong> applies after the due date.</li>
<li style="margin-bottom:6px;"><strong>EMAIL NOTIFICATION (auto from profile):</strong> A confirmation will be automatically sent to the email address registered on the borrower's profile — no need to type it again. If the due date passes, a reminder and the fine amount will be sent automatically.</li>
<li style="margin-bottom:6px;"><strong>LOSS OF PRIVILEGE:</strong> Repeated violations of these terms may result in temporary or permanent loss of borrowing privileges.</li>
</ol>
<p style="background:#fdf6e3;border-left:4px solid #c9a227;padding:10px 14px;font-size:12px;color:#8a6d1f;margin-bottom:8px;">
<strong>Reminder:</strong> You must tick the <strong>"I Agree"</strong> checkbox below before you can continue. The email address will be taken automatically from your registered profile.</p>
</div>
"""


# ============================================================
#  STUDENT FRONTEND — registration form ONLY
# ============================================================
STUDENT_FRONTEND = """
<!DOCTYPE html>
<html>
<head>
    <title>User Registration — SLSU-JGE Library</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <link rel="apple-touch-icon" href="/static/app-icon.png">
    <meta name="theme-color" content="#006633">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#eef0f3;min-height:100vh;display:flex;justify-content:center;align-items:flex-start;padding:30px 16px;overflow-x:hidden;}
        .container{width:100%;max-width:560px;}
        .card{background:#ffffff;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 2px 12px rgba(15,25,43,0.08);overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:42px 40px;}
        .brand-mark{width:52px;height:52px;margin:0 auto 16px auto;background:#1b2a41;color:#e8c766;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:12px;text-align:center;line-height:1.2;}
        h1{text-align:center;color:#1b2a41;margin-bottom:6px;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;word-break:break-word;}
        .subtitle{text-align:center;color:#64748b;margin-bottom:32px;font-size:14px;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:8px;color:#374151;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;}
        input,select{width:100%;padding:12px 14px;border:1px solid #d1d5db;border-radius:4px;font-size:14px;transition:border-color 0.2s,box-shadow 0.2s;background:#fafbfc;}
        input:focus,select:focus{outline:none;border-color:#1b2a41;background:#fff;box-shadow:0 0 0 3px rgba(27,42,65,0.1);}
        button.btn-primary{width:100%;padding:14px;background:#1b2a41;color:white;border:none;border-radius:4px;font-size:15px;font-weight:600;cursor:pointer;transition:background 0.2s;margin-top:6px;letter-spacing:.3px;}
        button.btn-primary:hover{background:#10192b;}
        #barcode-result{display:none;margin-top:28px;text-align:center;padding:26px;background:#f7f8fa;border-radius:6px;border:1px solid #d8dbe0;}
        #barcode-result h3{color:#1b2a41;margin-bottom:12px;font-size:16px;font-family:Georgia,'Times New Roman',serif;}
        .barcode-img{width:60mm;height:20mm;max-width:100%;margin:18px auto;display:block;padding:6px;background:white;border:1px solid #d8dbe0;border-radius:4px;object-fit:contain;image-rendering:crisp-edges;}
        .barcode-id{font-size:18px;font-weight:700;color:#1b2a41;margin:12px 0;word-break:break-word;}
        .btn-print{background:#1e6b34;color:#fff;border:none;padding:12px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;margin:4px;}
        .btn-print:hover{background:#175628;}
        .btn-download-barcode{background:#8a6d1f;color:#fff;border:none;padding:12px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;margin:4px;}
        .btn-download-barcode:hover{background:#6e5718;}
        .logout-link{display:block;text-align:center;margin-top:22px;color:#64748b;text-decoration:none;font-size:13px;border-top:1px solid #eef0f3;padding-top:18px;}
        .logout-link:hover{color:#1b2a41;}
        .privacy-link{display:block;text-align:center;margin-top:12px;color:#1b2a41;text-decoration:none;font-size:13px;}
        .privacy-link:hover{text-decoration:underline;}
        @media print{body *{visibility:hidden !important;}#barcode-result,#barcode-result *{visibility:visible !important;}#barcode-result{display:block !important;position:absolute;top:0;left:0;width:60mm;height:25mm;margin:0;padding:0;border:1px solid #000;background:#fff;}#barcode-result h3{display:none;}.barcode-img{width:60mm;height:18mm;object-fit:contain;padding:0;border:0;margin:4mm auto 0;}.barcode-id{font-size:8pt;margin:1mm 0 0;}.btn-print{display:none !important;}}
        @media(max-width:600px){.form-row{grid-template-columns:1fr;}.card-body{padding:30px 22px;}input,select{font-size:16px;}body{padding:16px 10px;}}
    </style>
</head>
<body>

    <div class="container">
        <div class="card">
            <div class="card-top"></div>
            <div class="card-body">
                <div class="brand-mark">SLSU<br>JGE</div>
                <h1>User Registration</h1>
                <p class="subtitle">Complete the form to generate an attendance barcode</p>
                <form id="register-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>ID Type *</label>
                            <select name="id_type" id="id-type-select" required>
                                <option value="Student">Student</option>
                                <option value="Employee">Employee</option>
                                <option value="Visitor">Visitor</option>
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
                    <div id="student-fields">
                        <div class="form-row">
                            <div class="form-group" id="student-department-group">
                                <label>Department</label>
                                <select name="department" id="dept-select">
                                    <option value="">-- Select Department --</option>
                                    <option value="CT">BSIT</option>
                                    <option value="BSED">BSED</option>
                                    <option value="BEED">BEED</option>
                                    <option value="BSFAS">BSFAS</option>
                                    <option value="BSBA">BSBA</option>
                                    <option value="BPA">BPA</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Major / Specialization</label>
                                <select name="major" id="major-select">
                                    <option value="">-- Select Department First --</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group" id="student-year-group">
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
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Contact Number *</label>
                            <input type="text" name="contact_number" required placeholder="09XX-XXX-XXXX">
                        </div>
                        <div class="form-group">
                            <label>Address *</label>
                            <input type="text" name="address" required placeholder="City, Province">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Email (saved once — auto-used for outside-borrow notifications)</label>
                        <input type="email" name="email" placeholder="you@example.com">
                    </div>
                    <button type="submit" class="btn-primary">Register &amp; Generate Barcode</button>
                </form>
                <div id="barcode-result">
                    <h3>Registration Successful</h3>
                    <p id="barcode-id" class="barcode-id"></p>
                    <img id="barcode-img" class="barcode-img"><br>
                    <button type="button" class="btn-print" onclick="window.print()">Print Barcode</button>
                    <button type="button" class="btn-download-barcode" onclick="downloadUserBarcode()">Download Barcode</button>
                </div>
                <a href="/privacy" class="privacy-link" target="_blank">Privacy Policy</a>
                <a href="/login" class="logout-link" onclick="logout(event)">← Back to Sign In</a>
            </div>
        </div>
    </div>
<script>
window.onerror=function(msg,src,line,col,err){var b=document.createElement('div');b.style.cssText='position:fixed;top:0;left:0;right:0;z-index:99999;background:#a52b2b;color:#fff;padding:12px 18px;font-family:Arial;font-size:13px;line-height:1.5;box-shadow:0 2px 10px rgba(0,0,0,.4);word-break:break-word;';b.innerHTML='<strong>JS ERROR (screenshot & send to dev):</strong><br>'+msg+' (line '+line+')';document.body.appendChild(b);return false;};
const MAJORS = {
    "BSBA": ["Marketing Management", "Financial Management"],
    "BSED": ["English", "Mathematics", "Science"],
    "CT": ["Computer Technology", "Food Technology", "BINDTECH", "CULINARY"],
};
function logout(e){
    if(e) e.preventDefault();
    document.cookie = "logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    document.cookie = "role=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    window.location.href = "/login";
}
function downloadUserBarcode(){
    const barcodeImage = document.getElementById("barcode-img");
    const idNumber = document.getElementById("barcode-id").textContent.replace("ID Number: ", "").trim();
    if(!barcodeImage.src || !idNumber){alert('Register first (Register & Generate Barcode) — then the barcode will be available to download.');return;}
    const link = document.createElement("a");
    link.href = barcodeImage.src;
    link.download = "barcode_" + idNumber + ".png";
    document.body.appendChild(link); link.click(); link.remove();
}
document.addEventListener("DOMContentLoaded", function(){
    const form = document.getElementById("register-form");
    const departmentSelect = document.getElementById("dept-select");
    const majorSelect = document.getElementById("major-select");
    const idTypeSelect = document.getElementById("id-type-select");
    const studentFields = document.getElementById("student-fields");
    function updateFieldsByIdType(){
        const isStudent = idTypeSelect.value === "Student";
        studentFields.style.display = isStudent ? "" : "none";
        studentFields.querySelectorAll("input, select").forEach(field=>{field.disabled = !isStudent;});
        const idInput = document.querySelector('#register-form input[name="id_number"]');
        if(idInput){
            const grp = idInput.closest('.form-group');
            if(grp){ grp.style.display = isStudent ? "" : "none"; }
            idInput.disabled = !isStudent;
        }
    }
    departmentSelect.addEventListener("change", function(){
        const department = departmentSelect.value;
        majorSelect.innerHTML = '<option value="">-- Select Major --</option>';
        (MAJORS[department]||[]).forEach(function(major){
            const option = document.createElement("option");
            option.value = major; option.textContent = major;
            majorSelect.appendChild(option);
        });
        majorSelect.disabled = (department === "BPA" || department === "");
    });
    majorSelect.disabled = true;
    idTypeSelect.addEventListener("change", updateFieldsByIdType);
    updateFieldsByIdType();
    form.addEventListener("submit", function(e){
        e.preventDefault();
        const formData = new FormData(form);
        fetch("/register",{method:"POST",body:formData})
        .then(res=>res.json()).then(data=>{
            if(data.success){
                document.getElementById("barcode-result").style.display="block";
                document.getElementById("barcode-id").textContent="ID Number: " + (data.id_number || formData.get("id_number"));
                document.getElementById("barcode-img").src="data:image/png;base64,"+data.barcode;
                form.reset();
                document.getElementById("dept-select").value="";
                majorSelect.innerHTML='<option value="">-- Select Department First --</option>';
                majorSelect.disabled = true;
                updateFieldsByIdType();
            }else{ alert(data.error); }
        }).catch(err=>alert("Error: "+err));
    });
});
</script>
</body>
</html>
"""

# ============================================================
#  STAFF (USER) FRONTEND — menu bar: Scanner | Daily Records | Borrowed Books | Book Search | Registration
#  Borrow flow: small checkbox (unchecked=Inside, checked=Outside). Outside shows Privacy & Terms
#  Agreement with an "I Agree" checkbox before ID scan. Email auto-fetched from profile — never asked.
# ============================================================
USER_FRONTEND = """
<!DOCTYPE html>
<html>
<head>
    <title>Staff Panel — SLSU-JGE Library System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <link rel="apple-touch-icon" href="/static/app-icon.png">
    <meta name="theme-color" content="#006633">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#eef0f3;min-height:100vh;overflow-x:hidden;}
        .topnav{background:#1b2a41;display:flex;align-items:center;flex-wrap:wrap;padding:0 20px;box-shadow:0 2px 8px rgba(15,25,43,.18);position:sticky;top:0;z-index:50;}
        .brand{display:flex;align-items:center;gap:12px;padding:14px 0;color:#fff;margin-right:auto;}
        .brand-mark{width:40px;height:40px;background:#24344f;color:#e8c766;border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:11px;text-align:center;line-height:1.2;flex:0 0 40px;}
        .brand-text h1{font-size:16px;font-family:Georgia,'Times New Roman',serif;color:#f1f3f6;word-break:break-word;}
        .brand-text p{font-size:11px;color:#8b9bb5;letter-spacing:.3px;}
        .nav-tabs{display:flex;gap:2px;flex-wrap:wrap;}
        .nav-tab{padding:14px 16px;color:#c3cede;cursor:pointer;font-size:13px;font-weight:600;border-bottom:3px solid transparent;transition:all .2s;white-space:nowrap;}
        .nav-tab:hover{background:#233450;color:#fff;}
        .nav-tab.active{color:#fff;border-bottom:3px solid #e8c766;background:#24344f;}
        .logout-btn{background:#7a1f1f;color:#fff;border:none;padding:9px 18px;border-radius:4px;font-size:13px;font-weight:600;cursor:pointer;margin-left:10px;}
        .logout-btn:hover{background:#5e1717;}
        .staff-content{max-width:1150px;margin:0 auto;padding:28px 20px 60px;}
        .staff-tab{display:none;}
        .staff-tab.active{display:block;}
        .container{width:100%;max-width:560px;margin:0 auto;}
        .card{background:#ffffff;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 2px 12px rgba(15,25,43,0.08);overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:42px 40px;}
        .reg-brand-mark{width:52px;height:52px;margin:0 auto 16px auto;background:#1b2a41;color:#e8c766;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:12px;text-align:center;line-height:1.2;}
        h1.reg-title{text-align:center;color:#1b2a41;margin-bottom:6px;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;word-break:break-word;}
        .subtitle{text-align:center;color:#64748b;margin-bottom:32px;font-size:14px;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:8px;color:#374151;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;}
        input,select{width:100%;padding:12px 14px;border:1px solid #d1d5db;border-radius:4px;font-size:14px;transition:border-color 0.2s,box-shadow 0.2s;background:#fafbfc;}
        input:focus,select:focus{outline:none;border-color:#1b2a41;background:#fff;box-shadow:0 0 0 3px rgba(27,42,65,0.1);}
        button.btn-primary{width:100%;padding:14px;background:#1b2a41;color:white;border:none;border-radius:4px;font-size:15px;font-weight:600;cursor:pointer;transition:background 0.2s;margin-top:6px;letter-spacing:.3px;}
        button.btn-primary:hover{background:#10192b;}
        #barcode-result{display:none;margin-top:28px;text-align:center;padding:26px;background:#f7f8fa;border-radius:6px;border:1px solid #d8dbe0;}
        #barcode-result h3{color:#1b2a41;margin-bottom:12px;font-size:16px;font-family:Georgia,'Times New Roman',serif;}
        .barcode-img{width:60mm;height:20mm;max-width:100%;margin:18px auto;display:block;padding:6px;background:white;border:1px solid #d8dbe0;border-radius:4px;object-fit:contain;image-rendering:crisp-edges;}
        .barcode-id{font-size:18px;font-weight:700;color:#1b2a41;margin:12px 0;word-break:break-word;}
        .btn-print{background:#1e6b34;color:#fff;border:none;padding:12px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;margin:4px;}
        .btn-print:hover{background:#175628;}
        .btn-download-barcode{background:#8a6d1f;color:#fff;border:none;padding:12px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;margin:4px;}
        .btn-download-barcode:hover{background:#6e5718;}
        .logout-link{display:block;text-align:center;margin-top:22px;color:#64748b;text-decoration:none;font-size:13px;border-top:1px solid #eef0f3;padding-top:18px;}
        .logout-link:hover{color:#1b2a41;}
        .privacy-link{display:block;text-align:center;margin-top:12px;color:#1b2a41;text-decoration:none;font-size:13px;}
        .privacy-link:hover{text-decoration:underline;}
        @media print{body *{visibility:hidden !important;}#barcode-result,#barcode-result *{visibility:visible !important;}#barcode-result{display:block !important;position:absolute;top:0;left:0;width:60mm;height:25mm;margin:0;padding:0;border:1px solid #000;background:#fff;}#barcode-result h3{display:none;}.barcode-img{width:60mm;height:18mm;object-fit:contain;padding:0;border:0;margin:4mm auto 0;}.barcode-id{font-size:8pt;margin:1mm 0 0;}.btn-print{display:none !important;}}
        .panel-card{background:#fff;border:1px solid #d8dbe0;border-radius:6px;padding:28px;box-shadow:0 2px 12px rgba(15,25,43,.08);}
        h2.panel-title{color:#1b2a41;font-size:19px;font-family:Georgia,'Times New Roman',serif;margin-bottom:18px;border-bottom:1px solid #eef0f3;padding-bottom:12px;word-break:break-word;}
        .scan-area{text-align:center;padding:30px;background:#f7f8fa;border-radius:6px;margin-bottom:18px;border:1px solid #d8dbe0;}
        .scan-input{font-size:20px;text-align:center;padding:14px;width:100%;max-width:480px;border-radius:4px;border:1px solid #b9c2cf;}
        .status{font-size:15px;font-weight:600;margin-top:16px;padding:14px;border-radius:4px;border-left:4px solid;word-break:break-word;}
        .success{background:#e8f5ec;color:#1e6b34;border-color:#2f8a4e;}
        .info{background:#eaf1f8;color:#1b4f72;border-color:#3a75a3;}
        .error{background:#fbeaea;color:#8a1f1f;border-color:#c0392b;}
        .warning{background:#fdf6e3;color:#8a6d1f;border-color:#c9a227;}
        .table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;}
        table{width:100%;border-collapse:collapse;margin-top:16px;min-width:560px;}
        th,td{padding:11px 12px;text-align:left;border:1px solid #e5e7eb;font-size:13px;word-break:break-word;vertical-align:top;}
        th{background:#1b2a41;color:#fff;font-weight:600;}
        tr:nth-child(even){background:#f7f8fa;}
        .book-detail{background:#f7f8fa;border:1px solid #d8dbe0;border-radius:6px;padding:22px;margin-top:18px;}
        .book-detail h3{color:#1b2a41;font-family:Georgia,'Times New Roman',serif;font-size:18px;margin-bottom:10px;word-break:break-word;}
        .book-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px 18px;margin:12px 0 18px;font-size:13px;}
        .book-meta div strong{color:#1b2a41;display:block;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#64748b;margin-bottom:2px;}
        .badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;}
        .badge-avail{background:#e8f5ec;color:#1e6b34;}
        .badge-borrowed{background:#fbeaea;color:#8a1f1f;}
        .badge-inside{background:#eaf1f8;color:#1b4f72;}
        .badge-outside{background:#fdf6e3;color:#8a6d1f;}
        .action-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;}
        .btn-return{background:#1e6b34;color:#fff;border:none;padding:8px 16px;border-radius:4px;font-size:12px;font-weight:600;cursor:pointer;}
        .btn-return:hover{background:#175628;}
        .btn-cancel{background:#5b6472;color:#fff;border:none;padding:11px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;}
        .btn-cancel:hover{background:#464d59;}
        /* small borrow-type checkbox (unchecked=Inside, checked=Outside) */
        .borrow-type-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:10px;padding:12px 14px;background:#fff;border:1px solid #d8dbe0;border-radius:6px;}
        .borrow-type-row label{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700;color:#374151;cursor:pointer;text-transform:none;letter-spacing:0;margin:0;}
        .borrow-type-row input[type=checkbox]{width:18px;height:18px;cursor:pointer;flex:0 0 auto;}
        .borrow-type-hint{font-size:12px;color:#64748b;}
        .awaiting-box{background:#fdf6e3;border:2px dashed #c9a227;border-radius:6px;padding:16px;text-align:center;margin-top:14px;font-weight:600;color:#8a6d1f;word-break:break-word;}
        .borrower-row{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#fff;border:1px solid #e5e7eb;border-radius:4px;margin-top:8px;font-size:13px;flex-wrap:wrap;gap:8px;word-break:break-word;}
        .terms-modal{position:fixed;inset:0;background:rgba(15,25,43,.62);display:flex;align-items:center;justify-content:center;padding:16px;z-index:300;}
        .terms-modal.hidden{display:none;}
        .terms-dialog{background:#fff;width:100%;max-width:640px;max-height:88vh;overflow-y:auto;border-radius:6px;box-shadow:0 12px 40px rgba(15,25,43,.35);padding:26px;}
        .terms-dialog h3{color:#8a1f1f;font-family:Georgia,'Times New Roman',serif;margin-bottom:14px;font-size:18px;word-break:break-word;}
        .i-agree-row{display:flex;align-items:center;gap:10px;margin-top:16px;padding:12px 14px;background:#f7f8fa;border:1px solid #d8dbe0;border-radius:6px;}
        .i-agree-row label{display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;cursor:pointer;color:#1b2a41;text-transform:none;letter-spacing:0;margin:0;}
        .i-agree-row input[type=checkbox]{width:18px;height:18px;cursor:pointer;flex:0 0 auto;}
        .terms-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;justify-content:flex-end;}
        .btn-agree{background:#1e6b34;color:#fff;border:none;padding:12px 24px;border-radius:4px;font-size:14px;font-weight:700;cursor:pointer;}
        .btn-agree:hover{background:#175628;}
        #toast{position:fixed;top:70px;right:20px;max-width:360px;z-index:400;display:flex;flex-direction:column;gap:8px;}
        .toast-item{padding:14px 18px;border-radius:6px;font-size:14px;font-weight:600;box-shadow:0 6px 20px rgba(15,25,43,.25);border-left:4px solid;animation:slideIn .25s ease;word-break:break-word;}
        @keyframes slideIn{from{transform:translateX(40px);opacity:0;}to{transform:translateX(0);opacity:1;}}
        .search-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px;align-items:center;}
        .search-row input{flex:1 1 260px;max-width:none;}
        .search-row button{margin:0;}
        .filter-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;align-items:center;}
        .filter-row select,.filter-row input{max-width:180px;}
        .borrower-list{margin-top:8px;font-size:12px;color:#8a1f1f;background:#fbeaea;padding:8px 12px;border-radius:4px;word-break:break-word;}
        @media(max-width:700px){
            .form-row{grid-template-columns:1fr;}
            .card-body{padding:30px 22px;}
            .nav-tab{padding:12px 12px;font-size:12px;}
            .staff-content{padding:18px 10px 40px;}
            .panel-card{padding:18px 14px;}
            input,select,textarea{font-size:16px;}
            .scan-input{font-size:18px;padding:12px;}
            .scan-area{padding:20px 12px;}
            .topnav{padding:0 12px;}
            .logout-btn{margin-left:0;margin-top:6px;margin-bottom:6px;width:100%;}
        }
        @media(max-width:480px){ #toast{left:12px;right:12px;max-width:none;top:60px;} }
    </style>
</head>
<body>

    <div class="topnav">
        <div class="brand">
            <div class="brand-mark">SLSU<br>JGE</div>
            <div class="brand-text"><h1>Library System — Staff</h1><p>Library Management System</p></div>
        </div>
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
    <!-- ===== OUTSIDE BORROW PRIVACY & TERMS AGREEMENT MODAL (with I Agree checkbox) ===== -->
    <div id="terms-modal" class="terms-modal hidden">
        <div class="terms-dialog">
            <h3>OUTSIDE BORROW — Privacy &amp; Terms Agreement</h3>
            <div style="text-align:left;font-size:13px;line-height:1.7;color:#374151;">
                <p style="margin-bottom:8px;">By choosing <strong>OUTSIDE</strong> (taking the book home), the borrower acknowledges and agrees to the following:</p>
                <ol style="padding-left:20px;margin-bottom:10px;">
                    <li style="margin-bottom:6px;"><strong>LIABILITY FOR DAMAGE:</strong> The borrower is fully responsible for any damage, destruction, or alteration to the book while it is in their care. They must pay the cost of repair or replacement.</li>
                    <li style="margin-bottom:6px;"><strong>PAYMENT IF LOST:</strong> If the book is lost, the borrower must <strong>pay the full replacement cost</strong> or replace it with an identical copy.</li>
                    <li style="margin-bottom:6px;"><strong>TIMELY RETURN:</strong> The book must be returned within three (3) working days or as set by the librarian. A late fine of <strong>₱5.00 per day</strong> applies after the due date.</li>
                    <li style="margin-bottom:6px;"><strong>EMAIL NOTIFICATION (auto from profile):</strong> The confirmation and overdue reminders will be sent automatically to the email address on the borrower's registered profile — no need to type it again.</li>
                    <li style="margin-bottom:6px;"><strong>LOSS OF PRIVILEGE:</strong> Repeated violations may result in suspension or permanent loss of borrowing privileges.</li>
                </ol>
                <p style="background:#fdf6e3;border-left:4px solid #c9a227;padding:10px 14px;font-size:12px;color:#8a6d1f;">You must tick the <strong>"I Agree"</strong> checkbox below before continuing.</p>
            </div>
            <div class="i-agree-row">
                <label><input type="checkbox" id="i-agree-check"> I Agree to the Privacy &amp; Terms above</label>
            </div>
            <div class="terms-actions">
                <button type="button" class="btn-cancel" onclick="closeTermsModal()">Cancel</button>
                <button type="button" class="btn-agree" onclick="agreeOutsideTerms()">I Agree &amp; Continue → Scan ID</button>
            </div>
        </div>
    </div>
    <div class="staff-content">
        <!-- ============ SCANNER (combined: attendance time in/out + book borrow) ============ -->
        <div id="tab-scan" class="staff-tab active">
            <div class="panel-card">
                <h2 class="panel-title">Unified Scanner — Time In/Out &amp; Book Borrow</h2>
                <div class="scan-area">
                    <input type="text" class="scan-input" id="att-scan-input" placeholder="Scan User ID (time in/out) OR Book barcode/QR (to borrow)..." autofocus>
                    <div id="att-status" class="status info">Waiting for scan... Scan a User ID for Time In/Out, or a Book barcode to borrow.</div>
                </div>
                <div id="book-detail-panel" style="display:none;"></div>
                <h2 class="panel-title" style="margin-top:26px;">Recent Borrow Transactions</h2>
                <button type="button" class="btn-cancel" style="background:#1b2a41;" onclick="loadBorrowHistory()">Refresh</button>
                <div class="table-wrap" id="borrow-history-table"></div>
            </div>
        </div>
        <!-- ============ DAILY RECORD ============ -->
        <div id="tab-daily" class="staff-tab">
            <div class="panel-card">
                <h2 class="panel-title">Daily Attendance Records</h2>
                <div class="filter-row">
                    <input type="date" id="daily-date" onchange="loadTodayRecords()">
                    <button type="button" class="btn-cancel" style="background:#1b2a41;margin:0;" onclick="loadTodayRecords()">Refresh</button>
                    <button type="button" class="btn-print" style="margin:0;" onclick="printDaily()">Print</button>
                    <button type="button" class="btn-download-barcode" style="margin:0;" onclick="downloadDaily()">Download Word</button>
                </div>
                <div class="table-wrap" id="today-records-table"></div>
            </div>
        </div>
        <!-- ============ BORROWED BOOKS RECORD (new headers, no Email column) ============ -->
        <div id="tab-borrowed" class="staff-tab">
            <div class="panel-card">
                <h2 class="panel-title">Borrow &amp; Return Records</h2>
                <div class="filter-row">
                    <label style="margin-bottom:0;font-size:13px;">Date:</label><input type="date" id="br-date" onchange="loadBorrowHistoryFull()">
                    <label style="margin-bottom:0;font-size:13px;">Borrower:</label><input type="text" id="br-borrower" placeholder="Name or ID" style="max-width:160px;" oninput="loadBorrowHistoryFull()">
                    <label style="margin-bottom:0;font-size:13px;">Status:</label>
                    <select id="br-status" onchange="loadBorrowHistoryFull()"><option value="">All</option><option value="Borrowed">Currently Borrowed</option><option value="Returned">Returned</option></select>
                    <button type="button" class="btn-cancel" style="background:#1b2a41;margin:0;" onclick="loadBorrowHistoryFull()">Refresh</button>
                    <button type="button" class="btn-print" style="margin:0;" onclick="window.open('/print-borrow-records','_blank')">Print</button>
                    <button type="button" class="btn-download-barcode" style="margin:0;" onclick="window.location.href='/download-borrow-word'">Download Word</button>
                </div>
                <div class="table-wrap" id="borrow-full-table"></div>
            </div>
        </div>
        <!-- ============ SEARCH BOOKS ============ -->
        <div id="tab-search" class="staff-tab">
            <div class="panel-card">
                <h2 class="panel-title">Search Books — Availability &amp; Current Borrowers</h2>
                <div class="search-row">
                    <input type="text" id="book-search-input" placeholder="Type book title, author, category, or code... e.g. Python" onkeypress="if(event.key==='Enter')doBookSearch()">
                    <button type="button" class="btn-primary" style="width:auto;margin:0;" onclick="doBookSearch()">Search</button>
                    <button type="button" class="btn-cancel" style="margin:0;" onclick="listAvailableBooks()">List All Available</button>
                </div>
                <p style="font-size:13px;color:#64748b;margin-bottom:14px;word-break:break-word;">When a book is borrowed, you can see here who borrowed it and when. Available copies are shown.</p>
                <div class="table-wrap" id="search-results-table"></div>
            </div>
        </div>
        <!-- ============ REGISTRATION ============ -->
        <div id="tab-register" class="staff-tab">
            <div class="container">
                <div class="card">
                    <div class="card-top"></div>
                    <div class="card-body">
                        <div class="reg-brand-mark">SLSU<br>JGE</div>
                        <h1 class="reg-title">User Registration</h1>
                        <p class="subtitle">Complete the form to generate an attendance barcode</p>
                        <form id="register-form">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>ID Type *</label>
                                    <select name="id_type" id="id-type-select" required>
                                        <option value="Student">Student</option>
                                        <option value="Employee">Employee</option>
                                        <option value="Visitor">Visitor</option>
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
                            <div id="student-fields">
                                <div class="form-row">
                                    <div class="form-group" id="student-department-group">
                                        <label>Department</label>
                                        <select name="department" id="dept-select">
                                            <option value="">-- Select Department --</option>
                                            <option value="CT">BSIT</option>
                                            <option value="BSED">BSED</option>
                                            <option value="BEED">BEED</option>
                                            <option value="BSFAS">BSFAS</option>
                                            <option value="BSBA">BSBA</option>
                                            <option value="BPA">BPA</option>
                                        </select>
                                    </div>
                                    <div class="form-group">
                                        <label>Major / Specialization</label>
                                        <select name="major" id="major-select">
                                            <option value="">-- Select Department First --</option>
                                        </select>
                                    </div>
                                </div>
                                <div class="form-row">
                                    <div class="form-group" id="student-year-group">
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
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Contact Number *</label>
                                    <input type="text" name="contact_number" required placeholder="09XX-XXX-XXXX">
                                </div>
                                <div class="form-group">
                                    <label>Address *</label>
                                    <input type="text" name="address" required placeholder="City, Province">
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Email (saved once — auto-used for outside-borrow notifications)</label>
                                <input type="email" name="email" placeholder="you@example.com">
                            </div>
                            <button type="submit" class="btn-primary">Register &amp; Generate Barcode</button>
                        </form>
                        <div id="barcode-result">
                            <h3>Registration Successful</h3>
                            <p id="barcode-id" class="barcode-id"></p>
                            <img id="barcode-img" class="barcode-img"><br>
                            <button type="button" class="btn-print" onclick="window.print()">Print Barcode</button>
                            <button type="button" class="btn-download-barcode" onclick="downloadUserBarcode()">Download Barcode</button>
                        </div>
                        <a href="/privacy" class="privacy-link" target="_blank">Privacy Policy</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
<script>
window.onerror=function(msg,src,line,col,err){var b=document.createElement('div');b.style.cssText='position:fixed;top:0;left:0;right:0;z-index:99999;background:#a52b2b;color:#fff;padding:12px 18px;font-family:Arial;font-size:13px;line-height:1.5;box-shadow:0 2px 10px rgba(0,0,0,.4);word-break:break-word;';b.innerHTML='<strong>JS ERROR (screenshot & send to dev):</strong><br>'+msg+' (line '+line+')';document.body.appendChild(b);return false;};
const MAJORS = {"BSBA":["Marketing Management","Financial Management"],"BSED":["English","Mathematics","Science"],"CT":["Computer Technology","Food Technology","BINDTECH","CULINARY"]};
const STAFF_TABS = ["scan","daily","borrowed","search","register"];
let scanState = "idle";          // idle | awaiting_borrower
let pendingBook = null;
let pendingBorrowerCode = null;  // scanned ID held while Outside terms are agreed
let scannerBuffer = "";
let scannerLastKeyAt = 0;
let scannerResetTimer = null;

function logout(){
    document.cookie = "logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    document.cookie = "role=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    window.location.href = "/login";
}
function showStaffTab(tab){
    document.querySelectorAll(".nav-tab").forEach(t=>t.classList.remove("active"));
    document.querySelectorAll(".staff-tab").forEach(t=>t.classList.remove("active"));
    document.getElementById("tab-"+tab).classList.add("active");
    const idx = STAFF_TABS.indexOf(tab);
    if(idx!==-1) document.querySelectorAll(".nav-tab")[idx].classList.add("active");
    if(tab==="scan"){setTimeout(()=>document.getElementById("att-scan-input")?.focus(),80);loadBorrowHistory();}
    if(tab==="daily"){loadTodayRecords();}
    if(tab==="borrowed"){loadBorrowHistoryFull();}
}
function showToast(msg, type){
    const toast = document.getElementById("toast");
    const el = document.createElement("div");
    el.className = "toast-item " + type;
    el.textContent = msg;
    const colors = {success:"#2f8a4e", error:"#c0392b", info:"#3a75a3", warning:"#c9a227"};
    el.style.borderLeftColor = colors[type] || "#3a75a3";
    el.style.background = type==="success"?"#e8f5ec":type==="error"?"#fbeaea":type==="warning"?"#fdf6e3":"#eaf1f8";
    el.style.color = type==="success"?"#1e6b34":type==="error"?"#8a1f1f":type==="warning"?"#8a6d1f":"#1b4f72";
    toast.appendChild(el);
    setTimeout(()=>{el.style.opacity="0";el.style.transition="opacity .4s";setTimeout(()=>el.remove(),400);},4500);
}
function setStatus(id, msg, type){
    const box = document.getElementById(id);
    if(!box) return;
    box.className = "status " + type;
    box.textContent = msg;
}
function resetBorrowFlow(){ scanState = "idle"; pendingBook = null; pendingBorrowerCode = null; }
function isOutsideChecked(){ return !!(document.getElementById("outside-borrow-check") && document.getElementById("outside-borrow-check").checked); }
function openTermsModal(){ document.getElementById("terms-modal").classList.remove("hidden"); }
function closeTermsModal(){
    document.getElementById("terms-modal").classList.add("hidden");
    const chk = document.getElementById("i-agree-check"); if(chk) chk.checked = false;
}
function agreeOutsideTerms(){
    const chk = document.getElementById("i-agree-check");
    if(!chk || !chk.checked){
        alert("Please tick the 'I Agree' checkbox first to accept the Privacy & Terms Agreement.");
        return;
    }
    closeTermsModal();
    // Outside agreed — record the borrow now (email auto-fetched from profile on the server)
    const code = pendingBorrowerCode;
    pendingBorrowerCode = null;
    if(!code){ setStatus("att-status","No borrower ID scanned.","error"); return; }
    fetch("/api/borrow-book",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({book_id: pendingBook.id, id_number: code, borrow_type: "Outside"})})
    .then(r=>r.json()).then(data=>{
        if(data.success){
            showToast(data.message, data.email_sent ? "success" : "warning");
            setStatus("att-status", data.message, data.email_sent ? "success" : "warning");
            resetBorrowFlow(); renderBookDetail(null); loadBorrowHistory();
        }else{
            showToast(data.message || "Borrow failed.", "error");
            setStatus("att-status", data.message || "Borrow failed.", "error");
        }
    }).catch(err=>{showToast("Error: "+err, "error");});
}
function handleScannedCode(code){
    code = (code||"").trim();
    if(!code) return;
    // ---- Borrow flow: a book is pending and this scan is the borrower ID ----
    if(scanState === "awaiting_borrower" && pendingBook){
        if(!isOutsideChecked()){
            // INSIDE READING — simple: record immediately
            fetch("/api/borrow-book",{method:"POST",headers:{"Content-Type":"application/json"},
                body:JSON.stringify({book_id: pendingBook.id, id_number: code, borrow_type: "Inside"})})
            .then(r=>r.json()).then(data=>{
                if(data.success){
                    showToast(data.message, "success");
                    setStatus("att-status", data.message, "success");
                    resetBorrowFlow(); renderBookDetail(null); loadBorrowHistory();
                }else{
                    showToast(data.message || "Borrow failed.", "error");
                    setStatus("att-status", data.message || "Borrow failed. Scan a valid User ID.", "error");
                }
            }).catch(err=>{showToast("Error: "+err, "error");});
            return;
        }
        // OUTSIDE — hold the ID, show Privacy & Terms Agreement with "I Agree" checkbox first
        pendingBorrowerCode = code;
        setStatus("att-status", "OUTSIDE borrow selected. Please read the Privacy & Terms Agreement and tick 'I Agree'.", "warning");
        openTermsModal();
        return;
    }
    // ---- Normal scan: detect book vs user attendance ----
    fetch("/api/smart-scan",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({code: code})})
    .then(r=>r.json()).then(data=>{
        if(!data.success){
            showToast(data.message || "Not found.", "error");
            setStatus("att-status", data.message || "Not found.", "error");
            return;
        }
        if(data.type === "attendance"){
            showToast(data.message, "success");
            setStatus("att-status", data.message, "success");
        }else if(data.type === "book"){
            pendingBook = data.book;
            scanState = "awaiting_borrower";
            renderBookDetail(data);
            setStatus("att-status", "Book found: " + data.book.title + ". Tick 'Outside Borrow' only if taking home, then scan the borrower's ID.", "info");
        }
    }).catch(err=>{showToast("Error: "+err, "error");});
}
function renderBookDetail(data){
    const panel = document.getElementById("book-detail-panel");
    if(!data){panel.style.display="none";panel.innerHTML="";return;}
    const b = data.book;
    const statusBadge = data.available_qty > 0
        ? '<span class="badge badge-avail">Available ('+data.available_qty+'/'+b.quantity+')</span>'
        : '<span class="badge badge-borrowed">Fully Borrowed (0/'+b.quantity+')</span>';
    let borrowersHtml = "";
    if(data.active_borrows && data.active_borrows.length){
        borrowersHtml = '<h3 style="color:#1b2a41;font-size:15px;margin:16px 0 6px;">Currently borrowed by (as of now):</h3>' +
            data.active_borrows.map(br=>'<div class="borrower-row"><span><strong>'+br.borrower_name+'</strong> ('+br.borrower_id+') — '+br.borrow_type+' — borrowed '+br.borrow_date+' '+br.borrow_time+'</span><button type="button" class="btn-return" onclick="confirmReturn('+br.borrow_id+')">Confirm Return</button></div>').join("");
    }
    const borrowTypeRow = data.available_qty > 0
        ? '<div class="borrow-type-row">' +
          '<label><input type="checkbox" id="outside-borrow-check"> Outside Borrow (take home)</label>' +
          '<span class="borrow-type-hint">Unchecked = Inside Reading (in-library only). If checked, the Privacy &amp; Terms Agreement will appear before recording.</span>' +
          '</div>' +
          '<div id="awaiting-box" style="display:block;" class="awaiting-box">Now scan the borrower&apos;s Student/Employee/Visitor ID barcode...</div>'
        : '<p style="color:#8a1f1f;font-weight:600;margin-top:10px;">No copies available — cannot borrow.</p>';
    panel.innerHTML = '<div class="book-detail">' +
        '<h3>'+b.title+' '+statusBadge+'</h3>' +
        '<div class="book-meta">' +
        '<div><strong>Author</strong>'+(b.author||'-')+'</div>' +
        '<div><strong>ISBN</strong>'+(b.isbn||'-')+'</div>' +
        '<div><strong>Category</strong>'+(b.category||'-')+'</div>' +
        '<div><strong>Shelf / Location</strong>'+(b.shelf_location||'-')+'</div>' +
        '<div><strong>Access Code</strong>'+b.access_code+'</div>' +
        '<div><strong>Times Borrowed</strong>'+(b.times_borrowed||0)+'</div>' +
        '</div>' +
        borrowTypeRow +
        '<div class="action-row" style="margin-top:10px;"><button type="button" class="btn-cancel" onclick="cancelBookFlow()">Clear</button></div>' +
        borrowersHtml + '</div>';
    panel.style.display = "block";
}
function cancelBookFlow(){
    resetBorrowFlow();
    renderBookDetail(null);
    setStatus("att-status", "Cancelled. Scan a User ID or Book barcode.", "info");
}
function confirmReturn(borrowId){
    if(!confirm("Confirm return of this book? This will record the return time and compute any late fine.")) return;
    fetch("/api/return-book",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({borrow_id: borrowId})})
    .then(r=>r.json()).then(data=>{
        if(data.success){
            showToast(data.message, "success");
            setStatus("att-status", data.message, "success");
            resetBorrowFlow(); renderBookDetail(null);
            loadBorrowHistory();
        }else{
            showToast(data.message||"Return failed.", "error");
        }
    }).catch(err=>showToast("Error: "+err,"error"));
}
function loadTodayRecords(){
    const d = document.getElementById("daily-date")?.value || "";
    const url = d ? ("/get-monthly-history?month="+d.slice(0,7)+"&date="+encodeURIComponent(d)) : "/get-records";
    fetch(url).then(r=>r.json()).then(d=>{
        const recs = d.records||[];
        const el = document.getElementById("today-records-table");
        if(!recs.length){el.innerHTML='<p style="text-align:center;color:#64748b;padding:24px;font-size:14px;">No attendance records for this date.</p>';return;}
        el.innerHTML='<table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>'+
            recs.map(r=>'<tr><td><strong>'+r.scan_date+'</strong></td><td>'+r.full_name+'</td><td>'+(r.department||"-")+'</td><td style="color:#1e6b34;font-weight:600;">'+(r.time_in||"-")+'</td><td style="color:#8a1f1f;font-weight:600;">'+(r.time_out||"-")+'</td></tr>').join("")+'</table>';
    }).catch(err=>console.error(err));
}
function printDaily(){
    const d = document.getElementById("daily-date")?.value || "";
    window.open("/print-daily"+(d?"?date="+encodeURIComponent(d):""),"_blank");
}
function downloadDaily(){ window.location.href = "/download-word"; }
function loadBorrowHistory(){
    fetch("/get-borrow-records").then(r=>r.json()).then(d=>{
        const recs = (d.records||[]).slice(0,15);
        const el = document.getElementById("borrow-history-table");
        if(!recs.length){el.innerHTML='<p style="text-align:center;color:#64748b;padding:24px;font-size:14px;">No borrow transactions yet.</p>';return;}
        el.innerHTML='<table><tr><th>Book Title / Book ID</th><th>Borrower Name &amp; ID</th><th>Borrow Type</th><th>Due Date</th><th>Date &amp; Time Borrowed</th><th>Date &amp; Time Returned</th><th>Current Status</th></tr>'+
            recs.map(r=>'<tr><td><strong>'+r.title+'</strong><br><span style="color:#64748b;font-size:11px;">'+r.access_code+'</span></td>'+
            '<td>'+r.borrower+'<br><span style="color:#64748b;font-size:11px;">'+r.borrower_id+'</span></td>'+
            '<td>'+(r.borrow_type==="Outside"?'<span class="badge badge-outside">Outside</span>':'<span class="badge badge-inside">Inside</span>')+'</td>'+
            '<td>'+r.due_date+'</td>'+
            '<td>'+r.borrow_date+' '+r.borrow_time+'</td>'+
            '<td>'+(r.return_date!=="-"?r.return_date+" "+r.return_time:"-")+'</td>'+
            '<td>'+(r.status==="Returned"?'<span class="badge badge-avail">Returned</span>':'<span class="badge badge-borrowed">Borrowed</span>')+(r.fine_amount>0?'<br><span style="color:#8a1f1f;font-size:11px;">Fine: ₱'+Number(r.fine_amount).toFixed(2)+'</span>':'')+'</td></tr>').join("")+'</table>';
    }).catch(err=>console.error(err));
}
function loadBorrowHistoryFull(){
    const date=document.getElementById("br-date")?.value||"";
    const borrower=document.getElementById("br-borrower")?.value||"";
    const status=document.getElementById("br-status")?.value||"";
    let q="/get-borrow-records?";if(date)q+="date="+encodeURIComponent(date)+"&";if(borrower)q+="borrower="+encodeURIComponent(borrower)+"&";if(status)q+="status="+encodeURIComponent(status)+"&";
    fetch(q).then(r=>r.json()).then(d=>{
        const recs=d.records||[];
        const el=document.getElementById("borrow-full-table");
        if(!recs.length){el.innerHTML='<p style="text-align:center;color:#64748b;padding:24px;font-size:14px;">No borrow records match.</p>';return;}
        el.innerHTML='<table><tr><th>Book Title / Book ID</th><th>Borrower Name &amp; ID</th><th>Borrow Type</th><th>Date &amp; Time Borrowed</th><th>Due Date</th><th>Date &amp; Time Returned</th><th>Overdue Fine (₱)</th><th>Current Status</th></tr>'+
            recs.map(r=>'<tr><td><strong>'+r.title+'</strong><br><span style="color:#64748b;font-size:11px;">'+r.access_code+'</span></td>'+
            '<td>'+r.borrower+'<br><span style="color:#64748b;font-size:11px;">'+r.borrower_id+'</span></td>'+
            '<td>'+(r.borrow_type==="Outside"?'<span class="badge badge-outside">Outside</span>':'<span class="badge badge-inside">Inside</span>')+'</td>'+
            '<td>'+r.borrow_date+' '+r.borrow_time+'</td>'+
            '<td>'+r.due_date+'</td>'+
            '<td>'+(r.return_date!=="-"?r.return_date+" "+r.return_time:"-")+'</td>'+
            '<td>'+(r.fine_amount>0?'<strong style="color:#8a1f1f;">₱'+Number(r.fine_amount).toFixed(2)+'</strong>':'-')+'</td>'+
            '<td>'+(r.status==="Returned"?'<span class="badge badge-avail">Returned</span>':'<span class="badge badge-borrowed">Borrowed</span>')+'</td></tr>').join("")+'</table>';
    }).catch(err=>console.error(err));
}
function doBookSearch(){
    const q = (document.getElementById("book-search-input")?.value||"").trim();
    if(!q){ listAvailableBooks(); return; }
    fetch("/api/search-books?q="+encodeURIComponent(q)).then(r=>r.json()).then(d=>{ renderSearchResults(d.books||[], "Search results for: '"+q+"'"); }).catch(err=>showToast("Error: "+err,"error"));
}
function listAvailableBooks(){
    fetch("/api/search-books?available=1").then(r=>r.json()).then(d=>{ renderSearchResults(d.books||[], "All Available Books"); }).catch(err=>showToast("Error: "+err,"error"));
}
function renderSearchResults(books, title){
    const el = document.getElementById("search-results-table");
    if(!books.length){el.innerHTML='<p style="text-align:center;color:#64748b;padding:24px;font-size:14px;">'+title+' — no books found.</p>';return;}
    let html = '<p style="font-size:13px;color:#1b2a41;font-weight:600;margin-bottom:8px;">'+title+' ('+books.length+' result(s))</p>';
    html += '<table><tr><th>Title</th><th>Author</th><th>Category</th><th>Shelf</th><th>Available</th><th>Currently Borrowed By (as of now)</th></tr>';
    books.forEach(b=>{
        let borrowers = '<span style="color:#1e6b34;">None — fully available</span>';
        if(b.current_borrowers && b.current_borrowers.length){
            borrowers = b.current_borrowers.map(br=>'<div class="borrower-list"><strong>'+br.borrower_name+'</strong> ('+br.borrower_id+') — '+br.borrow_type+' — since '+br.borrow_date+' '+br.borrow_time+'</div>').join("");
        }
        html += '<tr><td><strong>'+b.title+'</strong><br><span style="color:#64748b;font-size:11px;">'+b.access_code+'</span></td><td>'+b.author+'</td><td>'+b.category+'</td><td>'+b.shelf_location+'</td><td>'+(b.available_qty>0?'<span class="badge badge-avail">'+b.available_qty+'/'+b.quantity+' avail</span>':'<span class="badge badge-borrowed">0/'+b.quantity+'</span>')+'</td><td>'+borrowers+'</td></tr>';
    });
    html += '</table>';
    el.innerHTML = html;
}
function downloadUserBarcode(){
    const barcodeImage = document.getElementById("barcode-img");
    const idNumber = document.getElementById("barcode-id").textContent.replace("ID Number: ", "").trim();
    if(!barcodeImage.src || !idNumber){alert('Register first (Register & Generate Barcode) — then the barcode will be available to download.');return;}
    const link = document.createElement("a");
    link.href = barcodeImage.src;
    link.download = "barcode_" + idNumber + ".png";
    document.body.appendChild(link); link.click(); link.remove();
}
document.addEventListener("DOMContentLoaded", function(){
    const form = document.getElementById("register-form");
    const departmentSelect = document.getElementById("dept-select");
    const majorSelect = document.getElementById("major-select");
    const idTypeSelect = document.getElementById("id-type-select");
    const studentFields = document.getElementById("student-fields");
    function updateFieldsByIdType(){
        const isStudent = idTypeSelect.value === "Student";
        studentFields.style.display = isStudent ? "" : "none";
        studentFields.querySelectorAll("input, select").forEach(field=>{field.disabled = !isStudent;});
        const idInput = document.querySelector('#register-form input[name="id_number"]');
        if(idInput){
            const grp = idInput.closest('.form-group');
            if(grp){ grp.style.display = isStudent ? "" : "none"; }
            idInput.disabled = !isStudent;
        }
    }
    departmentSelect.addEventListener("change", function(){
        const department = departmentSelect.value;
        majorSelect.innerHTML = '<option value="">-- Select Major --</option>';
        (MAJORS[department]||[]).forEach(function(major){
            const option = document.createElement("option");
            option.value = major; option.textContent = major;
            majorSelect.appendChild(option);
        });
        majorSelect.disabled = (department === "BPA" || department === "");
    });
    majorSelect.disabled = true;
    idTypeSelect.addEventListener("change", updateFieldsByIdType);
    updateFieldsByIdType();
    form.addEventListener("submit", function(e){
        e.preventDefault();
        const formData = new FormData(form);
        fetch("/register",{method:"POST",body:formData})
        .then(res=>res.json()).then(data=>{
            if(data.success){
                document.getElementById("barcode-result").style.display="block";
                document.getElementById("barcode-id").textContent="ID Number: " + (data.id_number || formData.get("id_number"));
                document.getElementById("barcode-img").src="data:image/png;base64,"+data.barcode;
                form.reset();
                document.getElementById("dept-select").value="";
                majorSelect.innerHTML='<option value="">-- Select Department First --</option>';
                majorSelect.disabled = true;
                updateFieldsByIdType();
                showToast("Registration successful! Record saved.", "success");
            }else{ alert(data.error); }
        }).catch(err=>alert("Error: "+err));
    });
    document.getElementById("att-scan-input").addEventListener("keypress", e=>{
        if(e.key==="Enter"){handleScannedCode(e.target.value); e.target.value="";}
    });
    document.addEventListener("keydown", e=>{
        const target = e.target;
        const isEditable = target.matches("input, textarea, select");
        if(isEditable) return;
        const now = performance.now();
        if(now - scannerLastKeyAt > 120) scannerBuffer = "";
        scannerLastKeyAt = now;
        if(e.key === "Enter"){
            const scanned = scannerBuffer.trim();
            scannerBuffer = "";
            if(scanned){ e.preventDefault(); handleScannedCode(scanned); }
            return;
        }
        if(e.key.length === 1){
            scannerBuffer += e.key;
            clearTimeout(scannerResetTimer);
            scannerResetTimer = setTimeout(()=>{scannerBuffer="";}, 250);
        }
    });
    setInterval(()=>{
        if(document.getElementById("tab-scan").classList.contains("active")) loadBorrowHistory();
    }, 5000);
});
</script>
</body>
</html>
"""

# ============================================================
#  ADMIN FRONTEND — full access. Users list: ID Number | Full Name | Type |
#  Department | Major | Action (Email column removed, BPA tab added).
#  Borrow flow: small checkbox (Inside/Outside) + Privacy & Terms "I Agree" checkbox.
# ============================================================
ADMIN_FRONTEND = """
<!DOCTYPE html>
<html>
<head>
    <title>Library System — SLSU-JGE Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <link rel="apple-touch-icon" href="/static/app-icon.png">
    <meta name="theme-color" content="#006633">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#eef0f3;min-height:100vh;overflow-x:hidden;}
        .app-container{display:flex;min-height:100vh;position:relative;}
        .sidebar{width:270px;background:#1b2a41;display:flex;flex-direction:column;padding:0;position:relative;transition:width 0.25s ease;border-right:1px solid #10192b;flex:0 0 auto;}
        .sidebar.collapsed{width:74px;}
        .toggle-btn{position:absolute;right:-14px;top:26px;width:28px;height:28px;background:#1b2a41;border:1px solid #34455f;border-radius:50%;color:#e8c766;font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;z-index:10;transition:transform 0.2s;}
        .sidebar.collapsed .toggle-btn{transform:rotate(180deg);}
        .sidebar-header{padding:26px 22px 22px 22px;border-bottom:1px solid #2a3b56;}
        .sidebar.collapsed .sidebar-header{padding:26px 0;text-align:center;}
        .sidebar.collapsed .sidebar-header .full-title,.sidebar.collapsed .sidebar-header p{display:none;}
        .sidebar-header .brand-mark{width:40px;height:40px;background:#24344f;color:#e8c766;border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:11px;margin:0 auto 10px auto;}
        .sidebar-header h2{color:#f1f3f6;font-size:16px;font-weight:700;text-align:center;font-family:Georgia,'Times New Roman',serif;}
        .sidebar-header p{color:#8b9bb5;font-size:11px;margin-top:4px;text-align:center;letter-spacing:.3px;}
        .sidebar-menu{display:flex;flex-direction:column;gap:2px;padding:16px 12px;flex:1;overflow-y:auto;}
        .menu-item{display:flex;align-items:center;gap:14px;padding:12px 14px;color:#c3cede;border-radius:4px;cursor:pointer;transition:background 0.2s,color 0.2s;font-size:14px;font-weight:500;border-left:3px solid transparent;white-space:nowrap;}
        .sidebar.collapsed .menu-item{justify-content:center;padding:12px 0;}
        .sidebar.collapsed .menu-item span.label{display:none;}
        .menu-item:hover{background:#233450;color:#fff;}
        .menu-item.active{background:#24344f;color:#fff;border-left:3px solid #e8c766;}
        .menu-item .badge{width:26px;height:26px;flex:0 0 26px;background:#0f1c30;border:1px solid #34455f;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#e8c766;}
        .menu-item.active .badge{background:#1b2a41;border-color:#e8c766;}
        .sidebar-footer{padding:18px;border-top:1px solid #2a3b56;margin-top:auto;}
        .sidebar.collapsed .sidebar-footer{padding:18px 8px;}
        .logout-btn{width:100%;padding:12px;background:#7a1f1f;color:white;border:none;border-radius:4px;font-size:13px;font-weight:600;cursor:pointer;transition:background 0.2s;letter-spacing:.3px;}
        .logout-btn:hover{background:#5e1717;}
        .main-content{flex:1;padding:28px;overflow-x:hidden;min-width:0;}
        .content-header{margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #d8dbe0;display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
        .content-header h1{color:#1b2a41;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;word-break:break-word;}
        .hamburger{display:none;background:#1b2a41;color:#e8c766;border:1px solid #34455f;border-radius:4px;padding:8px 14px;font-size:16px;cursor:pointer;font-weight:600;}
        .sidebar-overlay{display:none;}
        .content-card{background:#ffffff;border-radius:6px;border:1px solid #d8dbe0;padding:32px;min-height:calc(100vh - 150px);}
        h2{color:#1b2a41;margin-bottom:22px;font-size:18px;font-weight:700;font-family:Georgia,'Times New Roman',serif;border-bottom:1px solid #eef0f3;padding-bottom:14px;word-break:break-word;}
        h3{font-family:Georgia,'Times New Roman',serif;color:#1b2a41;word-break:break-word;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:7px;color:#374151;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;}
        input,select{width:100%;padding:11px 14px;border:1px solid #d1d5db;border-radius:4px;font-size:14px;transition:border-color 0.2s,box-shadow 0.2s;background:#fafbfc;}
        input:focus,select:focus{outline:none;border-color:#1b2a41;background:white;box-shadow:0 0 0 3px rgba(27,42,65,0.1);}
        button{background:#1b2a41;color:white;border:none;padding:12px 26px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;transition:background 0.2s;margin:4px 4px 4px 0;letter-spacing:.2px;}
        button:hover{background:#10192b;}
        .scan-area{text-align:center;padding:36px;background:#f7f8fa;border-radius:6px;margin-bottom:20px;border:1px solid #d8dbe0;}
        #scan-input{font-size:20px;text-align:center;padding:16px;width:100%;max-width:460px;border-radius:4px;border:1px solid #b9c2cf;}
        .status{font-size:16px;font-weight:600;margin-top:18px;padding:16px;border-radius:4px;border-left:4px solid;word-break:break-word;}
        .success{background:#e8f5ec;color:#1e6b34;border-color:#2f8a4e;}
        .info{background:#eaf1f8;color:#1b4f72;border-color:#3a75a3;}
        .error{background:#fbeaea;color:#8a1f1f;border-color:#c0392b;}
        .warning{background:#fdf6e3;color:#8a6d1f;border-color:#c9a227;}
        .table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;}
        table{width:100%;border-collapse:collapse;margin-top:18px;min-width:620px;}
        th,td{padding:11px 12px;text-align:left;border:1px solid #e5e7eb;font-size:13px;vertical-align:top;word-break:break-word;}
        th{background:#1b2a41;color:#fff;font-weight:600;white-space:nowrap;}
        tr:nth-child(even){background:#f7f8fa;}
        tr:hover{background:#eef1f5;}
        .tab-content{display:none;}
        .tab-content.active{display:block;}
        .barcode-img{width:60mm;height:20mm;max-width:100%;margin:18px auto;display:block;padding:6px;background:white;border:0;object-fit:contain;image-rendering:crisp-edges;}
        .barcode-id{font-size:18px;font-weight:700;color:#1b2a41;margin:12px 0;word-break:break-word;}
        .book-qr-img{width:160px;height:160px;max-width:100%;object-fit:contain;image-rendering:crisp-edges;margin:10px auto;display:block;background:#fff;border:1px solid #d8dbe0;padding:6px;border-radius:4px;}
        .btn-print{background:#1e6b34;color:white;}
        .btn-print:hover{background:#175628;}
        .btn-barcode{background:#8a6d1f;color:white;padding:7px 16px;font-size:12px;border-radius:4px;}
        .btn-barcode:hover{background:#6e5718;}
        .student-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:18px 0 10px;}
        .student-actions button{margin:0;}
        .student-actions .btn-barcode,.student-actions .btn-download,.student-actions .btn-delete{width:150px;min-height:38px;padding:9px 12px;}
        .student-check{width:17px;height:17px;vertical-align:middle;}
        @media print{body *{visibility:hidden !important;}#barcode-result,#barcode-result *{visibility:visible !important;}#barcode-result{display:block !important;position:absolute;top:0;left:0;width:60mm;height:25mm;margin:0;padding:0;border:1px solid #000;background:#fff;}#barcode-result h3{display:none;}.barcode-img{width:60mm;height:18mm;object-fit:contain;padding:0;border:0;margin:4mm auto 0;}.barcode-id{font-size:8pt;margin:1mm 0 0;}.btn-print{display:none !important;}}
        .btn-download{background:#8a6d1f;color:white;}
        .btn-download:hover{background:#6e5718;}
        .btn-delete{background:#a52b2b;color:white;}
        .btn-delete:hover{background:#7f2020;}
        .btn-delete-daily{background:#8f2525;color:white;}
        .btn-delete-daily:hover{background:#6f1c1c;}
        .btn-edit{background:#3a4f75;color:white;padding:7px 16px;font-size:12px;border-radius:4px;}
        .btn-edit:hover{background:#2c3c59;}
        .btn-save{background:#1e6b34;color:white;}
        .btn-save:hover{background:#175628;}
        .btn-cancel{background:#5b6472;color:white;}
        .btn-cancel:hover{background:#464d59;}
        .btn-return{background:#1e6b34;color:white;padding:8px 16px;font-size:12px;border-radius:4px;}
        .btn-return:hover{background:#175628;}
        .btn-remind{background:#7a1f1f;color:white;padding:8px 16px;font-size:12px;border-radius:4px;}
        .btn-remind:hover{background:#5e1717;}
        .edit-modal{position:fixed;inset:0;background:rgba(15,25,43,.58);display:flex;align-items:center;justify-content:center;padding:20px;z-index:100;}
        .edit-modal.hidden{display:none;}
        .edit-dialog{background:#fff;width:100%;max-width:760px;max-height:90vh;overflow-y:auto;border-radius:6px;box-shadow:0 12px 40px rgba(15,25,43,.3);padding:28px;}
        .edit-dialog-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px;border-bottom:1px solid #eef0f3;padding-bottom:14px;}
        .edit-dialog-header h3{margin:0;}
        .edit-close{background:#5b6472;padding:7px 12px;margin:0;font-size:18px;line-height:1;}
        .edit-close:hover{background:#464d59;}
        .hidden{display:none !important;}
        .dept-tabs{display:flex;gap:8px;margin:18px 0;flex-wrap:wrap;}
        .dept-tab{padding:9px 16px;background:#f1f3f6;color:#374151;border:1px solid #d8dbe0;border-radius:4px;cursor:pointer;font-weight:600;transition:all 0.2s;font-size:13px;white-space:nowrap;}
        .dept-tab:hover{background:#e5e8ec;}
        .dept-tab.active{background:#1b2a41;color:white;border-color:#1b2a41;}
        .search-box{margin-bottom:18px;}
        .search-box input{font-size:14px;padding:11px 14px;}
        .month-filter,.filter-row{display:flex;gap:10px;align-items:center;margin-bottom:18px;flex-wrap:wrap;}
        .month-filter select,.filter-row select,.filter-row input{max-width:200px;}
        .btn-month-print{background:#5b3a75;color:white;}
        .btn-month-print:hover{background:#452b59;}
        .privacy-frame{width:100%;height:calc(100vh - 170px);min-height:700px;border:1px solid #d8dbe0;background:#eef0f3;}
        .badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;}
        .badge-avail{background:#e8f5ec;color:#1e6b34;}
        .badge-borrowed{background:#fbeaea;color:#8a1f1f;}
        .badge-inside{background:#eaf1f8;color:#1b4f72;}
        .badge-outside{background:#fdf6e3;color:#8a6d1f;}
        .badge-overdue{background:#fbeaea;color:#8a1f1f;border:1px solid #c0392b;}
        .book-detail{background:#f7f8fa;border:1px solid #d8dbe0;border-radius:6px;padding:22px;margin-top:18px;}
        .book-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px 18px;margin:12px 0 16px;font-size:13px;}
        .book-meta div strong{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#64748b;margin-bottom:2px;}
        .borrower-row{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#fff;border:1px solid #e5e7eb;border-radius:4px;margin-top:8px;font-size:13px;flex-wrap:wrap;gap:8px;word-break:break-word;}
        .awaiting-box{background:#fdf6e3;border:2px dashed #c9a227;border-radius:6px;padding:16px;text-align:center;margin-top:14px;font-weight:600;color:#8a6d1f;word-break:break-word;}
        /* small borrow-type checkbox (unchecked=Inside, checked=Outside) */
        .borrow-type-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:10px;padding:12px 14px;background:#fff;border:1px solid #d8dbe0;border-radius:6px;}
        .borrow-type-row label{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700;color:#374151;cursor:pointer;text-transform:none;letter-spacing:0;margin:0;}
        .borrow-type-row input[type=checkbox]{width:18px;height:18px;cursor:pointer;flex:0 0 auto;}
        .borrow-type-hint{font-size:12px;color:#64748b;}
        .qr-result{display:none;margin-top:24px;text-align:center;padding:24px;background:#f7f8fa;border-radius:6px;border:1px solid #d8dbe0;}
        .action-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;}
        .terms-modal{position:fixed;inset:0;background:rgba(15,25,43,.62);display:flex;align-items:center;justify-content:center;padding:16px;z-index:300;}
        .terms-modal.hidden{display:none;}
        .terms-dialog{background:#fff;width:100%;max-width:640px;max-height:88vh;overflow-y:auto;border-radius:6px;box-shadow:0 12px 40px rgba(15,25,43,.35);padding:26px;}
        .terms-dialog h3{color:#8a1f1f;font-family:Georgia,'Times New Roman',serif;margin-bottom:14px;font-size:18px;word-break:break-word;}
        .i-agree-row{display:flex;align-items:center;gap:10px;margin-top:16px;padding:12px 14px;background:#f7f8fa;border:1px solid #d8dbe0;border-radius:6px;}
        .i-agree-row label{display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;cursor:pointer;color:#1b2a41;text-transform:none;letter-spacing:0;margin:0;}
        .i-agree-row input[type=checkbox]{width:18px;height:18px;cursor:pointer;flex:0 0 auto;}
        .terms-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;justify-content:flex-end;}
        .btn-agree{background:#1e6b34;color:#fff;border:none;padding:12px 24px;border-radius:4px;font-size:14px;font-weight:700;cursor:pointer;}
        .btn-agree:hover{background:#175628;}
        .barcode-scan-box{background:#eaf1f8;border:2px solid #3a75a3;border-radius:6px;padding:18px;margin-bottom:22px;}
        .barcode-scan-box input{font-size:16px;text-align:center;}
        .new-barcode-box{background:#fdf6e3;border:2px dashed #c9a227;border-radius:6px;padding:18px;margin-bottom:22px;text-align:center;}
        .overdue-summary{background:#fbeaea;border-left:4px solid #c0392b;padding:14px 18px;border-radius:4px;margin-bottom:18px;font-size:14px;color:#8a1f1f;word-break:break-word;}
        @media(max-width:900px){
            .hamburger{display:inline-block;}
            .toggle-btn{display:none;}
            .sidebar{position:fixed;left:0;top:0;bottom:0;width:270px;z-index:200;transform:translateX(-105%);transition:transform .25s ease;box-shadow:4px 0 20px rgba(0,0,0,.3);height:100vh;}
            .sidebar.open{transform:translateX(0);}
            .sidebar.collapsed{width:270px;}
            .sidebar-header .full-title,.sidebar-header p,.menu-item span.label{display:block !important;}
            .menu-item{justify-content:flex-start !important;padding:12px 14px !important;}
            .sidebar-overlay.open{display:block;position:fixed;inset:0;background:rgba(10,15,25,.55);z-index:150;}
            .form-row{grid-template-columns:1fr;}
            .main-content{padding:14px 10px;}
            .content-card{padding:18px 14px;min-height:auto;}
            .content-header h1{font-size:19px;}
            .edit-dialog{padding:20px 14px;}
            .dept-tabs{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;padding-bottom:4px;}
            .dept-tab{flex:0 0 auto;}
            .scan-area{padding:24px 12px;}
            #scan-input{font-size:18px;padding:12px;}
            .student-actions .btn-barcode,.student-actions .btn-download,.student-actions .btn-delete{width:auto;flex:1 1 auto;min-width:120px;}
            .month-filter select,.filter-row select,.filter-row input{max-width:100%;flex:1 1 140px;}
            .privacy-frame{min-height:500px;height:70vh;}
            input,select,textarea{font-size:16px;}
            h2{font-size:16px;}
        }
        @media(max-width:480px){
            button{padding:10px 16px;font-size:13px;}
            .content-card{padding:14px 10px;}
            .book-meta{grid-template-columns:1fr 1fr;}
        }
    </style>
</head>
<body>

    <div class="app-container">
        <div class="sidebar-overlay" id="sidebar-overlay" onclick="toggleSidebar()"></div>
        <div class="sidebar" id="sidebar">
            <button type="button" class="toggle-btn" onclick="toggleSidebar()">◀</button>
            <div class="sidebar-header">
                <div class="brand-mark">SLSU<br>JGE</div>
                <h2 class="full-title">Library System</h2>
                <p>Full Administration</p>
            </div>
            <div class="sidebar-menu">
                <div class="menu-item active" onclick="showContent('scan')"><span class="badge">01</span> <span class="label">Scan / Attendance</span></div>
                <div class="menu-item" onclick="showContent('students')"><span class="badge">02</span> <span class="label">Users List</span></div>
                <div class="menu-item" onclick="showContent('records')"><span class="badge">03</span> <span class="label">Daily Records</span></div>
                <div class="menu-item" onclick="showContent('history')"><span class="badge">04</span> <span class="label">Monthly History</span></div>
                <div class="menu-item" onclick="showContent('books')"><span class="badge">05</span> <span class="label">Manage Books</span></div>
                <div class="menu-item" onclick="showContent('bookrecords')"><span class="badge">06</span> <span class="label">Book Records</span></div>
                <div class="menu-item" onclick="showContent('overdue')"><span class="badge">07</span> <span class="label">Overdue Reminders</span></div>
                <div class="menu-item" onclick="showContent('export')"><span class="badge">08</span> <span class="label">Export Reports</span></div>
                <div class="menu-item" onclick="showContent('privacy')"><span class="badge">09</span> <span class="label">Privacy Policy</span></div>
            </div>
            <div class="sidebar-footer"><button type="button" class="logout-btn" onclick="logout()">Log Out</button></div>
        </div>
        <div class="main-content">
            <div class="content-header">
                <button type="button" class="hamburger" onclick="toggleSidebar()">☰ Menu</button>
                <h1 id="page-title">Scan / Attendance</h1>
            </div>
            <div class="content-card">
                <!-- ===== OUTSIDE BORROW PRIVACY & TERMS AGREEMENT MODAL (with I Agree checkbox) ===== -->
                <div id="terms-modal" class="terms-modal hidden">
                    <div class="terms-dialog">
                        <h3>OUTSIDE BORROW — Privacy &amp; Terms Agreement</h3>
                        <div style="text-align:left;font-size:13px;line-height:1.7;color:#374151;">
                            <p style="margin-bottom:8px;">By choosing <strong>OUTSIDE</strong> (taking the book home), the borrower acknowledges and agrees to the following:</p>
                            <ol style="padding-left:20px;margin-bottom:10px;">
                                <li style="margin-bottom:6px;"><strong>LIABILITY FOR DAMAGE:</strong> The borrower is fully responsible for any damage, destruction, or alteration to the book while it is in their care. They must pay the cost of repair or replacement.</li>
                                <li style="margin-bottom:6px;"><strong>PAYMENT IF LOST:</strong> If the book is lost, the borrower must <strong>pay the full replacement cost</strong> or replace it with an identical copy.</li>
                                <li style="margin-bottom:6px;"><strong>TIMELY RETURN:</strong> The book must be returned within three (3) working days or as set by the librarian. A late fine of ₱5.00 per day applies after the due date.</li>
                                <li style="margin-bottom:6px;"><strong>EMAIL NOTIFICATION (auto from profile):</strong> The confirmation and overdue reminders will be sent automatically to the email address on the borrower's registered profile — no need to type it again.</li>
                                <li style="margin-bottom:6px;"><strong>LOSS OF PRIVILEGE:</strong> Repeated violations may result in suspension or permanent loss of borrowing privileges.</li>
                            </ol>
                            <p style="background:#fdf6e3;border-left:4px solid #c9a227;padding:10px 14px;font-size:12px;color:#8a6d1f;">You must tick the <strong>"I Agree"</strong> checkbox below before continuing.</p>
                        </div>
                        <div class="i-agree-row">
                            <label><input type="checkbox" id="i-agree-check"> I Agree to the Privacy &amp; Terms above</label>
                        </div>
                        <div class="terms-actions">
                            <button type="button" class="btn-cancel" onclick="closeTermsModal()">Cancel</button>
                            <button type="button" class="btn-agree" onclick="agreeOutsideTerms()">I Agree &amp; Continue → Record Borrow</button>
                        </div>
                    </div>
                </div>
                <!-- 01 SCAN / ATTENDANCE -->
                <div id="scan" class="tab-content active">
                    <h2>Scan — Book QR/Barcode or User ID</h2>
                    <div class="scan-area">
                        <input type="text" id="scan-input" placeholder="Scan Book QR/barcode or User ID barcode..." autofocus>
                        <div id="status-box" class="status info">Waiting for scan... Scan a Book (author &amp; title will appear), or a User ID for Time In/Out.</div>
                    </div>
                    <div id="admin-book-detail" style="display:none;"></div>
                </div>
                <!-- 02 USERS LIST — BPA tab added, Email column removed, columns: ID Number | Full Name | Type | Department | Major | Action -->
                <div id="students" class="tab-content">
                    <h2>Registered Users — Edit / Print / Delete / Download</h2>
                    <div class="search-box"><input type="text" id="search-input" placeholder="Search by Name or ID Number..." oninput="filterStudents()"></div>
                    <div class="dept-tabs">
                        <button type="button" class="dept-tab active" id="dept-ALL" onclick="switchDept('ALL')">ALL</button>
                        <button type="button" class="dept-tab" id="dept-CT" onclick="switchDept('CT')">CT</button>
                        <button type="button" class="dept-tab" id="dept-BSED" onclick="switchDept('BSED')">BSED</button>
                        <button type="button" class="dept-tab" id="dept-BEED" onclick="switchDept('BEED')">BEED</button>
                        <button type="button" class="dept-tab" id="dept-BSFAS" onclick="switchDept('BSFAS')">BSFAS</button>
                        <button type="button" class="dept-tab" id="dept-BSBA" onclick="switchDept('BSBA')">BSBA</button>
                        <button type="button" class="dept-tab" id="dept-BPA" onclick="switchDept('BPA')">BPA</button>
                        <button type="button" class="dept-tab" id="dept-EMPLOYEE" onclick="switchDept('EMPLOYEE')">EMPLOYEE</button>
                        <button type="button" class="dept-tab" id="dept-Visitor" onclick="switchDept('Visitor')">VISITOR</button>
                    </div>
                    <button type="button" onclick="loadStudents()">Refresh List</button>
                    <div class="student-actions">
                        <button type="button" class="btn-barcode" id="choose-barcode-btn" onclick="enableBarcodeSelection()">Select Users</button>
                        <div id="barcode-selection-actions" class="hidden">
                            <label style="text-transform:none;font-size:13px;margin:0;font-weight:600;"><input class="student-check" type="checkbox" id="select-all-students" onchange="toggleAllStudents(this.checked)"> Select All</label>
                            <button type="button" class="btn-barcode" onclick="printSelectedBarcodes()">Print Selected</button>
                            <button type="button" class="btn-download" onclick="downloadSelectedBarcodes()">Download Selected</button>
                            <button type="button" class="btn-delete" onclick="deleteSelectedStudents()">Delete Selected</button>
                            <button type="button" class="btn-cancel" onclick="disableBarcodeSelection()">Cancel</button>
                        </div>
                    </div>
                    <div class="table-wrap" id="students-table"></div>
                    <div id="edit-form-container" class="edit-modal hidden" onclick="if(event.target===this) hideEditForm()">
                        <div class="edit-dialog">
                            <div class="edit-dialog-header"><h3>Edit User Information</h3><button type="button" class="edit-close" onclick="hideEditForm()">&times;</button></div>
                            <form id="edit-form">
                                <input type="hidden" id="edit-id" name="id">
                                <div class="form-row">
                                    <div class="form-group"><label>ID Type</label><select id="edit-id-type" name="id_type" onchange="updateEditFieldsByIdType()"><option value="Student">Student</option><option value="Employee">Employee</option><option value="Visitor">Visitor</option></select></div>
                                    <div class="form-group"><label>ID Number</label><input type="text" id="edit-idnum" name="id_number" required></div>
                                </div>
                                <div class="form-group"><label>Full Name</label><input type="text" id="edit-fullname" name="full_name" required></div>
                                <div class="form-row" id="edit-student-extra">
                                    <div class="form-group"><label>Department</label><select id="edit-dept" name="department"><option value="">-- Select --</option><option value="CT">BSIT / Computer Technology</option><option value="BSED">BSED</option><option value="BEED">BEED</option><option value="BSFAS">BSFAS</option><option value="BSBA">BSBA</option><option value="BPA">BPA</option></select></div>
                                    <div class="form-group"><label>Major / Specialization</label><select id="edit-major" name="major"></select></div>
                                </div>
                                <div class="form-row">
                                    <div class="form-group" id="edit-year-group"><label>Year Level</label><select id="edit-year" name="year_level"><option value="1st Year">1st Year</option><option value="2nd Year">2nd Year</option><option value="3rd Year">3rd Year</option><option value="4th Year">4th Year</option><option value="N/A">N/A</option></select></div>
                                    <div class="form-group"><label>Contact Number</label><input type="text" id="edit-contact" name="contact_number"></div>
                                </div>
                                <div class="form-group"><label>Complete Address</label><input type="text" id="edit-address" name="address"></div>
                                <div class="form-group"><label>Email (for outside-borrow notifications — auto-used at borrow time)</label><input type="email" id="edit-email" name="email" placeholder="you@example.com"></div>
                                <button type="submit" class="btn-save">Save Changes</button>
                                <button type="button" class="btn-cancel" onclick="hideEditForm()">Cancel</button>
                            </form>
                        </div>
                    </div>
                </div>
                <!-- 03 DAILY RECORDS -->
                <div id="records" class="tab-content">
                    <h2>Today's Attendance Records</h2>
                    <button type="button" onclick="loadRecords()">Refresh Records</button>
                    <button type="button" class="btn-print" onclick="window.open('/print-daily','_blank')">Print</button>
                    <button type="button" class="btn-download" onclick="window.location.href='/download-word'">Download Word</button>
                    <div class="table-wrap" id="records-table"></div>
                </div>
                <!-- 04 MONTHLY HISTORY -->
                <div id="history" class="tab-content">
                    <h2>Attendance History</h2>
                    <div class="month-filter">
                        <label style="margin-bottom:0;">Month:</label>
                        <select id="month-select" onchange="loadMonthlyHistory()">
                            <option value="2026-01">January 2026</option><option value="2026-02">February 2026</option><option value="2026-03">March 2026</option><option value="2026-04">April 2026</option><option value="2026-05">May 2026</option><option value="2026-06">June 2026</option><option value="2026-07">July 2026</option><option value="2026-08">August 2026</option><option value="2026-09">September 2026</option><option value="2026-10" selected>October 2026</option><option value="2026-11">November 2026</option><option value="2026-12">December 2026</option><option value="2027-01">January 2027</option>
                        </select>
                        <label style="margin-bottom:0;">Specific day:</label><input type="date" id="history-date" onchange="loadMonthlyHistory()">
                        <button type="button" class="btn-month-print" onclick="printDailyReport()">Print Daily</button>
                        <button type="button" class="btn-month-print" onclick="printMonthlyReport()">Print Monthly</button>
                        <button type="button" class="btn-download" onclick="downloadMonthlyReport()">Download Word</button>
                        <select id="delete-history-date"><option value="">Select day to delete</option></select>
                        <button type="button" class="btn-delete-daily" onclick="deleteDailyHistory()">Delete Daily History</button>
                    </div>
                    <p style="font-size:13px;color:#64748b;margin:8px 0 18px;word-break:break-word;">Choose a month to view monthly records, or choose a specific date.</p>
                    <button type="button" onclick="loadMonthlyHistory()">Load Records</button>
                    <div class="table-wrap" id="history-table"></div>
                </div>
                <!-- 05 MANAGE BOOKS — with barcode scanner + generate new barcode -->
                <div id="books" class="tab-content">
                    <h2>Register New Book</h2>
                    <div class="barcode-scan-box">
                        <label style="font-size:13px;">Scan existing printed barcode (optional — leave blank and a barcode is auto-generated on register):</label>
                        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">
                            <input type="text" id="book-barcode-scan" placeholder="Scan or type the printed barcode number here..." style="flex:1 1 260px;max-width:none;" onkeypress="if(event.key==='Enter')scanBookBarcode()">
                            <button type="button" class="btn-barcode" style="margin:0;" onclick="scanBookBarcode()">Scan / Lookup</button>
                        </div>
                        <div id="barcode-scan-status" style="font-size:13px;margin-top:10px;word-break:break-word;"></div>
                    </div>
                    <form id="book-form">
                        <div class="form-row">
                            <div class="form-group"><label>Barcode Number (leave blank — auto-generated)</label><input type="text" name="barcode_number" id="book-barcode-number" placeholder="Auto-generated if blank"></div>
                            <div class="form-group"><label>Quantity</label><input type="number" name="quantity" value="1" min="1"></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>Title *</label><input type="text" name="title" id="book-title-input" required placeholder="Book title"></div>
                            <div class="form-group"><label>Author</label><input type="text" name="author" placeholder="Author name"></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>ISBN</label><input type="text" name="isbn" placeholder="ISBN (optional)"></div>
                            <div class="form-group"><label>Category</label><input type="text" name="category" placeholder="e.g. Fiction, Science, Math, Python"></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>Shelf / Location *</label><input type="text" name="shelf_location" placeholder="e.g. Shelf A-3" required></div>
                        </div>
                        <button type="submit" class="btn-save">Register Book &amp; Generate Barcode</button>
                    </form>
                    <div id="book-qr-result" class="qr-result">
                        <h3>Book Registered — Barcode Generated</h3>
                        <p id="book-qr-title" style="font-weight:600;color:#1b2a41;margin-top:8px;word-break:break-word;"></p>
                        <p id="book-qr-code" style="font-size:13px;color:#64748b;"></p>
                        <img id="book-barcode-img" class="barcode-img" style="height:20mm;width:60mm;">
                        <div class="action-row" style="justify-content:center;">
                            <button type="button" class="btn-print" onclick="window.print()">Print Barcode</button>
                            <button type="button" class="btn-barcode" onclick="downloadBookBarcode()">Download Barcode</button>
                        </div>
                    </div>
                    <h2 style="margin-top:32px;">All Books</h2>
                    <div class="search-box"><input type="text" id="book-search" placeholder="Search by title, author, ISBN, or code..." oninput="filterBooks()"></div>
                    <div class="filter-row">
                        <label style="margin-bottom:0;font-size:13px;">Status:</label>
                        <select id="book-status-filter" onchange="filterBooks()"><option value="">All</option><option value="Available">Available</option><option value="Borrowed">Fully Borrowed</option></select>
                        <label style="margin-bottom:0;font-size:13px;">Sort:</label>
                        <select id="book-sort" onchange="filterBooks()"><option value="title">Title A-Z</option><option value="most_borrowed">Most Borrowed</option><option value="recent">Recently Added</option></select>
                        <button type="button" onclick="loadBooks()">Refresh</button>
                        <button type="button" class="btn-barcode" id="choose-book-qr-btn" onclick="enableBookQRSelection()">Select Books</button>
                        <div id="book-qr-actions" class="hidden">
                            <label style="text-transform:none;font-size:13px;margin:0;font-weight:600;"><input class="student-check" type="checkbox" id="select-all-books" onchange="toggleAllBooks(this.checked)"> Select All</label>
                            <button type="button" class="btn-barcode" onclick="printSelectedBookBarcodes()">Print Selected</button>
                            <button type="button" class="btn-download" onclick="downloadSelectedBookBarcodes()">Download Selected</button>
                            <button type="button" class="btn-delete" onclick="deleteSelectedBooks()">Delete Selected</button>
                            <button type="button" class="btn-cancel" onclick="disableBookQRSelection()">Cancel</button>
                        </div>
                    </div>
                    <div class="table-wrap" id="books-table"></div>
                    <div id="book-edit-modal" class="edit-modal hidden" onclick="if(event.target===this) hideBookEdit()">
                        <div class="edit-dialog">
                            <div class="edit-dialog-header"><h3>Edit Book</h3><button type="button" class="edit-close" onclick="hideBookEdit()">&times;</button></div>
                            <form id="book-edit-form">
                                <input type="hidden" id="book-edit-id" name="id">
                                <div class="form-row"><div class="form-group"><label>Title *</label><input type="text" id="book-edit-title" name="title" required></div><div class="form-group"><label>Author</label><input type="text" id="book-edit-author" name="author"></div></div>
                                <div class="form-row"><div class="form-group"><label>ISBN</label><input type="text" id="book-edit-isbn" name="isbn"></div><div class="form-group"><label>Category</label><input type="text" id="book-edit-category" name="category"></div></div>
                                <div class="form-row"><div class="form-group"><label>Shelf / Location</label><input type="text" id="book-edit-shelf" name="shelf_location"></div><div class="form-group"><label>Quantity</label><input type="number" id="book-edit-qty" name="quantity" min="1"></div></div>
                                <div class="form-row"><div class="form-group"><label>Barcode Number</label><input type="text" id="book-edit-barcode" name="barcode_number"></div></div>
                                <button type="submit" class="btn-save">Save Changes</button>
                                <button type="button" class="btn-cancel" onclick="hideBookEdit()">Cancel</button>
                            </form>
                        </div>
                    </div>
                </div>
                <!-- 06 BOOK RECORDS (new headers, no Email column) -->
                <div id="bookrecords" class="tab-content">
                    <h2>Borrow &amp; Return Records — Edit / Print / Download</h2>
                    <div class="filter-row">
                        <label style="margin-bottom:0;font-size:13px;">Date:</label><input type="date" id="br-date" onchange="loadBorrowRecords()">
                        <label style="margin-bottom:0;font-size:13px;">Borrower:</label><input type="text" id="br-borrower" placeholder="Name or ID" style="max-width:180px;" oninput="loadBorrowRecords()">
                        <label style="margin-bottom:0;font-size:13px;">Status:</label>
                        <select id="br-status" onchange="loadBorrowRecords()"><option value="">All</option><option value="Borrowed">Currently Borrowed</option><option value="Returned">Returned</option></select>
                        <button type="button" onclick="loadBorrowRecords()">Refresh</button>
                        <button type="button" class="btn-print" onclick="window.open('/print-borrow-records','_blank')">Print</button>
                        <button type="button" class="btn-download" onclick="window.location.href='/download-borrow-word'">Download Word</button>
                    </div>
                    <div class="table-wrap" id="borrow-records-table"></div>
                </div>
                <!-- 07 OVERDUE REMINDERS -->
                <div id="overdue" class="tab-content">
                    <h2>Overdue Books — Send Return Reminders via Gmail</h2>
                    <div class="overdue-summary" id="overdue-summary">Loading overdue list...</div>
                    <button type="button" class="btn-remind" style="padding:12px 22px;font-size:14px;" onclick="sendAllOverdueReminders()">Send Reminder Email to ALL Overdue Borrowers</button>
                    <button type="button" class="btn-cancel" onclick="loadOverdue()">Refresh</button>
                    <div class="table-wrap" id="overdue-table"></div>
                </div>
                <!-- 08 EXPORT -->
                <div id="export" class="tab-content">
                    <h2>Export &amp; Print Reports</h2>
                    <p style="font-size:15px;color:#64748b;margin-bottom:22px;word-break:break-word;">Download reports as Microsoft Word documents or print directly.</p>
                    <button type="button" class="btn-download" onclick="window.location.href='/download-word'">Download Today's Attendance (Word)</button><br><br>
                    <button type="button" class="btn-download" onclick="window.location.href='/download-borrow-word'">Download Book Borrow Records (Word)</button><br><br>
                    <button type="button" class="btn-print" onclick="window.open('/print-borrow-records','_blank')">Print Borrow Records</button>
                    <button type="button" class="btn-print" onclick="window.print()">Print Page</button>
                </div>
                <!-- 09 PRIVACY -->
                <div id="privacy" class="tab-content">
                    <iframe class="privacy-frame" src="/privacy" title="Privacy Policy"></iframe>
                </div>
            </div>
        </div>
    </div>
<script>
window.onerror=function(msg,src,line,col,err){var b=document.createElement('div');b.style.cssText='position:fixed;top:0;left:0;right:0;z-index:99999;background:#a52b2b;color:#fff;padding:12px 18px;font-family:Arial;font-size:13px;line-height:1.5;box-shadow:0 2px 10px rgba(0,0,0,.4);word-break:break-word;';b.innerHTML='<strong>JS ERROR (screenshot & send to dev):</strong><br>'+msg+' (line '+line+')';document.body.appendChild(b);return false;};
const MAJORS = {"BSBA":["Marketing Management","Financial Management"],"BSED":["English","Mathematics","Science"],"CT":["Computer Technology","Food Technology","BINDTECH","CULINARY"]};
const PAGE_TITLES = {scan:"Scan / Attendance",students:"Registered Users — Full Access",records:"Daily Attendance Records",history:"Monthly Attendance History",books:"Manage Books — Barcode Scan & Generate",bookrecords:"Book Borrow Records",overdue:"Overdue Books — Email Reminders",export:"Export & Print Reports",privacy:"Privacy Policy"};
const MENU_ORDER = ["scan","students","records","history","books","bookrecords","overdue","export","privacy"];
let editingStudentId=null, currentDept="ALL", allStudents=[], barcodeSelectionMode=false;
let scannerBuffer="", scannerLastKeyAt=0, scannerResetTimer=null, recordsRefreshInProgress=false;
let scanState="idle", pendingBook=null, pendingBorrowerCode=null;
let allBooks=[], bookQRSelectionMode=false, lastBookBarcode=null;

function toggleSidebar(){
    const s=document.getElementById("sidebar");
    const ov=document.getElementById("sidebar-overlay");
    if(window.innerWidth<=900){
        s.classList.toggle("open");
        if(ov) ov.classList.toggle("open");
    } else {
        s.classList.toggle("collapsed");
        const tb=s.querySelector(".toggle-btn");
        if(tb) tb.textContent=s.classList.contains("collapsed")?"▶":"◀";
    }
}
function closeMobileSidebar(){
    if(window.innerWidth<=900){
        document.getElementById("sidebar").classList.remove("open");
        const ov=document.getElementById("sidebar-overlay");
        if(ov) ov.classList.remove("open");
    }
}
function logout(){document.cookie="logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";document.cookie="role=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";window.location.href="/login";}
function showContent(pageId){
    document.querySelectorAll(".menu-item").forEach(i=>i.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t=>t.classList.remove("active"));
    const idx=MENU_ORDER.indexOf(pageId);
    if(idx!==-1) document.querySelectorAll(".menu-item")[idx].classList.add("active");
    const t=document.getElementById(pageId); if(t) t.classList.add("active");
    document.getElementById("page-title").textContent=PAGE_TITLES[pageId]||"Library System";
    closeMobileSidebar();
    if(pageId==="scan") setTimeout(()=>document.getElementById("scan-input")?.focus(),100);
    if(pageId==="students") loadStudents();
    if(pageId==="records") loadRecords();
    if(pageId==="history") loadMonthlyHistory();
    if(pageId==="books") loadBooks();
    if(pageId==="bookrecords") loadBorrowRecords();
    if(pageId==="overdue") loadOverdue();
}
function setStatus(msg,type){const b=document.getElementById("status-box");if(b){b.className="status "+type;b.textContent=msg;}}
function submitScan(){const i=document.getElementById("scan-input");const v=i.value.trim();if(v){handleScannedCode(v);i.value="";}}
function resetBorrowFlow(){scanState="idle";pendingBook=null;pendingBorrowerCode=null;}
function isOutsideChecked(){ return !!(document.getElementById("outside-borrow-check") && document.getElementById("outside-borrow-check").checked); }
function openTermsModal(){document.getElementById("terms-modal").classList.remove("hidden");}
function closeTermsModal(){
    document.getElementById("terms-modal").classList.add("hidden");
    const chk=document.getElementById("i-agree-check"); if(chk) chk.checked=false;
}
function agreeOutsideTerms(){
    const chk=document.getElementById("i-agree-check");
    if(!chk || !chk.checked){
        alert("Please tick the 'I Agree' checkbox first to accept the Privacy & Terms Agreement.");
        return;
    }
    closeTermsModal();
    const code=pendingBorrowerCode;
    pendingBorrowerCode=null;
    if(!code){ setStatus("No borrower ID scanned.","error"); return; }
    fetch("/api/borrow-book",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({book_id:pendingBook.id,id_number:code,borrow_type:"Outside"})})
    .then(r=>r.json()).then(d=>{
        if(d.success){
            setStatus(d.message, d.email_sent?"success":"warning");
            resetBorrowFlow();
            document.getElementById("admin-book-detail").style.display="none";
        }else setStatus(d.message||"Borrow failed.","error");
    }).catch(e=>setStatus("Error: "+e,"error"));
}
function handleScannedCode(code){
    code=(code||"").trim(); if(!code) return;
    if(scanState==="awaiting_borrower" && pendingBook){
        if(!isOutsideChecked()){
            // INSIDE READING — record immediately, no extra steps
            fetch("/api/borrow-book",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({book_id:pendingBook.id,id_number:code,borrow_type:"Inside"})})
            .then(r=>r.json()).then(d=>{
                if(d.success){setStatus(d.message,"success");resetBorrowFlow();renderAdminBookDetail(null);}
                else{setStatus(d.message||"Borrow failed.","error");}
            }).catch(e=>setStatus("Error: "+e,"error"));
            return;
        }
        // OUTSIDE — hold the ID, show Privacy & Terms Agreement with "I Agree" checkbox first
        pendingBorrowerCode=code;
        setStatus("OUTSIDE borrow selected. Please read the Privacy & Terms Agreement and tick 'I Agree'.","warning");
        openTermsModal();
        return;
    }
    fetch("/api/smart-scan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code:code})})
    .then(r=>r.json()).then(d=>{
        if(!d.success){setStatus(d.message||"Not found.","error");return;}
        if(d.type==="attendance"){setStatus(d.message,"success");}
        else if(d.type==="book"){
            showContent("scan");
            pendingBook=d.book;
            scanState="awaiting_borrower";
            renderAdminBookDetail(d);
            setStatus("Book found: "+d.book.title+". Tick 'Outside Borrow' only if taking home, then scan the borrower's ID.","info");
        }
    }).catch(e=>setStatus("Error: "+e,"error"));
}
function renderAdminBookDetail(data){
    const panel=document.getElementById("admin-book-detail");
    if(!data){panel.style.display="none";panel.innerHTML="";return;}
    const b=data.book;
    const badge=data.available_qty>0?'<span class="badge badge-avail">Available ('+data.available_qty+'/'+b.quantity+')</span>':'<span class="badge badge-borrowed">Fully Borrowed (0/'+b.quantity+')</span>';
    let borrowers="";
    if(data.active_borrows&&data.active_borrows.length){
        borrowers='<h3 style="font-size:15px;margin:16px 0 6px;color:#1b2a41;">Currently borrowed by:</h3>'+
            data.active_borrows.map(br=>'<div class="borrower-row"><span><strong>'+br.borrower_name+'</strong> ('+br.borrower_id+') — '+br.borrow_type+' — '+br.borrow_date+' '+br.borrow_time+'</span><button type="button" class="btn-return" onclick="confirmReturn('+br.borrow_id+')">Confirm Return</button></div>').join("");
    }
    const borrowTypeRow = data.available_qty>0
        ? '<div class="borrow-type-row">'+
          '<label><input type="checkbox" id="outside-borrow-check"> Outside Borrow (take home)</label>'+
          '<span class="borrow-type-hint">Unchecked = Inside Reading (in-library only). If checked, the Privacy &amp; Terms Agreement will appear before recording.</span>'+
          '</div>'+
          '<div id="admin-awaiting" style="display:block;" class="awaiting-box">Now scan the borrower&apos;s Student/Employee/Visitor ID barcode...</div>'
        : '<p style="color:#8a1f1f;font-weight:600;margin-top:10px;">No copies available — cannot borrow.</p>';
    panel.innerHTML='<div class="book-detail"><h3>'+b.title+' '+badge+'</h3>'+
        '<div class="book-meta">'+
        '<div><strong>Author</strong>'+(b.author||'-')+'</div><div><strong>ISBN</strong>'+(b.isbn||'-')+'</div><div><strong>Category</strong>'+(b.category||'-')+'</div><div><strong>Shelf</strong>'+(b.shelf_location||'-')+'</div><div><strong>Code</strong>'+b.access_code+'</div><div><strong>Times Borrowed</strong>'+(b.times_borrowed||0)+'</div></div>'+
        borrowTypeRow +
        '<div class="action-row" style="margin-top:10px;"><button type="button" class="btn-cancel" onclick="cancelAdminBookFlow()">Clear</button></div>'+borrowers+'</div>';
    panel.style.display="block";
}
function cancelAdminBookFlow(){resetBorrowFlow();renderAdminBookDetail(null);setStatus("Cancelled. Scan a Book QR/barcode or User ID.","info");}
function confirmReturn(borrowId){
    if(!confirm("Confirm return of this book? Return time and any late fine will be recorded.")) return;
    fetch("/api/return-book",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({borrow_id:borrowId})})
    .then(r=>r.json()).then(d=>{
        if(d.success){setStatus(d.message,"success");resetBorrowFlow();renderAdminBookDetail(null);}
        else setStatus(d.message||"Return failed.","error");
    }).catch(e=>setStatus("Error: "+e,"error"));
}
// ===== Book registration: scan existing barcode =====
function scanBookBarcode(){
    const code=(document.getElementById("book-barcode-scan")?.value||"").trim();
    if(!code){alert("Scan or type a barcode number first.");return;}
    fetch("/api/scan-book-barcode",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code:code})})
    .then(r=>r.json()).then(d=>{
        const st=document.getElementById("barcode-scan-status");
        if(!d.success){st.innerHTML='<span style="color:#8a1f1f;">'+(d.error||"Error")+'</span>';return;}
        if(d.exists){
            st.innerHTML='<span style="color:#1e6b34;">Book already registered: <strong>'+d.book.title+'</strong> ('+d.book.access_code+'). Edit it in the list below.</span>';
        }else{
            document.getElementById("book-barcode-number").value=d.barcode_number;
            document.getElementById("book-title-input").focus();
            st.innerHTML='<span style="color:#1b4f72;">Barcode <strong>'+d.barcode_number+'</strong> is new. Fill in the book details below (Title, Author, Shelf, Category) then click Register.</span><br><img src="data:image/png;base64,'+d.barcode_img+'" style="max-width:240px;margin-top:8px;border:1px solid #d8dbe0;background:#fff;padding:4px;">';
        }
    }).catch(e=>alert("Error: "+e));
}
// ===== Users list =====
function switchDept(d){document.querySelectorAll(".dept-tab").forEach(t=>t.classList.remove("active"));document.getElementById("dept-"+d).classList.add("active");currentDept=d;filterStudents();}
function updateMajorOptions(ds,ms){const dept=document.getElementById(ds).value;const m=document.getElementById(ms);m.innerHTML='<option value="">-- Select Major --</option>';if(dept==="BPA"||!dept){m.disabled=true;return;}m.disabled=false;(MAJORS[dept]||[]).forEach(x=>{const o=document.createElement("option");o.value=x;o.textContent=x;m.appendChild(o);});}
function loadStudents(){fetch("/get-students").then(r=>r.json()).then(d=>{allStudents=d.students||[];filterStudents();}).catch(e=>alert("Load Error: "+e));}
function userDepartment(x){
    if(x.id_type==="Student") return x.department_display || x.department || "-";
    if(x.id_type==="Employee") return "EMPLOYEE";
    return "-";
}
function userMajor(x){
    if(x.id_type==="Student") return x.major || "-";
    return "-";
}
function filterStudents(){
    const s=(document.getElementById("search-input")?.value||"").toLowerCase();
    let f=allStudents;
    if(s) f=f.filter(x=>x.full_name.toLowerCase().includes(s)||x.id_number.toLowerCase().includes(s));
    const t=document.getElementById("students-table");
    const selCol = barcodeSelectionMode ? '<th>Select</th>' : '';
    const selCell = (x) => barcodeSelectionMode ? '<td><input class="student-check student-row-check" type="checkbox" value="'+x.id_number+'"></td>' : '';
    // Unified columns: ID Number | Full Name | Type | Department | Major | Action  (Email removed)
    const head = '<tr>'+selCol+'<th>ID Number</th><th>Full Name</th><th>Type</th><th>Department</th><th>Major</th><th>Action</th></tr>';
    const row = (x) => '<tr>'+selCell(x)+
        '<td><strong>'+x.id_number+'</strong></td>'+
        '<td>'+x.full_name+'</td>'+
        '<td>'+x.id_type+'</td>'+
        '<td>'+userDepartment(x)+'</td>'+
        '<td>'+userMajor(x)+'</td>'+
        '<td><button type="button" class="btn-edit" onclick="editStudent('+x.id+')">Edit</button></td></tr>';
    let html='';
    if(currentDept==="ALL"){
        const students = f.filter(x=>x.id_type==="Student");
        const employees = f.filter(x=>x.id_type==="Employee"||x.department==="EMPLOYEE");
        const visitors = f.filter(x=>x.id_type==="Visitor");
        if(students.length) html += '<h3 style="margin-top:8px;color:#1b2a41;font-size:16px;">Students ('+students.length+')</h3><div class="table-wrap"><table style="min-width:620px;">'+head+students.map(row).join("")+'</table></div>';
        if(employees.length) html += '<h3 style="margin-top:28px;color:#1b2a41;font-size:16px;">Employees ('+employees.length+')</h3><div class="table-wrap"><table style="min-width:560px;">'+head+employees.map(row).join("")+'</table></div>';
        if(visitors.length) html += '<h3 style="margin-top:28px;color:#1b2a41;font-size:16px;">Visitors ('+visitors.length+')</h3><div class="table-wrap"><table style="min-width:560px;">'+head+visitors.map(row).join("")+'</table></div>';
        if(!html) html='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No records found.</p>';
    } else if(currentDept==="EMPLOYEE"||currentDept==="Visitor"){
        const list = (currentDept==="EMPLOYEE") ? f.filter(x=>x.id_type==="Employee"||x.department==="EMPLOYEE") : f.filter(x=>x.id_type==="Visitor");
        if(list.length) html='<div class="table-wrap"><table style="min-width:560px;">'+head+list.map(row).join("")+'</table></div>';
        else html='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No records found.</p>';
    } else {
        // department filter (CT, BSED, BEED, BSFAS, BSBA, BPA) — matches on department field
        const students = f.filter(x=>x.department===currentDept);
        if(students.length) html='<div class="table-wrap"><table style="min-width:620px;">'+head+students.map(row).join("")+'</table></div>';
        else html='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No records found for '+currentDept+'.</p>';
    }
    t.innerHTML=html;
}
function enableBarcodeSelection(){barcodeSelectionMode=true;document.getElementById("choose-barcode-btn").classList.add("hidden");document.getElementById("barcode-selection-actions").classList.remove("hidden");document.getElementById("select-all-students").checked=false;filterStudents();}
function disableBarcodeSelection(){barcodeSelectionMode=false;document.getElementById("choose-barcode-btn").classList.remove("hidden");document.getElementById("barcode-selection-actions").classList.add("hidden");filterStudents();}
function toggleAllStudents(c){document.querySelectorAll(".student-row-check").forEach(x=>x.checked=c);}
function printSelectedBarcodes(){
    const sel=Array.from(document.querySelectorAll(".student-row-check:checked")).map(x=>x.value);
    if(!sel.length){alert("Please select at least one user.");return;}
    const w=window.open("","_blank","width=600,height=800");if(!w){alert("Allow pop-ups.");return;}
    const m=sel.map(id=>'<section class="bi"><div class="lbl">Student Number: '+id+'</div><img src="/barcode/'+encodeURIComponent(id)+'"></section>').join("");
    w.document.write('<!DOCTYPE html><html><head><style>*{box-sizing:border-box}@page{size:Letter portrait;margin:0.5in}body{font-family:Arial,sans-serif;margin:0;display:grid;grid-template-columns:2.2in;grid-auto-rows:1.0in;gap:0.15in;justify-content:center;align-content:center;min-height:100vh;padding:0}.bi{width:2.2in;height:1.0in;border:1px solid #000;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:0.08in;background:#fff}.bi .lbl{font-family:Arial,sans-serif;font-size:11pt;color:#000;width:1.0in;text-align:left;word-break:break-word}.bi img{width:1.1in;height:0.85in;object-fit:contain;image-rendering:crisp-edges;display:block}</style></head><body>'+m+'</body></html>');
    w.document.close();const imgs=w.document.images;let n=0;const pw=()=>{n++;if(n===imgs.length)w.print();};Array.from(imgs).forEach(i=>{i.onload=pw;i.onerror=pw;});
}
function downloadSelectedBarcodes(){
    const sel=Array.from(document.querySelectorAll(".student-row-check:checked")).map(x=>x.value);
    if(!sel.length){alert("Please select at least one user.");return;}
    fetch("/download-barcodes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id_numbers:sel})})
    .then(r=>{if(!r.ok)throw new Error("Download failed.");return r.blob();}).then(b=>{const l=document.createElement("a");const u=URL.createObjectURL(b);l.href=u;l.download="user_barcodes.pdf";document.body.appendChild(l);l.click();l.remove();URL.revokeObjectURL(u);}).catch(e=>alert(e.message));
}
function deleteSelectedStudents(){
    const sel=Array.from(document.querySelectorAll(".student-row-check:checked")).map(x=>x.value);
    if(!sel.length){alert("Please select at least one user.");return;}
    if(!confirm("Delete "+sel.length+" selected user(s)? Their attendance and borrow records will also be deleted.")) return;
    fetch("/delete-students",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id_numbers:sel})})
    .then(r=>r.json().then(d=>({ok:r.ok,d}))).then(res=>{if(!res.ok)throw new Error(res.d.error||"Delete failed.");alert(res.d.deleted_count+" user(s) deleted.");disableBarcodeSelection();loadStudents();}).catch(e=>alert(e.message));
}
function editStudent(id){const s=allStudents.find(x=>x.id===id);if(!s)return;editingStudentId=id;document.getElementById("edit-id").value=s.id;document.getElementById("edit-id-type").value=s.id_type;document.getElementById("edit-idnum").value=s.id_number;document.getElementById("edit-fullname").value=s.full_name;document.getElementById("edit-dept").value=s.department||"";document.getElementById("edit-major").value=s.major||"";document.getElementById("edit-year").value=s.year_level||"";document.getElementById("edit-contact").value=s.contact_number||"";document.getElementById("edit-address").value=s.address||"";document.getElementById("edit-email").value=s.email||"";document.getElementById("edit-form-container").classList.remove("hidden");updateEditFieldsByIdType();}
function updateEditFieldsByIdType(){const is=document.getElementById("edit-id-type").value==="Student";const ex=document.getElementById("edit-student-extra");if(ex)ex.style.display=is?"":"none";const yg=document.getElementById("edit-year-group");if(yg)yg.style.display=is?"":"none";const idi=document.getElementById("edit-idnum");if(idi)idi.disabled=!is;["edit-dept","edit-major","edit-year"].forEach(id=>{const f=document.getElementById(id);if(f)f.disabled=!is;});}
function hideEditForm(){document.getElementById("edit-form-container").classList.add("hidden");editingStudentId=null;document.getElementById("edit-form").reset();}
function loadRecords(){if(recordsRefreshInProgress)return;recordsRefreshInProgress=true;fetch("/get-records").then(r=>r.json()).then(d=>{const recs=d.records||[];const t=document.getElementById("records-table");if(recs.length){t.innerHTML='<table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>'+recs.map(r=>'<tr><td><strong>'+r.scan_date+'</strong></td><td>'+r.full_name+'</td><td>'+(r.department||"-")+'</td><td style="color:#1e6b34;font-weight:600;">'+(r.time_in||"-")+'</td><td style="color:#8a1f1f;font-weight:600;">'+(r.time_out||"-")+'</td></tr>').join("")+'</table>';}else t.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No attendance records yet.</p>';}).catch(e=>console.error(e)).finally(()=>recordsRefreshInProgress=false);}
function loadMonthlyHistory(){
    const ms=document.getElementById("month-select"), di=document.getElementById("history-date");
    const sd=di.value, month=sd?sd.slice(0,7):ms.value; if(sd)ms.value=month;
    const dq=sd?"&date="+encodeURIComponent(sd):"";
    fetch("/get-monthly-history?month="+month+dq).then(r=>r.json()).then(d=>{
        const recs=d.records||[];const dd=document.getElementById("delete-history-date");
        const dates=[...new Set(recs.map(r=>r.scan_date))];
        dd.innerHTML='<option value="">Select day to delete</option>'+dates.map(x=>'<option value="'+x+'">'+x+'</option>').join("");
        const t=document.getElementById("history-table");
        if(recs.length){const g=recs.reduce((a,r)=>{(a[r.scan_date]||=[]).push(r);return a;},{});
            t.innerHTML=Object.entries(g).map(([date,rs])=>'<section><h3 style="margin-top:24px;color:#1b2a41;">Records for '+date+'</h3><table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>'+rs.map(r=>'<tr><td><strong>'+r.scan_date+'</strong></td><td>'+r.full_name+'</td><td>'+(r.department||"-")+'</td><td style="color:#1e6b34;font-weight:600;">'+(r.time_in||"-")+'</td><td style="color:#8a1f1f;font-weight:600;">'+(r.time_out||"-")+'</td></tr>').join("")+'</table></section>').join("");}
        else t.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No records for '+(sd||month)+'.</p>';
    }).catch(e=>alert("Load Error: "+e));
}
function printDailyReport(){const d=document.getElementById("history-date").value||new Date().toISOString().slice(0,10);window.open("/print-daily?date="+encodeURIComponent(d),"_blank");}
function printMonthlyReport(){window.open("/print-monthly?month="+encodeURIComponent(document.getElementById("month-select").value),"_blank");}
function downloadMonthlyReport(){window.location.href="/download-monthly-word?month="+document.getElementById("month-select").value;}
function deleteDailyHistory(){
    const d=document.getElementById("delete-history-date").value;if(!d){alert("Select a day first.");return;}
    if(!confirm("Delete all attendance for "+d+"?")) return;
    fetch("/delete-daily-history",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({date:d})})
    .then(r=>r.json().then(x=>({ok:r.ok,x}))).then(res=>{if(!res.ok)throw new Error(res.x.error||"Failed.");alert(res.x.deleted_count+" record(s) deleted.");loadMonthlyHistory();}).catch(e=>alert(e.message));
}
function loadBooks(){fetch("/get-books").then(r=>r.json()).then(d=>{allBooks=d.books||[];filterBooks();}).catch(e=>alert("Load Error: "+e));}
function filterBooks(){
    const s=(document.getElementById("book-search")?.value||"").toLowerCase();
    const st=document.getElementById("book-status-filter")?.value||"";
    const sort=document.getElementById("book-sort")?.value||"title";
    let f=allBooks.slice();
    if(s) f=f.filter(b=>b.title.toLowerCase().includes(s)||(b.author||"").toLowerCase().includes(s)||(b.isbn||"").toLowerCase().includes(s)||b.access_code.toLowerCase().includes(s)||(b.barcode_number||"").toLowerCase().includes(s));
    if(st==="Available") f=f.filter(b=>b.available_qty>0);
    if(st==="Borrowed") f=f.filter(b=>b.available_qty<=0);
    if(sort==="most_borrowed") f.sort((a,b)=>b.times_borrowed-a.times_borrowed);
    else if(sort==="recent") f.sort((a,b)=>b.id-a.id);
    else f.sort((a,b)=>a.title.localeCompare(b.title));
    const t=document.getElementById("books-table");
    if(f.length){t.innerHTML='<table><tr>'+(bookQRSelectionMode?'<th>Sel</th>':'')+'<th>Code</th><th>Title</th><th>Author</th><th>Category</th><th>Shelf</th><th>Qty</th><th>Status</th><th>Borrowed</th><th>Action</th></tr>'+
        f.map(b=>'<tr>'+(bookQRSelectionMode?'<td><input class="student-check book-row-check" type="checkbox" value="'+b.id+'"></td>':'')+
        '<td><strong>'+b.access_code+'</strong>'+(b.barcode_number?'<br><span style="color:#64748b;font-size:10px;">bc:'+b.barcode_number+'</span>':'')+'</td><td>'+b.title+'</td><td>'+(b.author||"-")+'</td><td>'+(b.category||"-")+'</td><td>'+(b.shelf_location||"-")+'</td><td>'+b.available_qty+'/'+b.quantity+'</td>'+
        '<td>'+(b.available_qty>0?'<span class="badge badge-avail">Available</span>':'<span class="badge badge-borrowed">Borrowed</span>')+'</td>'+
        '<td>'+b.times_borrowed+'</td>'+
        '<td><button type="button" class="btn-edit" onclick="editBook('+b.id+')">Edit</button></td></tr>').join("")+'</table>';}
    else t.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No books found.</p>';
}
function enableBookQRSelection(){bookQRSelectionMode=true;document.getElementById("choose-book-qr-btn").classList.add("hidden");document.getElementById("book-qr-actions").classList.remove("hidden");document.getElementById("select-all-books").checked=false;filterBooks();}
function disableBookQRSelection(){bookQRSelectionMode=false;document.getElementById("choose-book-qr-btn").classList.remove("hidden");document.getElementById("book-qr-actions").classList.add("hidden");filterBooks();}
function toggleAllBooks(c){document.querySelectorAll(".book-row-check").forEach(x=>x.checked=c);}
function printSelectedBookBarcodes(){
    const sel=Array.from(document.querySelectorAll(".book-row-check:checked")).map(x=>parseInt(x.value));
    if(!sel.length){alert("Please select at least one book.");return;}
    // fetch book details to get title+code for labels
    const books = allBooks.filter(b=>sel.includes(b.id));
    const w=window.open("","_blank","width=600,height=800");if(!w){alert("Allow pop-ups.");return;}
    const cells=books.map(b=>{const code=(b.barcode_number||"").trim()||b.access_code;const t=(b.title||"").length>26?(b.title||"").slice(0,23)+"...":(b.title||"");return '<section class="bi"><div class="ttl">'+t+'</div><div class="cd">'+code+'</div><img src="/book-barcode/'+encodeURIComponent(code)+'"></section>';}).join("");
    w.document.write('<!DOCTYPE html><html><head><style>*{box-sizing:border-box}@page{size:A4;margin:1mm}body{font-family:Arial;text-align:center;display:grid;grid-template-columns:repeat(4,48mm);grid-auto-rows:32mm;gap:2mm;justify-content:center}.bi{width:48mm;height:32mm;border:1px solid #000;font-size:7pt;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding:1mm 0;overflow:hidden}.bi .ttl{font-weight:700;max-width:46mm;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bi .cd{color:#555;margin-bottom:1mm}.bi img{width:44mm;height:16mm;object-fit:contain;image-rendering:crisp-edges;margin:auto;display:block}</style></head><body>'+cells+'</body></html>');
    w.document.close();const imgs=w.document.images;let n=0;const pw=()=>{n++;if(n===imgs.length)w.print();};Array.from(imgs).forEach(i=>{i.onload=pw;i.onerror=pw;});
}
function downloadSelectedBookBarcodes(){
    const sel=Array.from(document.querySelectorAll(".book-row-check:checked")).map(x=>parseInt(x.value));
    if(!sel.length){alert("Please select at least one book.");return;}
    fetch("/download-book-barcodes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({book_ids:sel})})
    .then(r=>{if(!r.ok)throw new Error("Download failed.");return r.blob();}).then(b=>{const l=document.createElement("a");const u=URL.createObjectURL(b);l.href=u;l.download="book_barcodes.pdf";document.body.appendChild(l);l.click();l.remove();URL.revokeObjectURL(u);}).catch(e=>alert(e.message));
}
function deleteSelectedBooks(){
    const sel=Array.from(document.querySelectorAll(".book-row-check:checked")).map(x=>parseInt(x.value));
    if(!sel.length){alert("Select at least one book.");return;}
    if(!confirm("Delete "+sel.length+" selected book(s) and their borrow history?")) return;
    fetch("/delete-book",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({book_ids:sel})})
    .then(r=>r.json().then(d=>({ok:r.ok,d}))).then(res=>{if(!res.ok)throw new Error(res.d.error||"Delete failed.");alert(res.d.deleted_count+" book(s) deleted.");disableBookQRSelection();loadBooks();}).catch(e=>alert(e.message));
}
function editBook(id){const b=allBooks.find(x=>x.id===id);if(!b)return;document.getElementById("book-edit-id").value=b.id;document.getElementById("book-edit-title").value=b.title;document.getElementById("book-edit-author").value=b.author||"";document.getElementById("book-edit-isbn").value=b.isbn||"";document.getElementById("book-edit-category").value=b.category||"";document.getElementById("book-edit-shelf").value=b.shelf_location||"";document.getElementById("book-edit-qty").value=b.quantity;document.getElementById("book-edit-barcode").value=b.barcode_number||"";document.getElementById("book-edit-modal").classList.remove("hidden");}
function hideBookEdit(){document.getElementById("book-edit-modal").classList.add("hidden");document.getElementById("book-edit-form").reset();}
function downloadBookBarcode(){if(!lastBookBarcode){alert('Register a book first — then its barcode will be available to download.');return;}window.location.href="/book-barcode/"+encodeURIComponent(lastBookBarcode);}
function loadBorrowRecords(){
    const date=document.getElementById("br-date")?.value||"";
    const borrower=document.getElementById("br-borrower")?.value||"";
    const status=document.getElementById("br-status")?.value||"";
    let q="/get-borrow-records?";if(date)q+="date="+encodeURIComponent(date)+"&";if(borrower)q+="borrower="+encodeURIComponent(borrower)+"&";if(status)q+="status="+encodeURIComponent(status)+"&";
    fetch(q).then(r=>r.json()).then(d=>{
        const recs=d.records||[];const t=document.getElementById("borrow-records-table");
        if(recs.length){t.innerHTML='<table><tr><th>Book Title / Book ID</th><th>Borrower Name &amp; ID</th><th>Borrow Type</th><th>Date &amp; Time Borrowed</th><th>Due Date</th><th>Date &amp; Time Returned</th><th>Overdue Fine (₱)</th><th>Current Status</th></tr>'+
            recs.map(r=>'<tr><td><strong>'+r.title+'</strong><br><span style="color:#64748b;font-size:11px;">'+r.access_code+'</span></td>'+
            '<td>'+r.borrower+'<br><span style="color:#64748b;font-size:11px;">'+r.borrower_id+'</span></td>'+
            '<td>'+(r.borrow_type==="Outside"?'<span class="badge badge-outside">Outside</span>':'<span class="badge badge-inside">Inside</span>')+'</td>'+
            '<td>'+r.borrow_date+' '+r.borrow_time+'</td>'+
            '<td>'+r.due_date+'</td>'+
            '<td>'+(r.return_date!=="-"?r.return_date+" "+r.return_time:"-")+'</td>'+
            '<td>'+(r.fine_amount>0?'<strong style="color:#8a1f1f;">₱'+Number(r.fine_amount).toFixed(2)+'</strong>':'-')+'</td>'+
            '<td>'+(r.status==="Returned"?'<span class="badge badge-avail">Returned</span>':'<span class="badge badge-borrowed">Borrowed</span>')+'</td></tr>').join("")+'</table>';}
        else t.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No borrow records match the filters.</p>';
    }).catch(e=>alert("Load Error: "+e));
}
// ===== Overdue reminders =====
function loadOverdue(){
    fetch("/api/overdue-list").then(r=>r.json()).then(d=>{
        const recs=d.records||[];
        const sum=document.getElementById("overdue-summary");
        if(!recs.length){sum.innerHTML='<strong style="color:#1e6b34;">No overdue books.</strong> All borrowers have returned their books or are still within the due date.';document.getElementById("overdue-table").innerHTML="";return;}
        const totalFine=recs.reduce((a,r)=>a+Number(r.fine_amount||0),0);
        sum.innerHTML='<strong>'+recs.length+' overdue book(s)</strong> — total fines: <strong>₱'+totalFine.toFixed(2)+'</strong>. Click "Send Reminder" to email the borrower to return the book.';
        const t=document.getElementById("overdue-table");
        t.innerHTML='<table><tr><th>Book</th><th>Borrower</th><th>Email</th><th>Borrowed</th><th>Due Date</th><th>Days Late</th><th>Fine</th><th>Reminder</th><th>Action</th></tr>'+
            recs.map(r=>'<tr><td><strong>'+r.title+'</strong><br><span style="color:#64748b;font-size:11px;">'+r.access_code+'</span></td><td>'+r.borrower+'<br><span style="color:#64748b;font-size:11px;">'+r.borrower_id+'</span></td><td>'+r.email+'</td><td>'+r.borrow_date+' '+r.borrow_time+'</td><td><strong style="color:#8a1f1f;">'+r.due_date+'</strong></td><td><span class="badge badge-overdue">'+r.days_late+' day(s)</span></td><td><strong style="color:#8a1f1f;">₱'+Number(r.fine_amount).toFixed(2)+'</strong></td><td>'+(r.reminder_sent?'<span style="color:#1e6b34;font-size:12px;">Sent ✓</span>':'<span style="color:#8a6d1f;font-size:12px;">Not sent</span>')+'</td><td><button type="button" class="btn-remind" onclick="sendOneOverdueReminder('+r.id+')">Send Reminder Email</button></td></tr>').join("")+'</table>';
    }).catch(e=>alert("Load Error: "+e));
}
function sendOneOverdueReminder(borrowId){
    if(!confirm("Send overdue reminder email to this borrower? The email will include the fine amount.")) return;
    fetch("/api/send-overdue-reminder",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({borrow_id:borrowId})})
    .then(r=>r.json()).then(d=>{
        if(d.success){alert("Reminder sent. Fine: ₱"+Number(d.fine_amount).toFixed(2)+" ("+d.days_late+" day(s) late).");loadOverdue();}
        else alert("Failed: "+(d.message||d.error||"unknown"));
    }).catch(e=>alert("Error: "+e));
}
function sendAllOverdueReminders(){
    if(!confirm("Send overdue reminder emails to ALL borrowers with overdue books? This may take a few seconds.")) return;
    fetch("/api/send-all-overdue-reminders",{method:"POST",headers:{"Content-Type":"application/json"}})
    .then(r=>r.json()).then(d=>{
        alert(d.message||("Sent: "+d.sent+", Failed: "+d.failed));
        loadOverdue();
    }).catch(e=>alert("Error: "+e));
}
document.addEventListener("DOMContentLoaded",function(){
    setInterval(()=>{if(document.getElementById("records")?.classList.contains("active"))loadRecords();},2000);
    const si=document.getElementById("scan-input");
    if(si) si.addEventListener("keypress",e=>{if(e.key==="Enter")submitScan();});
    document.addEventListener("keydown",e=>{
        const t=e.target;
        if(t.matches("input,textarea,select")) return;
        const now=performance.now();
        if(now-scannerLastKeyAt>120) scannerBuffer="";
        scannerLastKeyAt=now;
        if(e.key==="Enter"){const sc=scannerBuffer.trim();scannerBuffer="";if(sc){e.preventDefault();handleScannedCode(sc);}return;}
        if(e.key.length===1){scannerBuffer+=e.key;clearTimeout(scannerResetTimer);scannerResetTimer=setTimeout(()=>{scannerBuffer="";},250);}
    });
    const eds=document.getElementById("edit-dept");if(eds)eds.addEventListener("change",()=>updateMajorOptions("edit-dept","edit-major"));
    const ef=document.getElementById("edit-form");
    if(ef)ef.addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(ef);fetch("/update-student",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{if(d.success){alert("Updated.");hideEditForm();loadStudents();}else alert("Error: "+d.error);}).catch(err=>alert("Error: "+err));});
    const bf=document.getElementById("book-form");
    if(bf)bf.addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(bf);fetch("/register-book",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{
        if(d.success){
            const res=document.getElementById("book-qr-result");res.style.display="block";
            document.getElementById("book-qr-title").textContent=d.title;
            document.getElementById("book-qr-code").textContent="Access Code: "+d.access_code;
            if(d.barcode){document.getElementById("book-barcode-img").src="data:image/png;base64,"+d.barcode;document.getElementById("book-barcode-img").style.display="block";}
            lastBookBarcode=d.access_code;
            bf.reset();document.querySelector('#book-form input[name="quantity"]').value=1;
            document.getElementById("barcode-scan-status").innerHTML="";
            loadBooks();
        }else alert("Error: "+d.error);}).catch(err=>alert("Error: "+err));});
    const bef=document.getElementById("book-edit-form");
    if(bef)bef.addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(bef);fetch("/update-book",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{if(d.success){alert("Book updated.");hideBookEdit();loadBooks();}else alert("Error: "+d.error);}).catch(err=>alert("Error: "+err));});
});
</script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
