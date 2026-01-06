"""
Scanner model - Represents scanner device information and scan results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class ScannerState(Enum):
    """Scanner connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class ScannerInfo:
    """Represents a barcode scanner device."""
    id: str
    com_port: str
    baud_rate: int = 9600
    state: ScannerState = ScannerState.DISCONNECTED
    last_scan_time: Optional[datetime] = None
    error_message: str = ""
    
    def is_connected(self) -> bool:
        """Check if scanner is connected."""
        return self.state == ScannerState.CONNECTED
    
    def display_status(self) -> str:
        """Get display status string."""
        status_map = {
            ScannerState.DISCONNECTED: "Đã ngắt kết nối",
            ScannerState.CONNECTING: "Đang kết nối...",
            ScannerState.CONNECTED: "Đã kết nối",
            ScannerState.ERROR: f"Lỗi: {self.error_message}"
        }
        return status_map.get(self.state, "Không xác định")
    
    def status_color(self) -> str:
        """Get status indicator color."""
        color_map = {
            ScannerState.DISCONNECTED: "#6B7280",  # Gray
            ScannerState.CONNECTING: "#F59E0B",    # Amber
            ScannerState.CONNECTED: "#10B981",     # Green
            ScannerState.ERROR: "#EF4444"          # Red
        }
        return color_map.get(self.state, "#6B7280")


@dataclass
class ScanResult:
    """Represents a scan result from barcode scanner."""
    raw_data: str
    scanner_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    order_id: Optional[str] = None
    is_valid: bool = False
    error_message: str = ""
    
    def __post_init__(self):
        """Parse the raw data after initialization."""
        self._parse_data()
    
    def _parse_data(self):
        """Parse raw scan data to extract order information."""
        from .order import Order
        
        if not self.raw_data:
            self.is_valid = False
            self.error_message = "Dữ liệu trống"
            return
        
        # Try to extract order ID from URL or raw data
        order_id = Order.from_qr_url(self.raw_data)
        
        if order_id:
            self.order_id = order_id
            self.is_valid = True
        else:
            self.is_valid = False
            self.error_message = "Không thể đọc mã đơn hàng từ QR code"
