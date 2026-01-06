# Hướng dẫn Triển khai Lemiex QC App

## 📋 Tổng quan các phương pháp

| Phương pháp | Ưu điểm | Nhược điểm | Phù hợp với |
|-------------|---------|------------|-------------|
| **Portable + Auto-Update** ✅ | Đơn giản, update dễ | Cần Python | Nội bộ, <20 người |
| **Network Folder** | Cực kỳ đơn giản | Cần mạng LAN | Cùng văn phòng |
| **EXE (PyInstaller)** | Không cần Python | Khó update, file lớn | Phân phối rộng |
| **Docker** | Consistent environment | Phức tạp | DevOps team |

---

## 🏆 KHUYẾN NGHỊ: Portable Folder + Network Update

### Lý do:
1. **Đơn giản**: Người dùng chỉ cần unzip và chạy
2. **Update dễ**: Chỉ copy file mới, không cần tải lại toàn bộ
3. **Nhẹ**: ~50MB thay vì 200MB+ như EXE
4. **Debug dễ**: Có thể xem/sửa code khi cần

---

## 🚀 Cách triển khai

### Bước 1: Build package

```powershell
cd "d:\2025 Code\Lemiex-app-qc"
python build.py
```

Kết quả trong thư mục `dist/`:
- `LemiexQC_v1.0.0.zip` - Bản cài đặt đầy đủ
- `update_v1.0.0.zip` - Bản update (chỉ code)
- `LemiexQC_v1.0.0/` - Thư mục portable

### Bước 2: Thiết lập Update Server

#### Option A: Shared Network Folder (Đơn giản nhất)

1. Tạo thư mục share trên server:
   ```
   \\server\shared\LemiexQC\
   ├── latest_version.json
   ├── v1.0.0/
   │   └── update.zip
   ├── v1.1.0/
   │   └── update.zip
   └── full_install/
       └── LemiexQC_v1.1.0.zip
   ```

2. Cập nhật `latest_version.json`:
   ```json
   {
     "version": "1.1.0",
     "changelog": "- Thêm tính năng ABC\n- Sửa lỗi XYZ",
     "required": false
   }
   ```

3. Cấu hình trong `updater/version.py`:
   ```python
   UPDATE_CONFIG = {
       "network_folder": {
           "enabled": True,
           "path": r"\\server\shared\LemiexQC\updates",
           "version_file": "latest_version.json"
       }
   }
   ```

#### Option B: GitHub Releases

1. Push code lên GitHub
2. Tạo Release với tag `v1.0.0`
3. Upload `update.zip` vào Release
4. Cập nhật repo name trong `updater/version.py`

#### Option C: Web Server

1. Upload files lên web server:
   ```
   https://your-domain.com/lemiex-qc/
   ├── version.json
   └── releases/
       └── v1.0.0/
           └── update.zip
   ```

### Bước 3: Phân phối cho người dùng

#### Cài đặt lần đầu:

1. Copy thư mục `LemiexQC_v1.0.0` hoặc gửi file zip
2. Người dùng giải nén vào `C:\LemiexQC\` hoặc Desktop
3. Chạy `Install_Dependencies.bat` (nếu chưa có Python)
4. Chạy `LemiexQC.bat` để khởi động

#### Update sau này:

Người dùng chỉ cần:
1. Chạy `Update.bat`
2. Nhấn `Y` để đồng ý update
3. Khởi động lại app

---

## 🔧 Phương pháp thay thế

### A. Build EXE với PyInstaller

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --icon=web/images/icon.ico --add-data "web;web" --add-data "config;config" app_eel.py
```

**Ưu điểm**: Không cần Python trên máy user
**Nhược điểm**: 
- File lớn (~150-200MB)
- Khó update (phải tải lại toàn bộ)
- Antivirus hay block

### B. Docker (Không khuyến khích cho desktop app)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8080
CMD ["python", "app_eel.py", "--no-browser"]
```

**Vấn đề**: 
- Eel cần browser, Docker khó handle GUI
- Overkill cho ứng dụng nội bộ
- Người dùng phải cài Docker Desktop

---

## 📁 Cấu trúc thư mục phân phối

```
LemiexQC/
├── python/                    # (Tùy chọn) Embedded Python
│   ├── python.exe
│   └── Lib/
├── web/                       # Frontend
│   ├── css/
│   ├── js/
│   └── index.html
├── config/                    # Cấu hình
│   └── roles_config.py
├── updater/                   # Hệ thống update
│   ├── version.py
│   └── auto_update.py
├── app_eel.py                 # Main app
├── version.json               # Version hiện tại
├── requirements.txt           # Dependencies
├── LemiexQC.bat              # Launcher
├── Update.bat                # Update checker
├── Install_Dependencies.bat  # Cài thư viện
└── README.txt                # Hướng dẫn
```

---

## 🔄 Quy trình Release mới

1. **Cập nhật version** trong `version.json` và `build.py`
2. **Test** đầy đủ trên máy dev
3. **Build**: `python build.py`
4. **Upload**:
   - Copy `update_v1.1.0.zip` vào network folder
   - Cập nhật `latest_version.json`
5. **Thông báo** người dùng chạy `Update.bat`

---

## 🆘 Troubleshooting

### "Python không tìm thấy"
- Cài Python 3.9+ từ python.org
- Hoặc copy Embedded Python vào thư mục `python/`

### "Module not found"
- Chạy `Install_Dependencies.bat`

### "Update failed"
- Kiểm tra kết nối mạng đến server
- Chạy lại `Update.bat`
- Nếu lỗi, thư mục `backup/` chứa bản cũ

### "Antivirus block"
- Thêm exception cho thư mục LemiexQC
- Hoặc sign code với certificate (tốn phí)

---

## 📞 Liên hệ hỗ trợ

- Slack: #lemiex-qc-support
- Email: support@lemiex.us
