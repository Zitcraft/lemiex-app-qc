"""
Scanner Manager - Manages multiple barcode scanners.
Handles auto-detection and aggregation of scan events.
"""

import logging
from typing import Dict, List, Optional, Callable
import threading

from models import ScannerInfo, ScanResult, ScannerState
from config import get_settings, ScannerConfig
from .com_scanner import COMScanner

logger = logging.getLogger(__name__)


class ScannerManager:
    """
    Manages multiple barcode scanners.
    Aggregates scan events from all connected scanners.
    """
    
    def __init__(
        self,
        on_scan: Optional[Callable[[ScanResult], None]] = None,
        on_scanner_state_change: Optional[Callable[[ScannerInfo], None]] = None
    ):
        """
        Initialize scanner manager.
        
        Args:
            on_scan: Callback when any scanner receives a scan
            on_scanner_state_change: Callback when scanner state changes
        """
        self.settings = get_settings()
        self.on_scan = on_scan
        self.on_scanner_state_change = on_scanner_state_change
        
        self._scanners: Dict[str, COMScanner] = {}
        self._lock = threading.Lock()
        self._running = False
    
    @property
    def scanners(self) -> Dict[str, COMScanner]:
        """Get all scanners."""
        return self._scanners.copy()
    
    @property
    def connected_scanners(self) -> List[ScannerInfo]:
        """Get list of connected scanner info."""
        return [
            scanner.info for scanner in self._scanners.values()
            if scanner.is_connected
        ]
    
    def initialize(self) -> None:
        """Initialize scanners from configuration."""
        for scanner_config in self.settings.scanners:
            if scanner_config.enabled:
                self.add_scanner(scanner_config)
    
    def add_scanner(self, config: ScannerConfig) -> COMScanner:
        """
        Add a scanner from configuration.
        
        Args:
            config: Scanner configuration
            
        Returns:
            COMScanner instance
        """
        with self._lock:
            # Remove existing scanner with same ID
            if config.id in self._scanners:
                self._scanners[config.id].stop()
            
            # Create new scanner
            scanner = COMScanner(
                scanner_id=config.id,
                com_port=config.com_port,
                baud_rate=config.baud_rate,
                on_scan=self._handle_scan,
                on_state_change=self._handle_state_change
            )
            
            self._scanners[config.id] = scanner
            
            # Start if manager is running
            if self._running:
                scanner.start()
            
            logger.info(f"Scanner added: {config.id} on {config.com_port}")
            return scanner
    
    def remove_scanner(self, scanner_id: str) -> None:
        """Remove a scanner by ID."""
        with self._lock:
            if scanner_id in self._scanners:
                self._scanners[scanner_id].stop()
                del self._scanners[scanner_id]
                logger.info(f"Scanner removed: {scanner_id}")
    
    def get_scanner(self, scanner_id: str) -> Optional[COMScanner]:
        """Get scanner by ID."""
        return self._scanners.get(scanner_id)
    
    def start(self) -> None:
        """Start all scanners."""
        self._running = True
        
        with self._lock:
            for scanner in self._scanners.values():
                scanner.start()
        
        logger.info(f"Scanner manager started with {len(self._scanners)} scanners")
    
    def stop(self) -> None:
        """Stop all scanners."""
        self._running = False
        
        with self._lock:
            for scanner in self._scanners.values():
                scanner.stop()
        
        logger.info("Scanner manager stopped")
    
    def reconnect_all(self) -> None:
        """Reconnect all scanners."""
        with self._lock:
            for scanner in self._scanners.values():
                scanner.disconnect()
                scanner.connect()
    
    def _handle_scan(self, result: ScanResult) -> None:
        """Handle scan from any scanner."""
        if self.on_scan:
            try:
                self.on_scan(result)
            except Exception as e:
                logger.error(f"Scan handler error: {e}")
    
    def _handle_state_change(self, info: ScannerInfo) -> None:
        """Handle state change from any scanner."""
        if self.on_scanner_state_change:
            try:
                self.on_scanner_state_change(info)
            except Exception as e:
                logger.error(f"State change handler error: {e}")
    
    def get_available_ports(self) -> List[dict]:
        """Get list of available COM ports."""
        return COMScanner.list_available_ports()
    
    def auto_detect_scanners(self) -> List[str]:
        """
        Auto-detect barcode scanners on available COM ports.
        Returns list of detected scanner ports.
        
        Note: This is a basic implementation that just returns
        ports with 'USB' in the description. A more robust
        implementation would try to communicate with each device.
        """
        detected = []
        
        for port_info in self.get_available_ports():
            desc = port_info.get("description", "").lower()
            hwid = port_info.get("hwid", "").lower()
            
            # Check for common barcode scanner identifiers
            if any(keyword in desc or keyword in hwid for keyword in [
                "barcode", "scanner", "usb serial", "usb-serial", 
                "ch340", "cp210", "ftdi", "prolific"
            ]):
                detected.append(port_info["port"])
        
        return detected
    
    def get_status_summary(self) -> Dict[str, int]:
        """Get summary of scanner statuses."""
        summary = {
            "total": len(self._scanners),
            "connected": 0,
            "disconnected": 0,
            "error": 0
        }
        
        for scanner in self._scanners.values():
            if scanner.info.state == ScannerState.CONNECTED:
                summary["connected"] += 1
            elif scanner.info.state == ScannerState.ERROR:
                summary["error"] += 1
            else:
                summary["disconnected"] += 1
        
        return summary
