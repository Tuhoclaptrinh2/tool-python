import os
import re
import shutil
import html
from pathlib import Path
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub


class Chapter:
    def __init__(self, title, content_html, images=None):
        self.title = title
        self.content_html = content_html
        self.images = images or []


class ImageInfo:
    def __init__(self, filename, data, media_type):
        self.filename = filename
        self.data = data
        self.media_type = media_type


class EpubProcessor:
    def __init__(self):
        self.chapters = []
        self.images = []
        self.book_title = ""
        self.book_language = "en"

    def read_epub(self, filepath):
        self.chapters = []
        self.images = []

        book = epub.read_epub(filepath, options={"ignore_ncx": True})

        self.book_title = book.get_metadata("DC", "title")
        if self.book_title:
            self.book_title = self.book_title[0][0]
        else:
            self.book_title = Path(filepath).stem

        lang_meta = book.get_metadata("DC", "language")
        if lang_meta:
            self.book_language = lang_meta[0][0]

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_IMAGE:
                img_info = ImageInfo(
                    filename=item.get_name(),
                    data=item.get_content(),
                    media_type=item.media_type
                )
                self.images.append(img_info)

        self._extract_chapters_from_spine(book)

        if not self.chapters:
            self._extract_all_documents(book)

        if not self.chapters:
            raise ValueError("Không tìm thấy nội dung chương nào trong file EPUB. File có thể bị hỏng hoặc không có nội dung.")

        return self.chapters

    def _extract_chapters_from_spine(self, book):
        spine_items = book.spine
        if not spine_items:
            return

        for item_ref in spine_items:
            item_id = item_ref[0] if isinstance(item_ref, tuple) else item_ref
            item = book.get_item_with_id(item_id)
            if item is None:
                continue
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue

            html_content = item.get_content()
            if not html_content or len(html_content.strip()) == 0:
                continue

            html_content = html_content.decode("utf-8", errors="replace")

            soup = BeautifulSoup(html_content, "lxml")
            body_text = soup.get_text(strip=True) if soup.body else soup.get_text(strip=True)
            if not body_text:
                continue

            title_tag = soup.find(["h1", "h2", "h3"])
            chapter_title = title_tag.get_text(strip=True) if title_tag else item.get_name()

            self.chapters.append(Chapter(
                title=chapter_title,
                content_html=html_content,
            ))

    def _extract_all_documents(self, book):
        for item in book.get_items():
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue

            html_content = item.get_content()
            if not html_content or len(html_content.strip()) == 0:
                continue

            html_content = html_content.decode("utf-8", errors="replace")

            soup = BeautifulSoup(html_content, "lxml")
            body_text = soup.get_text(strip=True) if soup.body else soup.get_text(strip=True)
            if not body_text:
                continue

            title_tag = soup.find(["h1", "h2", "h3"])
            chapter_title = title_tag.get_text(strip=True) if title_tag else item.get_name()

            self.chapters.append(Chapter(
                title=chapter_title,
                content_html=html_content,
            ))

    def read_txt(self, filepath):
        self.chapters = []
        self.images = []

        encoding = self._detect_encoding(filepath)
        with open(filepath, "r", encoding=encoding, errors="replace") as f:
            content = f.read()

        if not content or not content.strip():
            raise ValueError("File TXT rỗng, không có nội dung để dịch.")

        self.book_title = Path(filepath).stem
        self.book_language = "en"

        chapters = self._split_txt_into_chapters(content)

        if len(chapters) <= 1 and len(content) > 5000:
            chunk_size = 5000
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                self.chapters.append(Chapter(
                    title=f"Phần {len(self.chapters) + 1}",
                    content_html=self._text_to_html(chunk),
                ))
        else:
            for title, text in chapters:
                self.chapters.append(Chapter(
                    title=title,
                    content_html=self._text_to_html(text),
                ))

        return self.chapters

    def _detect_encoding(self, filepath):
        encodings = ["utf-8", "gbk", "gb2312", "euc-kr", "cp949", "shift_jis", "latin-1"]
        for enc in encodings:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    f.read()
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "utf-8"

    def _split_txt_into_chapters(self, content):
        lines = content.split("\n")
        chapters = []
        current_title = "Mở đầu"
        current_lines = []

        chapter_patterns = [
            re.compile(r'^第\s*\d+\s*[章节回卷集篇]'),
            re.compile(r'^Chapter\s+\d+', re.IGNORECASE),
            re.compile(r'^장\s*\d+', re.IGNORECASE),
            re.compile(r'^제\s*\d+\s*장', re.IGNORECASE),
            re.compile(r'^\d+[\.、]\s*\S+'),
            re.compile(r'^[IVXLC]+\.\s'),
        ]

        for line in lines:
            stripped = line.strip()
            is_chapter_header = False

            for pattern in chapter_patterns:
                if pattern.match(stripped):
                    is_chapter_header = True
                    break

            if not is_chapter_header and stripped and len(stripped) < 60 and stripped.isupper() and not any(c.isdigit() for c in stripped):
                is_chapter_header = True

            if is_chapter_header:
                if current_lines:
                    chapters.append((current_title, "\n".join(current_lines).strip()))
                current_title = stripped
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            chapters.append((current_title, "\n".join(current_lines).strip()))

        if not chapters:
            chapters = [("Nội dung", content.strip())]

        return chapters

    def _text_to_html(self, text):
        paragraphs = text.split("\n\n")
        html_parts = []
        for para in paragraphs:
            para = para.strip()
            if para:
                para_lines = para.split("\n")
                inner = "<br/>".join(line.strip() for line in para_lines if line.strip())
                html_parts.append(f"<p>{inner}</p>")
        return "\n".join(html_parts)

    def build_html_from_translated_text(self, translated_text, images=None):
        # Clean and normalize the translated text
        translated_text = translated_text.strip()
        if not translated_text:
            return "<p>(Nội dung trống)</p>"
        
        # Split by double newlines first
        paragraphs = [p.strip() for p in translated_text.split("\n\n") if p.strip()]
        
        # If no double newlines, try splitting by single newlines
        if len(paragraphs) <= 1:
            paragraphs = [p.strip() for p in translated_text.split("\n") if p.strip()]
        
        # If still no paragraphs, treat entire text as one paragraph
        if not paragraphs:
            paragraphs = [translated_text]
        
        html_parts = []
        for para in paragraphs:
            # Clean up the paragraph
            para = re.sub(r'\s+', ' ', para).strip()
            if not para:
                continue
                
            # Split long paragraphs by sentence boundaries for better readability
            if len(para) > 500:
                sentences = re.split(r'(?<=[.!?。！？])\s+', para)
                if len(sentences) > 1:
                    # Group sentences into smaller chunks
                    chunk = []
                    chunk_len = 0
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        if chunk_len + len(sent) > 300 and chunk:
                            html_parts.append(f"<p>{' '.join(chunk)}</p>")
                            chunk = [sent]
                            chunk_len = len(sent)
                        else:
                            chunk.append(sent)
                            chunk_len += len(sent) + 1
                    if chunk:
                        html_parts.append(f"<p>{' '.join(chunk)}</p>")
                    continue
            
            para_lines = para.split("\n")
            inner = "<br/>".join(line.strip() for line in para_lines if line.strip())
            html_parts.append(f"<p>{inner}</p>")
        
        if not html_parts:
            return "<p>(Nội dung trống)</p>"
        
        return "\n".join(html_parts)

    def replace_text_in_html(self, html_content, translated_text):
        soup = BeautifulSoup(html_content, "lxml")

        paragraphs = translated_text.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if not paragraphs:
            return html_content

        body = soup.find("body")
        if not body:
            body = soup

        for p in body.find_all(True):
            if p.name in ["script", "style", "img", "br", "hr", "meta", "link"]:
                continue
            if p.name in ["p", "div"]:
                p.clear()

        para_idx = 0
        for p in body.find_all(["p", "div"]):
            if para_idx < len(paragraphs):
                p.string = paragraphs[para_idx]
                para_idx += 1

        if para_idx < len(paragraphs):
            for remaining in paragraphs[para_idx:]:
                new_p = soup.new_tag("p")
                new_p.string = remaining
                body.append(new_p)

        return str(soup)

    def _extract_body_content(self, html_content):
        if not html_content or not html_content.strip():
            return "<p>(Nội dung trống)</p>"
        soup = BeautifulSoup(html_content, "lxml")
        body = soup.find("body")
        if body:
            children = list(body.children)
            if not children:
                return "<p>(Nội dung trống)</p>"
            content = "".join(str(child) for child in children)
            if not content or not content.strip():
                return "<p>(Nội dung trống)</p>"
            return content
        # If no body tag, wrap content in a p tag to ensure valid HTML
        content = html_content.strip()
        if not content:
            return "<p>(Nội dung trống)</p>"
        # Wrap plain text in p tag if not already wrapped
        if not content.startswith("<"):
            return f"<p>{content}</p>"
        return content

    def write_epub(self, output_path, src_lang="en", translated_chapters=None):
        output_path = str(output_path)
        images_dir = os.path.join(os.path.dirname(output_path), "images")
        os.makedirs(images_dir, exist_ok=True)

        new_book = epub.EpubBook()

        new_book.set_identifier("epubtranslator_" + Path(output_path).stem)
        new_book.set_title(self.book_title + " (VI)")
        new_book.set_language("vi")
        new_book.add_metadata("DC", "creator", "EpubTranslator")

        for img in self.images:
            safe_filename = Path(img.filename).name
            safe_filename = safe_filename.replace("/", "_").replace("\\", "_")

            img_path = os.path.join(images_dir, safe_filename)
            with open(img_path, "wb") as f:
                f.write(img.data)

            new_book.add_item(epub.EpubItem(
                uid="img_" + safe_filename,
                file_name="images/" + safe_filename,
                media_type=img.media_type,
                content=img.data,
            ))

            for chapter in self.chapters:
                if img.filename in chapter.content_html:
                    chapter.content_html = chapter.content_html.replace(
                        img.filename, "images/" + safe_filename
                    )
                old_path_variants = [
                    img.filename.replace("/", "\\"),
                    img.filename.replace("\\", "/"),
                ]
                for variant in old_path_variants:
                    if variant in chapter.content_html:
                        chapter.content_html = chapter.content_html.replace(
                            variant, "images/" + safe_filename
                        )

        if not self.chapters:
            raise ValueError("Không có chương nào để ghi vào EPUB.")

        chapter_items = []
        spine = ["nav"]

        for i, chapter in enumerate(self.chapters):
            if translated_chapters and i < len(translated_chapters):
                translated_html = translated_chapters[i]
            else:
                translated_html = chapter.content_html

            if not translated_html or not translated_html.strip():
                translated_html = "<p>(Nội dung trống)</p>"

            chapter_file = f"chapter_{i}.xhtml"

            c = epub.EpubHtml(
                title=chapter.title,
                file_name=chapter_file,
                lang="vi",
            )
            body_content = self._extract_body_content(translated_html)
            if not body_content or not body_content.strip():
                body_content = "<p>(Nội dung trống)</p>"

            safe_title = html.escape(str(chapter.title))

            full_html = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<!DOCTYPE html>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi" lang="vi">\n'
                f'<head><meta charset="utf-8"/><title>{safe_title}</title></head>\n'
                f'<body>{body_content}</body>\n'
                '</html>'
            )

            c.set_content(full_html.encode('utf-8'))

            new_book.add_item(c)
            chapter_items.append(c)
            spine.append(c)

        new_book.add_item(epub.EpubNcx())
        new_book.add_item(epub.EpubNav())

        new_book.spine = spine

        epub.write_epub(output_path, new_book, {})

        return output_path, images_dir
