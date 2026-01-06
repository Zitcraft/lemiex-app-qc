"""
Recording Service - Orchestrates auto-record workflow.
Manages recording sessions tied to orders.
"""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Callable
import uuid

from models import RecordingSession, RecordingStatus, Order
from camera import CameraManager, Camera
from config import get_settings
from .b2_uploader import B2Uploader

logger = logging.getLogger(__name__)


class RecordingService:
    """
    Orchestrates the auto-record workflow:
    - Start recording when order is scanned
    - Stop recording when same order is scanned again
    - Handle order switching (stop current, start new)
    - Upload completed recordings
    """
    
    def __init__(
        self,
        camera_manager: CameraManager,
        b2_uploader: Optional[B2Uploader] = None,
        on_recording_start: Optional[Callable[[RecordingSession], None]] = None,
        on_recording_stop: Optional[Callable[[RecordingSession], None]] = None,
        on_upload_complete: Optional[Callable[[RecordingSession], None]] = None
    ):
        """
        Initialize recording service.
        
        Args:
            camera_manager: Camera manager instance
            b2_uploader: B2 uploader instance
            on_recording_start: Callback when recording starts
            on_recording_stop: Callback when recording stops
            on_upload_complete: Callback when upload completes
        """
        self.settings = get_settings()
        self._camera_manager = camera_manager
        self._b2_uploader = b2_uploader
        
        self.on_recording_start = on_recording_start
        self.on_recording_stop = on_recording_stop
        self.on_upload_complete = on_upload_complete
        
        # Active recording sessions: order_id -> RecordingSession
        self._active_sessions: Dict[str, RecordingSession] = {}
        
        # Completed sessions pending upload
        self._pending_uploads: Dict[str, RecordingSession] = {}
        
        self._lock = threading.Lock()
        
        # Currently active order (for quick reference)
        self._current_order_id: Optional[str] = None
    
    @property
    def current_order_id(self) -> Optional[str]:
        """Get currently recording order ID."""
        return self._current_order_id
    
    @property
    def is_recording(self) -> bool:
        """Check if any recording is active."""
        return bool(self._active_sessions)
    
    def get_active_session(self, order_id: str) -> Optional[RecordingSession]:
        """Get active session for order."""
        return self._active_sessions.get(order_id)
    
    def get_current_session(self) -> Optional[RecordingSession]:
        """Get the current active recording session."""
        if self._current_order_id:
            return self._active_sessions.get(self._current_order_id)
        return None
    
    def handle_scan(self, order_id: str, order: Optional[Order] = None) -> RecordingSession:
        """
        Handle a new scan event.
        Implements the auto-record workflow:
        - If no active recording: start new recording
        - If same order scanned: stop recording and upload
        - If different order scanned: stop current, start new
        
        Args:
            order_id: Scanned order ID
            order: Optional order object
            
        Returns:
            The relevant RecordingSession
        """
        with self._lock:
            # Case 1: Same order scanned again - stop and upload
            if order_id in self._active_sessions:
                logger.info(f"Same order scanned, stopping recording: {order_id}")
                return self._stop_recording(order_id)
            
            # Case 2: Different order - stop current if exists, start new
            if self._current_order_id and self._current_order_id != order_id:
                logger.info(f"New order, switching from {self._current_order_id} to {order_id}")
                self._stop_recording(self._current_order_id)
            
            # Start new recording
            return self._start_recording(order_id)
    
    def _start_recording(self, order_id: str) -> RecordingSession:
        """Start a new recording session."""
        # Get primary camera
        camera = self._camera_manager.get_primary_camera()
        if not camera:
            logger.error("No camera available for recording")
            session = RecordingSession(
                id=str(uuid.uuid4()),
                order_id=order_id,
                camera_id="none"
            )
            session.set_error("Không có camera")
            return session
        
        # Create session
        session = RecordingSession(
            id=str(uuid.uuid4()),
            order_id=order_id,
            camera_id=camera.info.id
        )
        
        # Generate file path
        temp_dir = self.settings.get_temp_videos_path()
        filename = session.generate_filename()
        file_path = temp_dir / filename
        
        # Start camera recording
        if camera.start_recording(
            filepath=str(file_path),
            codec=self.settings.recording.video_codec
        ):
            session.start(file_path)
            self._active_sessions[order_id] = session
            self._current_order_id = order_id
            
            logger.info(f"Recording started: {order_id} -> {file_path}")
            
            if self.on_recording_start:
                self.on_recording_start(session)
        else:
            session.set_error("Không thể bắt đầu ghi hình")
        
        return session
    
    def _stop_recording(self, order_id: str) -> RecordingSession:
        """Stop recording and queue for upload."""
        session = self._active_sessions.pop(order_id, None)
        
        if not session:
            logger.warning(f"No active session for order: {order_id}")
            return RecordingSession(
                id=str(uuid.uuid4()),
                order_id=order_id,
                camera_id="none",
                status=RecordingStatus.ERROR
            )
        
        # Stop camera recording
        camera = self._camera_manager.get_camera(session.camera_id)
        if camera:
            camera.stop_recording()
        
        session.stop()
        
        # Update current order
        if self._current_order_id == order_id:
            self._current_order_id = None
        
        logger.info(f"Recording stopped: {order_id}, duration: {session.duration_seconds:.1f}s")
        
        if self.on_recording_stop:
            self.on_recording_stop(session)
        
        # Queue for upload if auto-upload enabled
        if self.settings.recording.auto_upload:
            self._queue_upload(session)
        
        return session
    
    def _queue_upload(self, session: RecordingSession) -> None:
        """Queue session for upload."""
        if not self._b2_uploader:
            logger.warning("B2 uploader not configured")
            return
        
        if not session.file_path or not session.file_path.exists():
            logger.error(f"Recording file not found: {session.file_path}")
            session.set_error("File không tồn tại")
            return
        
        session.set_uploading()
        self._pending_uploads[session.order_id] = session
        
        # Start background upload
        threading.Thread(
            target=self._upload_session,
            args=(session,),
            daemon=True
        ).start()
    
    def _upload_session(self, session: RecordingSession) -> None:
        """Upload session video (runs in background thread)."""
        try:
            url = self._b2_uploader.upload_file(
                file_path=session.file_path,
                folder=f"orders/{session.order_id}"
            )
            
            if url:
                session.set_done(url)
                logger.info(f"Upload complete: {session.order_id} -> {url}")
                
                # Delete local file if configured
                if self.settings.recording.delete_after_upload:
                    try:
                        session.file_path.unlink()
                        logger.debug(f"Deleted local file: {session.file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete file: {e}")
                
                if self.on_upload_complete:
                    self.on_upload_complete(session)
            else:
                session.set_error("Upload thất bại")
                
        except Exception as e:
            logger.error(f"Upload error: {e}")
            session.set_error(str(e))
        finally:
            self._pending_uploads.pop(session.order_id, None)
    
    def stop_all(self) -> None:
        """Stop all active recordings."""
        with self._lock:
            order_ids = list(self._active_sessions.keys())
            for order_id in order_ids:
                self._stop_recording(order_id)
    
    def get_recording_duration(self, order_id: str) -> float:
        """Get current recording duration for an order."""
        session = self._active_sessions.get(order_id)
        if session and session.is_recording() and session.start_time:
            return (datetime.now() - session.start_time).total_seconds()
        return 0.0
    
    def get_current_recording_duration(self) -> float:
        """Get duration of current recording."""
        if self._current_order_id:
            return self.get_recording_duration(self._current_order_id)
        return 0.0
