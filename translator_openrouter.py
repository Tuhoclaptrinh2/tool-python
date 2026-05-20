import time
import requests


DEFAULT_SYSTEM_PROMPT = (
    "Bạn là dịch giả chuyên nghiệp. Hãy dịch đoạn văn sau sang tiếng Việt tự nhiên, "
    "giữ nguyên văn phong và cảm xúc của bản gốc. Chỉ trả về bản dịch, không giải thích."
)

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Delay giữa các chunk để tránh rate limit (giây)
CHUNK_DELAY = 5
# Delay giữa các chunk khi refine (ít request hơn nên cần ít delay hơn)
REFINE_CHUNK_DELAY = 3


class OpenRouterTranslator:
    def __init__(self, api_key, model="google/gemma-4-31b-it:free",
                 temperature=0.3, system_prompt=None, log_callback=None):
        if not (model.endswith(":free") or model == "openrouter/free"):
            raise ValueError("Model này yêu cầu trả phí, hãy chọn model free")

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

    def _wait_rate_limit(self, response, retries, label=""):
        """Đọc Retry-After header, nếu không có thì exponential backoff."""
        retry_after = response.headers.get("Retry-After", "")
        if str(retry_after).isdigit():
            wait_time = int(retry_after)
        else:
            # 30s → 60s → 120s → 240s → tối đa 300s
            wait_time = min(30 * (2 ** (retries - 1)), 300)
        self._log(f"[API] Rate limit 429{label} — chờ {wait_time}s rồi thử lại ({retries})...")
        time.sleep(wait_time)

    def _chunk_text(self, text, max_tokens=1500):
        """
        Chunk lớn hơn để giảm số lần gọi API → ít rate limit hơn.
        Default tăng từ 800 lên 1500 tokens.
        """
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

    def _call_api(self, headers, payload, max_retries=5, chunk_label=""):
        """
        Gọi API với retry thông minh:
        - 429: đọc Retry-After, exponential backoff
        - 503: chờ 30s rồi thử lại
        - Lỗi mạng: exponential backoff
        Trả về content string hoặc None nếu thất bại.
        """
        retries = 0
        while retries < max_retries:
            try:
                response = requests.post(API_URL, headers=headers, json=payload, timeout=180)

                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
                    return content.strip()

                elif response.status_code == 429:
                    retries += 1
                    if retries >= max_retries:
                        self._log(f"[API] Rate limit 429 sau {max_retries} lần thử{chunk_label} — bỏ qua")
                        return None
                    self._wait_rate_limit(response, retries, chunk_label)

                elif response.status_code == 503:
                    retries += 1
                    if retries >= max_retries:
                        self._log(f"[API] Server 503 sau {max_retries} lần thử{chunk_label} — bỏ qua")
                        return None
                    wait_time = 30
                    self._log(f"[API] Server 503{chunk_label} — chờ {wait_time}s... ({retries})")
                    time.sleep(wait_time)

                elif response.status_code == 402:
                    raise ValueError("Model này yêu cầu trả phí, hãy chọn model free")

                else:
                    error_msg = response.text[:200]
                    raise ValueError(f"Lỗi API {response.status_code}: {error_msg}")

            except requests.exceptions.RequestException as e:
                retries += 1
                if retries >= max_retries:
                    self._log(f"[API] Lỗi kết nối sau {max_retries} lần thử: {e}")
                    return None
                wait_time = 2 ** retries
                self._log(f"[API] Lỗi kết nối, thử lại sau {wait_time}s...")
                time.sleep(wait_time)

        return None

    def translate_text(self, text, src_lang="ko", model=None, temperature=None):
        if not text or not text.strip():
            return text

        if model:
            if not (model.endswith(":free") or model == "openrouter/free"):
                raise ValueError("Model này yêu cầu trả phí, hãy chọn model free")
            self.model = model

        if temperature is not None:
            self.temperature = temperature

        chunks = self._chunk_text(text, max_tokens=1500)
        translated_chunks = []

        for i, chunk in enumerate(chunks):
            estimated_tokens = self._estimate_tokens(chunk)
            start_time = time.time()
            chunk_label = f" | Chunk {i+1}/{len(chunks)}"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://epubtranslator.local",
                "X-Title": "EpubTranslator",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Dịch đoạn văn sau từ ngôn ngữ nguồn (mã: {src_lang}) sang tiếng Việt:\n\n{chunk}"},
                ],
                "temperature": self.temperature,
                "max_tokens": 4000,
            }

            self._log(f"[API] Gọi model: {self.model} | Tokens ước tính: {estimated_tokens}{chunk_label}")

            result = self._call_api(headers, payload, max_retries=5, chunk_label=chunk_label)

            elapsed = time.time() - start_time
            if result is not None:
                self._log(f"[API] Thành công | {elapsed:.1f}s{chunk_label}")
                translated_chunks.append(result)
            else:
                self._log(f"[API] Thất bại sau {elapsed:.1f}s{chunk_label} — giữ nguyên bản gốc")
                translated_chunks.append(chunk)

            if i < len(chunks) - 1:
                time.sleep(CHUNK_DELAY)

        return "\n\n".join(translated_chunks)

    def refine_text(self, rough_text, refine_prompt="", src_lang="ko", max_tokens=1500):
        """Chỉnh sửa bản dịch thô tiếng Việt, KHÔNG dịch lại từ đầu."""
        if not rough_text or not rough_text.strip():
            return rough_text

        REFINE_SYSTEM_PROMPT = (
            "Bạn là biên tập viên tiếng Việt chuyên hiệu đính bản dịch tiểu thuyết. "
            "Chỉ trả về đoạn văn đã chỉnh, không giải thích, không thêm bớt nội dung."
        )

        DEFAULT_REFINE_PROMPT = (
            "Hãy chỉnh sửa bản dịch thô sau cho tự nhiên, đúng văn phong tiểu thuyết Việt Nam.\n"
            "- Sửa cách xưng hô cho phù hợp ngữ cảnh (anh/em/hắn/nàng/ta/ngươi...)\n"
            "- Sửa câu văn cứng nhắc thành tự nhiên, mượt mà\n"
            "- Sửa lỗi chính tả, dấu câu\n"
            "- Giữ nguyên tên riêng, địa danh, toàn bộ nội dung\n"
            "- Chỉ trả về đoạn văn đã chỉnh, không giải thích"
        )

        user_prompt = refine_prompt.strip() if refine_prompt.strip() else DEFAULT_REFINE_PROMPT
        chunks = self._chunk_text(rough_text, max_tokens=max_tokens)
        refined_chunks = []

        for i, chunk in enumerate(chunks):
            estimated_tokens = self._estimate_tokens(chunk)
            start_time = time.time()
            chunk_label = f" | Chunk {i+1}/{len(chunks)}"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://epubtranslator.local",
                "X-Title": "EpubTranslator",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": REFINE_SYSTEM_PROMPT},
                    {"role": "user", "content": f"{user_prompt}\n\nBản dịch thô:\n{chunk}"},
                ],
                "temperature": self.temperature,
                "max_tokens": 4000,
            }

            self._log(f"[API] Hiệu đính model: {self.model} | Tokens ước tính: {estimated_tokens}{chunk_label}")

            result = self._call_api(headers, payload, max_retries=5, chunk_label=chunk_label)

            elapsed = time.time() - start_time
            if result is not None:
                self._log(f"[API] Hiệu đính thành công | {elapsed:.1f}s{chunk_label}")
                refined_chunks.append(result)
            else:
                self._log(f"[API] Hiệu đính thất bại{chunk_label} — giữ nguyên bản thô")
                refined_chunks.append(chunk)

            if i < len(chunks) - 1:
                time.sleep(REFINE_CHUNK_DELAY)

        return "\n\n".join(refined_chunks)
