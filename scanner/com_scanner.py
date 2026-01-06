"""
COM Scanner - Single USB barcode scanner interface.
Reads from serial port in a separate thread for realtime scanning.
"""

import logging
import threading
import time
from typing import Optional, Callable
from datetime import datetime

import serial
import serial.tools.list_ports

from models import ScannerInfo, ScanResult, ScannerState

logger = logging.getLogger(__name__)


class COMScanner:
    """
    Single barcode scanner interface.
    Runs in a separate thread to avoid blocking the UI.
    """
    
    def __init__(
        self,
        scanner_id: str,
        com_port: str,
        baud_rate: int = 9600,
        on_scan: Optional[Callable[[ScanResult], None]] = None,
        on_state_change: Optional[Callable[[ScannerInfo], None]] = None
    ):
        """
        Initialize COM scanner.
        
        Args:
            scanner_id: Unique identifier for this scanner
            com_port: COM port (e.g., "COM3")
            baud_rate: Baud rate (default 9600)
            on_scan: Callback when scan is received
            on_state_change: Callback when state changes
        """
        self.info = ScannerInfo(
            id=scanner_id,
            com_port=com_port,
            baud_rate=baud_rate,
            state=ScannerState.DISCONNECTED
        )
        
        self.on_scan = on_scan
        self.on_state_change = on_state_change
        
        self._serial: Optional[serial.Serial] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._buffer = ""
        self._last_data_time = 0.0  # Track last data receive time
    
    @property
    def is_connected(self) -> bool:
        """Check if scanner is connected."""
        return self.info.state == ScannerState.CONNECTED
    
    def _update_state(self, state: ScannerState, error_msg: str = "") -> None:
        """Update scanner state and notify callback."""
        self.info.state = state
        self.info.error_message = error_msg
        
        if self.on_state_change:
            try:
                self.on_state_change(self.info)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    def connect(self) -> bool:
        """
        Connect to the scanner.
        Returns True if successful.
        """
        with self._lock:
            if self._serial and self._serial.is_open:
                return True
            
            self._update_state(ScannerState.CONNECTING)
            
            try:
                self._serial = serial.Serial(
                    port=self.info.com_port,
                    baudrate=self.info.baud_rate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.1  # Non-blocking read
                )
                
                self._update_state(ScannerState.CONNECTED)
                logger.info(f"Scanner {self.info.id} connected on {self.info.com_port}")
                return True
                
            except serial.SerialException as e:
                error_msg = f"Không thể kết nối {self.info.com_port}: {e}"
                logger.error(error_msg)
                self._update_state(ScannerState.ERROR, error_msg)
                return False
    
    def disconnect(self) -> None:
        """Disconnect from the scanner."""
        with self._lock:
            if self._serial:
                try:
                    self._serial.close()
                except Exception as e:
                    logger.error(f"Error closing serial port: {e}")
                finally:
                    self._serial = None
            
            self._update_state(ScannerState.DISCONNECTED)
            logger.info(f"Scanner {self.info.id} disconnected")
    
    def start(self) -> bool:
        """
        Start the scanner reading thread.
        Returns True if started successfully.
        """
        if self._running:
            return True
        
        if not self.connect():
            return False
        
        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop,
            name=f"Scanner-{self.info.id}",
            daemon=True
        )
        self._thread.start()
        
        logger.info(f"Scanner {self.info.id} reading thread started")
        return True
    
    def stop(self) -> None:
        """Stop the scanner reading thread."""
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        self.disconnect()
        logger.info(f"Scanner {self.info.id} stopped")
    
    def _read_loop(self) -> None:
        """
        Main reading loop running in separate thread.
        Reads data from serial port and emits scan events.
        """
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    # Try to reconnect
                    if not self.connect():
                        time.sleep(2.0)  # Wait before retry
                        continue
                
                # Read available data
                if self._serial.in_waiting:
                    data = self._serial.read(self._serial.in_waiting)
                    logger.debug(f"Raw bytes from {self.info.id}: {data!r}")
                    try:
                        text = data.decode('utf-8', errors='ignore')
                        logger.info(f"Decoded text from {self.info.id}: {text!r}")
                        self._last_data_time = time.time()
                        self._process_data(text)
                    except UnicodeDecodeError as e:
                        logger.error(f"Decode error: {e}")
                else:
                    # Check if buffer has data and timeout elapsed (no newline scanner)
                    if self._buffer and (time.time() - self._last_data_time) > 0.1:
                        line = self._buffer.strip()
                        self._buffer = ""
                        if line:
                            logger.info(f"Buffer timeout, processing: {line}")
                            self._handle_scan(line)
                    # Small sleep to prevent CPU spinning
                    time.sleep(0.01)
                    
            except serial.SerialException as e:
                logger.error(f"Serial error on {self.info.id}: {e}")
                self._update_state(ScannerState.ERROR, str(e))
                self.disconnect()
                time.sleep(2.0)  # Wait before retry
                
            except Exception as e:
                logger.error(f"Unexpected error in scanner loop: {e}")
                time.sleep(0.1)
    
    def _process_data(self, text: str) -> None:
        """
        Process received data and extract complete scans.
        Handles buffering for partial reads.
        """
        self._buffer += text
        
        # Check if buffer contains a complete URL (no newline needed)
        if 'lemiex.us/track/' in self._buffer:
            # URL detected, process immediately
            line = self._buffer.strip()
            self._buffer = ""
            if line:
                self._handle_scan(line)
            return
        
        # Process complete lines (scans end with newline)
        while '\n' in self._buffer or '\r' in self._buffer:
            # Find line ending
            idx = -1
            for sep in ['\r\n', '\n', '\r']:
                pos = self._buffer.find(sep)
                if pos >= 0:
                    if idx < 0 or pos < idx:
                        idx = pos
                        sep_len = len(sep)
            
            if idx >= 0:
                line = self._buffer[:idx].strip()
                self._buffer = self._buffer[idx + sep_len:]
                
                if line:
                    self._handle_scan(line)
            else:
                break
    
    def _handle_scan(self, raw_data: str) -> None:
        """Handle a complete scan."""
        logger.info(f"Scanner {self.info.id} scan: {raw_data}")
        
        # Update last scan time
        self.info.last_scan_time = datetime.now()
        
        # Create scan result
        result = ScanResult(
            raw_data=raw_data,
            scanner_id=self.info.id
        )
        
        # Notify callback
        if self.on_scan:
            try:
                self.on_scan(result)
            except Exception as e:
                logger.error(f"Scan callback error: {e}")
    
    @staticmethod
    def list_available_ports() -> list:
        """List all available COM ports."""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                "port": port.device,
                "description": port.description,
                "hwid": port.hwid
            })
        return ports
