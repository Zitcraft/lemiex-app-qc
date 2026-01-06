"""
B2 Uploader - Upload videos to Backblaze B2 cloud storage.
"""

import logging
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
import os

from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class UploadProgress:
    """Upload progress information."""
    file_path: str
    total_bytes: int
    uploaded_bytes: int
    percent: float
    status: str  # "uploading", "done", "error"
    url: str = ""
    error_message: str = ""


class B2Uploader:
    """
    Uploads files to Backblaze B2 cloud storage.
    Supports background uploads with progress callbacks.
    """
    
    def __init__(
        self,
        on_progress: Optional[Callable[[UploadProgress], None]] = None,
        on_complete: Optional[Callable[[UploadProgress], None]] = None,
        on_error: Optional[Callable[[UploadProgress], None]] = None
    ):
        """
        Initialize B2 uploader.
        
        Args:
            on_progress: Callback for upload progress updates
            on_complete: Callback when upload completes
            on_error: Callback when upload fails
        """
        self.settings = get_settings()
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        
        self._bucket = None
        self._b2_api = None
        self._initialized = False
        self._lock = threading.Lock()
        
        # Upload queue for background processing
        self._upload_queue: list = []
        self._upload_thread: Optional[threading.Thread] = None
        self._running = False
    
    def initialize(self) -> bool:
        """
        Initialize B2 API connection.
        Returns True if successful.
        """
        with self._lock:
            if self._initialized:
                return True
            
            try:
                from b2sdk.v2 import InMemoryAccountInfo, B2Api
                
                key_id = self.settings.b2_key_id
                app_key = self.settings.b2_application_key
                bucket_name = self.settings.b2_bucket_name
                
                if not all([key_id, app_key, bucket_name]):
                    logger.warning("B2 credentials not configured")
                    return False
                
                info = InMemoryAccountInfo()
                self._b2_api = B2Api(info)
                self._b2_api.authorize_account("production", key_id, app_key)
                
                self._bucket = self._b2_api.get_bucket_by_name(bucket_name)
                
                self._initialized = True
                logger.info("B2 uploader initialized")
                return True
                
            except ImportError:
                logger.error("b2sdk not installed. Run: pip install b2sdk")
                return False
            except Exception as e:
                logger.error(f"Failed to initialize B2: {e}")
                return False
    
    def upload_file(
        self,
        file_path: Path,
        remote_name: Optional[str] = None,
        folder: str = "videos"
    ) -> Optional[str]:
        """
        Upload file to B2 (blocking).
        
        Args:
            file_path: Local file path
            remote_name: Remote file name (default: use local filename)
            folder: Remote folder path
            
        Returns:
            Public URL if successful, None otherwise
        """
        if not self.initialize():
            return None
        
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if remote_name is None:
                remote_name = file_path.name
            
            remote_path = f"{folder}/{remote_name}"
            file_size = file_path.stat().st_size
            
            logger.info(f"Uploading {file_path} to B2...")
            
            # Create progress tracker
            progress = UploadProgress(
                file_path=str(file_path),
                total_bytes=file_size,
                uploaded_bytes=0,
                percent=0,
                status="uploading"
            )
            
            # Upload with progress
            uploaded_file = self._bucket.upload_local_file(
                local_file=str(file_path),
                file_name=remote_path,
                progress_listener=self._create_progress_listener(progress)
            )
            
            # Get download URL
            download_url = self._b2_api.get_download_url_for_fileid(
                uploaded_file.id_
            )
            
            progress.status = "done"
            progress.percent = 100
            progress.url = download_url
            
            if self.on_complete:
                self.on_complete(progress)
            
            logger.info(f"Upload complete: {download_url}")
            return download_url
            
        except Exception as e:
            error_msg = f"Upload failed: {e}"
            logger.error(error_msg)
            
            if self.on_error:
                progress = UploadProgress(
                    file_path=str(file_path),
                    total_bytes=0,
                    uploaded_bytes=0,
                    percent=0,
                    status="error",
                    error_message=error_msg
                )
                self.on_error(progress)
            
            return None
    
    def upload_file_async(
        self,
        file_path: Path,
        remote_name: Optional[str] = None,
        folder: str = "videos"
    ) -> None:
        """
        Queue file for background upload.
        
        Args:
            file_path: Local file path
            remote_name: Remote file name
            folder: Remote folder path
        """
        self._upload_queue.append({
            "file_path": file_path,
            "remote_name": remote_name,
            "folder": folder
        })
        
        # Start background thread if not running
        self._ensure_upload_thread()
    
    def _ensure_upload_thread(self) -> None:
        """Ensure background upload thread is running."""
        if self._upload_thread is None or not self._upload_thread.is_alive():
            self._running = True
            self._upload_thread = threading.Thread(
                target=self._upload_loop,
                name="B2-Uploader",
                daemon=True
            )
            self._upload_thread.start()
    
    def _upload_loop(self) -> None:
        """Background upload loop."""
        while self._running and self._upload_queue:
            try:
                item = self._upload_queue.pop(0)
                self.upload_file(
                    file_path=item["file_path"],
                    remote_name=item["remote_name"],
                    folder=item["folder"]
                )
            except IndexError:
                break
            except Exception as e:
                logger.error(f"Background upload error: {e}")
    
    def _create_progress_listener(self, progress: UploadProgress):
        """Create a progress listener for B2 upload."""
        try:
            from b2sdk.v2 import AbstractProgressListener
            
            uploader = self
            
            class ProgressListener(AbstractProgressListener):
                def __init__(self):
                    super().__init__()
                    self.progress = progress
                
                def set_total_bytes(self, total_byte_count):
                    self.progress.total_bytes = total_byte_count
                
                def bytes_completed(self, byte_count):
                    self.progress.uploaded_bytes = byte_count
                    if self.progress.total_bytes > 0:
                        self.progress.percent = (
                            byte_count / self.progress.total_bytes * 100
                        )
                    
                    if uploader.on_progress:
                        uploader.on_progress(self.progress)
                
                def close(self):
                    pass
            
            return ProgressListener()
            
        except ImportError:
            return None
    
    def stop(self) -> None:
        """Stop background upload thread."""
        self._running = False
        if self._upload_thread:
            self._upload_thread.join(timeout=5.0)
            self._upload_thread = None
    
    def get_pending_count(self) -> int:
        """Get number of pending uploads."""
        return len(self._upload_queue)
