# Lemiex Order Management App

Ứng dụng quản lý đơn hàng nội bộ với tích hợp **Multi-Scanner**, **Camera Recording**, và **Auto-Upload** video lên Backblaze B2.

## 📋 Tính năng

### Core Features
- ✅ **Đăng nhập** - Xác thực qua API Lemiex
- ✅ **Multi-Scanner Support** - Hỗ trợ nhiều scanner USB COM cùng lúc
- ✅ **QR Code Scanning** - Quét QR code chứa URL đơn hàng
- ✅ **Order Display** - Hiển thị chi tiết đơn hàng (sản phẩm, shipping, giá, seller)
- ✅ **Status Update** - Cập nhật trạng thái fulfill đơn hàng
- ✅ **Camera Recording** - Ghi hình với timestamp overlay
- ✅ **Auto-Record** - Tự động bắt đầu/dừng recording khi scan
- ✅ **B2 Upload** - Upload video lên Backblaze B2 cloud storage
- ✅ **Web Logging** - Đẩy activity logs lên hệ thống web

### Auto-Record Workflow
```
[Scan QR #1] → 🔵 New → 🔴 Start Recording
                              │
[Scan QR #1 again] → Stop → 🟠 Processing → Upload → 🟢 Done
                              │
[Scan QR #2 (khác)] → Stop #1 → Upload (background) → 🔴 Start #2
```

## 🏗️ Cấu trúc Project

```
OrderManagementApp/
├── main.py                        # Entry point
├── requirements.txt               # Python dependencies
├── .env.example                   # Template cho environment variables
├── config/
│   ├── __init__.py
│   ├── settings.py                # Config loader
│   └── config.yaml                # Local settings (COM, camera)
├── core/
│   ├── __init__.py
│   ├── api_client.py              # Web API client
│   └── auth_manager.py            # Token management
├── scanner/
│   ├── __init__.py
│   ├── scanner_manager.py         # Multi-scanner controller
│   └── com_scanner.py             # Single scanner interface
├── camera/
│   ├── __init__.py
│   ├── camera_manager.py          # Camera & recording
│   └── video_processor.py         # Timestamp overlay
├── services/
│   ├── __init__.py
│   ├── order_service.py           # Order operations
│   ├── b2_uploader.py             # Video upload to B2
│   ├── web_logger.py              # Push logs to web API
│   └── recording_service.py       # Auto-record orchestration
├── models/
│   ├── __init__.py
│   ├── order.py                   # Order dataclass
│   ├── status.py                  # Status enum
│   ├── scanner.py                 # Scanner model
│   └── recording.py               # Recording session model
├── ui/
│   ├── __init__.py
│   ├── main_window.py             # Main layout
│   ├── settings_panel.py          # Slide-out settings nav
│   ├── camera_view.py             # Camera preview grid
│   ├── order_view.py              # Order details
│   ├── login_view.py              # Login screen
│   └── scanner_status.py          # Scanner status indicators
├── assets/
│   └── qr_codes/                  # Setup QR images
├── temp_videos/                   # Temp video storage
└── logs/                          # Local debug logs
```

## 🚀 Cài đặt

### Yêu cầu hệ thống
- Python 3.10+
- Windows 10/11
- Webcam (USB hoặc built-in)
- Barcode Scanner (USB COM)
- Internet connection

### 1. Clone và cài đặt dependencies

```bash
cd "d:\2025 Code\app-Lemiex\OrderManagementApp"
pip install -r requirements.txt
```

### 2. Cấu hình Environment Variables

Copy `.env.example` thành `.env` và điền thông tin:

```env
# API Configuration
API_BASE_URL=https://manage.lemiex.us/api

# Backblaze B2 Configuration
B2_KEY_ID=your_key_id
B2_APPLICATION_KEY=your_app_key
B2_BUCKET_NAME=your_bucket_name

# Optional: Default credentials (for dev only)
DEFAULT_EMAIL=
DEFAULT_PASSWORD=
```

### 3. Cấu hình Scanner và Camera

Chỉnh sửa `config/config.yaml`:

```yaml
# Scanner Configuration
scanners:
  - id: scanner_1
    com_port: COM3
    baud_rate: 9600
    enabled: true
  - id: scanner_2
    com_port: COM4
    baud_rate: 9600
    enabled: false

# Camera Configuration
cameras:
  - id: camera_0
    device_index: 0
    resolution: [1280, 720]
    fps: 30
    enabled: true
  - id: camera_1
    device_index: 1
    resolution: [1280, 720]
    fps: 30
    enabled: false

# Recording Settings
recording:
  timestamp_format: "%Y-%m-%d %H:%M:%S"
  timestamp_position: "top-left"
  video_codec: "mp4v"
  auto_upload: true
  delete_after_upload: true

# UI Settings
ui:
  theme: "dark"
  language: "vi"
  window_size: [1400, 900]
```

### 4. Chạy ứng dụng

```bash
python main.py
```

## 📖 Hướng dẫn sử dụng

### Đăng nhập
1. Mở ứng dụng
2. Nhập email và password
3. Click "Đăng nhập"

### Scan đơn hàng
1. Kết nối scanner (tự động detect COM port)
2. Quét QR code trên đơn hàng
3. Thông tin đơn hiển thị tự động
4. Camera tự động bắt đầu ghi hình

### Cập nhật trạng thái
1. Xem chi tiết đơn hàng
2. Click button trạng thái mới (On Hold, Producing, Shipped, Complete)
3. Trạng thái được cập nhật lên hệ thống

### Kết thúc recording
1. Quét lại QR code cùng đơn → Dừng recording & upload
2. Hoặc quét QR đơn khác → Tự động dừng recording hiện tại, upload background, bắt đầu recording mới

### Settings Panel
1. Click icon ⚙️ góc phải trên
2. Panel settings slide ra
3. Cấu hình scanners, cameras, account
4. Click bên ngoài panel để đóng

## 🔌 API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/auth/login` | Đăng nhập, lấy token |
| GET | `/orders/{id}` | Lấy chi tiết đơn hàng |
| PUT | `/orders/change-fulfill-status` | Cập nhật trạng thái đơn |
| POST | `/activity-logs` | Ghi nhận activity (nếu có) |
| POST | `/orders/{id}/videos` | Gắn video vào đơn (nếu có) |

## 🎨 UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ☰ LEMIEX ORDER MANAGER                              [⚙️]      │
├─────────────────────────────────────────────────────────────────┤
│                                                    ┌────────────┤
│  ┌──────────────┐  ┌──────────────┐               │ SETTINGS   │
│  │  Camera 1    │  │  Camera 2    │               │ ─────────  │
│  │  🔴 REC      │  │  ⚫ IDLE     │               │            │
│  │  Order #123  │  │  Ready       │    ◄──────    │ Scanners   │
│  └──────────────┘  └──────────────┘    Slide-out  │ ☐ COM3     │
│                                                    │ ☐ COM4     │
│  ┌─────────────────────────────────┐              │            │
│  │  ORDER DETAILS                  │              │ Cameras    │
│  │  ID: #123                       │              │ ☐ Webcam 0 │
│  │  Status: Producing              │              │ ☐ Webcam 1 │
│  │  Items: T-Shirt x2              │              │            │
│  │  Ship to: John Doe, CA          │              │ Account    │
│  └─────────────────────────────────┘              │ [Logout]   │
│                                                    └────────────┤
│  [On Hold] [Producing] [Shipped] [Complete]                     │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 Troubleshooting

### Scanner không nhận
1. Kiểm tra COM port trong Device Manager
2. Đảm bảo driver đã cài đặt
3. Thử đổi COM port trong Settings
4. Restart ứng dụng

### Camera không hiển thị
1. Kiểm tra camera có được sử dụng bởi app khác không
2. Thử đổi camera index trong Settings
3. Kiểm tra permission camera trong Windows Settings

### Upload video thất bại
1. Kiểm tra kết nối internet
2. Verify B2 credentials trong `.env`
3. Video được lưu trong `temp_videos/` để retry sau

## 📝 Changelog

### v1.0.0 (2025-12-25)
- Initial release
- Multi-scanner support
- Camera recording với timestamp
- Auto-record workflow
- Backblaze B2 integration
- Slide-out settings panel

## 📄 License

Internal use only - Lemiex © 2025
