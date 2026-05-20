import re
import time
from deep_translator import GoogleTranslator as _GoogleTranslator


LITERARY_WORD_PAIRS = {
    "nói": "thốt lên",
    "đi": "bước đi",
    "chạy": "phi thân",
    "nhìn": "ngắm nhìn",
    "xem": "chiêm ngưỡng",
    "ăn": "thưởng thức",
    "uống": "nhâm nhi",
    "ngồi": "an tọa",
    "đứng": "trùng trùng",
    "cười": "khẽ cười",
    "khóc": "rơi lệ",
    "buồn": "u sầu",
    "vui": "hân hoan",
    "giận": "phẫn nộ",
    "yêu": "trọng tình",
    "ghét": "căm phẫn",
    "sợ": "e ngại",
    "mệt": "mỏi mệt",
    "đẹp": "diễm lệ",
    "xấu": "thô kệch",
    "to": "vĩ đại",
    "nhỏ": "tiểu nhỏ",
    "cao": "ngạo nghễ",
    "thấp": "khiêm nhường",
    "nhanh": "thoăn thoắt",
    "chậm": "chầm chậm",
    "ánh mắt": "ánh nhìn",
    "giọng nói": "thanh âm",
    "trái tim": "tâm khảm",
    "con đường": "lối nhỏ",
}

PRONOUN_INFORMAL = {
    "tôi": "mình",
    "anh": "bạn",
    "chị": "bạn",
    "ông": "ông",
    "bà": "bà",
    "hắn": "y",
    "y": "hắn",
    "ta": "mình",
    "chúng tôi": "chúng mình",
    "ngài": "ông",
}

MAX_CHARS_PER_CHUNK = 2000
MAX_RETRIES = 3
RETRY_DELAY = 2


class GoogleTranslator:
    def __init__(self, src_lang="ko", chunk_size=5, auto_optimize=True, style="neutral"):
        self.src_lang = src_lang
        self.auto_optimize = auto_optimize
        self.style = style
        self._translator = None

    def _get_translator(self, dest_lang="vi"):
        if self._translator is None:
            self._translator = _GoogleTranslator(target=dest_lang)
        return self._translator

    def _split_by_chars(self, text, max_chars=MAX_CHARS_PER_CHUNK):
        if len(text) <= max_chars:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > max_chars and current:
                chunks.append("\n\n".join(current))
                current = [para]
                current_len = para_len
            else:
                current.append(para)
                current_len += para_len + 2

        if current:
            chunks.append("\n\n".join(current))

        final = []
        for chunk in chunks:
            if len(chunk) <= max_chars:
                final.append(chunk)
            else:
                sentences = re.split(r'(?<=[.!?。！？\n])\s*', chunk)
                buf = []
                buf_len = 0
                for sent in sentences:
                    sent_len = len(sent)
                    if buf_len + sent_len > max_chars and buf:
                        final.append(" ".join(buf))
                        buf = [sent]
                        buf_len = sent_len
                    else:
                        buf.append(sent)
                        buf_len += sent_len + 1
                if buf:
                    final.append(" ".join(buf))

        return final if final else [text]

    def _post_process(self, text):
        # Preserve paragraph breaks (\n\n) while cleaning other whitespace
        paragraphs = text.split("\n\n")
        processed_paragraphs = []
        for para in paragraphs:
            # Clean whitespace within each paragraph
            para = re.sub(r'[ \t]+', ' ', para)
            para = re.sub(r'\s+([,.;:!?)])', r'\1', para)
            para = re.sub(r'([(\[])\s+', r'\1', para)
            para = re.sub(r'([.!?。！？])\s*([a-zàáảãạăằắẵặâầấẫậèéẻẽẹêềếễệìíỉĩịòóỏõọôồốỗộơờớỡợùúủũụưừứữựỳýỷỹỵđ])',
                           lambda m: m.group(1) + " " + m.group(2).upper(), para)
            if para and len(para) > 0:
                first_char = para[0]
                if first_char.isalpha():
                    para = first_char.upper() + para[1:]
            processed_paragraphs.append(para.strip())
        
        text = "\n\n".join(processed_paragraphs)
        return text.strip()

    def _apply_literary_style(self, text):
        words = text.split()
        result = []
        for word in words:
            lower = word.lower()
            if lower in LITERARY_WORD_PAIRS:
                replacement = LITERARY_WORD_PAIRS[lower]
                if word[0].isupper():
                    replacement = replacement[0].upper() + replacement[1:]
                result.append(replacement)
            else:
                result.append(word)
        return " ".join(result)

    def _apply_conversational_style(self, text):
        words = text.split()
        result = []
        for word in words:
            lower = word.lower().strip(".,;:!?()[]{}\"'")
            if lower in PRONOUN_INFORMAL:
                replacement = PRONOUN_INFORMAL[lower]
                if word[0].isupper():
                    replacement = replacement[0].upper() + replacement[1:]
                result.append(replacement)
            else:
                result.append(word)
        return " ".join(result)

    def translate_text(self, text, src_lang=None, dest_lang="vi"):
        if src_lang:
            self.src_lang = src_lang

        if not text or not text.strip():
            return text

        translator = self._get_translator(dest_lang)

        chunks = self._split_by_chars(text, MAX_CHARS_PER_CHUNK)
        translated_chunks = []

        for i, chunk in enumerate(chunks):
            if not chunk or not chunk.strip():
                translated_chunks.append("")
                continue

            translated = None
            last_error = None

            for attempt in range(MAX_RETRIES):
                try:
                    result = translator.translate(chunk)
                    if result and result.strip():
                        # Validate that translation actually changed the text
                        # If result is identical to chunk, it might not have been translated
                        if result.strip() != chunk.strip():
                            translated = result
                            break
                        else:
                            # Translation returned same text - might be already in target language or failed
                            # Try one more time with slight modification
                            if attempt < MAX_RETRIES - 1:
                                time.sleep(RETRY_DELAY)
                                continue
                            else:
                                # If still same, accept it (might be proper names, etc.)
                                translated = result
                                break
                    else:
                        last_error = "Empty translation result"
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    last_error = str(e)
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                    continue

            if translated:
                translated_chunks.append(translated)
            else:
                # If all retries failed, log and use placeholder
                print(f"[Google] Chunk {i+1}/{len(chunks)} failed after {MAX_RETRIES} attempts: {last_error}")
                # Use a placeholder instead of original text to avoid mixed languages
                translated_chunks.append(f"[Dịch thất bại - đoạn {i+1}]")

            # Add delay between chunks to avoid rate limiting
            if i < len(chunks) - 1:
                time.sleep(0.5)

        result = "\n\n".join(translated_chunks)

        if self.auto_optimize:
            result = self._post_process(result)

            if self.style == "literary":
                result = self._apply_literary_style(result)
            elif self.style == "conversational":
                result = self._apply_conversational_style(result)

        return result
