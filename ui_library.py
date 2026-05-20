import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QMenu, QAbstractItemView, QLabel
)
from PyQt6.QtCore import Qt
import library_db


class LibraryTab(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._load_books()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tìm kiếm theo tên truyện, ngôn ngữ...")
        self.search_btn = QPushButton("Tìm kiếm")
        self.search_btn.clicked.connect(self._search)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.setHorizontalHeaders(["Tên truyện", "Ngôn ngữ gốc", "Phương pháp dịch", "Ngày dịch", "Đường dẫn"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(self._open_epub)
        layout.addWidget(self.table)

        bottom_layout = QHBoxLayout()
        self.add_manual_btn = QPushButton("Thêm thủ công")
        self.add_manual_btn.clicked.connect(self._add_manual)
        bottom_layout.addWidget(self.add_manual_btn)
        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)

    def setHorizontalHeaders(self, headers):
        for i, header in enumerate(headers):
            self.table.setHorizontalHeaderItem(i, QTableWidgetItem(header))

    def _load_books(self):
        books = library_db.get_all_books()
        self._populate_table(books)

    def _populate_table(self, books):
        self.table.setRowCount(len(books))
        for row, book in enumerate(books):
            self.table.setItem(row, 0, QTableWidgetItem(book.get("title", "")))
            self.table.setItem(row, 1, QTableWidgetItem(book.get("original_language", "")))
            method = book.get("translation_method", "")
            method_display = "Google Dịch" if method == "google" else "AI (OpenRouter)" if method == "openrouter" else method
            self.table.setItem(row, 2, QTableWidgetItem(method_display))
            self.table.setItem(row, 3, QTableWidgetItem(book.get("translated_date", "")))
            self.table.setItem(row, 4, QTableWidgetItem(book.get("output_file_path", "")))
            self.table.setRowHeight(row, 30)

    def _search(self):
        query = self.search_input.text().strip()
        if not query:
            self._load_books()
        else:
            books = library_db.search_books(query)
            self._populate_table(books)

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        menu = QMenu(self)

        open_action = menu.addAction("Mở file EPUB")
        open_action.triggered.connect(lambda: self._open_epub(row, 0))

        open_folder_action = menu.addAction("Mở thư mục chứa")
        open_folder_action.triggered.connect(lambda: self._open_folder(row))

        menu.addSeparator()

        delete_action = menu.addAction("Xóa khỏi tủ")
        delete_action.triggered.connect(lambda: self._delete_book(row))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _open_epub(self, row, col=0):
        item = self.table.item(row, 4)
        if item:
            path = item.text()
            if path and os.path.exists(path):
                os.startfile(path)
            else:
                QMessageBox.warning(self, "Lỗi", f"Không tìm thấy file:\n{path}")

    def _open_folder(self, row):
        item = self.table.item(row, 4)
        if item:
            path = item.text()
            if path:
                folder = str(Path(path).parent)
                if os.path.exists(folder):
                    os.startfile(folder)
                else:
                    QMessageBox.warning(self, "Lỗi", f"Không tìm thấy thư mục:\n{folder}")

    def _delete_book(self, row):
        title_item = self.table.item(row, 0)
        title = title_item.text() if title_item else "Không rõ"

        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f'Bạn có muốn xóa "{title}" khỏi tủ truyện?\n(File trên đĩa sẽ không bị xóa.)',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            books = library_db.get_all_books()
            if row < len(books):
                library_db.delete_book(books[row]["id"])
                self._load_books()

    def _add_manual(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file EPUB để thêm vào tủ", "", "EPUB Files (*.epub)"
        )
        if not file_path:
            return

        title = Path(file_path).stem
        library_db.add_book(
            title=title,
            original_language="unknown",
            translation_method="manual",
            output_file_path=file_path,
            translated_date="",
            source_file_path=file_path,
            chapter_count=0,
        )
        self._load_books()
        QMessageBox.information(self, "Thành công", f'Đã thêm "{title}" vào tủ truyện.')

    def refresh(self):
        self._load_books()
