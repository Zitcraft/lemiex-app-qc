"""
Web Logger - Push activity logs to web API.
"""

import logging
import threading
import queue
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

from core import APIClient

logger = logging.getLogger(__name__)


class ActivityType(Enum):
    """Activity log types."""
    LOGIN = "login"
    LOGOUT = "logout"
    SCAN = "scan"
    ORDER_VIEW = "order_view"
    STATUS_UPDATE = "status_update"
    RECORDING_START = "recording_start"
    RECORDING_STOP = "recording_stop"
    UPLOAD_START = "upload_start"
    UPLOAD_COMPLETE = "upload_complete"
    ERROR = "error"


@dataclass
class ActivityLog:
    """Activity log entry."""
    activity_type: str
    message: str
    order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class WebLogger:
    """
    Logs activities to web API.
    Uses background thread to avoid blocking.
    """
    
    def __init__(self, api_client: APIClient):
        """
        Initialize web logger.
        
        Args:
            api_client: API client instance
        """
        self._api_client = api_client
        self._log_queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Local logging as fallback
        self._local_logger = logging.getLogger("activity")
    
    def start(self) -> None:
        """Start the background logging thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._log_loop,
            name="WebLogger",
            daemon=True
        )
        self._thread.start()
        logger.info("Web logger started")
    
    def stop(self) -> None:
        """Stop the background logging thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Web logger stopped")
    
    def log(
        self,
        activity_type: ActivityType,
        message: str,
        order_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an activity.
        
        Args:
            activity_type: Type of activity
            message: Log message
            order_id: Related order ID
            metadata: Additional metadata
        """
        log_entry = ActivityLog(
            activity_type=activity_type.value,
            message=message,
            order_id=order_id,
            metadata=metadata
        )
        
        # Add to queue
        try:
            self._log_queue.put_nowait(log_entry)
        except queue.Full:
            # Queue full, log locally
            self._local_logger.warning(f"Log queue full: {message}")
        
        # Also log locally for debugging
        self._local_logger.info(f"[{activity_type.value}] {message}")
    
    def log_login(self, user_email: str) -> None:
        """Log user login."""
        self.log(
            ActivityType.LOGIN,
            f"User logged in: {user_email}",
            metadata={"email": user_email}
        )
    
    def log_logout(self, user_email: str) -> None:
        """Log user logout."""
        self.log(
            ActivityType.LOGOUT,
            f"User logged out: {user_email}",
            metadata={"email": user_email}
        )
    
    def log_scan(self, order_id: str, scanner_id: str) -> None:
        """Log QR scan."""
        self.log(
            ActivityType.SCAN,
            f"QR scanned for order #{order_id}",
            order_id=order_id,
            metadata={"scanner_id": scanner_id}
        )
    
    def log_order_view(self, order_id: str, ref_id: str = "") -> None:
        """Log order view."""
        self.log(
            ActivityType.ORDER_VIEW,
            f"Order viewed: #{order_id} (ref: {ref_id})",
            order_id=order_id
        )
    
    def log_status_update(
        self,
        order_id: str,
        old_status: str,
        new_status: str
    ) -> None:
        """Log status update."""
        self.log(
            ActivityType.STATUS_UPDATE,
            f"Order status changed: {old_status} → {new_status}",
            order_id=order_id,
            metadata={
                "old_status": old_status,
                "new_status": new_status
            }
        )
    
    def log_recording_start(self, order_id: str, camera_id: str) -> None:
        """Log recording start."""
        self.log(
            ActivityType.RECORDING_START,
            f"Recording started for order #{order_id}",
            order_id=order_id,
            metadata={"camera_id": camera_id}
        )
    
    def log_recording_stop(
        self,
        order_id: str,
        duration_seconds: float
    ) -> None:
        """Log recording stop."""
        self.log(
            ActivityType.RECORDING_STOP,
            f"Recording stopped for order #{order_id} ({duration_seconds:.1f}s)",
            order_id=order_id,
            metadata={"duration": duration_seconds}
        )
    
    def log_upload_complete(self, order_id: str, video_url: str) -> None:
        """Log upload complete."""
        self.log(
            ActivityType.UPLOAD_COMPLETE,
            f"Video uploaded for order #{order_id}",
            order_id=order_id,
            metadata={"video_url": video_url}
        )
    
    def log_error(self, message: str, order_id: Optional[str] = None) -> None:
        """Log error."""
        self.log(
            ActivityType.ERROR,
            message,
            order_id=order_id
        )
    
    def _log_loop(self) -> None:
        """Background loop to push logs to API."""
        batch = []
        batch_size = 10
        flush_interval = 5.0  # seconds
        last_flush = datetime.now()
        
        while self._running:
            try:
                # Try to get log from queue
                try:
                    log_entry = self._log_queue.get(timeout=1.0)
                    batch.append(asdict(log_entry))
                except queue.Empty:
                    pass
                
                # Check if we should flush
                should_flush = (
                    len(batch) >= batch_size or
                    (datetime.now() - last_flush).total_seconds() >= flush_interval
                )
                
                if batch and should_flush:
                    self._flush_batch(batch)
                    batch = []
                    last_flush = datetime.now()
                    
            except Exception as e:
                logger.error(f"Log loop error: {e}")
        
        # Flush remaining logs on shutdown
        if batch:
            self._flush_batch(batch)
    
    def _flush_batch(self, batch: list) -> None:
        """Flush batch of logs to API."""
        try:
            self._api_client.post(
                "/activity-logs",
                json_data={"logs": batch}
            )
            logger.debug(f"Flushed {len(batch)} log entries")
        except Exception as e:
            # Log locally on failure
            for entry in batch:
                self._local_logger.warning(f"Failed to push: {entry}")
            logger.error(f"Failed to push logs: {e}")
