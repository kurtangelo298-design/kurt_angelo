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

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER = "library"
ADMIN_PASS = "slsu"
USER_USER = "slsu"
USER_PASS = "library"
STUDENT_USER = "student"
STUDENT_PASS = "student"
SCANNER_API_KEY = os.environ.get("SCANNER_API_KEY", "").strip()


def get_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"DB Connect Error: {e}")
        return None


def get_ph_time():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return now.strftime("%I:%M %p")


def get_ph_date():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")


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
    conn.commit()
    conn.close()
    print("DATABASE READY")


init_db()


def generate_barcode_b64(id_number):
    code128 = barcode.get_barcode_class("code128")
    writer = ImageWriter()
    writer.set_options({
        "module_width": 0.33,
        "module_height": 12.0,
        "font_size": 8,
        "text_distance": 1.5,
        "quiet_zone": 1.5,
        "center_text": True,
        "dpi": 300,
    })
    img = code128(id_number, writer=writer).render()
    target_size = (round(50 / 25.4 * 300), round(12 / 25.4 * 300))
    img.thumbnail(target_size, Image.Resampling.NEAREST)
    canvas = Image.new("RGB", target_size, "white")
    left = (target_size[0] - img.width) // 2
    top = (target_size[1] - img.height) // 2
    canvas.paste(img, (left, top))
    buffered = BytesIO()
    canvas.save(buffered, format="PNG", dpi=(300, 300), optimize=True)
    return base64.b64encode(buffered.getvalue()).decode()


def generate_qr_b64(data):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def book_status_info(book_id, quantity):
    """Return (active_borrow_count, available_qty, status_label)."""
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


@app.route('/book-qr/<path:access_code>')
def book_qr_image(access_code):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        image_data = base64.b64decode(generate_qr_b64(access_code))
        response = make_response(image_data)
        response.headers['Content-Type'] = 'image/png'
        response.headers['Content-Disposition'] = f'attachment; filename="book_qr_{access_code}.png"'
        response.headers['Cache-Control'] = 'no-store'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/download-barcodes', methods=['POST'])
def download_barcodes():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True, force=True) or {}
        id_numbers = payload.get('id_numbers', [])
        id_numbers = list(dict.fromkeys(str(value).strip() for value in id_numbers if str(value).strip()))
        if not id_numbers:
            return jsonify({"error": "Please select at least one student."}), 400
        page_size = (round(210 / 25.4 * 300), round(297 / 25.4 * 300))
        columns = 4
        rows = 11
        box_width = round(50 / 25.4 * 300)
        box_height = round(25 / 25.4 * 300)
        gap = round(2 / 25.4 * 300)
        grid_width = columns * box_width + (columns - 1) * gap
        grid_height = rows * box_height + (rows - 1) * gap
        grid_left = (page_size[0] - grid_width) // 2
        grid_top = (page_size[1] - grid_height) // 2
        barcode_size = (round(50 / 25.4 * 300), round(12 / 25.4 * 300))
        pages = []
        for page_start in range(0, len(id_numbers), columns * rows):
            page = Image.new('RGB', page_size, 'white')
            draw = ImageDraw.Draw(page)
            page_ids = id_numbers[page_start:page_start + columns * rows]
            for index, id_number in enumerate(page_ids):
                column = index % columns
                row = index // columns
                cell_left = grid_left + column * (box_width + gap)
                cell_top = grid_top + row * (box_height + gap)
                barcode_image = Image.open(BytesIO(base64.b64decode(generate_barcode_b64(id_number))))
                barcode_image = barcode_image.resize(barcode_size, Image.Resampling.NEAREST)
                barcode_left = cell_left + (box_width - barcode_image.width) // 2
                barcode_top = cell_top + round(8 / 25.4 * 300)
                page.paste(barcode_image, (barcode_left, barcode_top))
                label = f"ID Number: {id_number}"
                label_box = draw.textbbox((0, 0), label)
                label_width = label_box[2] - label_box[0]
                draw.text(
                    (cell_left + (box_width - label_width) // 2, cell_top + round(2 / 25.4 * 300)),
                    label,
                    fill='black'
                )
            for column in range(columns):
                for row in range(rows):
                    cell_left = grid_left + column * (box_width + gap)
                    cell_top = grid_top + row * (box_height + gap)
                    draw.rectangle(
                        (cell_left, cell_top, cell_left + box_width, cell_top + box_height),
                        outline='black',
                        width=3,
                    )
            pages.append(page)
        output = BytesIO()
        pages[0].save(output, format='PDF', resolution=300.0, save_all=True, append_images=pages[1:])
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename="student_barcodes.pdf"'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/download-book-qrcodes', methods=['POST'])
def download_book_qrcodes():
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
        c.execute("SELECT id, access_code, title FROM books WHERE id = ANY(%s) ORDER BY id", (book_ids,))
        books = c.fetchall()
        conn.close()
        page_size = (round(210 / 25.4 * 300), round(297 / 25.4 * 300))
        columns = 3
        rows = 6
        box_width = round(60 / 25.4 * 300)
        box_height = round(42 / 25.4 * 300)
        gap = round(4 / 25.4 * 300)
        grid_width = columns * box_width + (columns - 1) * gap
        grid_height = rows * box_height + (rows - 1) * gap
        grid_left = (page_size[0] - grid_width) // 2
        grid_top = (page_size[1] - grid_height) // 2
        qr_size = (round(35 / 25.4 * 300), round(35 / 25.4 * 300))
        pages = []
        for page_start in range(0, len(books), columns * rows):
            page = Image.new('RGB', page_size, 'white')
            draw = ImageDraw.Draw(page)
            page_books = books[page_start:page_start + columns * rows]
            for index, (bid, access_code, title) in enumerate(page_books):
                column = index % columns
                row = index // columns
                cell_left = grid_left + column * (box_width + gap)
                cell_top = grid_top + row * (box_height + gap)
                qr_img = Image.open(BytesIO(base64.b64decode(generate_qr_b64(access_code))))
                qr_img = qr_img.resize(qr_size, Image.Resampling.NEAREST)
                qr_left = cell_left + (box_width - qr_img.width) // 2
                qr_top = cell_top + round(2 / 25.4 * 300)
                page.paste(qr_img, (qr_left, qr_top))
                label = title if len(title) <= 38 else title[:35] + "..."
                label_box = draw.textbbox((0, 0), label)
                label_width = label_box[2] - label_box[0]
                draw.text(
                    (cell_left + (box_width - label_width) // 2, cell_top + box_height - round(6 / 25.4 * 300)),
                    label,
                    fill='black'
                )
                code_label = access_code
                code_box = draw.textbbox((0, 0), code_label)
                code_width = code_box[2] - code_box[0]
                draw.text(
                    (cell_left + (box_width - code_width) // 2, cell_top + box_height - round(3 / 25.4 * 300)),
                    code_label,
                    fill='black'
                )
                draw.rectangle(
                    (cell_left, cell_top, cell_left + box_width, cell_top + box_height),
                    outline='black',
                    width=3,
                )
            pages.append(page)
        output = BytesIO()
        pages[0].save(output, format='PDF', resolution=300.0, save_all=True, append_images=pages[1:])
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename="book_qrcodes.pdf"'
        return response
    except Exception as e:
        print(f"DOWNLOAD BOOK QR ERROR: {e}")
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
#  BOOK MANAGEMENT ROUTES (Admin)
# ============================================================

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
        c.execute("""INSERT INTO books (access_code, title, author, isbn, category, shelf_location, quantity, created_at)
            VALUES ('PENDING', %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (title, author, isbn, category, shelf_location, qty, created_at))
        book_id = c.fetchone()[0]
        access_code = f"BK{str(book_id).zfill(6)}"
        c.execute("UPDATE books SET access_code = %s WHERE id = %s", (access_code, book_id))
        conn.commit()
        conn.close()
        qr_b64 = generate_qr_b64(access_code)
        return jsonify({
            "success": True,
            "book_id": book_id,
            "access_code": access_code,
            "title": title,
            "qr": qr_b64,
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
        quantity, times_borrowed, last_borrowed_date, created_at FROM books ORDER BY title""")
    books = []
    for r in c.fetchall():
        active, available, status = book_status_info(r[0], r[7])
        books.append({
            "id": r[0], "access_code": r[1], "title": r[2], "author": r[3],
            "isbn": r[4], "category": r[5], "shelf_location": r[6],
            "quantity": r[7], "times_borrowed": r[8] or 0,
            "last_borrowed_date": r[9] or "-", "created_at": r[10],
            "active_borrows": active, "available_qty": available, "status": status,
        })
    conn.close()
    return jsonify({"books": books})


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
            shelf_location=%s, quantity=%s WHERE id=%s""",
            (title, author, isbn, category, shelf_location, qty, int(book_id)))
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
#  BORROW / RETURN / SMART SCAN
# ============================================================

@app.route('/api/smart-scan', methods=['POST'])
def smart_scan():
    """Unified scan: detect if code is a Book QR or a User ID (attendance)."""
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
    # 1) Try as BOOK QR (access_code)
    c.execute("""SELECT id, access_code, title, author, isbn, category, shelf_location, quantity,
        times_borrowed, last_borrowed_date FROM books WHERE UPPER(access_code) = UPPER(%s)""", (code,))
    book = c.fetchone()
    if book:
        book_id = book[0]
        active, available, status = book_status_info(book_id, book[7])
        c.execute("""SELECT br.id, u.full_name, u.id_number, br.borrow_date, br.borrow_time
            FROM borrow_records br JOIN users u ON br.user_id = u.id
            WHERE br.book_id = %s AND br.return_time IS NULL ORDER BY br.id""", (book_id,))
        active_borrows = [{"borrow_id": r[0], "borrower_name": r[1], "borrower_id": r[2],
                           "borrow_date": r[3], "borrow_time": r[4]} for r in c.fetchall()]
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
        return jsonify({"success": False, "message": f"Code '{code}' not found as a Book QR or User ID."})
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


@app.route('/api/borrow-book', methods=['POST'])
def borrow_book():
    if not is_scan_authorized():
        return jsonify({"success": False, "message": "Unauthorized."}), 401
    data = request.get_json(silent=True) or request.form
    book_id = str(data.get('book_id', '')).strip()
    id_number = str(data.get('id_number', '')).strip()
    if not book_id or not id_number:
        return jsonify({"success": False, "message": "book_id and id_number are required."}), 400
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    c = conn.cursor()
    c.execute("SELECT id, title, quantity FROM books WHERE id = %s", (int(book_id),))
    book = c.fetchone()
    if not book:
        conn.close()
        return jsonify({"success": False, "message": "Book not found."})
    active, available, _ = book_status_info(book[0], book[2])
    if available <= 0:
        conn.close()
        return jsonify({"success": False, "message": f"'{book[1]}' is fully borrowed. No copies available."})
    c.execute("SELECT id, full_name FROM users WHERE UPPER(id_number) = UPPER(%s)", (id_number,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False, "message": f"User ID '{id_number}' not found. Scan a registered Student/Visitor ID."})
    user_id, full_name = user
    today = get_ph_date()
    now = get_ph_time()
    c.execute("""INSERT INTO borrow_records (book_id, user_id, borrow_date, borrow_time, status)
        VALUES (%s, %s, %s, %s, 'Borrowed')""", (book[0], user_id, today, now))
    c.execute("UPDATE books SET times_borrowed = times_borrowed + 1, last_borrowed_date = %s WHERE id = %s", (today, book[0]))
    conn.commit()
    conn.close()
    return jsonify({"success": True,
                    "message": f"BORROWED: '{book[1]}' by {full_name} at {now}",
                    "book_title": book[1], "borrower": full_name, "date": today, "time": now})


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
    c.execute("""SELECT br.id, b.title, u.full_name FROM borrow_records br
        JOIN books b ON br.book_id = b.id JOIN users u ON br.user_id = u.id
        WHERE br.id = %s AND br.return_time IS NULL""", (int(borrow_id),))
    rec = c.fetchone()
    if not rec:
        conn.close()
        return jsonify({"success": False, "message": "This borrow record was already returned or not found."})
    today = get_ph_date()
    now = get_ph_time()
    c.execute("UPDATE borrow_records SET return_date = %s, return_time = %s, status = 'Returned' WHERE id = %s",
              (today, now, int(borrow_id)))
    conn.commit()
    conn.close()
    return jsonify({"success": True,
                    "message": f"RETURNED: '{rec[1]}' (borrowed by {rec[2]}) at {now}",
                    "book_title": rec[1], "borrower": rec[2], "date": today, "time": now})


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
        br.borrow_date, br.borrow_time, br.return_date, br.return_time, br.status
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
    records = [{"id": r[0], "title": r[1], "access_code": r[2], "borrower": r[3],
                "borrower_id": r[4], "borrow_date": r[5], "borrow_time": r[6],
                "return_date": r[7] or "-", "return_time": r[8] or "-",
                "status": "Returned" if r[8] else "Borrowed"} for r in c.fetchall()]
    conn.close()
    return jsonify({"records": records})


# ============================================================
#  EXISTING ROUTES (unchanged)
# ============================================================

PRIVACY_PAGE = """
<!DOCTYPE html><html><head>
<title>Privacy Policy - SLSU Library Attendance System</title>
<link rel="icon" type="image/png" href="/static/app-icon.png">
<link rel="apple-touch-icon" href="/static/app-icon.png">
<meta name="theme-color" content="#006633">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}body{font-family:'Segoe UI',Arial,sans-serif;background:#eef0f3;color:#374151;margin:0;padding:24px;line-height:1.65}.policy{max-width:980px;margin:0 auto;background:#fff;border:1px solid #d8dbe0;padding:34px 42px;box-shadow:0 2px 12px rgba(15,25,43,.08)}h1,h2{font-family:Georgia,'Times New Roman',serif;color:#1b2a41}h1{font-size:26px;margin:0 0 6px}h2{font-size:18px;margin:28px 0 8px;border-bottom:1px solid #eef0f3;padding-bottom:8px}p{margin:8px 0 14px}li{margin:5px 0}table{width:100%;border-collapse:collapse;margin:12px 0 20px}th,td{border:1px solid #d8dbe0;padding:10px;text-align:left;vertical-align:top}th{background:#1b2a41;color:#fff}@media(max-width:600px){body{padding:10px}.policy{padding:22px 18px}table{font-size:12px}}
</style></head><body><main class="policy">
<h1>Privacy Policy - SLSU Library Attendance System</h1>
<p><strong>Last Updated:</strong> September 13, 2026</p>
<h2>1. Who We Are</h2><p>This system - SLSU Library Attendance System - is designed exclusively for Southern Luzon State University (SLSU). It is created to simplify and manage library entry and exit records for students, employees, and authorized visitors.</p>
<h2>2. Exactly What Information We Collect</h2><p>We collect only the specific fields you enter during registration:</p>
<table><tr><th>Field</th><th>Purpose</th></tr><tr><td>Full Name</td><td>Identification and record-keeping</td></tr><tr><td>ID Type</td><td>Student / Employee / Visitor categorization</td></tr><tr><td>ID Number</td><td>Unique identifier - this becomes your barcode</td></tr><tr><td>Department</td><td>CT, FBT, BSED, BEED, BSFAS, BSBA, EMPLOYEE - for reporting</td></tr><tr><td>Year Level</td><td>Students only - classification and demographic reporting</td></tr><tr><td>Major / Specialization</td><td>BSED, BSBA, BSIT, Com Tech, Food Tech, Bind Tech - program-specific reporting</td></tr><tr><td>Contact Number</td><td>Library-related announcements only</td></tr><tr><td>Complete Address</td><td>Required per university guidelines</td></tr></table>
<p><strong>Attendance Data (Automatically Recorded Upon Scan)</strong></p><ul><li>Time In - exact date and time you scan your ID upon entry</li><li>Time Out - exact date and time you scan your ID upon exit</li><li>Date of Visit - automatically recorded for daily and monthly reports</li></ul>
<p><strong>System Data</strong></p><ul><li>Login timestamp and role</li><li>System logs for troubleshooting and security</li><li>We do not collect passwords, photos, biometrics, location data, browsing history, or financial information.</li></ul>
<h2>3. How We Use Your Information - Specifically</h2><p>Your data is used only to:</p><ul><li>Verify your identity when registering and generating your barcode</li><li>Record Time In and Time Out when you scan at the library entrance or exit</li><li>Generate daily, weekly, and monthly attendance reports accessible only to Library Staff and Administration</li><li>Track library occupancy and usage patterns</li><li>Comply with SLSU record-keeping and auditing requirements</li><li>Contact you through your provided number for library-related announcements only, never marketing</li></ul>
<p><strong>We will never:</strong></p><ul><li>Sell, rent, or share your data with any third party</li><li>Send commercial advertisements or marketing messages</li><li>Collect or store your photos, biometrics, or passwords</li><li>Make your personal profile publicly searchable</li></ul>
<h2>4. Data Storage and Security</h2><ul><li><strong>Database:</strong> PostgreSQL hosted on Render / Supabase Cloud - encrypted and password-protected</li><li><strong>Storage Duration:</strong> Attendance records are retained for one academic year per university policy. Personal data is kept while you are officially enrolled or employed at SLSU.</li><li><strong>Backups:</strong> Automatic daily backups are deleted after 30 days</li><li><strong>Security:</strong> All data is transmitted over HTTPS. Only the System Administrator has full database access.</li></ul>
<h2>5. Who Can See Your Data - Specifically and Exactly</h2><table><tr><th>User Role</th><th>What They Can See and Do</th></tr><tr><td>System Administrator (slsu)</td><td>Full access to all records - manage users, view attendance, generate reports, correct information, and manage system settings</td></tr><tr><td>Library Staff</td><td>Can view all attendance records for daily/monthly reporting. Cannot edit or delete personal information.</td></tr><tr><td>Individual User</td><td>Can access only the Registration Form and Barcode Generation. Cannot view attendance records, history, logs, or reports.</td></tr><tr><td>Public / Visitors</td><td>No access - login is required.</td></tr></table><p>Your personal information and attendance records are never made public, indexed by search engines, or shared outside SLSU.</p>
<h2>6. Your Exact Rights</h2><ul><li>Register and create your own barcode</li><li>Request correction of incorrect information</li><li>Request data deletion upon graduation, resignation, or separation from SLSU</li><li>Scan your printed barcode for entry and exit without logging in or viewing records</li><li>Opt out and use the manual paper logbook</li><li>Know that your information is protected and never shared or sold</li></ul>
<h2>7. Data Sharing - Specifically When It Happens</h2><p>We share your data only when required by SLSU Administration for official reports, audits, and library management, or when required by law through a court order or legal mandate. It is never shared with commercial companies, marketing agencies, or external organizations.</p>
<h2>8. Barcode / ID Number Usage - Specifically</h2><ul><li>Your Student Number or Employee Number is your unique identifier encoded into your barcode</li><li>Scanning reads only your ID number - no personal details, photos, or contact information are read directly from the card</li><li>The system matches the ID number to your database record and automatically logs Time In or Time Out</li><li>No personal information is stored inside the barcode itself - only your unique ID number</li></ul>
<h2>9. About the System</h2><p>This system was created for Southern Luzon State University (SLSU) to streamline library attendance while prioritizing user privacy and data security.</p>
<h2>10. Changes to This Policy</h2><p>We may update this Privacy Policy as needed. Changes will be posted here with an updated date. Significant changes will be announced through the system login page. Continued use of the system constitutes acceptance of the updated policy.</p>
<h2>11. Contact Information</h2><p><strong>System:</strong> SLSU Library Attendance System<br><strong>Institution:</strong> Southern Luzon State University - Judge Guillermo Eleazar<br><strong>Office:</strong> SLSU Library - SLSU-JGE</p>
<p><strong>By registering, generating your barcode, and scanning your ID, you confirm that you have read, understood, and agree to this Privacy Policy.</strong></p>
</main></body></html>"""


@app.route('/privacy')
def privacy_policy():
    return render_template_string(PRIVACY_PAGE)


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
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Sign In — Library Attendance System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <link rel="apple-touch-icon" href="/static/app-icon.png">
    <meta name="theme-color" content="#006633">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#172236 url('/static/jge.jpg') center/cover no-repeat fixed;min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;position:relative;}
        body:before{content:"";position:fixed;inset:0;background:rgba(10,20,35,.58);z-index:0;}
        .card{position:relative;z-index:1;background:rgba(255,255,255,.97);padding:0;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 8px 30px rgba(0,0,0,0.25);width:100%;max-width:440px;overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:44px 40px;}
        h1{text-align:center;color:#1b2a41;margin-bottom:10px;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
        .subtitle{text-align:center;color:#64748b;margin-bottom:30px;font-size:14px;}
        .error-box{background:#fbeaea;color:#8a1f1f;padding:14px 16px;border-left:3px solid #c0392b;border-radius:4px;margin-bottom:26px;text-align:left;font-size:14px;}
        a.back-link{display:block;text-align:center;padding:13px;background:#1b2a41;color:#fff;border-radius:4px;text-decoration:none;font-weight:600;font-size:14px;letter-spacing:.3px;transition:background 0.2s;}
        a.back-link:hover{background:#10192b;}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-top"></div>
        <div class="card-body">
            <h1>Invalid Credentials</h1>
            <p class="subtitle">SLSU–JGE Library Attendance System</p>
            <div class="error-box">The username or password you entered is incorrect. Please try again.</div>
            <a href="/login" class="back-link">Return to Sign In</a>
        </div>
    </div>
</body>
</html>"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Sign In — Library Attendance System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" type="image/png" href="/static/app-icon.png">
    <link rel="apple-touch-icon" href="/static/app-icon.png">
    <meta name="theme-color" content="#006633">
    <style>
        *{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;}
        body{background:#172236 url('/static/jge.jpg') center/cover no-repeat fixed;min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;position:relative;}
        body:before{content:"";position:fixed;inset:0;background:rgba(10,20,35,.58);z-index:0;}
        .card{position:relative;z-index:1;background:rgba(255,255,255,.97);padding:0;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 8px 30px rgba(0,0,0,0.25);width:100%;max-width:440px;overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:44px 40px;}
        .brand-mark{width:56px;height:56px;margin:0 auto 18px auto;background:#1b2a41;color:#e8c766;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:13px;letter-spacing:.5px;}
        h1{text-align:center;color:#1b2a41;margin-bottom:6px;font-size:24px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
        .subtitle{text-align:center;color:#64748b;margin-bottom:34px;font-size:14px;}
        .form-group{margin-bottom:20px;}
        label{display:block;margin-bottom:8px;color:#374151;font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:.4px;}
        input{width:100%;padding:13px 15px;border:1px solid #d1d5db;border-radius:4px;font-size:15px;transition:border-color 0.2s,box-shadow 0.2s;background:#fafbfc;}
        input:focus{outline:none;border-color:#1b2a41;background:#fff;box-shadow:0 0 0 3px rgba(27,42,65,0.1);}
        button{width:100%;padding:14px;background:#1b2a41;color:white;border:none;border-radius:4px;font-size:15px;font-weight:600;cursor:pointer;transition:background 0.2s;letter-spacing:.3px;margin-top:6px;}
        button:hover{background:#10192b;}
        .hint{margin-top:22px;text-align:center;font-size:12px;color:#94a3b8;line-height:1.7;border-top:1px solid #eef0f3;padding-top:16px;}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-top"></div>
        <div class="card-body">
            <div class="brand-mark">SLSU<br>JGE</div>
            <h1>Sign In</h1>
            <p class="subtitle">Library Attendance System</p>
            <form method="POST">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" required placeholder="Enter your username">
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required placeholder="Enter your password">
                </div>
                <button type="submit">Sign In</button>
            </form>
        </div>
    </div>
</body>
</html>"""


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
    return jsonify({"status": "ok"})


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
        registered_at = get_ph_date() + " " + get_ph_time()
        if id_type not in {"Student", "Employee", "Visitor"}:
            return jsonify({"success": False, "error": "Please select a valid ID type."}), 400
        if not full_name or not id_number or not contact_number or not address:
            return jsonify({"success": False, "error": "Full name, ID number, contact number, and address are required."}), 400
        if id_type in {"Employee", "Visitor"}:
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
        c.execute("""INSERT INTO users 
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (id_type, full_name, department, major, contact_number, address, year_level, id_number, registered_at))
        conn.commit()
        conn.close()
        barcode_b64 = generate_barcode_b64(id_number)
        info = f"{full_name}  |  ID: {id_number}  |  {id_type}"
        return jsonify({"success": True, "info": info, "barcode": barcode_b64})
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
        address, year_level, id_number FROM users ORDER BY full_name""")
    students = [{"id": r[0], "id_type": r[1], "full_name": r[2], "department": r[3],
                 "major": r[4], "contact_number": r[5], "address": r[6],
                 "year_level": r[7], "id_number": r[8],
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
        if id_type not in {"Student", "Employee", "Visitor"}:
            return jsonify({"success": False, "error": "Please select a valid ID type."}), 400
        if not all([student_id, id_number, full_name, contact_number, address]):
            return jsonify({"success": False, "error": "Full name, ID number, contact number, and address are required."}), 400
        if id_type in {"Employee", "Visitor"}:
            department = None
            major = None
            year_level = None
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "error": "Database error."}), 500
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
    doc.add_paragraph('SLSU–JGE Library Attendance System')
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
    doc.add_paragraph('SLSU–JGE Library Attendance System')
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
<style>
*{{box-sizing:border-box;}}
body{{font-family:'Segoe UI',Arial,sans-serif;padding:40px;max-width:1100px;margin:0 auto;color:#1f2937;}}
.report-header{{border-bottom:3px solid #1b2a41;padding-bottom:16px;margin-bottom:24px;}}
h1{{color:#1b2a41;font-family:Georgia,'Times New Roman',serif;font-size:24px;margin-bottom:6px;}}
.meta{{color:#64748b;font-size:13px;}}
table{{width:100%;border-collapse:collapse;margin-top:10px;}}
th,td{{border:1px solid #d8dbe0;padding:10px 12px;text-align:left;font-size:13px;}}
th{{background:#1b2a41;color:#fff;font-weight:600;}}
tr:nth-child(even){{background:#f7f8fa;}}
button{{padding:11px 26px;font-size:14px;cursor:pointer;background:#1b2a41;color:white;border:none;border-radius:4px;font-weight:600;margin-bottom:20px;}}
@media print{{button{{display:none;}}body{{padding:0;}}}}
</style>
</head><body>
<div class="report-header">
<h1>Monthly Attendance Report — {month}</h1>
<p class="meta">SLSU–JGE Library Attendance System &nbsp;•&nbsp; Generated: {get_ph_date()} {get_ph_time()}</p>
</div>
<button onclick="window.print()">Print Report</button>
<script>fetch('/get-monthly-history?month={month}').then(r=>r.json()).then(d=>{{
const grouped = d.records.reduce((days, record) => {{
    (days[record.scan_date] ||= []).push(record);
    return days;
}}, {{}});
let html='';
Object.entries(grouped).forEach(([date, records]) => {{
    html+='<h2 style="margin-top:28px;">'+date+'</h2><table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>';
    records.forEach(r=>html+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+r.department+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>');
    html+='</table>';
}});
document.body.innerHTML+=html;
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
<style>*{{box-sizing:border-box;}}body{{font-family:'Segoe UI',Arial,sans-serif;padding:40px;max-width:1100px;margin:0 auto;color:#1f2937;}}h1{{color:#1b2a41;font-family:Georgia,'Times New Roman',serif;}}.meta{{color:#64748b;font-size:13px;}}table{{width:100%;border-collapse:collapse;margin-top:24px;}}th,td{{border:1px solid #d8dbe0;padding:10px 12px;text-align:left;font-size:13px;}}th{{background:#1b2a41;color:#fff;}}tr:nth-child(even){{background:#f7f8fa;}}button{{padding:11px 26px;font-size:14px;cursor:pointer;background:#1b2a41;color:white;border:0;border-radius:4px;font-weight:600;margin-bottom:20px;}}@media print{{button{{display:none;}}body{{padding:0;}}}}</style>
</head><body><button onclick="window.print()">Print Daily Report</button><h1>Daily Attendance Report - {selected_date}</h1><p class="meta">SLSU-JGE Library Attendance System</p>
<script>fetch('/get-monthly-history?month={selected_date[:7]}&date={selected_date}').then(r=>r.json()).then(d=>{{let html='<table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>';d.records.forEach(r=>html+='<tr><td>'+r.scan_date+'</td><td>'+r.full_name+'</td><td>'+r.department+'</td><td>'+(r.time_in||'-')+'</td><td>'+(r.time_out||'-')+'</td></tr>');html+='</table>';document.body.innerHTML+=html;}})</script></body></html>"""


# ============================================================
#  STUDENT FRONTEND — registration form ONLY (nothing else)
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
        body{background:#eef0f3;min-height:100vh;display:flex;justify-content:center;align-items:flex-start;padding:30px 16px;}
        .container{width:100%;max-width:560px;}
        .card{background:#ffffff;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 2px 12px rgba(15,25,43,0.08);overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:42px 40px;}
        .brand-mark{width:52px;height:52px;margin:0 auto 16px auto;background:#1b2a41;color:#e8c766;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:12px;text-align:center;line-height:1.2;}
        h1{text-align:center;color:#1b2a41;margin-bottom:6px;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
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
        .barcode-img{width:50mm;height:12mm;max-width:100%;margin:18px auto;display:block;padding:0;background:white;border:1px solid #d8dbe0;border-radius:4px;object-fit:contain;image-rendering:crisp-edges;}
        .barcode-id{font-size:18px;font-weight:700;color:#1b2a41;margin:12px 0;}
        .btn-print{background:#1e6b34;color:#fff;border:none;padding:12px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;margin:4px;}
        .btn-print:hover{background:#175628;}
        .btn-download-barcode{background:#8a6d1f;color:#fff;border:none;padding:12px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;margin:4px;}
        .btn-download-barcode:hover{background:#6e5718;}
        .logout-link{display:block;text-align:center;margin-top:22px;color:#64748b;text-decoration:none;font-size:13px;border-top:1px solid #eef0f3;padding-top:18px;}
        .logout-link:hover{color:#1b2a41;}
        .privacy-link{display:block;text-align:center;margin-top:12px;color:#1b2a41;text-decoration:none;font-size:13px;}
        .privacy-link:hover{text-decoration:underline;}
        @media print{body *{visibility:hidden !important;}#barcode-result,#barcode-result *{visibility:visible !important;}#barcode-result{display:block !important;position:absolute;top:0;left:0;width:50mm;height:25mm;margin:0;padding:0;border:1px solid #000;background:#fff;}#barcode-result h3{display:none;}.barcode-img{width:50mm;height:12mm;object-fit:contain;padding:0;border:0;margin:7mm auto 0;}.barcode-id{font-size:8pt;margin:1mm 0 0;}.btn-print{display:none !important;}}
        @media(max-width:600px){.form-row{grid-template-columns:1fr;}.card-body{padding:30px 22px;}}
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
                                    <option value="EMPLOYEE">EMPLOYEE</option>
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
                            <label>Contact Number</label>
                            <input type="text" name="contact_number" required placeholder="09XX-XXX-XXXX">
                        </div>
                        <div class="form-group">
                            <label>Address</label>
                            <input type="text" name="address" required placeholder="City, Province">
                        </div>
                    </div>
                    <button type="submit" class="btn-primary">Register &amp; Generate Barcode</button>
                </form>
                <div id="barcode-result">
                    <h3>Registration Successful</h3>
                    <p id="barcode-id" class="barcode-id"></p>
                    <img id="barcode-img" class="barcode-img"><br>
                    <button class="btn-print" onclick="window.print()">Print Barcode</button>
                    <button class="btn-download-barcode" onclick="downloadUserBarcode()">Download Barcode</button>
                </div>
                <a href="/privacy" class="privacy-link" target="_blank">Privacy Policy</a>
                <a href="/login" class="logout-link" onclick="logout(event)">← Back to Sign In</a>
            </div>
        </div>
    </div>
<script>
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
    if(!barcodeImage.src || !idNumber) return;
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
    }
    departmentSelect.addEventListener("change", function(){
        const department = departmentSelect.value;
        majorSelect.innerHTML = '<option value="">-- Select Major --</option>';
        (MAJORS[department]||[]).forEach(function(major){
            const option = document.createElement("option");
            option.value = major; option.textContent = major;
            majorSelect.appendChild(option);
        });
        majorSelect.disabled = (department === "EMPLOYEE" || department === "BPA" || department === "");
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
                document.getElementById("barcode-id").textContent="ID Number: " + formData.get("id_number");
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
#  STAFF (USER) FRONTEND — registration form UNCHANGED + new tabs
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
        body{background:#eef0f3;min-height:100vh;}
        .topnav{background:#1b2a41;display:flex;align-items:center;flex-wrap:wrap;padding:0 20px;box-shadow:0 2px 8px rgba(15,25,43,.18);position:sticky;top:0;z-index:50;}
        .brand{display:flex;align-items:center;gap:12px;padding:14px 0;color:#fff;margin-right:auto;}
        .brand-mark{width:40px;height:40px;background:#24344f;color:#e8c766;border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:11px;text-align:center;line-height:1.2;flex:0 0 40px;}
        .brand-text h1{font-size:16px;font-family:Georgia,'Times New Roman',serif;color:#f1f3f6;}
        .brand-text p{font-size:11px;color:#8b9bb5;letter-spacing:.3px;}
        .nav-tabs{display:flex;gap:2px;flex-wrap:wrap;}
        .nav-tab{padding:14px 18px;color:#c3cede;cursor:pointer;font-size:14px;font-weight:600;border-bottom:3px solid transparent;transition:all .2s;white-space:nowrap;}
        .nav-tab:hover{background:#233450;color:#fff;}
        .nav-tab.active{color:#fff;border-bottom:3px solid #e8c766;background:#24344f;}
        .logout-btn{background:#7a1f1f;color:#fff;border:none;padding:9px 18px;border-radius:4px;font-size:13px;font-weight:600;cursor:pointer;margin-left:10px;}
        .logout-btn:hover{background:#5e1717;}
        .staff-content{max-width:1100px;margin:0 auto;padding:28px 20px 60px;}
        .staff-tab{display:none;}
        .staff-tab.active{display:block;}
        /* ---- original registration card (unchanged) ---- */
        .container{width:100%;max-width:560px;margin:0 auto;}
        .card{background:#ffffff;border-radius:6px;border:1px solid #d8dbe0;box-shadow:0 2px 12px rgba(15,25,43,0.08);overflow:hidden;}
        .card-top{height:5px;background:#1b2a41;}
        .card-body{padding:42px 40px;}
        .reg-brand-mark{width:52px;height:52px;margin:0 auto 16px auto;background:#1b2a41;color:#e8c766;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:Georgia,'Times New Roman',serif;font-weight:700;font-size:12px;text-align:center;line-height:1.2;}
        h1.reg-title{text-align:center;color:#1b2a41;margin-bottom:6px;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
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
        .barcode-img{width:50mm;height:12mm;max-width:100%;margin:18px auto;display:block;padding:0;background:white;border:1px solid #d8dbe0;border-radius:4px;object-fit:contain;image-rendering:crisp-edges;}
        .barcode-id{font-size:18px;font-weight:700;color:#1b2a41;margin:12px 0;}
        .btn-print{background:#1e6b34;color:#fff;border:none;padding:12px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;margin:4px;}
        .btn-print:hover{background:#175628;}
        .btn-download-barcode{background:#8a6d1f;color:#fff;border:none;padding:12px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;margin:4px;}
        .btn-download-barcode:hover{background:#6e5718;}
        .logout-link{display:block;text-align:center;margin-top:22px;color:#64748b;text-decoration:none;font-size:13px;border-top:1px solid #eef0f3;padding-top:18px;}
        .logout-link:hover{color:#1b2a41;}
        .privacy-link{display:block;text-align:center;margin-top:12px;color:#1b2a41;text-decoration:none;font-size:13px;}
        .privacy-link:hover{text-decoration:underline;}
        @media print{body *{visibility:hidden !important;}#barcode-result,#barcode-result *{visibility:visible !important;}#barcode-result{display:block !important;position:absolute;top:0;left:0;width:50mm;height:25mm;margin:0;padding:0;border:1px solid #000;background:#fff;}#barcode-result h3{display:none;}.barcode-img{width:50mm;height:12mm;object-fit:contain;padding:0;border:0;margin:7mm auto 0;}.barcode-id{font-size:8pt;margin:1mm 0 0;}.btn-print{display:none !important;}}
        /* ---- scan / book panels ---- */
        .panel-card{background:#fff;border:1px solid #d8dbe0;border-radius:6px;padding:28px;box-shadow:0 2px 12px rgba(15,25,43,.08);}
        h2.panel-title{color:#1b2a41;font-size:19px;font-family:Georgia,'Times New Roman',serif;margin-bottom:18px;border-bottom:1px solid #eef0f3;padding-bottom:12px;}
        .scan-area{text-align:center;padding:30px;background:#f7f8fa;border-radius:6px;margin-bottom:18px;border:1px solid #d8dbe0;}
        .scan-input{font-size:20px;text-align:center;padding:14px;width:100%;max-width:480px;border-radius:4px;border:1px solid #b9c2cf;}
        .status{font-size:15px;font-weight:600;margin-top:16px;padding:14px;border-radius:4px;border-left:4px solid;}
        .success{background:#e8f5ec;color:#1e6b34;border-color:#2f8a4e;}
        .info{background:#eaf1f8;color:#1b4f72;border-color:#3a75a3;}
        .error{background:#fbeaea;color:#8a1f1f;border-color:#c0392b;}
        .warning{background:#fdf6e3;color:#8a6d1f;border-color:#c9a227;}
        table{width:100%;border-collapse:collapse;margin-top:16px;}
        th,td{padding:11px 12px;text-align:left;border:1px solid #e5e7eb;font-size:13px;}
        th{background:#1b2a41;color:#fff;font-weight:600;}
        tr:nth-child(even){background:#f7f8fa;}
        .book-detail{background:#f7f8fa;border:1px solid #d8dbe0;border-radius:6px;padding:22px;margin-top:18px;}
        .book-detail h3{color:#1b2a41;font-family:Georgia,'Times New Roman',serif;font-size:18px;margin-bottom:10px;}
        .book-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px 18px;margin:12px 0 18px;font-size:13px;}
        .book-meta div strong{color:#1b2a41;display:block;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#64748b;margin-bottom:2px;}
        .badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;}
        .badge-avail{background:#e8f5ec;color:#1e6b34;}
        .badge-borrowed{background:#fbeaea;color:#8a1f1f;}
        .action-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;}
        .btn-borrow{background:#1b4f72;color:#fff;border:none;padding:11px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;}
        .btn-borrow:hover{background:#143a55;}
        .btn-return{background:#1e6b34;color:#fff;border:none;padding:8px 16px;border-radius:4px;font-size:12px;font-weight:600;cursor:pointer;}
        .btn-return:hover{background:#175628;}
        .btn-cancel{background:#5b6472;color:#fff;border:none;padding:11px 22px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;}
        .btn-cancel:hover{background:#464d59;}
        .awaiting-box{background:#fdf6e3;border:2px dashed #c9a227;border-radius:6px;padding:18px;text-align:center;margin-top:14px;font-weight:600;color:#8a6d1f;}
        .borrower-row{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#fff;border:1px solid #e5e7eb;border-radius:4px;margin-top:8px;font-size:13px;flex-wrap:wrap;gap:8px;}
        #toast{position:fixed;top:70px;right:20px;max-width:360px;z-index:200;display:flex;flex-direction:column;gap:8px;}
        .toast-item{padding:14px 18px;border-radius:6px;font-size:14px;font-weight:600;box-shadow:0 6px 20px rgba(15,25,43,.25);border-left:4px solid;animation:slideIn .25s ease;}
        @keyframes slideIn{from{transform:translateX(40px);opacity:0;}to{transform:translateX(0);opacity:1;}}
        @media(max-width:700px){.form-row{grid-template-columns:1fr;}.card-body{padding:30px 22px;}.nav-tab{padding:12px 12px;font-size:13px;}.staff-content{padding:18px 10px 40px;}.panel-card{padding:18px;}}
    </style>
</head>
<body>
    <div class="topnav">
        <div class="brand">
            <div class="brand-mark">SLSU<br>JGE</div>
            <div class="brand-text"><h1>Library System — Staff</h1><p>Attendance &amp; Book Borrowing</p></div>
        </div>
        <div class="nav-tabs">
            <div class="nav-tab active" onclick="showStaffTab('register')">Registration</div>
            <div class="nav-tab" onclick="showStaffTab('scan')">Scan / Attendance</div>
            <div class="nav-tab" onclick="showStaffTab('books')">Book Borrowing</div>
        </div>
        <button class="logout-btn" onclick="logout()">Log Out</button>
    </div>
    <div id="toast"></div>
    <div class="staff-content">
        <!-- ============ REGISTRATION (UNCHANGED) ============ -->
        <div id="tab-register" class="staff-tab active">
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
                                            <option value="EMPLOYEE">EMPLOYEE</option>
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
                                    <label>Contact Number</label>
                                    <input type="text" name="contact_number" required placeholder="09XX-XXX-XXXX">
                                </div>
                                <div class="form-group">
                                    <label>Address</label>
                                    <input type="text" name="address" required placeholder="City, Province">
                                </div>
                            </div>
                            <button type="submit" class="btn-primary">Register &amp; Generate Barcode</button>
                        </form>
                        <div id="barcode-result">
                            <h3>Registration Successful</h3>
                            <p id="barcode-id" class="barcode-id"></p>
                            <img id="barcode-img" class="barcode-img"><br>
                            <button class="btn-print" onclick="window.print()">Print Barcode</button>
                            <button class="btn-download-barcode" onclick="downloadUserBarcode()">Download Barcode</button>
                        </div>
                        <a href="/privacy" class="privacy-link" target="_blank">Privacy Policy</a>
                    </div>
                </div>
            </div>
        </div>
        <!-- ============ SCAN / ATTENDANCE ============ -->
        <div id="tab-scan" class="staff-tab">
            <div class="panel-card">
                <h2 class="panel-title">Scan Barcode — Time In / Time Out</h2>
                <div class="scan-area">
                    <input type="text" class="scan-input" id="att-scan-input" placeholder="Scan barcode or type ID number..." autofocus>
                    <div id="att-status" class="status info">Waiting for scan... (scanning)</div>
                </div>
                <h2 class="panel-title" style="margin-top:26px;">Today's Attendance Records</h2>
                <button class="btn-cancel" style="background:#1b2a41;" onclick="loadTodayRecords()">Refresh</button>
                <div id="today-records-table"></div>
            </div>
        </div>
        <!-- ============ BOOK BORROWING ============ -->
        <div id="tab-books" class="staff-tab">
            <div class="panel-card">
                <h2 class="panel-title">Book Borrow / Return — Scan Book QR</h2>
                <div class="scan-area">
                    <input type="text" class="scan-input" id="book-scan-input" placeholder="Scan Book QR code (or type access code BK000001)...">
                    <div id="book-status" class="status info">Scan a Book QR to begin. Scanning.</div>
                </div>
                <div id="book-detail-panel" style="display:none;"></div>
                <h2 class="panel-title" style="margin-top:26px;">Recent Borrow Transactions</h2>
                <button class="btn-cancel" style="background:#1b2a41;" onclick="loadBorrowHistory()">Refresh</button>
                <div id="borrow-history-table"></div>
            </div>
        </div>
    </div>
<script>
const MAJORS = {
    "BSBA": ["Marketing Management", "Financial Management"],
    "BSED": ["English", "Mathematics", "Science"],
    "CT": ["Computer Technology", "Food Technology", "BINDTECH", "CULINARY"],
};
let scanState = "idle"; // idle | awaiting_borrower
let pendingBook = null;
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
    const tabs = ["register","scan","books"];
    document.querySelectorAll(".nav-tab")[tabs.indexOf(tab)].classList.add("active");
    if(tab==="scan"){setTimeout(()=>document.getElementById("att-scan-input")?.focus(),80);loadTodayRecords();}
    if(tab==="books"){setTimeout(()=>document.getElementById("book-scan-input")?.focus(),80);loadBorrowHistory();}
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
    setTimeout(()=>{el.style.opacity="0";el.style.transition="opacity .4s";setTimeout(()=>el.remove(),400);},4200);
}
function setStatus(id, msg, type){
    const box = document.getElementById(id);
    if(!box) return;
    box.className = "status " + type;
    box.textContent = msg;
}
// ---- unified scan handler  ----
function handleScannedCode(code){
    code = (code||"").trim();
    if(!code) return;
    if(scanState === "awaiting_borrower" && pendingBook){
        // treat as borrower User ID
        fetch("/api/borrow-book",{method:"POST",headers:{"Content-Type":"application/json"},
            body:JSON.stringify({book_id: pendingBook.id, id_number: code})})
        .then(r=>r.json()).then(data=>{
            if(data.success){
                showToast(data.message, "success");
                setStatus("book-status", data.message, "success");
                scanState = "idle"; pendingBook = null;
                renderBookDetail(null);
                loadBorrowHistory();
            }else{
                showToast(data.message || "Borrow failed.", "error");
                setStatus("book-status", data.message || "Borrow failed. Scan a valid User ID.", "error");
            }
        }).catch(err=>{showToast("Error: "+err, "error");});
        return;
    }
    // idle: smart scan (book QR or user attendance)
    fetch("/api/smart-scan",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({code: code})})
    .then(r=>r.json()).then(data=>{
        if(!data.success){
            showToast(data.message || "Not found.", "error");
            setStatus("att-status", data.message || "Not found.", "error");
            setStatus("book-status", data.message || "Not found.", "error");
            return;
        }
        if(data.type === "attendance"){
            showToast(data.message, "success");
            setStatus("att-status", data.message, "success");
            loadTodayRecords();
        }else if(data.type === "book"){
            showStaffTab("books");
            pendingBook = data.book;
            renderBookDetail(data);
            setStatus("book-status", "Book found: " + data.book.title, "info");
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
        borrowersHtml = '<h3 style="color:#1b2a41;font-size:15px;margin:16px 0 6px;">Currently borrowed by:</h3>' +
            data.active_borrows.map(br=>'<div class="borrower-row"><span><strong>'+br.borrower_name+'</strong> ('+br.borrower_id+') — borrowed '+br.borrow_date+' '+br.borrow_time+'</span><button class="btn-return" onclick="confirmReturn('+br.borrow_id+')">Confirm Return</button></div>').join("");
    }
    const borrowBtn = data.available_qty > 0
        ? '<button class="btn-borrow" onclick="startBorrow()">Borrow this Book → Scan User ID</button>'
        : '';
    panel.innerHTML = '<div class="book-detail">' +
        '<h3>'+b.title+' '+statusBadge+'</h3>' +
        '<div class="book-meta">' +
        '<div><strong>Author</strong>'+(b.author||'-')+'</div>' +
        '<div><strong>ISBN</strong>'+(b.isbn||'-')+'</div>' +
        '<div><strong>Category</strong>'+(b.category||'-')+'</div>' +
        '<div><strong>Shelf / Location</strong>'+(b.shelf_location||'-')+'</div>' +
        '<div><strong>Access Code</strong>'+b.access_code+'</div>' +
        '<div><strong>Times Borrowed</strong>'+(b.times_borrowed||0)+'</div>' +
        '<div><strong>Last Borrowed</strong>'+(b.last_borrowed_date||'-')+'</div>' +
        '</div>' +
        '<div id="awaiting-box" style="display:none;" class="awaiting-box">AWAITING BORROWER SCAN — Scan the Student/Visitor ID barcode now...</div>' +
        '<div class="action-row">'+borrowBtn+'<button class="btn-cancel" onclick="cancelBookFlow()">Clear</button></div>' +
        borrowersHtml + '</div>';
    panel.style.display = "block";
}
function startBorrow(){
    scanState = "awaiting_borrower";
    const ab = document.getElementById("awaiting-box");
    if(ab) ab.style.display = "block";
    setStatus("book-status", "Borrow mode: now scan the borrower's User ID barcode.", "warning");
    showToast("Now scan the borrower's User ID barcode.", "warning");
}
function cancelBookFlow(){
    scanState = "idle"; pendingBook = null;
    renderBookDetail(null);
    setStatus("book-status", "Cancelled. Scan a Book QR to begin.", "info");
}
function confirmReturn(borrowId){
    if(!confirm("Confirm return of this book? This will record the return time.")) return;
    fetch("/api/return-book",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({borrow_id: borrowId})})
    .then(r=>r.json()).then(data=>{
        if(data.success){
            showToast(data.message, "success");
            setStatus("book-status", data.message, "success");
            scanState="idle"; pendingBook=null; renderBookDetail(null);
            loadBorrowHistory();
        }else{
            showToast(data.message||"Return failed.", "error");
        }
    }).catch(err=>showToast("Error: "+err,"error"));
}
function loadTodayRecords(){
    fetch("/get-records").then(r=>r.json()).then(d=>{
        const recs = d.records||[];
        const el = document.getElementById("today-records-table");
        if(!recs.length){el.innerHTML='<p style="text-align:center;color:#64748b;padding:24px;font-size:14px;">No attendance records yet today.</p>';return;}
        el.innerHTML='<table><tr><th>Date</th><th>Full Name</th><th>Department</th><th>Time In</th><th>Time Out</th></tr>'+
            recs.map(r=>'<tr><td><strong>'+r.scan_date+'</strong></td><td>'+r.full_name+'</td><td>'+(r.department||"-")+'</td><td style="color:#1e6b34;font-weight:600;">'+(r.time_in||"-")+'</td><td style="color:#8a1f1f;font-weight:600;">'+(r.time_out||"-")+'</td></tr>').join("")+'</table>';
    }).catch(err=>console.error(err));
}
function loadBorrowHistory(){
    fetch("/get-borrow-records").then(r=>r.json()).then(d=>{
        const recs = (d.records||[]).slice(0,30);
        const el = document.getElementById("borrow-history-table");
        if(!recs.length){el.innerHTML='<p style="text-align:center;color:#64748b;padding:24px;font-size:14px;">No borrow transactions yet.</p>';return;}
        el.innerHTML='<table><tr><th>Book</th><th>Borrower</th><th>Borrowed</th><th>Returned</th><th>Status</th></tr>'+
            recs.map(r=>'<tr><td><strong>'+r.title+'</strong><br><span style="color:#64748b;font-size:11px;">'+r.access_code+'</span></td><td>'+r.borrower+'<br><span style="color:#64748b;font-size:11px;">'+r.borrower_id+'</span></td><td>'+r.borrow_date+' '+r.borrow_time+'</td><td>'+(r.return_date!=="-"?r.return_date+" "+r.return_time:"-")+'</td><td>'+(r.status==="Returned"?'<span class="badge badge-avail">Returned</span>':'<span class="badge badge-borrowed">Borrowed</span>')+'</td></tr>').join("")+'</table>';
    }).catch(err=>console.error(err));
}
function downloadUserBarcode(){
    const barcodeImage = document.getElementById("barcode-img");
    const idNumber = document.getElementById("barcode-id").textContent.replace("ID Number: ", "").trim();
    if(!barcodeImage.src || !idNumber) return;
    const link = document.createElement("a");
    link.href = barcodeImage.src;
    link.download = "barcode_" + idNumber + ".png";
    document.body.appendChild(link); link.click(); link.remove();
}
document.addEventListener("DOMContentLoaded", function(){
    // ---- original registration logic (unchanged) ----
    const form = document.getElementById("register-form");
    const departmentSelect = document.getElementById("dept-select");
    const majorSelect = document.getElementById("major-select");
    const yearSelect = document.getElementById("year-select");
    const idTypeSelect = document.getElementById("id-type-select");
    const studentFields = document.getElementById("student-fields");
    function updateFieldsByIdType(){
        const isStudent = idTypeSelect.value === "Student";
        studentFields.style.display = isStudent ? "" : "none";
        studentFields.querySelectorAll("input, select").forEach(field=>{field.disabled = !isStudent;});
    }
    departmentSelect.addEventListener("change", function(){
        const department = departmentSelect.value;
        majorSelect.innerHTML = '<option value="">-- Select Major --</option>';
        (MAJORS[department]||[]).forEach(function(major){
            const option = document.createElement("option");
            option.value = major; option.textContent = major;
            majorSelect.appendChild(option);
        });
        majorSelect.disabled = (department === "EMPLOYEE" || department === "BPA" || department === "");
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
                document.getElementById("barcode-id").textContent="ID Number: " + formData.get("id_number");
                document.getElementById("barcode-img").src="data:image/png;base64,"+data.barcode;
                form.reset();
                document.getElementById("dept-select").value="";
                updateFieldsByIdType();
            }else{ alert(data.error); }
        }).catch(err=>alert("Error: "+err));
    });
    // ---- scan inputs ----
    document.getElementById("att-scan-input").addEventListener("keypress", e=>{
        if(e.key==="Enter"){handleScannedCode(e.target.value); e.target.value="";}
    });
    document.getElementById("book-scan-input").addEventListener("keypress", e=>{
        if(e.key==="Enter"){handleScannedCode(e.target.value); e.target.value="";}
    });
    // ---- global scanner listener (works ANYWHERE, any tab) ----
    document.addEventListener("keydown", e=>{
        const target = e.target;
        const isEditable = target.matches("input, textarea, select");
        if(isEditable) return; // let input fields handle their own Enter
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
        if(document.getElementById("tab-scan").classList.contains("active")) loadTodayRecords();
    }, 3000);
});
</script>
</body>
</html>
"""


# ============================================================
#  ADMIN FRONTEND — original + Manage Books + Book Records
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
        body{background:#eef0f3;min-height:100vh;}
        .app-container{display:flex;height:100vh;}
        .sidebar{width:270px;background:#1b2a41;display:flex;flex-direction:column;padding:0;position:relative;transition:width 0.25s ease;border-right:1px solid #10192b;}
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
        .main-content{flex:1;padding:28px;overflow-y:auto;}
        .content-header{margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #d8dbe0;}
        .content-header h1{color:#1b2a41;font-size:22px;font-weight:700;font-family:Georgia,'Times New Roman',serif;}
        .content-card{background:#ffffff;border-radius:6px;border:1px solid #d8dbe0;padding:32px;min-height:calc(100vh - 150px);}
        h2{color:#1b2a41;margin-bottom:22px;font-size:18px;font-weight:700;font-family:Georgia,'Times New Roman',serif;border-bottom:1px solid #eef0f3;padding-bottom:14px;}
        h3{font-family:Georgia,'Times New Roman',serif;color:#1b2a41;}
        .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;}
        .form-group{margin-bottom:18px;}
        label{display:block;margin-bottom:7px;color:#374151;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;}
        input,select{width:100%;padding:11px 14px;border:1px solid #d1d5db;border-radius:4px;font-size:14px;transition:border-color 0.2s,box-shadow 0.2s;background:#fafbfc;}
        input:focus,select:focus{outline:none;border-color:#1b2a41;background:white;box-shadow:0 0 0 3px rgba(27,42,65,0.1);}
        button{background:#1b2a41;color:white;border:none;padding:12px 26px;border-radius:4px;font-size:14px;font-weight:600;cursor:pointer;transition:background 0.2s;margin:4px 4px 4px 0;letter-spacing:.2px;}
        button:hover{background:#10192b;}
        .scan-area{text-align:center;padding:36px;background:#f7f8fa;border-radius:6px;margin-bottom:20px;border:1px solid #d8dbe0;}
        #scan-input{font-size:20px;text-align:center;padding:16px;width:100%;max-width:460px;border-radius:4px;border:1px solid #b9c2cf;}
        .status{font-size:16px;font-weight:600;margin-top:18px;padding:16px;border-radius:4px;border-left:4px solid;}
        .success{background:#e8f5ec;color:#1e6b34;border-color:#2f8a4e;}
        .info{background:#eaf1f8;color:#1b4f72;border-color:#3a75a3;}
        .error{background:#fbeaea;color:#8a1f1f;border-color:#c0392b;}
        .warning{background:#fdf6e3;color:#8a6d1f;border-color:#c9a227;}
        table{width:100%;border-collapse:collapse;margin-top:18px;}
        th,td{padding:11px 12px;text-align:left;border:1px solid #e5e7eb;font-size:13px;vertical-align:top;}
        th{background:#1b2a41;color:#fff;font-weight:600;}
        tr:nth-child(even){background:#f7f8fa;}
        tr:hover{background:#eef1f5;}
        .tab-content{display:none;}
        .tab-content.active{display:block;}
        .barcode-img{width:50mm;height:12mm;max-width:100%;margin:18px auto;display:block;padding:0;background:white;border:0;object-fit:contain;image-rendering:crisp-edges;}
        .barcode-id{font-size:18px;font-weight:700;color:#1b2a41;margin:12px 0;}
        .book-qr-img{width:160px;height:160px;object-fit:contain;image-rendering:crisp-edges;margin:10px auto;display:block;background:#fff;border:1px solid #d8dbe0;padding:6px;border-radius:4px;}
        .btn-print{background:#1e6b34;color:white;}
        .btn-print:hover{background:#175628;}
        .btn-barcode{background:#8a6d1f;color:white;padding:7px 16px;font-size:12px;border-radius:4px;}
        .btn-barcode:hover{background:#6e5718;}
        .student-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:18px 0 10px;}
        .student-actions button{margin:0;}
        .student-actions .btn-barcode,.student-actions .btn-download,.student-actions .btn-delete{width:150px;min-height:38px;padding:9px 12px;}
        .student-check{width:17px;height:17px;vertical-align:middle;}
        @media print{body *{visibility:hidden !important;}#barcode-result,#barcode-result *{visibility:visible !important;}#barcode-result{display:block !important;position:absolute;top:0;left:0;width:50mm;height:25mm;margin:0;padding:0;border:1px solid #000;background:#fff;}#barcode-result h3{display:none;}.barcode-img{width:50mm;height:12mm;object-fit:contain;padding:0;border:0;margin:7mm auto 0;}.barcode-id{font-size:8pt;margin:1mm 0 0;}.btn-print{display:none !important;}}
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
        .btn-borrow{background:#1b4f72;color:white;}
        .btn-borrow:hover{background:#143a55;}
        .btn-return{background:#1e6b34;color:white;padding:8px 16px;font-size:12px;border-radius:4px;}
        .btn-return:hover{background:#175628;}
        .edit-modal{position:fixed;inset:0;background:rgba(15,25,43,.58);display:flex;align-items:center;justify-content:center;padding:20px;z-index:100;}
        .edit-modal.hidden{display:none;}
        .edit-dialog{background:#fff;width:100%;max-width:760px;max-height:90vh;overflow-y:auto;border-radius:6px;box-shadow:0 12px 40px rgba(15,25,43,.3);padding:28px;}
        .edit-dialog-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px;border-bottom:1px solid #eef0f3;padding-bottom:14px;}
        .edit-dialog-header h3{margin:0;}
        .edit-close{background:#5b6472;padding:7px 12px;margin:0;font-size:18px;line-height:1;}
        .edit-close:hover{background:#464d59;}
        .hidden{display:none !important;}
        .dept-tabs{display:flex;gap:8px;margin:18px 0;flex-wrap:wrap;}
        .dept-tab{padding:9px 16px;background:#f1f3f6;color:#374151;border:1px solid #d8dbe0;border-radius:4px;cursor:pointer;font-weight:600;transition:all 0.2s;font-size:13px;}
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
        .book-detail{background:#f7f8fa;border:1px solid #d8dbe0;border-radius:6px;padding:22px;margin-top:18px;}
        .book-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px 18px;margin:12px 0 16px;font-size:13px;}
        .book-meta div strong{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#64748b;margin-bottom:2px;}
        .borrower-row{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#fff;border:1px solid #e5e7eb;border-radius:4px;margin-top:8px;font-size:13px;flex-wrap:wrap;gap:8px;}
        .awaiting-box{background:#fdf6e3;border:2px dashed #c9a227;border-radius:6px;padding:16px;text-align:center;margin-top:14px;font-weight:600;color:#8a6d1f;}
        .qr-result{display:none;margin-top:24px;text-align:center;padding:24px;background:#f7f8fa;border-radius:6px;border:1px solid #d8dbe0;}
        .action-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;}
        @media(max-width:900px){
            .sidebar{width:74px;}
            .sidebar-header .full-title,.sidebar-header p,.menu-item span.label{display:none;}
            .menu-item{justify-content:center;padding:12px 0;}
            .form-row{grid-template-columns:1fr;}
            .main-content{padding:14px;}
            .content-card{padding:20px;}
        }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="sidebar" id="sidebar">
            <button class="toggle-btn" onclick="toggleSidebar()">◀</button>
            <div class="sidebar-header">
                <div class="brand-mark">SLSU<br>JGE</div>
                <h2 class="full-title">Library System</h2>
                <p>Full Administration</p>
            </div>
            <div class="sidebar-menu">
                <div class="menu-item active" onclick="showContent('scan')"><span class="badge">01</span> <span class="label">Scan / Attendance</span></div>
                <div class="menu-item" onclick="showContent('register')"><span class="badge">02</span> <span class="label">Register User</span></div>
                <div class="menu-item" onclick="showContent('students')"><span class="badge">03</span> <span class="label">Students List</span></div>
                <div class="menu-item" onclick="showContent('records')"><span class="badge">04</span> <span class="label">Daily Records</span></div>
                <div class="menu-item" onclick="showContent('history')"><span class="badge">05</span> <span class="label">Monthly History</span></div>
                <div class="menu-item" onclick="showContent('books')"><span class="badge">06</span> <span class="label">Manage Books</span></div>
                <div class="menu-item" onclick="showContent('bookrecords')"><span class="badge">07</span> <span class="label">Book Records</span></div>
                <div class="menu-item" onclick="showContent('export')"><span class="badge">08</span> <span class="label">Export Reports</span></div>
                <div class="menu-item" onclick="showContent('privacy')"><span class="badge">09</span> <span class="label">Privacy Policy</span></div>
            </div>
            <div class="sidebar-footer"><button class="logout-btn" onclick="logout()">Log Out</button></div>
        </div>
        <div class="main-content">
            <div class="content-header"><h1 id="page-title">Scan / Attendance</h1></div>
            <div class="content-card">
                <!-- 01 SCAN / ATTENDANCE (smart: book QR + user ID) -->
                <div id="scan" class="tab-content active">
                    <h2>Scan — Book QR or User ID</h2>
                    <div class="scan-area">
                        <input type="text" id="scan-input" placeholder="Scan Book QR or User ID barcode..." autofocus>
                        <div id="status-box" class="status info">Waiting for scan... Scan a Book QR for borrow/return, or a User ID for Time In/Out.</div>
                    </div>
                    <div id="admin-book-detail" style="display:none;"></div>
                </div>
                <!-- 02 REGISTER USER (unchanged) -->
                <div id="register" class="tab-content">
                    <h2>Register New User</h2>
                    <form id="register-form">
                        <div class="form-row">
                            <div class="form-group"><label>ID Type *</label>
                                <select name="id_type" id="id-type-select" required>
                                    <option value="Student">Student</option><option value="Employee">Employee</option><option value="Visitor">Visitor</option>
                                </select></div>
                            <div class="form-group"><label>ID Number *</label><input type="text" name="id_number" required placeholder="e.g. 2024-0001"></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>Full Name *</label><input type="text" name="full_name" required placeholder="Last, First Middle"></div>
                            <div class="form-group" id="student-department-group"><label>Department</label>
                                <select name="department" id="dept-select">
                                    <option value="">-- Select Department --</option><option value="CT">BSIT</option><option value="BSED">BSED</option><option value="BEED">BEED</option><option value="BSFAS">BSFAS</option><option value="BSBA">BSBA</option><option value="BPA">BPA</option><option value="EMPLOYEE">EMPLOYEE</option>
                                </select></div>
                        </div>
                        <div class="form-row" id="major-row">
                            <div class="form-group"><label>Major / Specialization</label><select name="major" id="major-select"><option value="">-- Select Department First --</option></select></div>
                            <div class="form-group" id="student-year-group"><label>Year Level</label>
                                <select name="year_level" id="year-select"><option value="1st Year">1st Year</option><option value="2nd Year">2nd Year</option><option value="3rd Year">3rd Year</option><option value="4th Year">4th Year</option><option value="N/A">N/A — Not Applicable</option></select></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>Contact Number</label><input type="text" name="contact_number" required placeholder="09XX-XXX-XXXX"></div>
                            <div class="form-group"><label>Complete Address</label><input type="text" name="address" required placeholder="City, Province"></div>
                        </div>
                        <button type="submit" class="btn-primary">Register &amp; Generate Barcode</button>
                    </form>
                    <div id="barcode-result" style="display:none;margin-top:28px;text-align:center;padding:26px;background:#f7f8fa;border-radius:6px;border:1px solid #d8dbe0;">
                        <h3>Registration Successful</h3>
                        <p id="barcode-id" class="barcode-id"></p>
                        <img id="barcode-img" class="barcode-img"><br><br>
                        <button class="btn-print" onclick="window.print()">Print Barcode</button>
                        <button class="btn-download" onclick="downloadRegisteredBarcode()">Download Barcode</button>
                    </div>
                </div>
                <!-- 03 STUDENTS LIST (unchanged) -->
                <div id="students" class="tab-content">
                    <h2>Registered Users — By Department</h2>
                    <div class="search-box"><input type="text" id="search-input" placeholder="Search by Name or ID Number..." oninput="filterStudents()"></div>
                    <div class="dept-tabs">
                        <button class="dept-tab active" id="dept-ALL" onclick="switchDept('ALL')">ALL</button>
                        <button class="dept-tab" id="dept-CT" onclick="switchDept('CT')">CT</button>
                        <button class="dept-tab" id="dept-BSED" onclick="switchDept('BSED')">BSED</button>
                        <button class="dept-tab" id="dept-BEED" onclick="switchDept('BEED')">BEED</button>
                        <button class="dept-tab" id="dept-BSFAS" onclick="switchDept('BSFAS')">BSFAS</button>
                        <button class="dept-tab" id="dept-BSBA" onclick="switchDept('BSBA')">BSBA</button>
                        <button class="dept-tab" id="dept-EMPLOYEE" onclick="switchDept('EMPLOYEE')">EMPLOYEE</button>
                        <button class="dept-tab" id="dept-Visitor" onclick="switchDept('Visitor')">VISITOR</button>
                    </div>
                    <button onclick="loadStudents()">Refresh List</button>
                    <div class="student-actions">
                        <button class="btn-barcode" id="choose-barcode-btn" onclick="enableBarcodeSelection()">Select Students</button>
                        <div id="barcode-selection-actions" class="hidden">
                            <label style="text-transform:none;font-size:13px;margin:0;font-weight:600;"><input class="student-check" type="checkbox" id="select-all-students" onchange="toggleAllStudents(this.checked)"> Select All</label>
                            <button class="btn-barcode" onclick="printSelectedBarcodes()">Print Selected</button>
                            <button class="btn-download" onclick="downloadSelectedBarcodes()">Download Selected</button>
                            <button class="btn-delete" onclick="deleteSelectedStudents()">Delete Selected</button>
                            <button class="btn-cancel" onclick="disableBarcodeSelection()">Cancel</button>
                        </div>
                    </div>
                    <div id="students-table"></div>
                    <div id="edit-form-container" class="edit-modal hidden" onclick="if(event.target===this) hideEditForm()">
                        <div class="edit-dialog">
                            <div class="edit-dialog-header"><h3>Edit User Information</h3><button type="button" class="edit-close" onclick="hideEditForm()">&times;</button></div>
                            <form id="edit-form">
                                <input type="hidden" id="edit-id" name="id">
                                <div class="form-row">
                                    <div class="form-group"><label>ID Type</label><select id="edit-id-type" name="id_type"><option value="Student">Student</option><option value="Employee">Employee</option><option value="Visitor">Visitor</option></select></div>
                                    <div class="form-group"><label>ID Number</label><input type="text" id="edit-idnum" name="id_number" required></div>
                                </div>
                                <div class="form-row">
                                    <div class="form-group"><label>Full Name</label><input type="text" id="edit-fullname" name="full_name" required></div>
                                    <div class="form-group"><label>Department</label><select id="edit-dept" name="department"><option value="">-- Select --</option><option value="CT">BSIT / Computer Technology</option><option value="BSED">BSED</option><option value="BEED">BEED</option><option value="BSFAS">BSFAS</option><option value="BSBA">BSBA</option><option value="BPA">BPA</option><option value="EMPLOYEE">EMPLOYEE</option></select></div>
                                </div>
                                <div class="form-row">
                                    <div class="form-group"><label>Major / Specialization</label><select id="edit-major" name="major"></select></div>
                                    <div class="form-group"><label>Year Level</label><select id="edit-year" name="year_level"><option value="1st Year">1st Year</option><option value="2nd Year">2nd Year</option><option value="3rd Year">3rd Year</option><option value="4th Year">4th Year</option><option value="N/A">N/A</option></select></div>
                                </div>
                                <div class="form-row">
                                    <div class="form-group"><label>Contact Number</label><input type="text" id="edit-contact" name="contact_number"></div>
                                    <div class="form-group"><label>Complete Address</label><input type="text" id="edit-address" name="address"></div>
                                </div>
                                <button type="submit" class="btn-save">Save Changes</button>
                                <button type="button" class="btn-cancel" onclick="hideEditForm()">Cancel</button>
                            </form>
                        </div>
                    </div>
                </div>
                <!-- 04 DAILY RECORDS -->
                <div id="records" class="tab-content">
                    <h2>Today's Attendance Records</h2>
                    <button onclick="loadRecords()">Refresh Records</button>
                    <div id="records-table"></div>
                </div>
                <!-- 05 MONTHLY HISTORY -->
                <div id="history" class="tab-content">
                    <h2>Attendance History</h2>
                    <div class="month-filter">
                        <label style="margin-bottom:0;">Month:</label>
                        <select id="month-select" onchange="loadMonthlyHistory()">
                            <option value="2026-01">January 2026</option><option value="2026-02">February 2026</option><option value="2026-03">March 2026</option><option value="2026-04">April 2026</option><option value="2026-05">May 2026</option><option value="2026-06">June 2026</option><option value="2026-07">July 2026</option><option value="2026-08">August 2026</option><option value="2026-09" selected>September 2026</option><option value="2026-10">October 2026</option><option value="2026-11">November 2026</option><option value="2026-12">December 2026</option>
                        </select>
                        <label style="margin-bottom:0;">Specific day:</label><input type="date" id="history-date" onchange="loadMonthlyHistory()">
                        <button class="btn-month-print" onclick="printDailyReport()">Print Daily</button>
                        <button class="btn-month-print" onclick="printMonthlyReport()">Print Monthly</button>
                        <button class="btn-download" onclick="downloadMonthlyReport()">Download Word</button>
                        <select id="delete-history-date"><option value="">Select day to delete</option></select>
                        <button class="btn-delete-daily" onclick="deleteDailyHistory()">Delete Daily History</button>
                    </div>
                    <p style="font-size:13px;color:#64748b;margin:8px 0 18px;">Choose a month to view monthly records, or choose a specific date.</p>
                    <button onclick="loadMonthlyHistory()">Load Records</button>
                    <div id="history-table"></div>
                </div>
                <!-- 06 MANAGE BOOKS (NEW) -->
                <div id="books" class="tab-content">
                    <h2>Register New Book</h2>
                    <form id="book-form">
                        <div class="form-row">
                            <div class="form-group"><label>Title *</label><input type="text" name="title" required placeholder="Book title"></div>
                            <div class="form-group"><label>Author</label><input type="text" name="author" placeholder="Author name"></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>ISBN</label><input type="text" name="isbn" placeholder="ISBN (optional)"></div>
                            <div class="form-group"><label>Category</label><input type="text" name="category" placeholder="e.g. Fiction, Science, Math"></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group"><label>Shelf / Location</label><input type="text" name="shelf_location" placeholder="e.g. Shelf A-3"></div>
                            <div class="form-group"><label>Quantity</label><input type="number" name="quantity" value="1" min="1"></div>
                        </div>
                        <button type="submit" class="btn-save">Register Book &amp; Generate QR</button>
                    </form>
                    <div id="book-qr-result" class="qr-result">
                        <h3>Book Registered — QR Code Generated</h3>
                        <p id="book-qr-title" style="font-weight:600;color:#1b2a41;margin-top:8px;"></p>
                        <p id="book-qr-code" style="font-size:13px;color:#64748b;"></p>
                        <img id="book-qr-img" class="book-qr-img">
                        <div class="action-row" style="justify-content:center;">
                            <button class="btn-print" onclick="printBookQR()">Print QR</button>
                            <button class="btn-download" onclick="downloadBookQR()">Download QR</button>
                        </div>
                    </div>
                    <h2 style="margin-top:32px;">All Books</h2>
                    <div class="search-box"><input type="text" id="book-search" placeholder="Search by title, author, ISBN, or code..." oninput="filterBooks()"></div>
                    <div class="filter-row">
                        <label style="margin-bottom:0;font-size:13px;">Status:</label>
                        <select id="book-status-filter" onchange="filterBooks()"><option value="">All</option><option value="Available">Available</option><option value="Borrowed">Fully Borrowed</option></select>
                        <label style="margin-bottom:0;font-size:13px;">Sort:</label>
                        <select id="book-sort" onchange="filterBooks()"><option value="title">Title A-Z</option><option value="most_borrowed">Most Borrowed</option><option value="recent">Recently Added</option></select>
                        <button onclick="loadBooks()">Refresh</button>
                        <button class="btn-barcode" id="choose-book-qr-btn" onclick="enableBookQRSelection()">Select Books for QR</button>
                        <div id="book-qr-actions" class="hidden">
                            <label style="text-transform:none;font-size:13px;margin:0;font-weight:600;"><input class="student-check" type="checkbox" id="select-all-books" onchange="toggleAllBooks(this.checked)"> Select All</label>
                            <button class="btn-download" onclick="downloadSelectedBookQRs()">Download QR PDF</button>
                            <button class="btn-delete" onclick="deleteSelectedBooks()">Delete Selected</button>
                            <button class="btn-cancel" onclick="disableBookQRSelection()">Cancel</button>
                        </div>
                    </div>
                    <div id="books-table"></div>
                    <div id="book-edit-modal" class="edit-modal hidden" onclick="if(event.target===this) hideBookEdit()">
                        <div class="edit-dialog">
                            <div class="edit-dialog-header"><h3>Edit Book</h3><button type="button" class="edit-close" onclick="hideBookEdit()">&times;</button></div>
                            <form id="book-edit-form">
                                <input type="hidden" id="book-edit-id" name="id">
                                <div class="form-row"><div class="form-group"><label>Title *</label><input type="text" id="book-edit-title" name="title" required></div><div class="form-group"><label>Author</label><input type="text" id="book-edit-author" name="author"></div></div>
                                <div class="form-row"><div class="form-group"><label>ISBN</label><input type="text" id="book-edit-isbn" name="isbn"></div><div class="form-group"><label>Category</label><input type="text" id="book-edit-category" name="category"></div></div>
                                <div class="form-row"><div class="form-group"><label>Shelf / Location</label><input type="text" id="book-edit-shelf" name="shelf_location"></div><div class="form-group"><label>Quantity</label><input type="number" id="book-edit-qty" name="quantity" min="1"></div></div>
                                <button type="submit" class="btn-save">Save Changes</button>
                                <button type="button" class="btn-cancel" onclick="hideBookEdit()">Cancel</button>
                            </form>
                        </div>
                    </div>
                </div>
                <!-- 07 BOOK RECORDS (NEW) -->
                <div id="bookrecords" class="tab-content">
                    <h2>Borrow &amp; Return Records</h2>
                    <div class="filter-row">
                        <label style="margin-bottom:0;font-size:13px;">Date:</label><input type="date" id="br-date" onchange="loadBorrowRecords()">
                        <label style="margin-bottom:0;font-size:13px;">Borrower:</label><input type="text" id="br-borrower" placeholder="Name or ID" style="max-width:180px;" oninput="loadBorrowRecords()">
                        <label style="margin-bottom:0;font-size:13px;">Status:</label>
                        <select id="br-status" onchange="loadBorrowRecords()"><option value="">All</option><option value="Borrowed">Currently Borrowed</option><option value="Returned">Returned</option></select>
                        <button onclick="loadBorrowRecords()">Refresh</button>
                    </div>
                    <div id="borrow-records-table"></div>
                </div>
                <!-- 08 EXPORT -->
                <div id="export" class="tab-content">
                    <h2>Export &amp; Print Reports</h2>
                    <p style="font-size:15px;color:#64748b;margin-bottom:22px;">Download today's complete attendance as a Microsoft Word document or print directly.</p>
                    <button class="btn-download" onclick="window.location.href='/download-word'">Download Today's Attendance Report</button><br><br>
                    <button class="btn-print" onclick="window.print()">Print Page</button>
                </div>
                <!-- 09 PRIVACY -->
                <div id="privacy" class="tab-content">
                    <iframe class="privacy-frame" src="/privacy" title="Privacy Policy"></iframe>
                </div>
            </div>
        </div>
    </div>
<script>
const MAJORS = {"BSBA":["Marketing Management","Financial Management"],"BSED":["English","Mathematics","Science"],"CT":["Computer Technology","Food Technology","BINDTECH","CULINARY"]};
const PAGE_TITLES = {scan:"Scan / Attendance",register:"Register New User",students:"Registered Users",records:"Daily Attendance Records",history:"Monthly Attendance History",books:"Manage Books",bookrecords:"Book Borrow Records",export:"Export & Print Reports",privacy:"Privacy Policy"};
const MENU_ORDER = ["scan","register","students","records","history","books","bookrecords","export","privacy"];
let editingStudentId=null, currentDept="ALL", allStudents=[], barcodeSelectionMode=false;
let scannerBuffer="", scannerLastKeyAt=0, scannerResetTimer=null, recordsRefreshInProgress=false;
let scanState="idle", pendingBook=null;
let allBooks=[], bookQRSelectionMode=false, lastBookQRCode=null;

function toggleSidebar(){const s=document.getElementById("sidebar");s.classList.toggle("collapsed");s.querySelector(".toggle-btn").textContent=s.classList.contains("collapsed")?"▶":"◀";}
function logout(){document.cookie="logged_in=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";document.cookie="role=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";window.location.href="/login";}
function showContent(pageId){
    document.querySelectorAll(".menu-item").forEach(i=>i.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t=>t.classList.remove("active"));
    const idx=MENU_ORDER.indexOf(pageId);
    if(idx!==-1) document.querySelectorAll(".menu-item")[idx].classList.add("active");
    const t=document.getElementById(pageId); if(t) t.classList.add("active");
    document.getElementById("page-title").textContent=PAGE_TITLES[pageId]||"Library System";
    if(pageId==="scan") setTimeout(()=>document.getElementById("scan-input")?.focus(),100);
    if(pageId==="students") loadStudents();
    if(pageId==="records") loadRecords();
    if(pageId==="history") loadMonthlyHistory();
    if(pageId==="books") loadBooks();
    if(pageId==="bookrecords") loadBorrowRecords();
}
function setStatus(msg,type){const b=document.getElementById("status-box");if(b){b.className="status "+type;b.textContent=msg;}}
function submitScan(){const i=document.getElementById("scan-input");const v=i.value.trim();if(v){handleScannedCode(v);i.value="";}}
function handleScannedCode(code){
    code=(code||"").trim(); if(!code) return;
    if(scanState==="awaiting_borrower" && pendingBook){
        fetch("/api/borrow-book",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({book_id:pendingBook.id,id_number:code})})
        .then(r=>r.json()).then(d=>{
            if(d.success){setStatus(d.message,"success");scanState="idle";pendingBook=null;renderAdminBookDetail(null);}
            else{setStatus(d.message||"Borrow failed.","error");}
        }).catch(e=>setStatus("Error: "+e,"error"));
        return;
    }
    fetch("/api/smart-scan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code:code})})
    .then(r=>r.json()).then(d=>{
        if(!d.success){setStatus(d.message||"Not found.","error");return;}
        if(d.type==="attendance"){setStatus(d.message,"success");}
        else if(d.type==="book"){
            showContent("scan");
            pendingBook=d.book;
            renderAdminBookDetail(d);
            setStatus("Book found: "+d.book.title+" — "+d.status,"info");
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
            data.active_borrows.map(br=>'<div class="borrower-row"><span><strong>'+br.borrower_name+'</strong> ('+br.borrower_id+') — '+br.borrow_date+' '+br.borrow_time+'</span><button class="btn-return" onclick="confirmReturn('+br.borrow_id+')">Confirm Return</button></div>').join("");
    }
    const borrowBtn=data.available_qty>0?'<button class="btn-borrow" onclick="startAdminBorrow()">Borrow this Book → Scan User ID</button>':'';
    panel.innerHTML='<div class="book-detail"><h3>'+b.title+' '+badge+'</h3>'+
        '<div class="book-meta">'+
        '<div><strong>Author</strong>'+(b.author||'-')+'</div><div><strong>ISBN</strong>'+(b.isbn||'-')+'</div><div><strong>Category</strong>'+(b.category||'-')+'</div><div><strong>Shelf</strong>'+(b.shelf_location||'-')+'</div><div><strong>Code</strong>'+b.access_code+'</div><div><strong>Times Borrowed</strong>'+(b.times_borrowed||0)+'</div><div><strong>Last Borrowed</strong>'+(b.last_borrowed_date||'-')+'</div></div>'+
        '<div id="admin-awaiting" style="display:none;" class="awaiting-box">AWAITING BORROWER — Scan the Student/Visitor ID barcode now...</div>'+
        '<div class="action-row">'+borrowBtn+'<button class="btn-cancel" onclick="cancelAdminBookFlow()">Clear</button></div>'+borrowers+'</div>';
    panel.style.display="block";
}
function startAdminBorrow(){scanState="awaiting_borrower";const a=document.getElementById("admin-awaiting");if(a)a.style.display="block";setStatus("Borrow mode: now scan the borrower's User ID barcode.","warning");}
function cancelAdminBookFlow(){scanState="idle";pendingBook=null;renderAdminBookDetail(null);setStatus("Cancelled. Scan a Book QR or User ID.","info");}
function confirmReturn(borrowId){
    if(!confirm("Confirm return of this book? Return time will be recorded.")) return;
    fetch("/api/return-book",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({borrow_id:borrowId})})
    .then(r=>r.json()).then(d=>{
        if(d.success){setStatus(d.message,"success");scanState="idle";pendingBook=null;renderAdminBookDetail(null);}
        else setStatus(d.message||"Return failed.","error");
    }).catch(e=>setStatus("Error: "+e,"error"));
}
function switchDept(d){document.querySelectorAll(".dept-tab").forEach(t=>t.classList.remove("active"));document.getElementById("dept-"+d).classList.add("active");currentDept=d;filterStudents();}
function updateMajorOptions(ds,ms,ys){const dept=document.getElementById(ds).value;const m=document.getElementById(ms);m.innerHTML='<option value="">-- Select Major --</option>';const y=ys?document.getElementById(ys):null;if(y)y.disabled=false;if(dept==="Visitor"||dept==="EMPLOYEE"||dept==="BPA"||!dept){m.disabled=true;return;}m.disabled=false;(MAJORS[dept]||[]).forEach(x=>{const o=document.createElement("option");o.value=x;o.textContent=x;m.appendChild(o);});}
function updateAdminFieldsByIdType(){const is=document.getElementById("id-type-select").value==="Student";["student-department-group","major-row","student-year-group"].forEach(id=>{const e=document.getElementById(id);if(e)e.style.display=is?"":"none";});["dept-select","major-select","year-select"].forEach(id=>{const f=document.getElementById(id);if(f)f.disabled=!is;});}
function loadStudents(){fetch("/get-students").then(r=>r.json()).then(d=>{allStudents=d.students||[];filterStudents();}).catch(e=>alert("Load Error: "+e));}
function filterStudents(){
    const s=(document.getElementById("search-input")?.value||"").toLowerCase();
    let f=allStudents;
    if(currentDept!=="ALL") f=f.filter(x=>x.department===currentDept||(currentDept==="Visitor"&&x.id_type==="Visitor"));
    if(s) f=f.filter(x=>x.full_name.toLowerCase().includes(s)||x.id_number.toLowerCase().includes(s));
    const t=document.getElementById("students-table");
    if(f.length){t.innerHTML='<table><tr>'+(barcodeSelectionMode?'<th>Select</th>':'')+'<th>ID Number</th><th>Full Name</th><th>Type</th><th>Department</th><th>Major</th><th>Action</th></tr>'+
        f.map(x=>'<tr>'+(barcodeSelectionMode?'<td><input class="student-check student-row-check" type="checkbox" value="'+x.id_number+'"></td>':'')+'<td><strong>'+x.id_number+'</strong></td><td>'+x.full_name+'</td><td>'+x.id_type+'</td><td>'+x.department_display+'</td><td>'+(x.major||"-")+'</td><td><button class="btn-edit" onclick="editStudent('+x.id+')">Edit</button></td></tr>').join("")+'</table>';}
    else t.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No records found.</p>';
}
function enableBarcodeSelection(){barcodeSelectionMode=true;document.getElementById("choose-barcode-btn").classList.add("hidden");document.getElementById("barcode-selection-actions").classList.remove("hidden");document.getElementById("select-all-students").checked=false;filterStudents();}
function disableBarcodeSelection(){barcodeSelectionMode=false;document.getElementById("choose-barcode-btn").classList.remove("hidden");document.getElementById("barcode-selection-actions").classList.add("hidden");filterStudents();}
function toggleAllStudents(c){document.querySelectorAll(".student-row-check").forEach(x=>x.checked=c);}
function printSelectedBarcodes(){
    const sel=Array.from(document.querySelectorAll(".student-row-check:checked")).map(x=>x.value);
    if(!sel.length){alert("Please select at least one student.");return;}
    const w=window.open("","_blank","width=600,height=800");if(!w){alert("Allow pop-ups.");return;}
    const m=sel.map(id=>'<section class="bi"><div>Student Number: '+id+'</div><img src="/barcode/'+encodeURIComponent(id)+'"></section>').join("");
    w.document.write('<!DOCTYPE html><html><head><style>*{box-sizing:border-box}@page{size:A4;margin:1mm}body{font-family:Arial;text-align:center;display:grid;grid-template-columns:repeat(4,50mm);grid-auto-rows:25mm;gap:2mm;justify-content:center}.bi{width:50mm;height:25mm;border:1px solid #000;font-size:8pt;display:flex;flex-direction:column;align-items:center;padding:1mm 0}.bi img{width:50mm;height:12mm;object-fit:contain;image-rendering:crisp-edges;margin:1mm auto 0;display:block}</style></head><body>'+m+'</body></html>');
    w.document.close();const imgs=w.document.images;let n=0;const pw=()=>{n++;if(n===imgs.length)w.print();};Array.from(imgs).forEach(i=>{i.onload=pw;i.onerror=pw;});
}
function downloadSelectedBarcodes(){
    const sel=Array.from(document.querySelectorAll(".student-row-check:checked")).map(x=>x.value);
    if(!sel.length){alert("Please select at least one student.");return;}
    fetch("/download-barcodes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id_numbers:sel})})
    .then(r=>{if(!r.ok)throw new Error("Download failed.");return r.blob();}).then(b=>{const l=document.createElement("a");const u=URL.createObjectURL(b);l.href=u;l.download="student_barcodes.pdf";document.body.appendChild(l);l.click();l.remove();URL.revokeObjectURL(u);}).catch(e=>alert(e.message));
}
function deleteSelectedStudents(){
    const sel=Array.from(document.querySelectorAll(".student-row-check:checked")).map(x=>x.value);
    if(!sel.length){alert("Please select at least one student.");return;}
    if(!confirm("Delete "+sel.length+" selected user(s)? Their attendance and borrow records will also be deleted.")) return;
    fetch("/delete-students",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id_numbers:sel})})
    .then(r=>r.json().then(d=>({ok:r.ok,d}))).then(res=>{if(!res.ok)throw new Error(res.d.error||"Delete failed.");alert(res.d.deleted_count+" user(s) deleted.");disableBarcodeSelection();loadStudents();}).catch(e=>alert(e.message));
}
function editStudent(id){const s=allStudents.find(x=>x.id===id);if(!s)return;editingStudentId=id;document.getElementById("edit-id").value=s.id;document.getElementById("edit-id-type").value=s.id_type;document.getElementById("edit-idnum").value=s.id_number;document.getElementById("edit-fullname").value=s.full_name;document.getElementById("edit-dept").value=s.department||"";document.getElementById("edit-major").value=s.major||"";document.getElementById("edit-year").value=s.year_level||"";document.getElementById("edit-contact").value=s.contact_number||"";document.getElementById("edit-address").value=s.address||"";document.getElementById("edit-form-container").classList.remove("hidden");}
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
function downloadRegisteredBarcode(){const i=document.getElementById("barcode-img");const n=document.getElementById("barcode-id").textContent.replace("ID Number: ","").trim();if(!i.src||!n)return;const l=document.createElement("a");l.href=i.src;l.download="barcode_"+n+".png";document.body.appendChild(l);l.click();l.remove();}
function loadBooks(){fetch("/get-books").then(r=>r.json()).then(d=>{allBooks=d.books||[];filterBooks();}).catch(e=>alert("Load Error: "+e));}
function filterBooks(){
    const s=(document.getElementById("book-search")?.value||"").toLowerCase();
    const st=document.getElementById("book-status-filter")?.value||"";
    const sort=document.getElementById("book-sort")?.value||"title";
    let f=allBooks.slice();
    if(s) f=f.filter(b=>b.title.toLowerCase().includes(s)||(b.author||"").toLowerCase().includes(s)||(b.isbn||"").toLowerCase().includes(s)||b.access_code.toLowerCase().includes(s));
    if(st==="Available") f=f.filter(b=>b.available_qty>0);
    if(st==="Borrowed") f=f.filter(b=>b.available_qty<=0);
    if(sort==="most_borrowed") f.sort((a,b)=>b.times_borrowed-a.times_borrowed);
    else if(sort==="recent") f.sort((a,b)=>b.id-a.id);
    else f.sort((a,b)=>a.title.localeCompare(b.title));
    const t=document.getElementById("books-table");
    if(f.length){t.innerHTML='<table><tr>'+(bookQRSelectionMode?'<th>Sel</th>':'')+'<th>Code</th><th>Title</th><th>Author</th><th>Category</th><th>Shelf</th><th>Qty</th><th>Status</th><th>Borrowed</th><th>Last Borrowed</th><th>Action</th></tr>'+
        f.map(b=>'<tr>'+(bookQRSelectionMode?'<td><input class="student-check book-row-check" type="checkbox" value="'+b.id+'"></td>':'')+
        '<td><strong>'+b.access_code+'</strong></td><td>'+b.title+'</td><td>'+(b.author||"-")+'</td><td>'+(b.category||"-")+'</td><td>'+(b.shelf_location||"-")+'</td><td>'+b.available_qty+'/'+b.quantity+'</td>'+
        '<td>'+(b.available_qty>0?'<span class="badge badge-avail">Available</span>':'<span class="badge badge-borrowed">Borrowed</span>')+'</td>'+
        '<td>'+b.times_borrowed+'</td><td>'+b.last_borrowed_date+'</td>'+
        '<td><button class="btn-barcode" onclick="viewBookQR(\\''+b.access_code+'\\')">QR</button> <button class="btn-edit" onclick="editBook('+b.id+')">Edit</button></td></tr>').join("")+'</table>';}
    else t.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No books found.</p>';
}
function viewBookQR(code){lastBookQRCode=code;const w=window.open("","_blank","width=400,height=500");if(!w){alert("Allow pop-ups.");return;}w.document.write('<!DOCTYPE html><html><head><title>Book QR '+code+'</title><style>body{font-family:Arial;text-align:center;padding:20px}img{width:200px;height:200px}h2{font-size:14px}</style></head><body><h2>'+code+'</h2><img src="/book-qr/'+encodeURIComponent(code)+'" onload="window.print()"></body></html>');w.document.close();}
function enableBookQRSelection(){bookQRSelectionMode=true;document.getElementById("choose-book-qr-btn").classList.add("hidden");document.getElementById("book-qr-actions").classList.remove("hidden");document.getElementById("select-all-books").checked=false;filterBooks();}
function disableBookQRSelection(){bookQRSelectionMode=false;document.getElementById("choose-book-qr-btn").classList.remove("hidden");document.getElementById("book-qr-actions").classList.add("hidden");filterBooks();}
function toggleAllBooks(c){document.querySelectorAll(".book-row-check").forEach(x=>x.checked=c);}
function downloadSelectedBookQRs(){
    const sel=Array.from(document.querySelectorAll(".book-row-check:checked")).map(x=>parseInt(x.value));
    if(!sel.length){alert("Select at least one book.");return;}
    fetch("/download-book-qrcodes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({book_ids:sel})})
    .then(r=>{if(!r.ok)throw new Error("Download failed.");return r.blob();}).then(b=>{const l=document.createElement("a");const u=URL.createObjectURL(b);l.href=u;l.download="book_qrcodes.pdf";document.body.appendChild(l);l.click();l.remove();URL.revokeObjectURL(u);}).catch(e=>alert(e.message));
}
function deleteSelectedBooks(){
    const sel=Array.from(document.querySelectorAll(".book-row-check:checked")).map(x=>parseInt(x.value));
    if(!sel.length){alert("Select at least one book.");return;}
    if(!confirm("Delete "+sel.length+" selected book(s) and their borrow history?")) return;
    fetch("/delete-book",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({book_ids:sel})})
    .then(r=>r.json().then(d=>({ok:r.ok,d}))).then(res=>{if(!res.ok)throw new Error(res.d.error||"Delete failed.");alert(res.d.deleted_count+" book(s) deleted.");disableBookQRSelection();loadBooks();}).catch(e=>alert(e.message));
}
function editBook(id){const b=allBooks.find(x=>x.id===id);if(!b)return;document.getElementById("book-edit-id").value=b.id;document.getElementById("book-edit-title").value=b.title;document.getElementById("book-edit-author").value=b.author||"";document.getElementById("book-edit-isbn").value=b.isbn||"";document.getElementById("book-edit-category").value=b.category||"";document.getElementById("book-edit-shelf").value=b.shelf_location||"";document.getElementById("book-edit-qty").value=b.quantity;document.getElementById("book-edit-modal").classList.remove("hidden");}
function hideBookEdit(){document.getElementById("book-edit-modal").classList.add("hidden");document.getElementById("book-edit-form").reset();}
function printBookQR(){if(!lastBookQRCode)return;const w=window.open("","_blank","width=400,height=500");if(!w){alert("Allow pop-ups.");return;}w.document.write('<!DOCTYPE html><html><head><title>Book QR</title><style>body{font-family:Arial;text-align:center;padding:20px}img{width:200px;height:200px}h2{font-size:14px}</style></head><body><h2>'+lastBookQRCode+'</h2><img src="/book-qr/'+encodeURIComponent(lastBookQRCode)+'" onload="window.print()"></body></html>');w.document.close();}
function downloadBookQR(){if(!lastBookQRCode)return;window.location.href="/book-qr/"+encodeURIComponent(lastBookQRCode);}
function loadBorrowRecords(){
    const date=document.getElementById("br-date")?.value||"";
    const borrower=document.getElementById("br-borrower")?.value||"";
    const status=document.getElementById("br-status")?.value||"";
    let q="/get-borrow-records?";if(date)q+="date="+encodeURIComponent(date)+"&";if(borrower)q+="borrower="+encodeURIComponent(borrower)+"&";if(status)q+="status="+encodeURIComponent(status)+"&";
    fetch(q).then(r=>r.json()).then(d=>{
        const recs=d.records||[];const t=document.getElementById("borrow-records-table");
        if(recs.length){t.innerHTML='<table><tr><th>Book</th><th>Borrower</th><th>Borrowed Date/Time</th><th>Returned Date/Time</th><th>Status</th></tr>'+
            recs.map(r=>'<tr><td><strong>'+r.title+'</strong><br><span style="color:#64748b;font-size:11px;">'+r.access_code+'</span></td><td>'+r.borrower+'<br><span style="color:#64748b;font-size:11px;">'+r.borrower_id+'</span></td><td>'+r.borrow_date+' '+r.borrow_time+'</td><td>'+(r.return_date!=="-"?r.return_date+" "+r.return_time:"-")+'</td><td>'+(r.status==="Returned"?'<span class="badge badge-avail">Returned</span>':'<span class="badge badge-borrowed">Borrowed</span>')+'</td></tr>').join("")+'</table>';}
        else t.innerHTML='<p style="text-align:center;color:#64748b;padding:30px;font-size:14px;">No borrow records match the filters.</p>';
    }).catch(e=>alert("Load Error: "+e));
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
    const ds=document.getElementById("dept-select");if(ds)ds.addEventListener("change",()=>updateMajorOptions("dept-select","major-select","year-select"));
    const its=document.getElementById("id-type-select");if(its){its.addEventListener("change",updateAdminFieldsByIdType);updateAdminFieldsByIdType();}
    const eds=document.getElementById("edit-dept");if(eds)eds.addEventListener("change",()=>updateMajorOptions("edit-dept","edit-major","edit-year"));
    const rf=document.getElementById("register-form");
    if(rf)rf.addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(rf);fetch("/register",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{
        if(d.success){document.getElementById("barcode-result").style.display="block";document.getElementById("barcode-id").textContent="ID Number: "+fd.get("id_number");document.getElementById("barcode-img").src="data:image/png;base64,"+d.barcode;rf.reset();document.getElementById("major-select").innerHTML='<option value="">-- Select Department First --</option>';updateAdminFieldsByIdType();}
        else alert("Error: "+d.error);}).catch(err=>alert("Error: "+err));});
    const ef=document.getElementById("edit-form");
    if(ef)ef.addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(ef);fetch("/update-student",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{if(d.success){alert("Updated.");hideEditForm();loadStudents();}else alert("Error: "+d.error);}).catch(err=>alert("Error: "+err));});
    const bf=document.getElementById("book-form");
    if(bf)bf.addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(bf);fetch("/register-book",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{
        if(d.success){
            const res=document.getElementById("book-qr-result");res.style.display="block";
            document.getElementById("book-qr-title").textContent=d.title;
            document.getElementById("book-qr-code").textContent="Access Code: "+d.access_code;
            document.getElementById("book-qr-img").src="data:image/png;base64,"+d.qr;
            lastBookQRCode=d.access_code;
            bf.reset();document.querySelector('#book-form input[name="quantity"]').value=1;
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


