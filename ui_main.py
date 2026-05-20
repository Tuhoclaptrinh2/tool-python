import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QLineEdit, QSlider,
    QTextEdit, QProgressBar, QFileDialog, QMessageBox, QDialog,
    QCheckBox, QSpinBox, QFormLayout, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt
from config import ConfigManager


GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


class GoogleSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Cài đặt Google Dịch")
        self.setModal(True)
        self.resize(350, 220)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        self.auto_optimize_cb = QCheckBox("Tối ưu văn phong tự động")
        self.auto_optimize_cb.setChecked(self.config.get("google_auto_optimize", True))
        layout.addRow(self.auto_optimize_cb)

        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Giọng văn:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Trung lập", "Văn học", "Hội thoại"])
        current_style = self.config.get("google_style", "neutral")
        style_map = {"neutral": 0, "literary": 1, "conversational": 2}
        self.style_combo.setCurrentIndex(style_map.get(current_style, 0))
        style_layout.addWidget(self.style_combo)
        layout.addRow(style_layout)

        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(QLabel("Số câu gộp nhóm:"))
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(1, 20)
        self.chunk_spin.setValue(self.config.get("google_chunk_size", 5))
        chunk_layout.addWidget(self.chunk_spin)
        layout.addRow(chunk_layout)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Lưu")
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def _save_and_close(self):
        style_map = {0: "neutral", 1: "literary", 2: "conversational"}
        self.config.set("google_auto_optimize", self.auto_optimize_cb.isChecked())
        self.config.set("google_style", style_map[self.style_combo.currentIndex()])
        self.config.set("google_chunk_size", self.chunk_spin.value())
        self.accept()

    def get_settings(self):
        style_map = {0: "neutral", 1: "literary", 2: "conversational"}
        return {
            "auto_optimize": self.auto_optimize_cb.isChecked(),
            "style": style_map[self.style_combo.currentIndex()],
            "chunk_size": self.chunk_spin.value(),
        }


class OpenRouterSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Cài đặt AI Dịch (OpenRouter)")
        self.setModal(True)
        self.resize(450, 380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        api_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.config.get_openrouter_api_key()
        if saved_key:
            self.api_key_input.setText(saved_key)
        self.api_key_input.setPlaceholderText("Nhập OpenRouter API Key...")
        api_layout.addWidget(self.api_key_input)

        self.toggle_key_btn = QPushButton("Hiện")
        self.toggle_key_btn.setFixedWidth(50)
        self.toggle_key_btn.clicked.connect(self._toggle_key_visibility)
        api_layout.addWidget(self.toggle_key_btn)
        layout.addRow("OpenRouter API Key:", api_layout)

        save_key_btn = QPushButton("Lưu key")
        save_key_btn.clicked.connect(self._save_key)
        layout.addRow("", save_key_btn)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model AI:"))
        self.model_combo = QComboBox()
        free_models = [
            "google/gemma-4-31b-it:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "openai/gpt-oss-120b:free",
            "deepseek/deepseek-v4-flash:free",
            "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
            "openrouter/free",
        ]
        self.model_combo.addItems(free_models)
        current_model = self.config.get("openrouter_model", free_models[0])
        idx = self.model_combo.findText(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        model_layout.addWidget(self.model_combo)
        layout.addRow(model_layout)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Nhiệt độ (Temperature):"))
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 100)
        current_temp = int(self.config.get("openrouter_temperature", 0.3) * 100)
        self.temp_slider.setValue(current_temp)
        self.temp_label = QLabel(f"{current_temp / 100:.1f}")
        self.temp_label.setFixedWidth(30)
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v / 100:.1f}"))
        temp_layout.addWidget(self.temp_slider)
        temp_layout.addWidget(self.temp_label)
        layout.addRow(temp_layout)

        layout.addRow(QLabel("System prompt tùy chỉnh:"))
        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setMaximumHeight(80)
        saved_prompt = self.config.get("openrouter_system_prompt", "")
        if saved_prompt:
            self.system_prompt_edit.setPlainText(saved_prompt)
        self.system_prompt_edit.setPlaceholderText("Để trống để dùng prompt mặc định...")
        layout.addRow(self.system_prompt_edit)

        warning_label = QLabel("⚠ Chỉ dùng model miễn phí — không phát sinh chi phí")
        warning_label.setStyleSheet("color: #cc6600; font-weight: bold;")
        layout.addRow(warning_label)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Lưu")
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

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
            self.config.set_openrouter_api_key(key)
            QMessageBox.information(self, "Thành công", "API key đã được lưu (mã hóa base64).")
        else:
            QMessageBox.warning(self, "Lỗi", "API key không được để trống.")

    def _save_and_close(self):
        self.config.set("openrouter_model", self.model_combo.currentText())
        self.config.set("openrouter_temperature", self.temp_slider.value() / 100)
        self.config.set("openrouter_system_prompt", self.system_prompt_edit.toPlainText().strip())
        key = self.api_key_input.text().strip()
        if key:
            self.config.set_openrouter_api_key(key)
        self.accept()

    def get_settings(self):
        return {
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_combo.currentText(),
            "temperature": self.temp_slider.value() / 100,
            "system_prompt": self.system_prompt_edit.toPlainText().strip(),
        }


class GeminiSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Cài đặt AI Dịch (Gemini)")
        self.setModal(True)
        self.resize(450, 250)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        api_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.config.get("gemini_api_key", "")
        if saved_key:
            self.api_key_input.setText(saved_key)
        self.api_key_input.setPlaceholderText("Nhập Gemini API Key...")
        api_layout.addWidget(self.api_key_input)

        self.toggle_key_btn = QPushButton("Hiện")
        self.toggle_key_btn.setFixedWidth(50)
        self.toggle_key_btn.clicked.connect(self._toggle_key_visibility)
        api_layout.addWidget(self.toggle_key_btn)
        layout.addRow("Gemini API Key:", api_layout)

        save_key_btn = QPushButton("Lưu key")
        save_key_btn.clicked.connect(self._save_key)
        layout.addRow("", save_key_btn)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model AI:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(GEMINI_MODELS)
        current_model = self.config.get("gemini_model", "gemini-2.0-flash")
        idx = self.model_combo.findText(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        model_layout.addWidget(self.model_combo)
        layout.addRow(model_layout)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Nhiệt độ (Temperature):"))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self.config.get("gemini_temperature", 0.3))
        temp_layout.addWidget(self.temp_spin)
        layout.addRow(temp_layout)

        link_label = QLabel('<a href="https://aistudio.google.com/app/apikey">Lấy API key miễn phí tại Google AI Studio</a>')
        link_label.setOpenExternalLinks(True)
        layout.addRow(link_label)

        warning_label = QLabel("⚠ Free tier: 15 req/phút, 1500 req/ngày, 1M token/ngày")
        warning_label.setStyleSheet("color: #cc6600; font-weight: bold;")
        layout.addRow(warning_label)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Lưu")
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

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
            self.config.set("gemini_api_key", key)
            QMessageBox.information(self, "Thành công", "API key đã được lưu.")
        else:
            QMessageBox.warning(self, "Lỗi", "API key không được để trống.")

    def _save_and_close(self):
        key = self.api_key_input.text().strip()
        model = self.model_combo.currentText()
        if not key:
            QMessageBox.warning(self, "Lỗi", "API key không được để trống.")
            return
        self.config.set("gemini_api_key", key)
        self.config.set("gemini_model", model)
        self.config.set("gemini_temperature", self.temp_spin.value())
        self.accept()

    def get_settings(self):
        return {
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_combo.currentText(),
            "temperature": self.temp_spin.value(),
        }


class GroqSettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Cài đặt AI Dịch (Groq)")
        self.setModal(True)
        self.resize(450, 380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        api_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        saved_key = self.config.get_groq_api_key()
        if saved_key:
            self.api_key_input.setText(saved_key)
        self.api_key_input.setPlaceholderText("Nhập Groq API Key...")
        api_layout.addWidget(self.api_key_input)

        self.toggle_key_btn = QPushButton("Hiện")
        self.toggle_key_btn.setFixedWidth(50)
        self.toggle_key_btn.clicked.connect(self._toggle_key_visibility)
        api_layout.addWidget(self.toggle_key_btn)
        layout.addRow("Groq API Key:", api_layout)

        save_key_btn = QPushButton("Lưu key")
        save_key_btn.clicked.connect(self._save_key)
        layout.addRow("", save_key_btn)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model AI:"))
        self.model_combo = QComboBox()
        groq_models = [
            "llama-3.1-8b-instant",
            "llama3-70b-8192",
            "llama-3.3-70b-versatile",
        ]
        self.model_combo.addItems(groq_models)
        current_model = self.config.get("groq_model", groq_models[0])
        idx = self.model_combo.findText(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        model_layout.addWidget(self.model_combo)
        layout.addRow(model_layout)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Nhiệt độ (Temperature):"))
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 100)
        current_temp = int(self.config.get("groq_temperature", 0.3) * 100)
        self.temp_slider.setValue(current_temp)
        self.temp_label = QLabel(f"{current_temp / 100:.1f}")
        self.temp_label.setFixedWidth(30)
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v / 100:.1f}"))
        temp_layout.addWidget(self.temp_slider)
        temp_layout.addWidget(self.temp_label)
        layout.addRow(temp_layout)

        layout.addRow(QLabel("System prompt tùy chỉnh:"))
        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setMaximumHeight(80)
        saved_prompt = self.config.get("groq_system_prompt", "")
        if saved_prompt:
            self.system_prompt_edit.setPlainText(saved_prompt)
        self.system_prompt_edit.setPlaceholderText("Để trống để dùng prompt mặc định...")
        layout.addRow(self.system_prompt_edit)

        warning_label = QLabel("⚠ Chỉ dùng model miễn phí — không phát sinh chi phí")
        warning_label.setStyleSheet("color: #cc6600; font-weight: bold;")
        layout.addRow(warning_label)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Lưu")
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

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
            self.config.set_groq_api_key(key)
            QMessageBox.information(self, "Thành công", "API key đã được lưu (mã hóa base64).")
        else:
            QMessageBox.warning(self, "Lỗi", "API key không được để trống.")

    def _save_and_close(self):
        self.config.set("groq_model", self.model_combo.currentText())
        self.config.set("groq_temperature", self.temp_slider.value() / 100)
        self.config.set("groq_system_prompt", self.system_prompt_edit.toPlainText().strip())
        key = self.api_key_input.text().strip()
        if key:
            self.config.set_groq_api_key(key)
        self.accept()

    def get_settings(self):
        return {
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_combo.currentText(),
            "temperature": self.temp_slider.value() / 100,
            "system_prompt": self.system_prompt_edit.toPlainText().strip(),
        }


class TranslateTab(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.file_path = ""
        self.output_folder = config.get("last_output_folder", "")
        self._setup_ui()
        self._update_start_button()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        file_group = QGroupBox("File đầu vào / Đầu ra")
        file_layout = QFormLayout()

        file_row = QHBoxLayout()
        self.select_file_btn = QPushButton("Chọn file...")
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

        settings_group = QGroupBox("Cài đặt dịch")
        settings_layout = QFormLayout()

        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Ngôn ngữ nguồn:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "Tiếng Hàn (ko)",
            "Tiếng Trung (zh)",
            "Tiếng Nhật (ja)",
            "Tiếng Anh (en)",
        ])
        lang_map = {"ko": 0, "zh": 1, "ja": 2, "en": 3}
        default_lang = self.config.get("default_src_language", "ko")
        self.lang_combo.setCurrentIndex(lang_map.get(default_lang, 0))
        lang_layout.addWidget(self.lang_combo)
        settings_layout.addRow(lang_layout)

        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Phương pháp dịch:"))
        self.method_group = QButtonGroup(self)
        self.google_radio = QRadioButton("Google Dịch")
        self.ai_radio = QRadioButton("AI Dịch (OpenRouter)")
        self.gemini_radio = QRadioButton("Gemini (Google AI Studio)")
        self.groq_radio = QRadioButton("AI Dịch (Groq)")
        default_method = self.config.get("default_method", "google")
        if default_method == "openrouter":
            self.ai_radio.setChecked(True)
        elif default_method == "gemini":
            self.gemini_radio.setChecked(True)
        elif default_method == "groq":
            self.groq_radio.setChecked(True)
        else:
            self.google_radio.setChecked(True)
        self.method_group.addButton(self.google_radio)
        self.method_group.addButton(self.ai_radio)
        self.method_group.addButton(self.gemini_radio)
        self.method_group.addButton(self.groq_radio)
        self.method_group.buttonClicked.connect(self._on_method_changed)
        method_layout.addWidget(self.google_radio)
        method_layout.addWidget(self.ai_radio)
        method_layout.addWidget(self.gemini_radio)
        method_layout.addWidget(self.groq_radio)
        settings_layout.addRow(method_layout)

        self.google_settings_btn = QPushButton("Cài đặt Google Dịch")
        self.google_settings_btn.clicked.connect(self._open_google_settings)
        settings_layout.addRow(self.google_settings_btn)

        ai_btn_layout = QHBoxLayout()
        self.ai_settings_btn = QPushButton("Cài đặt AI Dịch (OpenRouter)")
        self.ai_settings_btn.clicked.connect(self._open_ai_settings)
        ai_btn_layout.addWidget(self.ai_settings_btn)

        self.gemini_settings_btn = QPushButton("Cài đặt Gemini")
        self.gemini_settings_btn.clicked.connect(self._open_gemini_settings)
        ai_btn_layout.addWidget(self.gemini_settings_btn)

        self.groq_settings_btn = QPushButton("Cài đặt AI Dịch (Groq)")
        self.groq_settings_btn.clicked.connect(self._open_groq_settings)
        ai_btn_layout.addWidget(self.groq_settings_btn)
        settings_layout.addRow(ai_btn_layout)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        action_layout = QVBoxLayout()

        self.start_btn = QPushButton("BẮT ĐẦU DỊCH")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; "
            "padding: 10px; font-size: 14px; border-radius: 5px; } "
            "QPushButton:hover { background-color: #1976D2; } "
            "QPushButton:disabled { background-color: #BDBDBD; }"
        )
        self.start_btn.clicked.connect(self._start_translation)
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
        self.stop_btn.clicked.connect(self._stop_translation)
        self.stop_btn.setEnabled(False)
        bottom_btn_layout.addWidget(self.stop_btn)
        bottom_btn_layout.addStretch()
        action_layout.addLayout(bottom_btn_layout)

        main_layout.addLayout(action_layout)

        self._on_method_changed()

    def _on_method_changed(self):
        method = "google" if self.google_radio.isChecked() else ("openrouter" if self.ai_radio.isChecked() else ("gemini" if self.gemini_radio.isChecked() else "groq"))
        self.google_settings_btn.setVisible(method == "google")
        self.ai_settings_btn.setVisible(method == "openrouter")
        self.gemini_settings_btn.setVisible(method == "gemini")
        self.groq_settings_btn.setVisible(method == "groq")

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file EPUB hoặc TXT", "", "EPUB/TXT Files (*.epub *.txt)"
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

    def _open_google_settings(self):
        dialog = GoogleSettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._log("Đã lưu cài đặt Google Dịch")

    def _open_ai_settings(self):
        dialog = OpenRouterSettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._log("Đã lưu cài đặt AI Dịch (OpenRouter)")

    def _open_gemini_settings(self):
        dialog = GeminiSettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._log("Đã lưu cài đặt Gemini")

    def _open_groq_settings(self):
        dialog = GroqSettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._log("Đã lưu cài đặt AI Dịch (Groq)")

    def _log(self, message):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def _start_translation(self):
        if not self.file_path or not self.output_folder:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file và thư mục xuất.")
            return

        method = "google" if self.google_radio.isChecked() else ("openrouter" if self.ai_radio.isChecked() else ("gemini" if self.gemini_radio.isChecked() else "groq"))
        self.config.set("default_method", method)

        lang_map = {"Tiếng Hàn (ko)": "ko", "Tiếng Trung (zh)": "zh",
                    "Tiếng Nhật (ja)": "ja", "Tiếng Anh (en)": "en"}
        src_lang = lang_map.get(self.lang_combo.currentText(), "ko")
        self.config.set("default_src_language", src_lang)

        if method == "openrouter":
            api_key = self.config.get_openrouter_api_key()
            if not api_key or len(api_key) < 20:
                QMessageBox.warning(
                    self, "Lỗi",
                    "API key OpenRouter chưa được lưu hoặc không hợp lệ.\n"
                    "Vui lòng vào 'Cài đặt AI Dịch (OpenRouter)' để nhập và lưu key."
                )
                return

        if method == "gemini":
            api_key = self.config.get("gemini_api_key", "")
            if not api_key or len(api_key) < 10:
                QMessageBox.warning(
                    self, "Lỗi",
                    "API key Gemini chưa được lưu hoặc không hợp lệ.\n"
                    "Vui lòng vào 'Cài đặt Gemini' để nhập và lưu key.\n"
                    "Lấy miễn phí tại: https://aistudio.google.com/app/apikey"
                )
                return

        if method == "groq":
            api_key = self.config.get_groq_api_key()
            if not api_key or len(api_key) < 20:
                QMessageBox.warning(
                    self, "Lỗi",
                    "API key Groq chưa được lưu hoặc không hợp lệ.\n"
                    "Vui lòng vào 'Cài đặt AI Dịch (Groq)' để nhập và lưu key."
                )
                return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_area.clear()

        self._emit_start_signal()

    def _emit_start_signal(self):
        pass

    def _stop_translation(self):
        self.stop_btn.setEnabled(False)
        self._log("Đang yêu cầu dừng...")

    def get_translation_params(self):
        method = "google" if self.google_radio.isChecked() else ("openrouter" if self.ai_radio.isChecked() else ("gemini" if self.gemini_radio.isChecked() else "groq"))
        lang_map = {"Tiếng Hàn (ko)": "ko", "Tiếng Trung (zh)": "zh",
                    "Tiếng Nhật (ja)": "ja", "Tiếng Anh (en)": "en"}
        src_lang = lang_map.get(self.lang_combo.currentText(), "ko")

        return {
            "file_path": self.file_path,
            "output_folder": self.output_folder,
            "src_lang": src_lang,
            "method": method,
            "google_chunk_size": self.config.get("google_chunk_size", 5),
            "google_style": self.config.get("google_style", "neutral"),
            "google_auto_optimize": self.config.get("google_auto_optimize", True),
            "openrouter_api_key": self.config.get_openrouter_api_key(),
            "openrouter_model": self.config.get("openrouter_model", "google/gemma-4-31b-it:free"),
            "openrouter_temperature": self.config.get("openrouter_temperature", 0.3),
            "openrouter_system_prompt": self.config.get("openrouter_system_prompt", ""),
            "gemini_api_key": self.config.get("gemini_api_key", ""),
            "gemini_model": self.config.get("gemini_model", "gemini-2.0-flash"),
            "gemini_temperature": self.config.get("gemini_temperature", 0.3),
            "groq_api_key": self.config.get_groq_api_key(),
            "groq_model": self.config.get("groq_model", "llama-3.1-8b-instant"),
            "groq_temperature": self.config.get("groq_temperature", 0.3),
            "groq_system_prompt": self.config.get("groq_system_prompt", ""),
        }
