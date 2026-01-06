# -*- coding: utf-8 -*-
"""
Role-based Configuration for Lemiex QC App
Dễ dàng điều chỉnh chức năng cho từng role
"""

# =============================================================================
# API ENDPOINTS
# =============================================================================
API_BASE_URL = "https://manage.lemiex.us"

API_ENDPOINTS = {
    # Auth
    "login": "/api/auth/login",
    "logout": "/api/auth/logout", 
    "me": "/api/auth/me",
    
    # Orders
    "orders": "/api/orders",
    "order_detail": "/api/orders/{order_id}",
    "track": "/api/orders/track/{order_id}",
    
    # Status & Actions
    "change_status_items": "/api/orders/change-status-items",
    "qc_reject": "/api/orders/qc-reject",
    "upload_video": "/api/orders/upload-video",
    
    # Label
    "update_label": "/api/orders/update-label",
    "webhook_label": "/api/update-label",
}

# =============================================================================
# MULTI-INSTANCE CONFIGURATION
# Cho phép chạy nhiều role trên cùng 1 máy
# =============================================================================
INSTANCE_CONFIG = {
    "QC": {
        "port": 8081,
        "window_title": "Lemiex QC",
    },
    "Packing": {
        "port": 8082,
        "window_title": "Lemiex Packing",
    },
    "Shipout": {
        "port": 8083,
        "window_title": "Lemiex Shipout",
    },
    "Admin": {
        "port": 8080,
        "window_title": "Lemiex Admin",
    },
}

# =============================================================================
# ROLE DEFINITIONS
# =============================================================================
ROLES = {
    "QC": {
        "name": "QC",
        "display_name": "Kiểm tra chất lượng",
        "color": "#10B981",  # Green
        "icon": "✓",
        
        # Chức năng được phép
        "features": {
            "scan_qr": True,
            "view_order": True,
            "record_video": True,
            "upload_video": True,
            "activate_positions": True,  # Activate từng position (front, back, etc.)
            "reject_item": True,
            "print_label": False,
        },
        
        # API permissions
        "api_actions": [
            "track",
            "change_status_items",
            "qc_reject",
            "upload_video",
        ],
        
        # Recording settings
        "recording": {
            "enabled": True,
            "base_duration": 15,      # Giây cơ bản
            "per_item_duration": 10,  # Thêm mỗi item
            "auto_start": True,
            "auto_upload": True,
        },
        
        # Positions to activate (QC activates all design positions)
        "activate_positions": ["front", "back", "sleeve_left", "sleeve_right", "neck"],
    },
    
    "Packing": {
        "name": "Packing", 
        "display_name": "Đóng gói",
        "color": "#F59E0B",  # Orange/Warning
        "icon": "📦",
        
        "features": {
            "scan_qr": True,
            "view_order": True,
            "record_video": True,
            "upload_video": True,
            "activate_positions": True,  # Activate packing position
            "reject_item": False,
            "print_label": False,
        },
        
        "api_actions": [
            "track",
            "change_status_items",
            "upload_video",
        ],
        
        "recording": {
            "enabled": True,
            "base_duration": 15,
            "per_item_duration": 10,
            "auto_start": True,
            "auto_upload": True,
        },
        
        # Packing chỉ activate 1 position cho tất cả items
        "activate_positions": ["front"],  # Dùng 'front' như packing position
    },
    
    "Shipout": {
        "name": "Shipout",
        "display_name": "Xuất hàng",
        "color": "#3B82F6",  # Blue
        "icon": "🚚",
        
        "features": {
            "scan_qr": True,
            "view_order": True,
            "record_video": False,
            "upload_video": False,
            "activate_positions": True,
            "reject_item": False,
            "print_label": True,  # Shipout có quyền in label
        },
        
        "api_actions": [
            "track",
            "change_status_items",
        ],
        
        "recording": {
            "enabled": False,
        },
        
        # Shipout activate tất cả positions để đánh dấu shipped
        "activate_positions": ["front", "back", "sleeve_left", "sleeve_right", "neck"],
        
        # Printing settings
        "printing": {
            "auto_print": True,           # Tự động in khi scan
            "preload_label": True,        # Pre-download label trước khi in
            "retry_on_fail": True,
            "max_retries": 2,
        },
    },
    
    "Admin": {
        "name": "Admin",
        "display_name": "Quản trị viên",
        "color": "#EF4444",  # Red
        "icon": "👑",
        
        "features": {
            "scan_qr": True,
            "view_order": True,
            "record_video": True,
            "upload_video": True,
            "activate_positions": True,
            "reject_item": True,
            "print_label": True,
            "manage_settings": True,
        },
        
        "api_actions": "*",  # All actions
        
        "recording": {
            "enabled": True,
            "base_duration": 15,
            "per_item_duration": 10,
            "auto_start": True,
            "auto_upload": True,
        },
        
        "activate_positions": ["front", "back", "sleeve_left", "sleeve_right", "neck"],
        
        "printing": {
            "auto_print": False,  # Admin chọn manual
            "preload_label": True,
        },
    },
}

# =============================================================================
# COMMON SETTINGS (áp dụng cho tất cả roles)
# =============================================================================
COMMON_SETTINGS = {
    # Order display
    "order_display": {
        "show_mockup": True,
        "show_color_image": True,
        "show_timeline": True,
        "multi_order_warning": True,  # Cảnh báo đơn nhiều áo
    },
    
    # Label settings
    "label": {
        "cache_enabled": True,
        "cache_duration": 3600,  # 1 hour
        "preload_on_scan": True,
        "print_timeout": 15,
    },
    
    # Scanner settings
    "scanner": {
        "auto_detect": True,
        "preferred_port": "COM3",
        "baud_rate": 9600,
        "debounce_ms": 500,  # Tránh scan trùng
    },
    
    # Camera settings
    "camera": {
        "auto_start": True,
        "resolution": [1280, 720],
        "fps": 30,
    },
    
    # API settings
    "api": {
        "timeout": 10,
        "retry_count": 3,
        "retry_delay": 1,
    },
    
    # UI settings
    "ui": {
        "theme": "dark",
        "language": "vi",
        "toast_duration": 3000,  # ms
        "animation_enabled": True,
    },
}

# =============================================================================
# LABEL OPTIMIZATION (để in nhanh nhất có thể)
# =============================================================================
LABEL_CONFIG = {
    # Pre-download strategy
    "preload": {
        "enabled": True,
        "on_track_api_response": True,   # Download ngay khi có track data
        "background_download": True,      # Download không blocking UI
    },
    
    # Cache strategy
    "cache": {
        "enabled": True,
        "directory": "temp_videos",       # Cùng folder với videos
        "max_age_hours": 24,              # Xóa cache cũ hơn 24h
        "use_url_hash": True,             # Dùng hash URL làm filename
    },
    
    # Print optimization
    "print": {
        "powershell_no_profile": True,    # -NoProfile cho khởi động nhanh
        "execution_policy": "Bypass",
        "timeout": 15,
        "paper_size": "4x6",              # Thermal label size
        "no_margins": True,
        "auto_fit": True,
        "portrait": True,
    },
    
    # Fallback options
    "fallback": {
        "use_mspaint": True,
        "show_manual_button": True,
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def get_role_config(role_name: str) -> dict:
    """Lấy config cho role cụ thể"""
    return ROLES.get(role_name, ROLES.get("QC"))  # Default to QC

def get_role_features(role_name: str) -> dict:
    """Lấy features của role"""
    role = get_role_config(role_name)
    return role.get("features", {})

def can_role_do(role_name: str, feature: str) -> bool:
    """Kiểm tra role có quyền làm feature không"""
    features = get_role_features(role_name)
    return features.get(feature, False)

def get_recording_settings(role_name: str) -> dict:
    """Lấy recording settings cho role"""
    role = get_role_config(role_name)
    return role.get("recording", {"enabled": False})

def get_activate_positions(role_name: str) -> list:
    """Lấy danh sách positions cần activate cho role"""
    role = get_role_config(role_name)
    return role.get("activate_positions", [])

def get_api_endpoint(name: str, **kwargs) -> str:
    """Lấy API endpoint URL đầy đủ với params"""
    endpoint = API_ENDPOINTS.get(name, "")
    if kwargs:
        endpoint = endpoint.format(**kwargs)
    return f"{API_BASE_URL}{endpoint}"
