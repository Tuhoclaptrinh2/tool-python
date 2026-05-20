import sys
import os
import zipfile
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox,
    QFileDialog, QPushButton, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QMenuBar, QMenu, QListWidget, QListWidgetItem, QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction

from config import ConfigManager
import library_db
from ui_main import TranslateTab
from ui_library import LibraryTab
from ui_refine import RefineTab
from worker import TranslationWorker
import backup_restore


class HelpTab(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout
        layout = QVBoxLayout(self)

        help_text = QTextBrowser()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h2>Hướng dẫn sử dụng EpubTranslator</h2>

        <h3>1. Dịch truyện (Tab 1)</h3>
        <ol>
            <li>Nhấn <b>[Chọn file...]</b> để chọn file EPUB hoặc TXT cần dịch.</li>
            <li>Nhấn <b>[Chọn thư mục xuất...]</b> để chọn nơi lưu file kết quả.</li>
            <li>Chọn <b>ngôn ngữ nguồn</b> (Hàn, Trung, Nhật, Anh).</li>
            <li>Chọn <b>phương pháp dịch</b>:
                <ul>
                    <li><b>Google Dịch</b>: Miễn phí, nhanh, chất lượng cơ bản.</li>
                    <li><b>AI Dịch (OpenRouter)</b>: Chất lượng cao hơn, cần API key.</li>
                </ul>
            </li>
            <li>Nhấn <b>[Cài đặt...]</b> để tùy chỉnh chi tiết.</li>
            <li>Nhấn <b>[BẮT ĐẦU DỊCH]</b> để bắt đầu.</li>
        </ol>

        <h3>2. Tủ truyện (Tab 2)</h3>
        <ul>
            <li>Xem danh sách sách đã dịch.</li>
            <li>Tìm kiếm theo tên, ngôn ngữ.</li>
            <li>Click đúp hoặc chuột phải để mở file.</li>
            <li>Nhấn <b>[Thêm thủ công]</b> để thêm EPUB có sẵn.</li>
        </ul>

        <h3>3. Cách lấy API key OpenRouter miễn phí</h3>
        <ol>
            <li>Truy cập <a href="https://openrouter.ai/keys">https://openrouter.ai/keys</a></li>
            <li>Đăng ký tài khoản (miễn phí).</li>
            <li>Tạo API key mới.</li>
            <li>Copy key và dán vào <b>Cài đặt AI Dịch</b>.</li>
        </ol>
        <p><b>Lưu ý:</b> Chỉ dùng model có đuôi <code>:free</code> để không mất phí.</p>

        <h3>4. Lưu ý khi dùng Google Dịch</h3>
        <ul>
            <li>Có thể bị chặn nếu dịch quá nhanh (đã có delay tự động).</li>
            <li>Chất lượng dịch không bằng AI, đặc biệt với văn học.</li>
            <li>Chế độ "Văn học" sẽ thay thế từ ngữ thông thường bằng từ văn chương hơn.</li>
            <li>Chế độ "Hội thoại" sẽ dùng đại từ thân mật hơn.</li>
        </ul>

        <h3>5. Định dạng hỗ trợ</h3>
        <ul>
            <li><b>Đầu vào:</b> .epub, .txt</li>
            <li><b>Đầu ra:</b> .epub (tiếng Việt) + thư mục images/</li>
            <li>Tất cả ảnh gốc được giữ nguyên.</li>
        </ul>

        <h3>6. Phím tắt</h3>
        <ul>
            <li>Nhấn <b>[Dừng]</b> để dừng dịch giữa chừng.</li>
            <li>File đã dịch một phần sẽ không được lưu.</li>
        </ul>
        """)
        help_text.setOpenExternalLinks(True)
        layout.addWidget(help_text)


class EpubTranslatorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        library_db.init_db()
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("EpubTranslator — Dịch truyện EPUB/TXT sang tiếng Việt")
        self.resize(900, 700)

        self._create_menu_bar()

        self.tabs = QTabWidget()

        self.translate_tab = TranslateTab(self.config, self)
        self.library_tab = LibraryTab()
        self.help_tab = HelpTab()
        self.refine_tab = RefineTab(self.config)

        self.tabs.addTab(self.translate_tab, "Dịch truyện")
        self.tabs.addTab(self.library_tab, "Tủ truyện")
        self.tabs.addTab(self.help_tab, "Hướng dẫn")
        self.tabs.addTab(self.refine_tab, "AI Chỉnh sửa")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self.tabs)

    def _on_tab_changed(self, index):
        if index == 1:
            self.library_tab.refresh()

    def _create_menu_bar(self):
        menubar = self.menuBar()

        tools_menu = menubar.addMenu("Công cụ")

        backup_action = QAction("Sao lưu dự án (py.backup)", self)
        backup_action.triggered.connect(self._do_backup)
        tools_menu.addAction(backup_action)

        restore_action = QAction("Khôi phục dự án (py.restore)", self)
        restore_action.triggered.connect(self._do_restore)
        tools_menu.addAction(restore_action)

        tools_menu.addSeparator()

        console_action = QAction("Nhập lệnh...", self)
        console_action.triggered.connect(self._show_command_input)
        tools_menu.addAction(console_action)

    def _do_backup(self):
        try:
            zip_path = backup_restore.backup()
            QMessageBox.information(self, "Sao lưu thành công", f"Đã tạo bản sao lưu:\n{zip_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi sao lưu", f"Lỗi khi sao lưu:\n{e}")

    def _do_restore(self):
        backup_dir = backup_restore.BACKUP_DIR
        if not backup_dir.exists():
            QMessageBox.warning(self, "Không tìm thấy bản sao lưu", "Chưa có bản sao lưu nào.")
            return

        zip_files = sorted(backup_dir.glob("backup_*.zip"))
        if not zip_files:
            QMessageBox.warning(self, "Không tìm thấy bản sao lưu", "Chưa có bản sao lưu nào.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Khôi phục từ bản sao lưu")
        dialog.resize(500, 350)

        layout = QVBoxLayout(dialog)

        info_label = QLabel("Chọn bản sao lưu để khôi phục:")
        layout.addWidget(info_label)

        list_widget = QListWidget()
        for i, zf in enumerate(zip_files, 1):
            stat = zf.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_kb = stat.st_size / 1024
            item = QListWidgetItem(f"[{i}] {zf.name}  ({mtime}, {size_kb:.1f} KB)")
            item.setData(Qt.ItemDataRole.UserRole, str(zf))
            list_widget.addItem(item)
        layout.addWidget(list_widget)

        btn_layout = QHBoxLayout()
        restore_btn = QPushButton("Khôi phục")
        restore_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; "
            "padding: 8px; border-radius: 5px; }"
        )
        cancel_btn = QPushButton("Hủy")

        def on_restore():
            selected = list_widget.currentItem()
            if not selected:
                QMessageBox.warning(dialog, "Chưa chọn", "Vui lòng chọn một bản sao lưu.")
                return

            selected_path = selected.data(Qt.ItemDataRole.UserRole)
            filename = Path(selected_path).name

            reply = QMessageBox.question(
                dialog, "Xác nhận khôi phục",
                f"Khôi phục từ '{filename}'?\n\nĐiều này sẽ ghi đè lên các file hiện tại.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    with zipfile.ZipFile(selected_path, "r") as zf:
                        zf.extractall(backup_restore.PROJECT_DIR)
                    dialog.accept()
                    QMessageBox.information(self, "Khôi phục thành công", f"Đã khôi phục từ: {filename}")
                except Exception as e:
                    QMessageBox.critical(self, "Lỗi khôi phục", f"Lỗi khi khôi phục:\n{e}")

        restore_btn.clicked.connect(on_restore)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(restore_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        list_widget.itemDoubleClicked.connect(lambda _: on_restore())

        dialog.exec()

    def _show_command_input(self):
        cmd, ok = QInputDialog.getText(self, "Nhập lệnh", "Gõ lệnh (py.backup / py.restore):")
        if ok and cmd:
            handled = backup_restore.handle_command(cmd)
            if handled:
                QMessageBox.information(self, "Thành công", f"Lệnh '{cmd}' đã được thực thi.")
            else:
                QMessageBox.warning(self, "Lệnh không hợp lệ", f"Không nhận diện lệnh: {cmd}\n\nHỗ trợ: py.backup, py.restore")

    def start_translation(self, params):
        self.worker = TranslationWorker()
        self.worker.file_path = params["file_path"]
        self.worker.output_folder = params["output_folder"]
        self.worker.src_lang = params["src_lang"]
        self.worker.method = params["method"]
        self.worker.google_chunk_size = params["google_chunk_size"]
        self.worker.google_style = params["google_style"]
        self.worker.google_auto_optimize = params["google_auto_optimize"]
        self.worker.openrouter_api_key = params["openrouter_api_key"]
        self.worker.openrouter_model = params["openrouter_model"]
        self.worker.openrouter_temperature = params["openrouter_temperature"]
        self.worker.openrouter_system_prompt = params["openrouter_system_prompt"]
        self.worker.groq_api_key = params["groq_api_key"]
        self.worker.groq_model = params["groq_model"]
        self.worker.groq_temperature = params["groq_temperature"]
        self.worker.groq_system_prompt = params["groq_system_prompt"]
        self.worker.gemini_api_key = params.get("gemini_api_key", "")
        self.worker.gemini_model = params.get("gemini_model", "gemini-2.0-flash")
        self.worker.gemini_temperature = params.get("gemini_temperature", 0.3)

        self.worker.progress.connect(self.translate_tab.progress_bar.setValue)
        self.worker.status.connect(self.translate_tab.status_label.setText)
        self.worker.log.connect(self.translate_tab._log)
        self.worker.finished.connect(self._on_translation_finished)

        self.worker.start()

    def stop_translation(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()

    def _on_translation_finished(self, success, message):
        self.translate_tab.start_btn.setEnabled(True)
        self.translate_tab.stop_btn.setEnabled(False)

        if success:
            self._add_to_library()
            self._show_success_dialog(message)
        else:
            QMessageBox.critical(self, "Lỗi dịch", f"Quá trình dịch thất bại:\n\n{message}")

    def _add_to_library(self):
        params = self.translate_tab.get_translation_params()
        original_name = Path(params["file_path"]).stem
        output_filename = f"{original_name}_VI.epub"
        output_path = os.path.join(params["output_folder"], output_filename)
        images_folder = os.path.join(params["output_folder"], "images")

        from epub_processor import EpubProcessor
        processor = EpubProcessor()
        try:
            if params["file_path"].endswith(".txt"):
                chapters = processor.read_txt(params["file_path"])
            else:
                chapters = processor.read_epub(params["file_path"])
            chapter_count = len(chapters)
            title = processor.book_title
            orig_lang = processor.book_language
        except Exception:
            chapter_count = 0
            title = original_name
            orig_lang = params["src_lang"]

        library_db.add_book(
            title=title,
            original_language=orig_lang,
            translation_method=params["method"],
            model_used=params["openrouter_model"] if params["method"] == "openrouter" else (params["groq_model"] if params["method"] == "groq" else None),
            translated_date=datetime.now().isoformat(),
            source_file_path=params["file_path"],
            output_file_path=output_path,
            output_images_folder=images_folder,
            chapter_count=chapter_count,
        )

    def _show_success_dialog(self, message):
        dialog = QDialog(self)
        dialog.setWindowTitle("Dịch thành công!")
        dialog.resize(400, 250)

        layout = QVBoxLayout(dialog)

        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)

        btn_layout = QHBoxLayout()

        open_file_btn = QPushButton("Mở file EPUB ngay")
        open_file_btn.clicked.connect(lambda: self._open_output_file(dialog))
        btn_layout.addWidget(open_file_btn)

        open_folder_btn = QPushButton("Mở thư mục")
        open_folder_btn.clicked.connect(lambda: self._open_output_folder(dialog))
        btn_layout.addWidget(open_folder_btn)

        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _open_output_file(self, dialog):
        params = self.translate_tab.get_translation_params()
        original_name = Path(params["file_path"]).stem
        output_path = os.path.join(params["output_folder"], f"{original_name}_VI.epub")
        if os.path.exists(output_path):
            os.startfile(output_path)
        dialog.accept()

    def _open_output_folder(self, dialog):
        params = self.translate_tab.get_translation_params()
        folder = params["output_folder"]
        if os.path.exists(folder):
            os.startfile(folder)
        dialog.accept()


def main():
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        if backup_restore.handle_command(cmd):
            return

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = EpubTranslatorMainWindow()

    from ui_main import TranslateTab
    original_emit = window.translate_tab._emit_start_signal

    def patched_emit():
        params = window.translate_tab.get_translation_params()
        window.start_translation(params)

    window.translate_tab._emit_start_signal = patched_emit

    original_stop = window.translate_tab._stop_translation

    def patched_stop():
        window.stop_translation()

    window.translate_tab._stop_translation = patched_stop

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
