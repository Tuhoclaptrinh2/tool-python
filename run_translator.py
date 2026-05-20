import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime

# ─── Cấu hình ───
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("LỖI: Không tìm thấy biến môi trường OPENROUTER_API_KEY")
    sys.exit(1)

EPUB_INPUT = os.environ.get("EPUB_INPUT", "")
PROGRESS_FILE = "progress.json"
OUTPUT_DIR = "output"
CHECKPOINT_INTERVAL = 1  # Lưu checkpoint sau mỗi chương

# Model miễn phí
MODEL = "google/gemma-4-31b-it:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Prompt mặc định
DEFAULT_SYSTEM_PROMPT = (
    "Bạn là dịch giả chuyên nghiệp. Hãy dịch đoạn văn sau sang tiếng Việt tự nhiên, "
    "giữ nguyên văn phong và cảm xúc của bản gốc. Chỉ trả về bản dịch, không giải thích."
)

DEFAULT_REFINE_PROMPT = (
    "Hãy chỉnh sửa bản dịch thô sau cho tự nhiên, đúng văn phong tiểu thuyết Việt Nam.\n"
    "- Sửa cách xưng hô cho phù hợp ngữ cảnh (anh/em/hắn/nàng/ta/ngươi...)\n"
    "- Sửa câu văn cứng nhắc thành tự nhiên, mượt mà\n"
    "- Sửa lỗi chính tả, dấu câu\n"
    "- Giữ nguyên tên riêng, địa danh, toàn bộ nội dung\n"
    "- Chỉ trả về đoạn văn đã chỉnh, không giải thích"
)


# ─── Checkpoint Manager ───
class CheckpointManager:
    def __init__(self, filepath=PROGRESS_FILE):
        self.filepath = filepath
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "total_chapters": 0,
            "completed_chapters": [],
            "last_updated": None,
            "mode": "translate",  # translate | refine | hybrid
        }

    def save(self):
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f"[Checkpoint] Đã lưu tiến trình: {len(self.data['completed_chapters'])}/{self.data['total_chapters']} chương")

    def mark_complete(self, chapter_index, chapter_title=""):
        entry = {
            "index": chapter_index,
            "title": chapter_title,
            "completed_at": datetime.now().isoformat(),
        }
        # Tránh trùng lặp
        self.data["completed_chapters"] = [
            c for c in self.data["completed_chapters"] if c["index"] != chapter_index
        ]
        self.data["completed_chapters"].append(entry)
        self.save()

    def get_next_index(self):
        completed = {c["index"] for c in self.data["completed_chapters"]}
        for i in range(self.data["total_chapters"]):
            if i not in completed:
                return i
        return -1  # Đã hoàn thành tất cả

    def is_complete(self):
        return len(self.data["completed_chapters"]) >= self.data["total_chapters"]

    def reset(self):
        self.data = {
            "total_chapters": 0,
            "completed_chapters": [],
            "last_updated": None,
            "mode": "translate",
        }
        if os.path.exists(self.filepath):
            os.remove(self.filepath)


# ─── OpenRouter Translator ──
class OpenRouterTranslator:
    def __init__(self, api_key, model=MODEL, temperature=0.3, system_prompt=None):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def _estimate_tokens(self, text):
        return max(1, len(text) // 4)

    def _chunk_text(self, text, max_tokens=800):
        chunks = []
        current = []
        current_tokens = 0
        for para in text.split("\n\n"):
            pt = self._estimate_tokens(para)
            if current_tokens + pt > max_tokens and current:
                chunks.append("\n\n".join(current))
                current = [para]
                current_tokens = pt
            else:
                current.append(para)
                current_tokens += pt
        if current:
            chunks.append("\n\n".join(current))
        return chunks if chunks else [text]

    def _call_api(self, system_msg, user_msg, max_retries=5):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/epub-translator",
            "X-Title": "EpubTranslator",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "temperature": self.temperature,
            "max_tokens": 4000,
        }

        for attempt in range(max_retries):
            try:
                resp = requests.post(API_URL, headers=headers, json=payload, timeout=180)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
                    return text.strip()
                elif resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 30 * (attempt + 1)))
                    print(f"  [Rate limit] Chờ {wait}s... (lần thử {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                elif resp.status_code == 402:
                    raise ValueError("Model yêu cầu trả phí")
                else:
                    print(f"  [Lỗi API {resp.status_code}] {resp.text[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(10 * (attempt + 1))
            except requests.exceptions.RequestException as e:
                print(f"  [Lỗi kết nối] {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
        return None

    def translate_text(self, text, src_lang="ko"):
        if not text or not text.strip():
            return text
        chunks = self._chunk_text(text)
        results = []
        for i, chunk in enumerate(chunks):
            print(f"    Chunk {i+1}/{len(chunks)}...")
            user_msg = f"Dịch đoạn văn sau từ ngôn ngữ nguồn (mã: {src_lang}) sang tiếng Việt:\n\n{chunk}"
            result = self._call_api(self.system_prompt, user_msg)
            results.append(result if result else chunk)
            if i < len(chunks) - 1:
                time.sleep(3)
        return "\n\n".join(results)

    def refine_text(self, rough_text, refine_prompt=""):
        if not rough_text or not rough_text.strip():
            return rough_text
        user_prompt = refine_prompt.strip() if refine_prompt.strip() else DEFAULT_REFINE_PROMPT
        chunks = self._chunk_text(rough_text, max_tokens=1500)
        results = []
        for i, chunk in enumerate(chunks):
            print(f"    Chunk {i+1}/{len(chunks)}...")
            user_msg = f"{user_prompt}\n\nBản dịch thô:\n{chunk}"
            system_msg = (
                "Bạn là biên tập viên tiếng Việt chuyên hiệu đính bản dịch tiểu thuyết. "
                "Chỉ trả về đoạn văn đã chỉnh, không giải thích, không thêm bớt nội dung."
            )
            result = self._call_api(system_msg, user_msg)
            results.append(result if result else chunk)
            if i < len(chunks) - 1:
                time.sleep(5)
        return "\n\n".join(results)


# ─── EPUB Processor (đơn giản hóa cho cloud) ───
class SimpleEpubProcessor:
    def __init__(self):
        self.chapters = []
        self.book_title = "Unknown"
        self.images = []

    def read_epub(self, filepath):
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup

            book = epub.read_epub(filepath, options={"ignore_ncx": True})
            title_meta = book.get_metadata("DC", "title")
            self.book_title = title_meta[0][0] if title_meta else Path(filepath).stem

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    html = item.get_content().decode("utf-8", errors="replace")
                    soup = BeautifulSoup(html, "lxml")
                    text = soup.get_text(separator="\n\n", strip=True)
                    if text:
                        title_tag = soup.find(["h1", "h2", "h3"])
                        chapter_title = title_tag.get_text(strip=True) if title_tag else f"Chương {len(self.chapters)+1}"
                        self.chapters.append({
                            "title": chapter_title,
                            "text": text,
                            "html": html,
                        })

            # Lưu ảnh
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE:
                    self.images.append({
                        "filename": Path(item.get_name()).name,
                        "data": item.get_content(),
                        "media_type": item.media_type,
                    })

        except ImportError:
            print("Cài đặt ebooklib và beautifulsoup4: pip install EbookLib beautifulsoup4 lxml")
            sys.exit(1)

        if not self.chapters:
            raise ValueError("Không tìm thấy nội dung trong EPUB")

        return self.chapters

    def save_chapter_html(self, chapter_index, translated_text, output_dir):
        from bs4 import BeautifulSoup
        import html as html_module

        paragraphs = [p.strip() for p in translated_text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [translated_text]

        html_parts = []
        for para in paragraphs:
            para = " ".join(para.split())
            if para:
                html_parts.append(f"<p>{html_module.escape(para)}</p>")

        body_content = "\n".join(html_parts) if html_parts else "<p>(Nội dung trống)</p>"
        chapter = self.chapters[chapter_index]
        safe_title = html_module.escape(chapter["title"])

        full_html = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi" lang="vi">\n'
            f'<head><meta charset="utf-8"/><title>{safe_title}</title></head>\n'
            f'<body>{body_content}</body>\n'
            '</html>'
        )

        chapter_file = os.path.join(output_dir, f"chapter_{chapter_index}.xhtml")
        with open(chapter_file, "w", encoding="utf-8") as f:
            f.write(full_html)
        return chapter_file

    def build_epub(self, output_dir, output_filename):
        import ebooklib
        from ebooklib import epub
        import html as html_module

        new_book = epub.EpubBook()
        new_book.set_identifier("epubtranslator_" + Path(output_filename).stem)
        new_book.set_title(self.book_title + " (VI)")
        new_book.set_language("vi")
        new_book.add_metadata("DC", "creator", "EpubTranslator")

        # Thêm ảnh
        images_dir = os.path.join(output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        for img in self.images:
            img_path = os.path.join(images_dir, img["filename"])
            with open(img_path, "wb") as f:
                f.write(img["data"])
            new_book.add_item(epub.EpubItem(
                uid="img_" + img["filename"],
                file_name="images/" + img["filename"],
                media_type=img["media_type"],
                content=img["data"],
            ))

        # Thêm chương
        spine = ["nav"]
        for i, chapter in enumerate(self.chapters):
            chapter_file = os.path.join(output_dir, f"chapter_{i}.xhtml")
            if not os.path.exists(chapter_file):
                print(f"  Cảnh báo: Thiếu file chương {i}, bỏ qua")
                continue

            with open(chapter_file, "r", encoding="utf-8") as f:
                content = f.read().encode("utf-8")

            c = epub.EpubHtml(
                title=chapter["title"],
                file_name=f"chapter_{i}.xhtml",
                lang="vi",
            )
            c.set_content(content)
            new_book.add_item(c)
            spine.append(c)

        new_book.add_item(epub.EpubNcx())
        new_book.add_item(epub.EpubNav())
        new_book.spine = spine

        output_path = os.path.join(output_dir, output_filename)
        epub.write_epub(output_path, new_book, {})
        return output_path


# ─── Main ───
def main():
    print("=" * 60)
    print("  EpubTranslator — Cloud Edition")
    print("=" * 60)

    # Tìm file EPUB đầu vào
    epub_files = list(Path(".").glob("*.epub"))
    if EPUB_INPUT and Path(EPUB_INPUT).exists():
        input_epub = EPUB_INPUT
    elif epub_files:
        input_epub = str(epub_files[0])
    else:
        print("LỖI: Không tìm thấy file EPUB nào trong thư mục.")
        print("Hãy đặt file EPUB vào repo hoặc cung cấp URL qua workflow_dispatch.")
        sys.exit(1)

    print(f"\n File đầu vào: {input_epub}")

    # Khởi tạo
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    processor = SimpleEpubProcessor()
    chapters = processor.read_epub(input_epub)
    translator = OpenRouterTranslator(OPENROUTER_API_KEY)

    # Checkpoint
    checkpoint = CheckpointManager()
    checkpoint.data["total_chapters"] = len(chapters)

    if checkpoint.is_complete():
        print("\n✅ Tất cả chương đã được dịch xong!")
        print("Đang đóng gói EPUB...")
    else:
        start_idx = checkpoint.get_next_index()
        print(f"\n Tổng số chương: {len(chapters)}")
        print(f"📊 Đã hoàn thành: {len(checkpoint.data['completed_chapters'])}")
        print(f"🚀 Bắt đầu từ chương {start_idx + 1}...")

        for i in range(start_idx, len(chapters)):
            chapter = chapters[i]
            print(f"\n{'─' * 50}")
            print(f"📝 Chương {i + 1}/{len(chapters)}: {chapter['title']}")

            # Bước 1: Dịch thô
            print("  → Đang dịch thô...")
            rough_text = translator.translate_text(chapter["text"], src_lang="ko")

            # Bước 2: AI chỉnh sửa
            print("  → Đang AI chỉnh sửa...")
            refined_text = translator.refine_text(rough_text, DEFAULT_REFINE_PROMPT)

            # Lưu HTML chương
            processor.save_chapter_html(i, refined_text, OUTPUT_DIR)

            # Checkpoint
            checkpoint.mark_complete(i, chapter["title"])
            print(f"  ✅ Hoàn thành chương {i + 1}")

            # Delay giữa các chương để tránh rate limit
            if i < len(chapters) - 1:
                print("  ⏳ Chờ 10s trước chương tiếp theo...")
                time.sleep(10)

    # Đóng gói EPUB
    print(f"\n📦 Đang đóng gói EPUB...")
    output_filename = f"{processor.book_title}_VI.epub"
    output_path = processor.build_epub(OUTPUT_DIR, output_filename)
    print(f"✅ Hoàn thành! File: {output_path}")

    # Dọn checkpoint nếu hoàn thành
    if checkpoint.is_complete():
        print("🗑️ Xóa file checkpoint (đã hoàn thành 100%)")
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)


if __name__ == "__main__":
    main()
