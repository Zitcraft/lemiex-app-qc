"""
Camera Manager - Manages camera capture and preview.
Uses separate thread for capture to avoid blocking UI.
Uses queue-based frame delivery for smooth realtime preview.
"""

import logging
import threading
import queue
import time
import os
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import cv2
import numpy as np
import subprocess
import shutil

# Suppress OpenCV warnings to reduce console noise
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

from config import get_settings, CameraConfig

logger = logging.getLogger(__name__)


class CameraState(Enum):
    """Camera connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class CameraInfo:
    """Camera information."""
    id: str
    device_index: int
    resolution: Tuple[int, int]
    fps: int
    state: CameraState = CameraState.DISCONNECTED
    error_message: str = ""
    
    def is_connected(self) -> bool:
        return self.state == CameraState.CONNECTED
    
    def status_color(self) -> str:
        colors = {
            CameraState.DISCONNECTED: "#6B7280",
            CameraState.CONNECTING: "#F59E0B",
            CameraState.CONNECTED: "#10B981",
            CameraState.ERROR: "#EF4444"
        }
        return colors.get(self.state, "#6B7280")


class Camera:
    """
    Single camera instance.
    Captures frames in a separate thread and delivers via queue.
    """
    
    def __init__(
        self,
        camera_id: str,
        device_index: int,
        resolution: Tuple[int, int] = (1280, 720),
        fps: int = 30,
        on_state_change: Optional[Callable[["CameraInfo"], None]] = None
    ):
        """
        Initialize camera.
        
        Args:
            camera_id: Unique identifier
            device_index: OpenCV device index
            resolution: (width, height)
            fps: Frames per second
            on_state_change: Callback for state changes
        """
        self.info = CameraInfo(
            id=camera_id,
            device_index=device_index,
            resolution=resolution,
            fps=fps,
            state=CameraState.DISCONNECTED
        )
        
        self.on_state_change = on_state_change
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=2)  # Small queue for latest frames
        self._lock = threading.Lock()
        
        # Current frame (thread-safe access)
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        
        # Recording state
        self._recording = False
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._recording_lock = threading.Lock()
        self._recording_size: Optional[tuple] = None
        self._recording_filepath: str = ""
    
    def _update_state(self, state: CameraState, error_msg: str = "") -> None:
        """Update camera state."""
        self.info.state = state
        self.info.error_message = error_msg
        
        if self.on_state_change:
            try:
                self.on_state_change(self.info)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    def connect(self) -> bool:
        """Connect to camera."""
        with self._lock:
            if self._cap and self._cap.isOpened():
                return True
            
            self._update_state(CameraState.CONNECTING)
            
            try:
                # Try DirectShow backend first (better on Windows)
                self._cap = cv2.VideoCapture(self.info.device_index, cv2.CAP_DSHOW)
                
                if not self._cap.isOpened():
                    # Fallback to default backend
                    logger.debug(f"DirectShow failed for camera {self.info.device_index}, trying default backend")
                    self._cap = cv2.VideoCapture(self.info.device_index)
                
                if not self._cap.isOpened():
                    raise RuntimeError("Không thể mở camera")
                
                # Set resolution
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.info.resolution[0])
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.info.resolution[1])
                self._cap.set(cv2.CAP_PROP_FPS, self.info.fps)
                
                # Set buffer size to minimum for low latency
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # Test read to ensure camera works
                for _ in range(3):
                    ret, _ = self._cap.read()
                    if ret:
                        break
                    time.sleep(0.1)
                
                if not ret:
                    raise RuntimeError("Camera không đọc được frame")
                
                self._update_state(CameraState.CONNECTED)
                logger.info(f"Camera {self.info.id} connected")
                return True
                
            except Exception as e:
                error_msg = f"Lỗi kết nối camera: {e}"
                logger.error(error_msg)
                if self._cap:
                    self._cap.release()
                    self._cap = None
                self._update_state(CameraState.ERROR, error_msg)
                return False
    
    def disconnect(self) -> None:
        """Disconnect camera."""
        with self._lock:
            if self._cap:
                try:
                    self._cap.release()
                except Exception as e:
                    logger.error(f"Error releasing camera: {e}")
                finally:
                    self._cap = None
            
            self._update_state(CameraState.DISCONNECTED)
    
    def start(self) -> bool:
        """Start capture thread."""
        if self._running:
            return True
        
        if not self.connect():
            return False
        
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"Camera-{self.info.id}",
            daemon=True
        )
        self._thread.start()
        
        logger.info(f"Camera {self.info.id} started")
        return True
    
    def stop(self) -> None:
        """Stop capture thread."""
        self._running = False
        
        # Stop recording if active
        self.stop_recording()
        
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        self.disconnect()
        logger.info(f"Camera {self.info.id} stopped")
    
    def _capture_loop(self) -> None:
        """Main capture loop running in separate thread."""
        frame_interval = 1.0 / self.info.fps
        last_frame_time = 0
        consecutive_failures = 0
        max_failures = 10  # Reconnect after 10 consecutive failures
        
        while self._running:
            try:
                current_time = time.time()
                
                # Rate limiting
                if current_time - last_frame_time < frame_interval * 0.8:
                    time.sleep(0.001)
                    continue
                
                if not self._cap or not self._cap.isOpened():
                    if not self.connect():
                        time.sleep(1.0)
                        continue
                    consecutive_failures = 0
                
                ret, frame = self._cap.read()
                
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.warning(f"Camera {self.info.id} too many failures, reconnecting...")
                        self.disconnect()
                        time.sleep(0.5)
                        consecutive_failures = 0
                    else:
                        time.sleep(0.1)
                    continue
                
                # Success - reset failure counter
                consecutive_failures = 0
                
                last_frame_time = current_time
                
                # Update current frame (thread-safe)
                with self._frame_lock:
                    self._current_frame = frame.copy()
                
                # Add to queue (non-blocking, drop old frames)
                try:
                    # Clear queue if full
                    while not self._frame_queue.empty():
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            break
                    self._frame_queue.put_nowait(frame)
                except queue.Full:
                    pass
                
                # Write to video if recording
                self._write_recording_frame(frame)
                
            except Exception as e:
                logger.error(f"Capture error on camera {self.info.id}: {e}")
                time.sleep(0.1)
    
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get the latest frame (non-blocking).
        Returns None if no frame available.
        """
        with self._frame_lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
        return None
    
    def get_frame_from_queue(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """
        Get frame from queue (blocking with timeout).
        """
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def start_recording(self, filepath: str, codec: str = None) -> bool:
        """Start recording video."""
        with self._recording_lock:
            if self._recording:
                return True
            
            try:
                # Get actual frame size from current capture first
                frame = self.get_frame()
                if frame is not None:
                    h, w = frame.shape[:2]
                    self._recording_size = (w, h)
                else:
                    self._recording_size = self.info.resolution
                
                # Use MP4 format with mp4v codec
                mp4_filepath = filepath if filepath.endswith('.mp4') else filepath.replace('.avi', '.mp4')
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                
                self._video_writer = cv2.VideoWriter(
                    mp4_filepath,
                    fourcc,
                    float(self.info.fps),
                    self._recording_size
                )
                
                if not self._video_writer.isOpened():
                    # Fallback to XVID with AVI
                    logger.warning("mp4v failed, trying XVID fallback")
                    avi_filepath = mp4_filepath.replace('.mp4', '.avi')
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    self._video_writer = cv2.VideoWriter(
                        avi_filepath,
                        fourcc,
                        float(self.info.fps),
                        self._recording_size
                    )
                    mp4_filepath = avi_filepath
                
                if not self._video_writer.isOpened():
                    raise RuntimeError("Không thể tạo file video")
                
                # Test write a frame to verify
                if frame is not None:
                    self._video_writer.write(frame)
                
                self._recording = True
                self._recording_filepath = mp4_filepath
                logger.info(f"Camera {self.info.id} started recording: {mp4_filepath} at {self._recording_size})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start recording: {e}")
                if self._video_writer:
                    self._video_writer.release()
                    self._video_writer = None
                return False
    
    def stop_recording(self) -> str:
        """Stop recording video. Returns the filepath if was recording, None otherwise."""
        with self._recording_lock:
            if not self._recording:
                return None
            
            self._recording = False
            filepath = self._recording_filepath
            
            if self._video_writer:
                try:
                    self._video_writer.release()
                except Exception as e:
                    logger.error(f"Error releasing video writer: {e}")
                finally:
                    self._video_writer = None
            
            logger.info(f"Camera {self.info.id} stopped recording")
            
            # Convert to H.264 using ffmpeg for browser compatibility
            if filepath:
                filepath = self._convert_to_h264(filepath)
            
            return filepath
    
    def _convert_to_h264(self, input_path: str) -> str:
        """Convert video to H.264 codec using ffmpeg for browser playback."""
        try:
            # Get ffmpeg path from imageio-ffmpeg
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            
            # Create output path
            output_path = input_path.replace('.mp4', '_h264.mp4').replace('.avi', '_h264.mp4')
            
            # Run ffmpeg to convert to H.264
            cmd = [
                ffmpeg_path,
                '-i', input_path,
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-y',  # Overwrite output
                output_path
            ]
            
            logger.info(f"Converting video to H.264: {input_path} -> {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Remove original file and rename
                import os
                os.remove(input_path)
                final_path = input_path  # Keep original name
                os.rename(output_path, final_path)
                logger.info(f"Video converted successfully: {final_path}")
                return final_path
            else:
                logger.error(f"ffmpeg error: {result.stderr}")
                return input_path
                
        except Exception as e:
            logger.error(f"Failed to convert video to H.264: {e}")
            return input_path
    
    def _write_recording_frame(self, frame: np.ndarray) -> None:
        """Write frame to video if recording."""
        with self._recording_lock:
            if self._recording and self._video_writer:
                try:
                    # Ensure frame matches recording size
                    if hasattr(self, '_recording_size') and self._recording_size:
                        h, w = frame.shape[:2]
                        if (w, h) != self._recording_size:
                            frame = cv2.resize(frame, self._recording_size)
                    self._video_writer.write(frame)
                except Exception as e:
                    logger.error(f"Error writing frame: {e}")
    
    @property
    def is_recording(self) -> bool:
        """Check if camera is recording."""
        return self._recording
    
    @staticmethod
    def list_available_cameras(max_index: int = 5) -> List[int]:
        """List available camera indices."""
        available = []
        
        for idx in range(max_index):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                available.append(idx)
                cap.release()
        
        return available


class CameraManager:
    """
    Manages multiple cameras.
    """
    
    def __init__(
        self,
        on_camera_state_change: Optional[Callable[[CameraInfo], None]] = None
    ):
        """Initialize camera manager."""
        self.settings = get_settings()
        self.on_camera_state_change = on_camera_state_change
        
        self._cameras: Dict[str, Camera] = {}
        self._lock = threading.Lock()
        self._running = False
    
    @property
    def cameras(self) -> Dict[str, Camera]:
        """Get all cameras."""
        return self._cameras.copy()
    
    @property
    def connected_cameras(self) -> List[CameraInfo]:
        """Get connected camera info list."""
        return [
            cam.info for cam in self._cameras.values()
            if cam.info.is_connected()
        ]
    
    def initialize(self) -> None:
        """Initialize cameras from configuration."""
        for cam_config in self.settings.cameras:
            if cam_config.enabled:
                self.add_camera(cam_config)
    
    def add_camera(self, config: CameraConfig) -> Camera:
        """Add camera from configuration."""
        with self._lock:
            if config.id in self._cameras:
                self._cameras[config.id].stop()
            
            camera = Camera(
                camera_id=config.id,
                device_index=config.device_index,
                resolution=config.resolution,
                fps=config.fps,
                on_state_change=self._handle_state_change
            )
            
            self._cameras[config.id] = camera
            
            if self._running:
                camera.start()
            
            logger.info(f"Camera added: {config.id}")
            return camera
    
    def remove_camera(self, camera_id: str) -> None:
        """Remove camera by ID."""
        with self._lock:
            if camera_id in self._cameras:
                self._cameras[camera_id].stop()
                del self._cameras[camera_id]
                logger.info(f"Camera removed: {camera_id}")
    
    def get_camera(self, camera_id: str) -> Optional[Camera]:
        """Get camera by ID."""
        return self._cameras.get(camera_id)
    
    def get_primary_camera(self) -> Optional[Camera]:
        """Get the first available camera."""
        for camera in self._cameras.values():
            if camera.info.is_connected():
                return camera
        return list(self._cameras.values())[0] if self._cameras else None
    
    def start(self) -> None:
        """Start all cameras."""
        self._running = True
        
        with self._lock:
            for camera in self._cameras.values():
                camera.start()
        
        logger.info(f"Camera manager started with {len(self._cameras)} cameras")
    
    def stop(self) -> None:
        """Stop all cameras."""
        self._running = False
        
        with self._lock:
            for camera in self._cameras.values():
                camera.stop()
        
        logger.info("Camera manager stopped")
    
    def _handle_state_change(self, info: CameraInfo) -> None:
        """Handle camera state change."""
        if self.on_camera_state_change:
            try:
                self.on_camera_state_change(info)
            except Exception as e:
                logger.error(f"Camera state change handler error: {e}")
    
    def get_available_cameras(self) -> List[int]:
        """Get list of available camera indices."""
        return Camera.list_available_cameras()
