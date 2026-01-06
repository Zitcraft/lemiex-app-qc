"""
Status enums for orders and recordings.
"""

from enum import Enum


class FulfillStatus(Enum):
    """Order fulfillment status enum."""
    NEW = "new"
    ON_HOLD = "on_hold"
    PRODUCING = "producing"
    SHIPPED = "shipped"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    
    @classmethod
    def from_string(cls, value: str) -> "FulfillStatus":
        """Convert string to FulfillStatus enum."""
        value_lower = value.lower().replace("-", "_").replace(" ", "_")
        for status in cls:
            if status.value == value_lower:
                return status
        return cls.NEW
    
    def display_name(self) -> str:
        """Get display name for the status."""
        names = {
            FulfillStatus.NEW: "Mới",
            FulfillStatus.ON_HOLD: "Tạm giữ",
            FulfillStatus.PRODUCING: "Đang sản xuất",
            FulfillStatus.SHIPPED: "Đã giao",
            FulfillStatus.COMPLETE: "Hoàn thành",
            FulfillStatus.CANCELLED: "Đã hủy"
        }
        return names.get(self, self.value)
    
    def color(self) -> str:
        """Get color for the status."""
        colors = {
            FulfillStatus.NEW: "#3B82F6",       # Blue
            FulfillStatus.ON_HOLD: "#F59E0B",   # Amber
            FulfillStatus.PRODUCING: "#8B5CF6", # Purple
            FulfillStatus.SHIPPED: "#06B6D4",   # Cyan
            FulfillStatus.COMPLETE: "#10B981",  # Green
            FulfillStatus.CANCELLED: "#EF4444"  # Red
        }
        return colors.get(self, "#6B7280")


class RecordingStatus(Enum):
    """Recording session status enum."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    UPLOADING = "uploading"
    DONE = "done"
    ERROR = "error"
    
    def display_name(self) -> str:
        """Get display name for the status."""
        names = {
            RecordingStatus.IDLE: "Sẵn sàng",
            RecordingStatus.RECORDING: "Đang ghi",
            RecordingStatus.PROCESSING: "Đang xử lý",
            RecordingStatus.UPLOADING: "Đang upload",
            RecordingStatus.DONE: "Hoàn thành",
            RecordingStatus.ERROR: "Lỗi"
        }
        return names.get(self, self.value)
    
    def color(self) -> str:
        """Get color for the status."""
        colors = {
            RecordingStatus.IDLE: "#6B7280",      # Gray
            RecordingStatus.RECORDING: "#EF4444", # Red
            RecordingStatus.PROCESSING: "#F59E0B",# Amber
            RecordingStatus.UPLOADING: "#3B82F6", # Blue
            RecordingStatus.DONE: "#10B981",      # Green
            RecordingStatus.ERROR: "#EF4444"      # Red
        }
        return colors.get(self, "#6B7280")
