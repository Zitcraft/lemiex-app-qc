"""
Recording model - Represents a video recording session.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .status import RecordingStatus


@dataclass
class RecordingSession:
    """Represents a video recording session for an order."""
    id: str
    order_id: str
    camera_id: str
    status: RecordingStatus = RecordingStatus.IDLE
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # File info
    file_path: Optional[Path] = None
    file_size: int = 0
    duration_seconds: float = 0.0
    
    # Upload info
    upload_url: str = ""
    upload_progress: float = 0.0
    
    # Error handling
    error_message: str = ""
    retry_count: int = 0
    
    def start(self, file_path: Path) -> None:
        """Start recording session."""
        self.status = RecordingStatus.RECORDING
        self.start_time = datetime.now()
        self.file_path = file_path
        self.error_message = ""
    
    def stop(self) -> None:
        """Stop recording session."""
        self.end_time = datetime.now()
        self.status = RecordingStatus.PROCESSING
        
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration_seconds = delta.total_seconds()
    
    def set_uploading(self) -> None:
        """Set status to uploading."""
        self.status = RecordingStatus.UPLOADING
        self.upload_progress = 0.0
    
    def set_done(self, upload_url: str) -> None:
        """Set status to done with upload URL."""
        self.status = RecordingStatus.DONE
        self.upload_url = upload_url
        self.upload_progress = 100.0
    
    def set_error(self, message: str) -> None:
        """Set error status."""
        self.status = RecordingStatus.ERROR
        self.error_message = message
        self.retry_count += 1
    
    def is_recording(self) -> bool:
        """Check if session is currently recording."""
        return self.status == RecordingStatus.RECORDING
    
    def is_finished(self) -> bool:
        """Check if session is finished (done or error)."""
        return self.status in (RecordingStatus.DONE, RecordingStatus.ERROR)
    
    def duration_display(self) -> str:
        """Get formatted duration string."""
        if self.is_recording() and self.start_time:
            delta = datetime.now() - self.start_time
            seconds = int(delta.total_seconds())
        else:
            seconds = int(self.duration_seconds)
        
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def generate_filename(self) -> str:
        """Generate filename for the recording."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use .mp4 format with H.264 codec for browser playback
        return f"order_{self.order_id}_{timestamp}.mp4"
