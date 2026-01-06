"""
Video Processor - Handles video post-processing.
Adds timestamp overlay and processes recorded videos.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import threading

import cv2
import numpy as np

from config import get_settings

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Processes video frames and files.
    - Adds timestamp overlay to frames
    - Post-processes recorded videos
    """
    
    def __init__(self):
        """Initialize video processor."""
        self.settings = get_settings()
        self._processing_lock = threading.Lock()
    
    def add_timestamp_overlay(
        self,
        frame: np.ndarray,
        timestamp: Optional[datetime] = None,
        position: str = "top-left",
        format_str: str = "%Y-%m-%d %H:%M:%S",
        font_scale: float = 0.7,
        color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
        order_id: Optional[str] = None
    ) -> np.ndarray:
        """
        Add timestamp overlay to a frame.
        
        Args:
            frame: Input frame
            timestamp: Timestamp to display (default: now)
            position: Position - "top-left", "top-right", "bottom-left", "bottom-right"
            format_str: strftime format string
            font_scale: Font scale
            color: Text color (BGR)
            bg_color: Background color (BGR)
            order_id: Optional order ID to display
            
        Returns:
            Frame with overlay
        """
        if frame is None:
            return frame
        
        result = frame.copy()
        h, w = result.shape[:2]
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Build display text
        time_text = timestamp.strftime(format_str)
        if order_id:
            display_text = f"Order #{order_id} | {time_text}"
        else:
            display_text = time_text
        
        # Get text size
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(
            display_text, font, font_scale, thickness
        )
        
        # Calculate position
        padding = 10
        if position == "top-left":
            x, y = padding, text_h + padding
        elif position == "top-right":
            x, y = w - text_w - padding, text_h + padding
        elif position == "bottom-left":
            x, y = padding, h - padding
        elif position == "bottom-right":
            x, y = w - text_w - padding, h - padding
        else:  # Default to top-left
            x, y = padding, text_h + padding
        
        # Draw background rectangle
        cv2.rectangle(
            result,
            (x - 5, y - text_h - 5),
            (x + text_w + 5, y + baseline + 5),
            bg_color,
            -1
        )
        
        # Draw text
        cv2.putText(
            result,
            display_text,
            (x, y),
            font,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA
        )
        
        return result
    
    def add_recording_indicator(
        self,
        frame: np.ndarray,
        is_recording: bool,
        duration_seconds: float = 0
    ) -> np.ndarray:
        """
        Add recording indicator to frame.
        
        Args:
            frame: Input frame
            is_recording: Whether currently recording
            duration_seconds: Recording duration in seconds
            
        Returns:
            Frame with indicator
        """
        if frame is None:
            return frame
        
        result = frame.copy()
        h, w = result.shape[:2]
        
        if is_recording:
            # Red recording dot
            center = (w - 30, 30)
            cv2.circle(result, center, 12, (0, 0, 255), -1)
            cv2.circle(result, center, 12, (255, 255, 255), 2)
            
            # Duration text
            minutes, seconds = divmod(int(duration_seconds), 60)
            hours, minutes = divmod(minutes, 60)
            
            if hours > 0:
                duration_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration_text = f"{minutes:02d}:{seconds:02d}"
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(
                result,
                duration_text,
                (w - 110, 38),
                font,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
        
        return result
    
    def process_frame_for_preview(
        self,
        frame: np.ndarray,
        target_size: Tuple[int, int],
        is_recording: bool = False,
        order_id: Optional[str] = None,
        recording_duration: float = 0
    ) -> np.ndarray:
        """
        Process frame for UI preview display.
        Resizes and adds overlays.
        
        Args:
            frame: Input frame (BGR)
            target_size: (width, height) for output
            is_recording: Whether currently recording
            order_id: Order ID being processed
            recording_duration: Recording duration in seconds
            
        Returns:
            Processed frame (RGB for Tkinter)
        """
        if frame is None:
            return self._create_placeholder_frame(target_size)
        
        # Resize frame maintaining aspect ratio
        result = self._resize_with_aspect(frame, target_size)
        
        # Add timestamp
        result = self.add_timestamp_overlay(
            result,
            position=self.settings.recording.timestamp_position,
            format_str=self.settings.recording.timestamp_format,
            order_id=order_id
        )
        
        # Add recording indicator
        if is_recording:
            result = self.add_recording_indicator(
                result,
                is_recording=True,
                duration_seconds=recording_duration
            )
        
        # Convert BGR to RGB for Tkinter
        result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        
        return result
    
    def _resize_with_aspect(
        self,
        frame: np.ndarray,
        target_size: Tuple[int, int]
    ) -> np.ndarray:
        """Resize frame maintaining aspect ratio with letterboxing."""
        h, w = frame.shape[:2]
        target_w, target_h = target_size
        
        # Calculate scale to fit
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        # Resize
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Create output with letterboxing
        result = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        result[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
        
        return result
    
    def _create_placeholder_frame(
        self,
        size: Tuple[int, int]
    ) -> np.ndarray:
        """Create a placeholder frame when no camera is available."""
        w, h = size
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (40, 40, 40)  # Dark gray
        
        # Add text
        text = "No Camera"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2
        
        (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        x = (w - text_w) // 2
        y = (h + text_h) // 2
        
        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            font_scale,
            (100, 100, 100),
            thickness,
            cv2.LINE_AA
        )
        
        # Already in RGB format for this placeholder
        return frame
    
    def add_timestamp_to_video(
        self,
        input_path: Path,
        output_path: Path,
        format_str: str = "%Y-%m-%d %H:%M:%S",
        order_id: Optional[str] = None
    ) -> bool:
        """
        Add timestamp overlay to an existing video file.
        
        Args:
            input_path: Input video file
            output_path: Output video file
            format_str: strftime format string
            order_id: Optional order ID to display
            
        Returns:
            True if successful
        """
        with self._processing_lock:
            try:
                cap = cv2.VideoCapture(str(input_path))
                if not cap.isOpened():
                    raise RuntimeError(f"Không thể mở video: {input_path}")
                
                # Get video properties
                fps = int(cap.get(cv2.CAP_PROP_FPS))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # Create writer
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                writer = cv2.VideoWriter(
                    str(output_path),
                    fourcc,
                    fps,
                    (width, height)
                )
                
                frame_count = 0
                start_time = datetime.now()
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Calculate timestamp for this frame
                    frame_time = start_time.timestamp() + (frame_count / fps)
                    timestamp = datetime.fromtimestamp(frame_time)
                    
                    # Add overlay
                    processed = self.add_timestamp_overlay(
                        frame,
                        timestamp=timestamp,
                        format_str=format_str,
                        order_id=order_id
                    )
                    
                    writer.write(processed)
                    frame_count += 1
                
                cap.release()
                writer.release()
                
                logger.info(f"Video processed: {output_path}")
                return True
                
            except Exception as e:
                logger.error(f"Error processing video: {e}")
                return False
