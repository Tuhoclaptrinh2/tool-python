import time
import requests


GROQ_MODELS = {
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama-3.3-70b-versatile",
}

DEFAULT_SYSTEM_PROMPT = (
    "Bạn là dịch giả chuyên nghiệp. Hãy dịch đoạn văn sau sang tiếng Việt tự nhiên, "
    "giữ nguyên văn phong và cảm xúc của bản gốc. Chỉ trả về bản dịch, không giải thích."
)

API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqTranslator:
    def __init__(self, api_key, model="llama-3.1-8b-instant",
                 temperature=0.3, system_prompt=None, log_callback=None):
        if model not in GROQ_MODELS:
            raise ValueError(f"Model '{model}' không nằm trong danh sách Groq miễn phí")

        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.log_callback = log_callback

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def _estimate_tokens(self, text):
        return max(1, len(text) // 4)

    def _chunk_text(self, text, max_tokens=400):
        chunks = []
        current = []
        current_tokens = 0

        paragraphs = text.split("\n\n")
        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)
            if current_tokens + para_tokens > max_tokens and current:
                chunks.append("\n\n".join(current))
                current = [para]
                current_tokens = para_tokens
            else:
                current.append(para)
                current_tokens += para_tokens

        if current:
            chunks.append("\n\n".join(current))

        if not chunks and text:
            words = text.split()
            current = []
            current_tokens = 0
            for word in words:
                word_tokens = self._estimate_tokens(word)
                if current_tokens + word_tokens > max_tokens and current:
                    chunks.append(" ".join(current))
                    current = [word]
                    current_tokens = word_tokens
                else:
                    current.append(word)
                    current_tokens += word_tokens
            if current:
                chunks.append(" ".join(current))

        return chunks if chunks else [text]

    def translate_text(self, text, src_lang="ko", model=None, temperature=None):
        if not text or not text.strip():
            return text

        if model:
            if model not in GROQ_MODELS:
                raise ValueError(f"Model '{model}' không nằm trong danh sách Groq miễn phí")
            self.model = model

        if temperature is not None:
            self.temperature = temperature

        chunks = self._chunk_text(text, max_tokens=400)
        translated_chunks = []

        retry_delays = [15, 30, 60, 90, 120]
        max_retries = 5

        for i, chunk in enumerate(chunks):
            estimated_tokens = self._estimate_tokens(chunk)
            start_time = time.time()

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            user_message = f"Dịch đoạn văn sau từ ngôn ngữ nguồn (mã: {src_lang}) sang tiếng Việt:\n\n{chunk}"

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": self.temperature,
                "max_tokens": 4000,
            }

            retries = 0
            success = False

            while retries <= max_retries:
                try:
                    self._log(f"[Groq] Gọi model: {self.model} | Tokens ước tính: {estimated_tokens} | Chunk {i+1}/{len(chunks)}")

                    response = requests.post(API_URL, headers=headers, json=payload, timeout=120)

                    if response.status_code == 200:
                        data = response.json()
                        translated = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        elapsed = time.time() - start_time
                        self._log(f"[Groq] Thành công | Thời gian: {elapsed:.1f}s | Chunk {i+1}/{len(chunks)}")
                        translated_chunks.append(translated.strip())
                        success = True
                        break

                    elif response.status_code == 429:
                        if retries >= max_retries:
                            self._log(f"[Groq] Rate limit (429) sau {max_retries} lần thử — bỏ qua chunk này")
                            translated_chunks.append(chunk)
                            success = True
                            break
                        wait_time = retry_delays[retries]
                        self._log(f"[Groq] Rate limit (429) — chờ {wait_time}s rồi thử lại ({retries+1}/{max_retries})...")
                        time.sleep(wait_time)
                        retries += 1

                    else:
                        error_msg = response.text[:200]
                        raise ValueError(f"Lỗi API {response.status_code}: {error_msg}")

                except requests.exceptions.RequestException as e:
                    retries += 1
                    if retries > max_retries:
                        self._log(f"[Groq] Lỗi kết nối sau {max_retries} lần thử: {e}")
                        translated_chunks.append(chunk)
                        success = True
                        break
                    wait_time = retry_delays[min(retries - 1, len(retry_delays) - 1)]
                    self._log(f"[Groq] Lỗi kết nối, thử lại sau {wait_time}s...")
                    time.sleep(wait_time)

            if not success:
                translated_chunks.append(chunk)

            if i < len(chunks) - 1:
                time.sleep(3)

        return "\n\n".join(translated_chunks)
