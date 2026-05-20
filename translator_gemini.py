import time
import requests

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

CHUNK_DELAY = 4


class GeminiTranslator:
    def __init__(self, api_key, model="gemini-2.0-flash",
                 temperature=0.3, log_callback=None):
        if model not in GEMINI_MODELS:
            raise ValueError(f"Model '{model}' không hợp lệ. Chọn một trong: {', '.join(GEMINI_MODELS)}")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.log_callback = log_callback

    def _log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def _estimate_tokens(self, text):
        return max(1, len(text) // 4)

    def _chunk_text(self, text, max_tokens=3000):
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

    def _call_api(self, prompt_text, max_retries=5, chunk_label=""):
        url = API_URL.format(model=self.model, api_key=self.api_key)
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": 8192,
            }
        }
        retries = 0
        while retries < max_retries:
            try:
                response = requests.post(url, json=payload, timeout=180)
                if response.status_code == 200:
                    data = response.json()
                    text = (data.get("candidates", [{}])[0]
                                .get("content", {})
                                .get("parts", [{}])[0]
                                .get("text", ""))
                    return text.strip()
                elif response.status_code == 429:
                    retries += 1
                    retry_after = response.headers.get("Retry-After", "")
                    wait_time = int(retry_after) if str(retry_after).isdigit() else min(30 * (2 ** (retries - 1)), 300)
                    self._log(f"[Gemini] Rate limit 429{chunk_label} — chờ {wait_time}s... ({retries})")
                    time.sleep(wait_time)
                elif response.status_code == 503:
                    retries += 1
                    self._log(f"[Gemini] Server 503{chunk_label} — chờ 30s... ({retries})")
                    time.sleep(30)
                else:
                    raise ValueError(f"Lỗi API {response.status_code}: {response.text[:200]}")
            except requests.exceptions.RequestException as e:
                retries += 1
                wait_time = 2 ** retries
                self._log(f"[Gemini] Lỗi kết nối, thử lại sau {wait_time}s...")
                time.sleep(wait_time)
        return None

    def translate_text(self, text, src_lang="ko", **kwargs):
        if not text or not text.strip():
            return text
        chunks = self._chunk_text(text, max_tokens=3000)
        results = []
        for i, chunk in enumerate(chunks):
            label = f" | Chunk {i+1}/{len(chunks)}"
            self._log(f"[Gemini] Dịch | Tokens ước tính: {self._estimate_tokens(chunk)}{label}")
            prompt = (
                f"Dịch đoạn văn sau từ ngôn ngữ nguồn (mã: {src_lang}) sang tiếng Việt tự nhiên. "
                f"Giữ nguyên văn phong, cảm xúc. Chỉ trả về bản dịch, không giải thích.\n\n{chunk}"
            )
            result = self._call_api(prompt, chunk_label=label)
            results.append(result if result is not None else chunk)
            if i < len(chunks) - 1:
                time.sleep(CHUNK_DELAY)
        return "\n\n".join(results)

    def refine_text(self, rough_text, refine_prompt="", src_lang="ko", **kwargs):
        if not rough_text or not rough_text.strip():
            return rough_text
        DEFAULT_PROMPT = (
            "Hãy chỉnh sửa bản dịch thô sau cho tự nhiên, đúng văn phong tiểu thuyết Việt Nam.\n"
            "- Sửa cách xưng hô cho phù hợp ngữ cảnh (anh/em/hắn/nàng/ta/ngươi...)\n"
            "- Sửa câu văn cứng nhắc thành tự nhiên, mượt mà\n"
            "- Sửa lỗi chính tả, dấu câu\n"
            "- Giữ nguyên tên riêng, địa danh, toàn bộ nội dung\n"
            "- Chỉ trả về đoạn văn đã chỉnh, không giải thích"
        )
        user_prompt = refine_prompt.strip() if refine_prompt.strip() else DEFAULT_PROMPT
        chunks = self._chunk_text(rough_text, max_tokens=3000)
        results = []
        for i, chunk in enumerate(chunks):
            label = f" | Chunk {i+1}/{len(chunks)}"
            self._log(f"[Gemini] Hiệu đính | Tokens ước tính: {self._estimate_tokens(chunk)}{label}")
            prompt = f"{user_prompt}\n\nBản dịch thô:\n{chunk}"
            result = self._call_api(prompt, chunk_label=label)
            results.append(result if result is not None else chunk)
            if i < len(chunks) - 1:
                time.sleep(CHUNK_DELAY)
        return "\n\n".join(results)
