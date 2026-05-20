# EpubTranslator — Công Cụ Dịch Truyện EPUB/TXT Sang Tiếng Việt

## Giới thiệu
EpubTranslator là ứng dụng desktop giúp dịch tiểu thuyết từ file EPUB và TXT sang tiếng Việt, hỗ trợ 4 ngôn ngữ nguồn: Tiếng Hàn, Tiếng Trung, Tiếng Nhật, Tiếng Anh.

## Hướng dẫn cài đặt

### Yêu cầu hệ thống
- Python 3.10 trở lên
- pip (trình quản lý gói Python)

### Cài đặt dependencies
```bash
cd EpubTranslator
pip install -r requirements.txt
```

## Cách chạy ứng dụng
```bash
python main.py
```

## Cách lấy API key OpenRouter miễn phí

1. Truy cập: https://openrouter.ai/keys
2. Đăng ký tài khoản (miễn phí)
3. Tạo API key mới
4. Copy key và dán vào phần "Cài đặt AI Dịch" trong ứng dụng

### Lưu ý quan trọng
- **Chỉ dùng model có đuôi `:free`** hoặc `openrouter/free` để không phát sinh chi phí
- Các model miễn phí được hỗ trợ:
  - `google/gemma-4-31b-it:free`
  - `qwen/qwen3-next-80b-a3b-instruct:free`
  - `openai/gpt-oss-120b:free`
  - `deepseek/deepseek-v4-flash:free`
  - `cognitivecomputations/dolphin-mistral-24b-venice-edition:free`
  - `openrouter/free` (tự động chọn model miễn phí phù hợp)
- API key được lưu mã hóa base64 trong file config, không lưu dạng plaintext

## Định dạng hỗ trợ

### Đầu vào
- `.epub` — File EPUB tiêu chuẩn
- `.txt` — File văn bản thuần (tự động phát hiện encoding)

### Đầu ra
- File `.epub` đã dịch sang tiếng Việt (định dạng: `{ten_truyen}_VI.epub`)
- Thư mục `images/` chứa tất cả ảnh gốc từ file nguồn

## Tính năng chính

### Tab 1 — Dịch truyện
- Chọn file EPUB/TXT và thư mục xuất
- Hai phương pháp dịch: Google Dịch hoặc AI (OpenRouter)
- Cài đặt chi tiết cho từng phương pháp
- Thanh tiến trình, log hoạt động, nút dừng

### Tab 2 — Tủ truyện
- Quản lý sách đã dịch
- Tìm kiếm, mở file, xóa khỏi tủ
- Thêm thủ công file EPUB có sẵn

### Tab 3 — Hướng dẫn
- Hướng dẫn sử dụng chi tiết
- Cách lấy API key OpenRouter
- Lưu ý khi dùng Google Dịch

## Giới hạn

### Google Dịch
- Có thể bị chặn nếu dịch quá nhanh (đã có delay 0.5s giữa các lần gọi)
- Chất lượng dịch không bằng AI, đặc biệt với văn học
- Không giữ được sắc thái văn chương tốt

### AI Dịch (OpenRouter)
- Cần có API key
- Tốc độ phụ thuộc vào server OpenRouter
- Model miễn phí có giới hạn rate (429 error — sẽ tự retry sau 60s)

### EPUB
- File EPUB DRM-protected không được hỗ trợ
- Ảnh động (GIF) được giữ nguyên nhưng không xử lý
- Font chữ nhúng (embedded fonts) được giữ nguyên

## Cấu trúc dự án
```
EpubTranslator/
├── main.py              # Entry point
├── ui_main.py           # Giao diện chính
├── ui_library.py        # Tab tủ truyện
├── translator_google.py # Engine Google Dịch
├── translator_openrouter.py  # Engine AI OpenRouter
├── epub_processor.py    # Xử lý EPUB/TXT
├── library_db.py        # Database SQLite
├── config.py            # Quản lý cấu hình
├── worker.py            # Thread dịch nền
├── requirements.txt     # Dependencies
└── README.md            # Tài liệu này
```

## License
MIT License
