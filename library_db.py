import sqlite3
from pathlib import Path
from config import APP_DATA_DIR

DB_FILE = APP_DATA_DIR / "library.db"


def _get_connection():
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            original_language TEXT,
            translation_method TEXT,
            model_used TEXT,
            translated_date TEXT,
            source_file_path TEXT,
            output_file_path TEXT NOT NULL,
            output_images_folder TEXT,
            chapter_count INTEGER,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_book(title, original_language, translation_method, output_file_path,
             model_used=None, translated_date=None, source_file_path=None,
             output_images_folder=None, chapter_count=None, notes=None):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO books (
            title, original_language, translation_method, model_used,
            translated_date, source_file_path, output_file_path,
            output_images_folder, chapter_count, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title, original_language, translation_method, model_used,
        translated_date, source_file_path, output_file_path,
        output_images_folder, chapter_count, notes
    ))
    conn.commit()
    book_id = cursor.lastrowid
    conn.close()
    return book_id


def get_all_books():
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books ORDER BY translated_date DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def search_books(query):
    conn = _get_connection()
    cursor = conn.cursor()
    like_query = f"%{query}%"
    cursor.execute("""
        SELECT * FROM books
        WHERE title LIKE ? OR original_language LIKE ? OR translation_method LIKE ?
        ORDER BY translated_date DESC
    """, (like_query, like_query, like_query))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_book(book_id):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()


def update_book_notes(book_id, notes):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE books SET notes = ? WHERE id = ?", (notes, book_id))
    conn.commit()
    conn.close()
