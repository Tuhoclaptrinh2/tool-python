import os
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit, QProgressBar, QFileDialog,
    QMessageBox, QDialog, QFormLayout
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from config import ConfigManager


DEFAULT_REFINE_PROMPT = (
    "Hãy chỉnh sửa bản dịch sau cho tự nhiên, đúng văn phong tiểu thuyết Việt Nam.\n"
    "- Sửa cách xưng hô cho phù hợp ngữ cảnh (anh/em/hắn/nàng/ta/ngươi...)\n"
    "- Sửa câu văn cứng nhắc thành tự nhiên, mượt mà\n"
    "- Sửa lỗi chính tả, dấu câu\n"
    "- Giữ nguyên tên riêng, địa danh, toàn bộ nội dung\n"
    "- Chỉ trả về đoạn văn đã chỉnh, không giải thích"
)

OPENROUTER_MODELS = [
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openai/gpt-oss-120b:free",
    "deepseek/deepseek-v4-flash:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "openrouter/free",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


class RefineSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Cài đặt AI Chỉnh sửa")
        self.setModal(True)
        self.resize(450, 350)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        self.gemini_link = None
        self.warning_label = None

        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenRouter", "Google AI Studio (Gemini)"])
        saved_model = self.config.get("refine_model", "google/gemma-4-31b-it:free")
        if saved_model.startswith("gemini-"):
            self.provider_combo.setCurrentIndex(1)
        provider_layout.addWidget(self.provider_combo)
        layout.addRow(provider_layout)

        api_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.config.get("refine_api_key", "")
        if saved_key:
            self.api_key_input.setText(saved_key)
        self.api_key_input.setPlaceholderText("Nhập API Key...")
        api_layout.addWidget(self.api_key_input)

        self.toggle_key_btn = QPushButton("Hiện")
        self.toggle_key_btn.setFixedWidth(50)
        self.toggle_key_btn.clicked.connect(self._toggle_key_visibility)
        api_layout.addWidget(self.toggle_key_btn)
        layout.addRow("API Key:", api_layout)

        save_key_btn = QPushButton("Lưu key")
        save_key_btn.clicked.connect(self._save_key)
        layout.addRow("", save_key_btn)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model AI:"))
        self.model_combo = QComboBox()
        self._refresh_models()
        model_layout.addWidget(self.model_combo)
        layout.addRow(model_layout)

        self.provider_combo.currentIndexChanged.connect(self._refresh_models)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Nhiệt độ (Temperature):"))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self.config.get("refine_temperature", 0.3))
        temp_layout.addWidget(self.temp_spin)
        layout.addRow(temp_layout)

        self.gemini_link = QLabel('<a href="https://aistudio.google.com/app/apikey">Lấy API key Gemini miễn phí tại đây</a>')
        self.gemini_link.setOpenExternalLinks(True)
        self.gemini_link.setVisible(self.provider_combo.currentIndex() == 1)
        layout.addRow(self.gemini_link)

        self.warning_label = QLabel("⚠ Gemini free: 15 req/phút, 1500 req/ngày, 1M token/ngày")
        self.warning_label.setStyleSheet("color: #cc6600; font-weight: bold;")
        self.warning_label.setVisible(self.provider_combo.currentIndex() == 1)
        layout.addRow(self.warning_label)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Lưu")
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def _refresh_models(self):
        self.model_combo.clear()
        if self.provider_combo.currentIndex() == 0:
            self.model_combo.addItems(OPENROUTER_MODELS)
            saved = self.config.get("refine_model", "google/gemma-4-31b-it:free")
            if self.gemini_link:
                self.gemini_link.setVisible(False)
            if self.warning_label:
                self.warning_label.setVisible(False)
        else:
            self.model_combo.addItems(GEMINI_MODELS)
            saved = self.config.get("refine_model", "gemini-2.0-flash")
            if self.gemini_link:
                self.gemini_link.setVisible(True)
            if self.warning_label:
                self.warning_label.setVisible(True)
        idx = self.model_combo.findText(saved)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    def _toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_btn.setText("Ẩn")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("Hiện")

    def _save_key(self):
        key = self.api_key_input.text().strip()
        if key:
            self.config.set("refine_api_key", key)
            QMessageBox.information(self, "Thành công", "API key đã được lưu.")
        else:
            QMessageBox.warning(self, "Lỗi", "API key không được để trống.")

    def _save_and_close(self):
        key = self.api_key_input.text().strip()
        model = self.model_combo.currentText()
        if not key:
            QMessageBox.warning(self, "Lỗi", "API key không được để trống.")
            return
        self.config.set("refine_api_key", key)
        self.config.set("refine_model", model)
        self.config.set("refine_temperature", self.temp_spin.value())
        self.accept()


class RefineWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    chapter_done = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()
        self._stop_event = False
        self.file_path = ""
        self.output_folder = ""
        self.api_key = ""
        self.model = "google/gemma-4-31b-it:free"
        self.temperature = 0.3
        self.refine_prompt = ""

    def stop(self):
        self._stop_event = True

    def run(self):
        try:
            start_time = time.time()

            self.log.emit(f"Bắt đầu chỉnh sửa: {self.file_path}")

            from epub_processor import EpubProcessor
            processor = EpubProcessor()

            self.log.emit("Đang đọc file EPUB...")
            chapters = processor.read_epub(self.file_path)

            total_chapters = len(chapters)
            self.log.emit(f"Số chương: {total_chapters}")

            if self.model.startswith("gemini-"):
                from translator_gemini import GeminiTranslator
                ai_translator = GeminiTranslator(
                    api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                    log_callback=lambda msg: self.log.emit(msg),
                )
            else:
                from translator_openrouter import OpenRouterTranslator
                ai_translator = OpenRouterTranslator(
                    api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                    log_callback=lambda msg: self.log.emit(msg),
                )

            refined_htmls = []

            for i, chapter in enumerate(chapters):
                if self._stop_event:
                    self.log.emit("Người dùng đã dừng.")
                    self.progress.emit(100)
                    self.status.emit("Đã dừng")
                    self.finished.emit(False, "Đã dừng bởi người dùng")
                    return

                self.status.emit(f"Đang chỉnh sửa chương {i + 1}/{total_chapters}...")
                self.log.emit(f"--- Chỉnh sửa chương {i + 1}: {chapter.title} ---")

                chapter_start = time.time()

                from bs4 import BeautifulSoup as _BS
                _soup = _BS(chapter.content_html, "lxml")
                plain_text = _soup.get_text(separator="\n\n", strip=True)

                if not plain_text or not plain_text.strip():
                    self.log.emit(f"Chương {i + 1} không có nội dung text, bỏ qua.")
                    refined_html = chapter.content_html
                else:
                    self.log.emit(f"AI chỉnh sửa chương {i + 1}...")
                    refined_text = ai_translator.refine_text(
                        plain_text,
                        self.refine_prompt,
                    )
                    if not refined_text or not refined_text.strip():
                        refined_text = plain_text
                    refined_html = processor.replace_text_in_html(
                        chapter.content_html, refined_text
                    )

                refined_htmls.append(refined_html)

                elapsed = time.time() - chapter_start
                self.log.emit(f"Chương {i + 1} hoàn thành ({elapsed:.1f}s)")

                progress = int(((i + 1) / total_chapters) * 100)
                self.progress.emit(progress)

                remaining = total_chapters - (i + 1)
                if i > 0:
                    avg_time = (time.time() - start_time) / (i + 1)
                    eta = avg_time * remaining
                    eta_min = int(eta // 60)
                    eta_sec = int(eta % 60)
                    self.status.emit(
                        f"Đang chỉnh sửa chương {i + 1}/{total_chapters} — Còn ~{eta_min}p {eta_sec}s"
                    )
                else:
                    self.status.emit(f"Đang chỉnh sửa chương {i + 1}/{total_chapters}")

                self.chapter_done.emit(i, refined_html)

            original_name = processor.book_title
            output_filename = f"{original_name}_refined.epub"
            output_path = f"{self.output_folder}/{output_filename}"

            self.log.emit("Đang tạo file EPUB...")
            final_path, images_dir = processor.write_epub(
                output_path,
                src_lang="vi",
                translated_chapters=refined_htmls,
            )

            total_time = time.time() - start_time
            self.log.emit(f"Hoàn thành! File: {final_path}")
            self.log.emit(f"Thư mục ảnh: {images_dir}")
            self.log.emit(f"Tổng thời gian: {total_time:.1f}s")

            self.status.emit("Hoàn thành!")
            self.progress.emit(100)

            stats = (
                f"Chỉnh sửa thành công!\n\n"
                f"Số chương: {total_chapters}\n"
                f"Thời gian: {total_time:.1f}s\n"
                f"Model: {self.model}\n"
                f"File: {final_path}"
            )

            self.finished.emit(True, stats)

        except Exception as e:
            self.log.emit(f"LỖI: {str(e)}")
            self.status.emit("Lỗi!")
            self.progress.emit(0)
            self.finished.emit(False, str(e))


class RefineTab(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.file_path = ""
        self.output_folder = config.get("last_output_folder", "")
        self.worker = None
        self._setup_ui()
        self._update_start_button()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        file_group = QGroupBox("File đầu vào / Đầu ra")
        file_layout = QFormLayout()

        file_row = QHBoxLayout()
        self.select_file_btn = QPushButton("Chọn file EPUB...")
        self.select_file_btn.clicked.connect(self._select_file)
        file_row.addWidget(self.select_file_btn)
        self.file_label = QLabel("Chưa chọn file")
        self.file_label.setStyleSheet("color: #888;")
        file_row.addWidget(self.file_label)
        file_layout.addRow(file_row)

        folder_row = QHBoxLayout()
        self.select_folder_btn = QPushButton("Chọn thư mục xuất...")
        self.select_folder_btn.clicked.connect(self._select_folder)
        folder_row.addWidget(self.select_folder_btn)
        self.folder_label = QLabel("Chưa chọn thư mục")
        self.folder_label.setStyleSheet("color: #888;")
        folder_row.addWidget(self.folder_label)
        file_layout.addRow(folder_row)

        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        settings_group = QGroupBox("Cài đặt AI")
        settings_layout = QFormLayout()

        self.ai_settings_btn = QPushButton("Cài đặt AI...")
        self.ai_settings_btn.clicked.connect(self._open_ai_settings)
        settings_layout.addRow(self.ai_settings_btn)

        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("Model:"))
        self.model_label = QLabel(self.config.get("refine_model", "google/gemma-4-31b-it:free"))
        info_layout.addWidget(self.model_label)
        info_layout.addStretch()
        settings_layout.addRow(info_layout)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        prompt_group = QGroupBox("Prompt chỉnh sửa")
        prompt_layout = QVBoxLayout()
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(150)
        self.prompt_edit.setPlaceholderText(DEFAULT_REFINE_PROMPT)
        prompt_layout.addWidget(self.prompt_edit)
        prompt_group.setLayout(prompt_layout)
        main_layout.addWidget(prompt_group)

        action_layout = QVBoxLayout()

        self.start_btn = QPushButton("BẮT ĐẦU CHỈNH SỬA")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; "
            "padding: 10px; font-size: 14px; border-radius: 5px; } "
            "QPushButton:hover { background-color: #1976D2; } "
            "QPushButton:disabled { background-color: #BDBDBD; }"
        )
        self.start_btn.clicked.connect(self._start_refine)
        action_layout.addWidget(self.start_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        action_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setStyleSheet("font-weight: bold;")
        action_layout.addWidget(self.status_label)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(200)
        self.log_area.setStyleSheet("font-family: monospace; font-size: 11px;")
        action_layout.addWidget(self.log_area)

        bottom_btn_layout = QHBoxLayout()
        self.stop_btn = QPushButton("Dừng")
        self.stop_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; font-weight: bold; "
            "padding: 8px; border-radius: 5px; }"
        )
        self.stop_btn.clicked.connect(self._stop_refine)
        self.stop_btn.setEnabled(False)
        bottom_btn_layout.addWidget(self.stop_btn)
        bottom_btn_layout.addStretch()
        action_layout.addLayout(bottom_btn_layout)

        main_layout.addLayout(action_layout)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file EPUB", "", "EPUB Files (*.epub)"
        )
        if file_path:
            self.file_path = file_path
            self.file_label.setText(file_path)
            self.file_label.setStyleSheet("color: #000;")
            self._log(f"Đã chọn file: {file_path}")
            self._update_start_button()

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất")
        if folder:
            self.output_folder = folder
            self.folder_label.setText(folder)
            self.folder_label.setStyleSheet("color: #000;")
            self.config.set("last_output_folder", folder)
            self._log(f"Thư mục xuất: {folder}")
            self._update_start_button()

    def _update_start_button(self):
        enabled = bool(self.file_path) and bool(self.output_folder)
        self.start_btn.setEnabled(enabled)

    def _open_ai_settings(self):
        dialog = RefineSettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.model_label.setText(self.config.get("refine_model", "google/gemma-4-31b-it:free"))
            self._log("Đã lưu cài đặt AI Chỉnh sửa")

    def _log(self, message):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def _start_refine(self):
        if not self.file_path or not self.output_folder:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file và thư mục xuất.")
            return

        api_key = self.config.get("refine_api_key", "")
        if not api_key or len(api_key) < 10:
            QMessageBox.warning(
                self, "Lỗi",
                "API key chưa được lưu hoặc không hợp lệ.\n"
                "Vui lòng vào 'Cài đặt AI' để nhập và lưu key."
            )
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_area.clear()

        self.worker = RefineWorker()
        self.worker.file_path = self.file_path
        self.worker.output_folder = self.output_folder
        self.worker.api_key = api_key
        self.worker.model = self.config.get("refine_model", "google/gemma-4-31b-it:free")
        self.worker.temperature = self.config.get("refine_temperature", 0.3)
        self.worker.refine_prompt = self.prompt_edit.toPlainText().strip()

        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.log.connect(self._log)
        self.worker.finished.connect(self._on_finished)

        self.worker.start()

    def _stop_refine(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.stop_btn.setEnabled(False)
            self._log("Đang yêu cầu dừng...")

    def _on_finished(self, success, message):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if success:
            self._show_success_dialog(message)
        else:
            QMessageBox.critical(self, "Lỗi chỉnh sửa", f"Quá trình chỉnh sửa thất bại:\n\n{message}")

    def _show_success_dialog(self, message):
        dialog = QDialog(self)
        dialog.setWindowTitle("Chỉnh sửa thành công!")
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
        original_name = Path(self.file_path).stem
        output_path = os.path.join(self.output_folder, f"{original_name}_refined.epub")
        if os.path.exists(output_path):
            os.startfile(output_path)
        dialog.accept()

    def _open_output_folder(self, dialog):
        if os.path.exists(self.output_folder):
            os.startfile(self.output_folder)
        dialog.accept()
