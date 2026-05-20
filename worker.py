from PyQt6.QtCore import QThread, pyqtSignal
import time
import re


class TranslationWorker(QThread):
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
        self.src_lang = "ko"
        self.method = "google"
        self.google_chunk_size = 5
        self.google_style = "neutral"
        self.google_auto_optimize = True
        self.openrouter_api_key = ""
        self.openrouter_model = "google/gemini-2.0-flash-exp:free"
        self.openrouter_temperature = 0.3
        self.openrouter_system_prompt = ""
        self.groq_api_key = ""
        self.groq_model = "llama-3.1-8b-instant"
        self.groq_temperature = 0.3
        self.groq_system_prompt = ""
        self.gemini_api_key = ""
        self.gemini_model = "gemini-2.0-flash"
        self.gemini_temperature = 0.3

    def stop(self):
        self._stop_event = True

    def run(self):
        try:
            start_time = time.time()

            self.log.emit(f"Bắt đầu dịch: {self.file_path}")
            self.log.emit(f"Ngôn ngữ nguồn: {self.src_lang}")
            self.log.emit(f"Phương pháp: {self.method}")

            from epub_processor import EpubProcessor
            processor = EpubProcessor()

            if self.file_path.endswith(".txt"):
                self.log.emit("Đang đọc file TXT...")
                chapters = processor.read_txt(self.file_path)
            else:
                self.log.emit("Đang đọc file EPUB...")
                chapters = processor.read_epub(self.file_path)

            total_chapters = len(chapters)
            self.log.emit(f"Số chương: {total_chapters}")

            if self.method == "google":
                from translator_google import GoogleTranslator
                translator = GoogleTranslator(
                    src_lang=self.src_lang,
                    chunk_size=self.google_chunk_size,
                    auto_optimize=self.google_auto_optimize,
                    style=self.google_style,
                )
            elif self.method == "openrouter":
                from translator_openrouter import OpenRouterTranslator
                translator = OpenRouterTranslator(
                    api_key=self.openrouter_api_key,
                    model=self.openrouter_model,
                    temperature=self.openrouter_temperature,
                    system_prompt=self.openrouter_system_prompt if self.openrouter_system_prompt else None,
                    log_callback=lambda msg: self.log.emit(msg),
                )
            elif self.method == "gemini":
                from translator_gemini import GeminiTranslator
                translator = GeminiTranslator(
                    api_key=self.gemini_api_key,
                    model=self.gemini_model,
                    temperature=self.gemini_temperature,
                    log_callback=lambda msg: self.log.emit(msg),
                )
            else:
                from translator_groq import GroqTranslator
                translator = GroqTranslator(
                    api_key=self.groq_api_key,
                    model=self.groq_model,
                    temperature=self.groq_temperature,
                    system_prompt=self.groq_system_prompt if self.groq_system_prompt else None,
                    log_callback=lambda msg: self.log.emit(msg),
                )

            translated_htmls = []

            for i, chapter in enumerate(chapters):
                if self._stop_event:
                    self.log.emit("Người dùng đã dừng dịch.")
                    self.progress.emit(100)
                    self.status.emit("Đã dừng")
                    self.finished.emit(False, "Đã dừng bởi người dùng")
                    return

                self.status.emit(f"Đang dịch chương {i + 1}/{total_chapters}...")
                self.log.emit(f"--- Dịch chương {i + 1}: {chapter.title} ---")

                chapter_start = time.time()

                from bs4 import BeautifulSoup as _BS
                _soup = _BS(chapter.content_html, "lxml")
                plain_text = _soup.get_text(separator="\n\n", strip=True)

                if not plain_text or not plain_text.strip():
                    self.log.emit(f"Chương {i + 1} không có nội dung text, bỏ qua dịch.")
                    translated_html = chapter.content_html
                else:
                    if self.method == "gemini":
                        translated_text = translator.translate_text(
                            plain_text,
                            src_lang=self.src_lang,
                        )
                        translated_html = processor.build_html_from_translated_text(translated_text)
                    else:
                        translated_text = translator.translate_text(
                            plain_text,
                            src_lang=self.src_lang,
                        )
                        translated_html = processor.build_html_from_translated_text(translated_text)
                translated_htmls.append(translated_html)

                elapsed = time.time() - chapter_start
                self.log.emit(f"Chương {i + 1} hoàn thành ({elapsed:.1f}s)")

                progress = int(((i + 1) / total_chapters) * 100)
                self.progress.emit(progress)

                remaining_chapters = total_chapters - (i + 1)
                if i > 0:
                    avg_time = (time.time() - start_time) / (i + 1)
                    eta = avg_time * remaining_chapters
                    eta_min = int(eta // 60)
                    eta_sec = int(eta % 60)
                    self.status.emit(
                        f"Đang dịch chương {i + 1}/{total_chapters} — Còn ~{eta_min}p {eta_sec}s"
                    )
                else:
                    self.status.emit(f"Đang dịch chương {i + 1}/{total_chapters}")

                self.chapter_done.emit(i, translated_html)

            original_name = processor.book_title
            output_filename = f"{original_name}_VI.epub"
            output_path = f"{self.output_folder}/{output_filename}"

            self.log.emit("Đang tạo file EPUB...")
            final_path, images_dir = processor.write_epub(
                output_path,
                src_lang=self.src_lang,
                translated_chapters=translated_htmls,
            )

            total_time = time.time() - start_time
            self.log.emit(f"Hoàn thành! File: {final_path}")
            self.log.emit(f"Thư mục ảnh: {images_dir}")
            self.log.emit(f"Tổng thời gian: {total_time:.1f}s")

            self.status.emit("Hoàn thành!")
            self.progress.emit(100)

            stats = (
                f"Dịch thành công!\n\n"
                f"Số chương: {total_chapters}\n"
                f"Thời gian: {total_time:.1f}s\n"
                f"Phương pháp: {self.method}\n"
                f"File: {final_path}\n"
                f"Ảnh: {images_dir}"
            )

            self.finished.emit(True, stats)

        except Exception as e:
            self.log.emit(f"LỖI: {str(e)}")
            self.status.emit("Lỗi!")
            self.progress.emit(0)
            self.finished.emit(False, str(e))
