"""
Lemiex Order Management App - Eel Backend

HTML-based UI sử dụng Eel (Python + Web Technologies)
"""

import sys
import os

# Suppress OpenCV warnings before importing cv2
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

import logging
import eel
import base64
import threading
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional
import serial.tools.list_ports

# Handle PyInstaller frozen mode
def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        base_path = Path(sys._MEIPASS)
    else:
        # Running as script
        base_path = Path(__file__).parent
    return str(base_path / relative_path)

# Add project root to path
if getattr(sys, 'frozen', False):
    project_root = Path(sys._MEIPASS)
else:
    project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import get_settings
from core import APIClient, AuthManager
from scanner import ScannerManager
from camera import CameraManager
from services import OrderService, WebLogger, RecordingService
from models import Order, ScanResult, FulfillStatus

# Setup logging
def setup_logging():
    """Setup application logging."""
    settings = get_settings()
    log_path = settings.get_logs_path() / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

setup_logging()
logger = logging.getLogger(__name__)

# Initialize Eel with web folder (use correct path for frozen mode)
web_folder = get_resource_path('web')
eel.init(web_folder)


class EelApp:
    """Eel Application Backend"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Core components
        self.api_client = APIClient()
        self.auth_manager = AuthManager(self.api_client)
        
        # Services
        self.order_service = OrderService(self.api_client)
        self.web_logger = WebLogger(self.api_client)
        
        # Upload queue for handling concurrent uploads
        self._upload_queue = []
        self._upload_in_progress = False
        self._upload_lock = threading.Lock()
        
        # Managers
        self.scanner_manager = ScannerManager(
            on_scan=self._on_scan,
            on_scanner_state_change=self._on_scanner_state_change
        )
        
        self.camera_manager = CameraManager(
            on_camera_state_change=self._on_camera_state_change
        )
        
        self.recording_service = RecordingService(
            camera_manager=self.camera_manager,
            b2_uploader=None,  # Not using B2 anymore, upload directly to server
            on_recording_start=self._on_recording_start,
            on_recording_stop=self._on_recording_stop,
            on_upload_complete=self._on_recording_uploaded
        )
        
        # State
        self._current_order: Optional[Order] = None
        self._camera_active = False
        self._camera_thread: Optional[threading.Thread] = None
        self._recording_start_time: Optional[datetime] = None
        self._selected_camera_index = 0
        self._recording_limit = 300  # 5 minutes default
        self._auto_record = True
        
        # Packing recording settings
        self._packing_recording_base = 15  # Base recording time in seconds
        self._packing_recording_per_item = 10  # Additional seconds per item
        self._packing_recording_order_id = None
        self._packing_recording_total_items = 1
        self._packing_recording_limit = 15  # Dynamic limit based on items
        
    # ===== Eel Exposed Functions =====
    
    def login(self, email: str, password: str):
        """Login user"""
        try:
            success = self.auth_manager.login(email, password)
            if success:
                user = self.auth_manager.current_user
                eel.onLoginSuccess({
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'role': user.role
                })
                logger.info(f"User logged in: {email}")
                # Auto-start devices after login
                self.auto_start_devices()
            else:
                eel.onLoginError("Email hoặc mật khẩu không đúng")
        except Exception as e:
            logger.error(f"Login error: {e}")
            eel.onLoginError(str(e))
    
    def check_auth(self):
        """Check if user is authenticated and token is valid"""
        if self.auth_manager.is_authenticated:
            # Validate token before confirming login
            if self.auth_manager.validate_token():
                user = self.auth_manager.current_user
                eel.onLoginSuccess({
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'role': user.role
                })
                # Auto-start devices after successful auth
                self.auto_start_devices()
            else:
                # Token expired, need to login again
                logger.warning("Saved token expired, please login again")
                eel.onTokenExpired()
    
    def logout(self):
        """Logout user"""
        self.auth_manager.logout()
        self._stop_recording()
        self._stop_camera()
    
    def search_order(self, order_id: str):
        """Search for an order by ID"""
        try:
            order = self.order_service.get_order(order_id)
            if order:
                self._current_order = order
                order_dict = self._order_to_dict(order)
                eel.onOrderLoaded(order_dict)
                
                # Log order view
                self.web_logger.log_order_view(order.id, order.ref_id)
                
                # Start recording if camera is active AND auto-record is enabled
                if self._camera_active and self._auto_record:
                    self._start_recording(order_id)
            else:
                eel.onOrderError(f"Không tìm thấy đơn hàng #{order_id}")
        except Exception as e:
            logger.error(f"Search order error: {e}")
            eel.onOrderError(str(e))
    
    def change_order_status(self, order_id: str, new_status: str):
        """Change order status"""
        try:
            # Map status string to FulfillStatus enum
            status_map = {
                'on_hold': FulfillStatus.ON_HOLD,
                'producing': FulfillStatus.IN_PROCESS,
                'shipped': FulfillStatus.SHIPPED,
                'complete': FulfillStatus.FULFILLED,
            }
            
            status = status_map.get(new_status)
            if status:
                success = self.order_service.update_fulfill_status(order_id, status)
                eel.onStatusChanged(order_id, new_status, success)
                
                # Stop recording if status is complete/shipped
                if success and new_status in ['complete', 'shipped']:
                    self._stop_recording()
            else:
                eel.onStatusChanged(order_id, new_status, False)
        except Exception as e:
            logger.error(f"Change status error: {e}")
            eel.onStatusChanged(order_id, new_status, False)
    
    def change_fulfill_status(self, order_id: int, new_status: str):
        """Change fulfill status via API"""
        try:
            import requests
            
            token = self.auth_manager.token
            if not token:
                return {"success": False, "message": "Chưa đăng nhập"}
            
            api_base = self.settings.api_base_url
            response = requests.put(
                f"{api_base}/orders/change-fulfill-status",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                cookies={"token": token},
                json={
                    "order_id": order_id,
                    "fulfill_status": new_status
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Changed fulfill status for order {order_id} to {new_status}")
                
                # Stop recording if shipped
                if new_status == 'shipped':
                    self._stop_recording()
                
                return {"success": True}
            else:
                logger.error(f"Failed to change fulfill status: {response.status_code} - {response.text}")
                return {"success": False, "message": f"Lỗi: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Change fulfill status error: {e}")
            return {"success": False, "message": str(e)}
    
    def activate_qc_item(self, order_id: int, item_id: int, positions: list = None):
        """Activate QC status for an item via API - activate all positions"""
        try:
            import requests
            
            token = self.auth_manager.token
            if not token:
                return {"success": False, "message": "Chưa đăng nhập"}
            
            # Default positions if not provided
            if not positions:
                positions = ["front"]  # Default to front only
            
            results = []
            last_response = None
            api_base = self.settings.api_base_url
            
            # Activate each position
            for meta_key in positions:
                url = f"{api_base}/orders/change-status-items"
                payload = {
                    "item_id": item_id,
                    "meta_key": meta_key,
                    "status": True
                }
                logger.info(f"Calling QC API: PUT {url}")
                logger.info(f"Payload: {payload}")
                
                response = requests.put(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}"
                    },
                    json=payload,
                    timeout=10
                )
                
                logger.info(f"Response status: {response.status_code}")
                if response.status_code != 200:
                    logger.info(f"Response body: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"QC activated for item {item_id}, position: {meta_key}")
                    results.append({"position": meta_key, "success": True})
                    last_response = data
                else:
                    logger.error(f"Failed to activate QC position {meta_key}: {response.status_code}")
                    results.append({"position": meta_key, "success": False})
            
            if last_response:
                return {"success": True, "data": last_response.get("data", {}), "results": results}
            else:
                return {"success": False, "message": "Không thể activate QC"}
                
        except Exception as e:
            logger.error(f"Activate QC error: {e}")
            return {"success": False, "message": str(e)}
    
    def activate_packing_items(self, order_id: int, items_with_positions: list):
        """Activate packing status for multiple items
        
        items_with_positions: list of dicts with {item_id}
        Note: Packing only uses 'front' position for all items
        """
        try:
            import requests
            
            token = self.auth_manager.token
            if not token:
                return {"success": False, "message": "Chưa đăng nhập"}
            
            api_base = self.settings.api_base_url
            results = []
            
            for item_data in items_with_positions:
                item_id = item_data.get('item_id') or item_data.get('itemId')
                
                # Packing only uses 'front' position
                url = f"{api_base}/orders/change-status-items"
                payload = {
                    "item_id": item_id,
                    "meta_key": "front",
                    "status": True
                }
                logger.info(f"Calling Packing API: PUT {url}")
                logger.info(f"Payload: {payload}")
                
                response = requests.put(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}"
                    },
                    json=payload,
                    timeout=10
                )
                
                logger.info(f"Response status: {response.status_code}")
                if response.status_code != 200:
                    logger.info(f"Response body: {response.text}")
                
                if response.status_code == 200:
                    logger.info(f"Packing activated for item {item_id}")
                    results.append({"item_id": item_id, "success": True})
                else:
                    logger.error(f"Failed to activate packing for item {item_id}: {response.status_code}")
                    results.append({"item_id": item_id, "success": False})
            
            all_success = all(r["success"] for r in results)
            logger.info(f"Packing activated for order {order_id}: {results}")
            return {"success": all_success, "results": results}
                
        except Exception as e:
            logger.error(f"Activate packing error: {e}")
            return {"success": False, "message": str(e)}
    
    def activate_shipout_order(self, order_id: int, items: list):
        """Activate shipout status for all items and all positions in an order
        
        items: list of item dicts with 'id' and 'designs' (positions)
        """
        try:
            import requests
            
            token = self.auth_manager.token
            if not token:
                return {"success": False, "message": "Chưa đăng nhập"}
            
            api_base = self.settings.api_base_url
            url = f"{api_base}/orders/change-status-items"
            results = []
            
            for item in items:
                item_id = item.get('id')
                # Get positions from designs
                designs = item.get('designs', [])
                positions = [d.get('position') for d in designs if d.get('position')]
                if not positions:
                    positions = ['front']
                
                for position in positions:
                    payload = {
                        "item_id": item_id,
                        "meta_key": position,
                        "status": True
                    }
                    logger.info(f"Calling Shipout API: PUT {url}")
                    logger.info(f"Payload: {payload}")
                    
                    response = requests.put(
                        url,
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {token}"
                        },
                        json=payload,
                        timeout=10
                    )
                    
                    logger.info(f"Response status: {response.status_code}")
                    if response.status_code != 200:
                        logger.info(f"Response body: {response.text}")
                    
                    results.append({
                        "item_id": item_id,
                        "position": position,
                        "success": response.status_code == 200
                    })
            
            all_success = all(r["success"] for r in results)
            logger.info(f"Shipout activated for order {order_id}: {len([r for r in results if r['success']])}/{len(results)} success")
            return {"success": all_success, "results": results}
                
        except Exception as e:
            logger.error(f"Activate shipout error: {e}")
            return {"success": False, "message": str(e)}
    
    def get_connected_printers(self):
        """Get list of connected printers"""
        try:
            import subprocess
            import platform
            
            printers = []
            
            if platform.system() == 'Windows':
                # Use PowerShell to get printers
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-Printer | Select-Object Name, PrinterStatus, PortName | ConvertTo-Json'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    import json
                    printer_data = json.loads(result.stdout)
                    
                    # Handle single printer (returns dict) vs multiple (returns list)
                    if isinstance(printer_data, dict):
                        printer_data = [printer_data]
                    
                    for p in printer_data:
                        printers.append({
                            "name": p.get("Name", ""),
                            "status": "Ready" if p.get("PrinterStatus") == 0 else "Offline",
                            "port": p.get("PortName", "")
                        })
            
            logger.info(f"Found {len(printers)} printers")
            return {"success": True, "printers": printers}
            
        except Exception as e:
            logger.error(f"Get printers error: {e}")
            return {"success": False, "printers": [], "message": str(e)}
    
    def preload_label(self, label_url: str):
        """Pre-download label image to cache for faster printing"""
        try:
            import requests
            import hashlib
            
            if not label_url:
                return {"success": False}
            
            temp_dir = self.settings.get_temp_videos_path()
            url_hash = hashlib.md5(label_url.encode()).hexdigest()[:12]
            label_path = temp_dir / f"label_cache_{url_hash}.jpg"
            
            if not label_path.exists():
                logger.info(f"Preloading label: {label_url}")
                response = requests.get(label_url, timeout=10)
                if response.status_code == 200:
                    with open(label_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"Label preloaded: {label_path}")
                    return {"success": True, "cached": True}
            else:
                logger.debug(f"Label already cached: {label_path}")
                return {"success": True, "cached": False}
                
        except Exception as e:
            logger.debug(f"Preload label error: {e}")
            return {"success": False}
    
    def print_label(self, label_url: str, printer_name: str = None):
        """Download label image and print it
        
        label_url: URL of the label image (jpg/png)
        printer_name: Optional specific printer name, uses default if not specified
        Auto-fit to page, portrait orientation
        """
        try:
            import subprocess
            import tempfile
            import requests
            from pathlib import Path
            import hashlib
            
            # Check cache first (use URL hash as filename)
            temp_dir = self.settings.get_temp_videos_path()
            url_hash = hashlib.md5(label_url.encode()).hexdigest()[:12]
            label_path = temp_dir / f"label_cache_{url_hash}.jpg"
            
            # Download only if not cached
            if not label_path.exists():
                logger.info(f"Downloading label: {label_url}")
                response = requests.get(label_url, timeout=10)
                
                if response.status_code != 200:
                    return {"success": False, "message": f"Không thể tải label: {response.status_code}"}
                
                with open(label_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Label saved: {label_path}")
            else:
                logger.info(f"Using cached label: {label_path}")
            
            # Print using Windows print command
            import platform
            if platform.system() == 'Windows':
                # Use PowerShell with -NoProfile for faster startup
                # Full page print for 4x6 inch thermal labels (no margins)
                ps_script = f'''
Add-Type -AssemblyName System.Drawing
$imagePath = "{label_path}"
$printerName = "{printer_name or ''}"
$image = [System.Drawing.Image]::FromFile($imagePath)
$doc = New-Object System.Drawing.Printing.PrintDocument
if ($printerName -ne "") {{ $doc.PrinterSettings.PrinterName = $printerName }}
$doc.DefaultPageSettings.Landscape = $false
$doc.DefaultPageSettings.Margins = New-Object System.Drawing.Printing.Margins(0,0,0,0)
$doc.add_PrintPage({{
    param($sender, $e)
    $pw = $e.PageBounds.Width; $ph = $e.PageBounds.Height
    $iw = $image.Width; $ih = $image.Height
    $scale = [Math]::Min($pw/$iw, $ph/$ih)
    $sw = [int]($iw * $scale); $sh = [int]($ih * $scale)
    $x = [int](($pw - $sw) / 2); $y = [int](($ph - $sh) / 2)
    $e.Graphics.DrawImage($image, (New-Object System.Drawing.Rectangle($x,$y,$sw,$sh)))
}})
$doc.Print(); $image.Dispose(); "OK"
'''
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if result.returncode != 0 or "OK" not in result.stdout:
                    logger.warning(f"PowerShell print failed: {result.stderr}")
                    # Fallback to mspaint
                    subprocess.run(['mspaint', '/p', str(label_path)], timeout=30)
                
                logger.info(f"Label sent to printer: {printer_name or 'default'}")
                
                # Notify frontend
                try:
                    eel.onLabelPrinted(str(label_url), printer_name or "default")
                except:
                    pass
                
                return {"success": True, "message": "Đã gửi label đến máy in"}
            else:
                return {"success": False, "message": "Chỉ hỗ trợ Windows"}
                
        except Exception as e:
            logger.error(f"Print label error: {e}")
            return {"success": False, "message": str(e)}
    
    def activate_shipout_item(self, order_id: int, item_id: int):
        """Activate shipout status for an item"""
        try:
            import requests
            
            token = self.auth_manager.token
            if not token:
                return {"success": False, "message": "Chưa đăng nhập"}
            
            api_base = self.settings.api_base_url
            response = requests.post(
                f"{api_base}/orders/change-status-items",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                cookies={"token": token},
                json={
                    "order_id": order_id,
                    "item_id": item_id,
                    "stage": "shipout"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Shipout activated for item {item_id} in order {order_id}")
                return {"success": True}
            else:
                logger.error(f"Failed to activate shipout: {response.status_code} - {response.text}")
                return {"success": False, "message": f"Lỗi: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Activate shipout error: {e}")
            return {"success": False, "message": str(e)}
    
    def get_order_with_item(self, order_id: str, item_id: str):
        """Get order data with specific item details"""
        try:
            order = self.order_service.fetch_order(order_id)
            if order:
                # Find the specific item
                item_data = None
                for item in order.get('items', []):
                    if str(item.get('id')) == str(item_id):
                        item_data = item
                        break
                
                return {"order": order, "item": item_data}
            return None
        except Exception as e:
            logger.error(f"Get order with item error: {e}")
            return None
    
    def get_track_data(self, track_url: str):
        """Call track API to get item/order data from QR URL"""
        try:
            # Convert track URL to API URL
            # https://manage.lemiex.us/track/20?stt=1&item_id=1 -> https://manage.lemiex.us/api/orders/track/20?stt=1&item_id=1
            api_url = track_url.replace('/track/', '/api/orders/track/')
            
            # Fix malformed URL with double ? (replace second ? with &)
            first_q = api_url.find('?')
            if first_q >= 0:
                second_q = api_url.find('?', first_q + 1)
                if second_q >= 0:
                    api_url = api_url[:second_q] + '&' + api_url[second_q + 1:]
            
            logger.info(f"Calling track API: {api_url}")
            
            # Get headers from API client
            headers = self.api_client._get_headers()
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Track API response success, items count: {len(data.get('data', {}).get('items', []))}")
                return {"success": True, "data": data.get("data", data)}
            else:
                logger.error(f"Track API error: {response.status_code}")
                return {"success": False, "message": f"API error: {response.status_code}"}
        except Exception as e:
            logger.error(f"Track API error: {e}")
            return {"success": False, "message": str(e)}

    def get_order_data(self, order_id: str):
        """Get order data without loading to UI"""
        try:
            return self.order_service.fetch_order(order_id)
        except Exception as e:
            logger.error(f"Get order data error: {e}")
            return None
    
    def get_com_ports(self):
        """Get available COM ports"""
        try:
            ports = []
            for port in serial.tools.list_ports.comports():
                ports.append({
                    'port': port.device,
                    'description': port.description,
                    'hwid': port.hwid
                })
            
            # Sort with USB priority
            ports.sort(key=lambda x: (0 if 'USB' in x.get('description', '').upper() else 1, x['port']))
            
            # Send just port names to frontend
            port_names = [p['port'] for p in ports]
            eel.onComPortsLoaded(port_names)
            return ports
        except Exception as e:
            logger.error(f"Get COM ports error: {e}")
            eel.onComPortsLoaded([])
            return []
    
    def toggle_scanner(self, enabled: bool, port: str):
        """Toggle scanner on/off"""
        try:
            if enabled:
                # Connect scanner
                from config import ScannerConfig
                config = ScannerConfig(
                    id="scanner_1",
                    com_port=port,
                    enabled=True
                )
                self.scanner_manager.add_scanner(config)
                self.scanner_manager.start()
                eel.onScannerStatusChanged(True, port)
                logger.info(f"Scanner started on {port}")
            else:
                self.scanner_manager.stop()
                eel.onScannerStatusChanged(False, port)
                logger.info("Scanner stopped")
        except Exception as e:
            logger.error(f"Toggle scanner error: {e}")
            eel.onScannerStatusChanged(False, port)
    
    def refresh_scanner(self):
        """Refresh scanner - reload COM ports"""
        try:
            ports = self.get_com_ports()
            # Auto-connect to first USB port if available
            usb_ports = [p for p in ports if 'USB' in p.get('description', '').upper()]
            if usb_ports:
                port = usb_ports[0]['port']
                self.toggle_scanner(True, port)
                return {'success': True, 'port': port}
            return {'success': False, 'message': 'No USB scanner found'}
        except Exception as e:
            logger.error(f"Refresh scanner error: {e}")
            return {'success': False, 'message': str(e)}
    
    def refresh_camera(self):
        """Refresh camera - reinitialize"""
        try:
            self._stop_camera()
            import time
            time.sleep(0.5)
            self._start_camera()
            return {'success': True}
        except Exception as e:
            logger.error(f"Refresh camera error: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_available_cameras(self):
        """Get list of available cameras"""
        try:
            from camera import Camera
            indices = Camera.list_available_cameras()
            cameras = [{'index': i, 'name': f'Camera {i}'} for i in indices]
            eel.onCamerasLoaded(cameras)
            return cameras
        except Exception as e:
            logger.error(f"Get cameras error: {e}")
            eel.onCamerasLoaded([])
            return []
    
    def fetch_design_preview(self, json_url: str):
        """Fetch design preview image from json_url"""
        if not json_url or json_url == 'null' or json_url == 'undefined':
            return {'success': False, 'message': 'No URL provided'}
        
        try:
            import requests
            response = requests.get(json_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                preview = data.get('preview', {})
                if preview:
                    image_data = preview.get('image_data', '')
                    format_type = preview.get('format', 'png')
                    encoding = preview.get('encoding', 'base64')
                    if image_data and encoding == 'base64':
                        return {
                            'success': True,
                            'image_data': image_data,
                            'format': format_type
                        }
            return {'success': False, 'message': 'No preview data'}
        except Exception as e:
            logger.error(f"Fetch design preview error: {e}")
            return {'success': False, 'message': str(e)}
    
    def select_camera(self, camera_index: int):
        """Select camera by index"""
        try:
            self._selected_camera_index = camera_index
            logger.info(f"Camera selected: {camera_index}")
            
            # Restart camera with new index
            if self._camera_active:
                self._stop_camera()
                import time
                time.sleep(0.3)
                self._start_camera()
            
            return {'success': True}
        except Exception as e:
            logger.error(f"Select camera error: {e}")
            return {'success': False, 'message': str(e)}
    
    def set_recording_limit(self, seconds: int):
        """Set recording time limit"""
        self._recording_limit = max(10, min(3600, seconds))
        logger.info(f"Recording limit set to: {self._recording_limit}s")
        return {'success': True}
    
    def set_auto_record(self, enabled: bool):
        """Enable/disable auto recording on scan"""
        self._auto_record = enabled
        logger.info(f"Auto-record: {'enabled' if enabled else 'disabled'}")
        return {'success': True}
    
    def sync_device_state(self):
        """Sync device states with frontend (called after page refresh)"""
        try:
            # Send camera status
            try:
                eel.onCameraStatusChanged(self._camera_active)
            except Exception as e:
                logger.debug(f"Camera status sync error: {e}")
            
            # Send scanner status
            # connected_scanners is a List[ScannerInfo], not a dict
            try:
                connected = self.scanner_manager.connected_scanners
                if connected:
                    # Get port from first connected scanner
                    port = connected[0].com_port if connected else 'Unknown'
                    eel.onScannerStatusChanged(True, port)
                else:
                    eel.onScannerStatusChanged(False, "")
            except Exception as e:
                logger.debug(f"Scanner status sync error: {e}")
            
            # Send recording status
            try:
                if self._recording_start_time:
                    duration = int((datetime.now() - self._recording_start_time).total_seconds())
                    eel.onRecordingStatus(True, duration)
            except Exception as e:
                logger.debug(f"Recording status sync error: {e}")
            
            logger.info("Device states synced with frontend")
            # Return None to avoid eel return value issues
            return None
        except Exception as e:
            logger.error(f"Sync device state error: {e}")
            return {'success': False, 'message': str(e)}
    
    def auto_start_devices(self):
        """Auto-start scanner and camera"""
        try:
            # Auto-start camera (only if not already running)
            if not self._camera_active:
                logger.info("Auto-starting camera...")
                self._start_camera()
            else:
                # Camera already active - restart stream thread for new websocket
                logger.info("Camera already active, restarting stream for new connection")
                self._restart_camera_stream()
            
            # Auto-start scanner on COM3 or first USB port
            logger.info("Auto-detecting scanner...")
            ports = self.get_com_ports()
            
            # Priority: COM3 first, then USB ports, then any port
            target_port = None
            
            # Check for COM3 first (common scanner port)
            com3_ports = [p for p in ports if p.get('port', '').upper() == 'COM3']
            if com3_ports:
                target_port = com3_ports[0]['port']
                logger.info(f"Found COM3: {com3_ports[0]}")
            else:
                # Try USB ports
                usb_ports = [p for p in ports if 'USB' in p.get('description', '').upper()]
                if usb_ports:
                    target_port = usb_ports[0]['port']
            
            if target_port:
                # Check if scanner already connected
                if not self.scanner_manager.connected_scanners:
                    self.toggle_scanner(True, target_port)
                    logger.info(f"Auto-started scanner on {target_port}")
                else:
                    logger.info("Scanner already connected")
                    try:
                        eel.onScannerStatusChanged(True, target_port)
                    except:
                        pass
            else:
                logger.info("No scanner port detected")
                
        except Exception as e:
            logger.error(f"Auto-start devices error: {e}")
    
    def _restart_camera_stream(self):
        """Restart camera completely for new websocket connection (after F5 refresh)"""
        logger.info("Restarting camera for new connection...")
        
        # Stop everything
        self._camera_active = False
        if self._camera_thread:
            self._camera_thread.join(timeout=1.0)
            self._camera_thread = None
        
        # Stop and restart camera manager to get fresh capture
        self.camera_manager.stop()
        import time
        time.sleep(0.3)
        
        # Restart camera
        self._camera_active = True
        self.camera_manager.start()
        
        # Start new stream thread
        self._camera_thread = threading.Thread(target=self._stream_camera_frames)
        self._camera_thread.daemon = True
        self._camera_thread.start()
        
        # Notify frontend
        try:
            eel.onCameraStatusChanged(True)
        except:
            pass
        logger.info("Camera fully restarted for new connection")
    
    def toggle_camera(self, enabled: bool):
        """Toggle camera on/off"""
        try:
            if enabled:
                self._start_camera()
            else:
                self._stop_camera()
        except Exception as e:
            logger.error(f"Toggle camera error: {e}")
    
    # ===== Internal Methods =====
    
    def _order_to_dict(self, order: Order) -> dict:
        """Convert Order object to dictionary for frontend"""
        items = []
        for item in order.items:
            designs = []
            if hasattr(item, 'designs') and item.designs:
                for d in item.designs:
                    designs.append({
                        'position': getattr(d, 'position', ''),
                        'pdf_url': getattr(d, 'pdf_url', ''),
                        'dst_url': getattr(d, 'dst_url', ''),
                        'emb_url': getattr(d, 'emb_url', ''),
                        'pes_url': getattr(d, 'pes_url', ''),
                        'json_url': getattr(d, 'json_url', ''),
                        'status': getattr(d, 'status', 0),
                        'qc_status': getattr(d, 'qc_status', 0),
                        'stitch_count': getattr(d, 'stitch_count', 0),
                        'width_mm': getattr(d, 'width_mm', 0),
                        'height_mm': getattr(d, 'height_mm', 0),
                        'color_count': getattr(d, 'color_count', 0),
                        'colors': getattr(d, 'colors', []),
                        'needle_assignment': getattr(d, 'needle_assignment', {})
                    })
            
            items.append({
                'id': item.id,
                'product_name': item.product_name,
                'variant_id': getattr(item, 'variant_id', ''),
                'quantity': item.quantity,
                'status': getattr(item, 'status', False),
                'mockup': getattr(item, 'mockup', '') or '',
                'mockup_back': getattr(item, 'mockup_back', '') or '',
                'designs': designs,
                # New product info fields
                'size': getattr(item, 'size', ''),
                'color': getattr(item, 'color', ''),
                'style': getattr(item, 'style', ''),
                'stock': getattr(item, 'stock', 0),
                'color_image': getattr(item, 'color_image', '')
            })
        
        # Seller info
        seller = None
        if hasattr(order, 'seller') and order.seller:
            seller = {
                'store_name': getattr(order.seller, 'store_name', ''),
                'username': getattr(order.seller, 'username', ''),
                'email': getattr(order.seller, 'email', ''),
                'tier': getattr(order.seller, 'tier', '')
            }
        
        # Shipping info
        shipping = None
        if order.shipping:
            address = order.shipping.address if hasattr(order.shipping, 'address') else order.shipping
            shipping = {
                'method': getattr(order.shipping, 'method', '') or '',
                'service': getattr(order.shipping, 'service', '') or '',
                'label_url': getattr(order.shipping, 'label_url', '') or '',
                'tracking_id': getattr(order.shipping, 'tracking_id', '') or '',
                'first_name': getattr(address, 'first_name', '') or '',
                'last_name': getattr(address, 'last_name', '') or '',
                'phone': getattr(address, 'phone', '') or '',
                'street1': getattr(address, 'street1', '') or '',
                'street2': getattr(address, 'street2', '') or '',
                'city': getattr(address, 'city', '') or '',
                'state': getattr(address, 'state', '') or '',
                'zip': getattr(address, 'zip', '') or '',
                'country': getattr(address, 'country', '') or ''
            }
        
        # Pricing info
        pricing = None
        if hasattr(order, 'pricing') and order.pricing:
            pricing = {
                'print_cost': getattr(order.pricing, 'print_cost', 0),
                'shipping_cost': getattr(order.pricing, 'shipping_cost', 0),
                'extra_fee': getattr(order.pricing, 'extra_fee', 0),
                'total': getattr(order.pricing, 'total', 0)
            }
        
        return {
            'id': order.id,
            'ref_id': getattr(order, 'ref_id', '') or '',
            'seller_ref': getattr(order, 'seller_ref', '') or '',
            'order_stt': getattr(order, 'order_stt', str(order.status)) or '',
            'status': str(order.status) if hasattr(order.status, 'value') else order.status,
            'fulfill_status': str(order.fulfill_status) if hasattr(order.fulfill_status, 'value') else order.fulfill_status,
            'tracking_id': getattr(order.shipping, 'tracking_id', '') or '',
            'note': getattr(order, 'note', '') or '',
            'convert_label': getattr(order, 'convert_label', '') or '',
            'items': items,
            'seller': seller,
            'shipping': shipping,
            'pricing': pricing
        }
    
    def _start_camera(self):
        """Start camera preview"""
        if self._camera_active:
            return
        
        self._camera_active = True
        
        # Initialize camera with selected index
        from config import CameraConfig
        camera_id = f"camera_{self._selected_camera_index}"
        
        # Remove existing camera if different
        if self.camera_manager.cameras:
            for cid in list(self.camera_manager.cameras.keys()):
                if cid != camera_id:
                    self.camera_manager.remove_camera(cid)
        
        # Add camera if not exists
        if camera_id not in self.camera_manager.cameras:
            config = CameraConfig(
                id=camera_id,
                device_index=self._selected_camera_index,
                enabled=True
            )
            self.camera_manager.add_camera(config)
        
        self.camera_manager.start()
        
        # Start frame streaming thread
        self._camera_thread = threading.Thread(target=self._stream_camera_frames)
        self._camera_thread.daemon = True
        self._camera_thread.start()
        
        # Notify frontend
        try:
            eel.onCameraStatusChanged(True)
        except:
            pass
    
    def _stop_camera(self):
        """Stop camera"""
        self._camera_active = False
        if self._camera_thread:
            self._camera_thread.join(timeout=1)
            self._camera_thread = None
        self.camera_manager.stop()
        # Notify frontend
        try:
            eel.onCameraStatusChanged(False)
        except:
            pass
    
    def _stream_camera_frames(self):
        """Stream camera frames to frontend"""
        import cv2
        import time
        
        while self._camera_active:
            camera = self.camera_manager.get_primary_camera()
            if camera:
                frame = camera.get_frame()
                if frame is not None:
                    # Resize for preview
                    h, w = frame.shape[:2]
                    preview_w = 320
                    preview_h = int(h * preview_w / w)
                    preview = cv2.resize(frame, (preview_w, preview_h))
                    
                    # Encode to JPEG
                    _, buffer = cv2.imencode('.jpg', preview, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')
                    
                    try:
                        eel.onCameraFrame(frame_base64)
                    except:
                        pass
            
            time.sleep(0.1)  # 10 FPS for preview
    
    def _start_recording(self, order_id: str):
        """Start recording for order"""
        if not self._camera_active:
            return
        
        self._recording_start_time = datetime.now()
        # Use handle_scan which manages recording sessions
        if self._current_order:
            self.recording_service.handle_scan(order_id, self._current_order)
        self._start_recording_timer()
    
    def _stop_recording(self):
        """Stop recording"""
        self._recording_start_time = None
        
        # If QC recording is active, use stop_qc_recording for upload
        qc_order_id = getattr(self, '_qc_recording_order_id', None)
        if qc_order_id:
            logger.info(f"Stopping QC recording for order {qc_order_id}")
            self.stop_qc_recording()
        else:
            # Only call recording_service if not QC recording
            self.recording_service.stop_all()
            
        try:
            eel.onRecordingStatus(False, 0)
        except:
            pass  # Ignore if browser closed
    
    def _start_recording_timer(self):
        """Start timer to update recording duration and auto-stop at limit"""
        def update_timer():
            import time
            while self._recording_start_time:
                duration = int((datetime.now() - self._recording_start_time).total_seconds())
                try:
                    eel.onRecordingStatus(True, duration)
                except:
                    break
                
                # Check if limit reached
                if duration >= self._recording_limit:
                    logger.info(f"Recording limit reached: {duration}s >= {self._recording_limit}s")
                    self._stop_recording()
                    try:
                        eel.onRecordingLimitReached(self._recording_limit)
                    except:
                        pass
                    break
                
                time.sleep(1)
        
        timer_thread = threading.Thread(target=update_timer)
        timer_thread.daemon = True
        timer_thread.start()
    
    # ===== Callbacks =====
    
    def _on_scan(self, result: ScanResult):
        """Handle scanner data"""
        logger.info(f"Scan received: {result.raw_data}")
        data = result.raw_data.strip()
        
        # Check if it's a QR URL (track URL)
        if 'manage.lemiex.us/track/' in data or 'lemiex.us/track/' in data:
            # Call track API and send data to frontend
            track_result = self.get_track_data(data)
            logger.info(f"Track result items: {len(track_result.get('data', {}).get('items', []))}")
            try:
                eel.onQRScanned(data, track_result)
            except Exception as e:
                logger.error(f"onQRScanned error: {e}")
        else:
            # Regular barcode/order ID
            try:
                eel.onScannerData(data)
            except Exception as e:
                logger.error(f"onScannerData error: {e}")

    def _on_scanner_state_change(self, info):
        """Handle scanner state change"""
        try:
            is_connected = info.state.value == "connected" if hasattr(info.state, 'value') else False
            eel.onScannerStatusChanged(is_connected, info.com_port)
        except:
            pass
    
    def _on_camera_state_change(self, info):
        """Handle camera state change"""
        try:
            from camera.camera_manager import CameraState
            is_connected = info.state == CameraState.CONNECTED
            eel.onCameraStatusChanged(is_connected)
            
            # Send error message if camera failed
            if info.state == CameraState.ERROR and info.error_message:
                eel.onCameraError(info.error_message)
        except:
            pass
    
    def _on_upload_progress(self, progress: float):
        """Handle upload progress"""
        pass
    
    def _on_upload_complete(self, url: str):
        """Handle upload complete"""
        logger.info(f"Upload complete: {url}")
    
    def _on_upload_error(self, error: str):
        """Handle upload error"""
        logger.error(f"Upload error: {error}")
    
    def _on_recording_start(self, order_id: str):
        """Handle recording start"""
        logger.info(f"Recording started for order: {order_id}")
    
    def _on_recording_stop(self, video_path: str):
        """Handle recording stop"""
        logger.info(f"Recording stopped: {video_path}")
    
    def _on_recording_uploaded(self, order_id: str, video_url: str):
        """Handle recording uploaded"""
        logger.info(f"Recording uploaded for order {order_id}: {video_url}")
        # Log video to web
        self.web_logger.log_video_upload(order_id, video_url)
    
    def start_qc_recording(self, order_id: int, item_id: int):
        """Start recording for QC scan item"""
        try:
            if not self._camera_active:
                logger.warning("Camera not active, cannot start recording")
                return {"success": False, "message": "Camera không hoạt động"}
            
            # Store item_id for later upload
            self._qc_recording_order_id = order_id
            self._qc_recording_item_id = item_id
            
            self._recording_start_time = datetime.now()
            self._start_recording_timer()
            
            # Start camera recording
            video_filename = f"qc_{order_id}_{item_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            video_path = self.settings.get_temp_videos_path() / video_filename
            
            camera = self.camera_manager.get_primary_camera()
            if camera and camera.start_recording(str(video_path)):
                logger.info(f"QC recording started: {video_path}")
                return {"success": True, "video_path": str(video_path)}
            else:
                logger.error("Failed to start camera recording")
                return {"success": False, "message": "Không thể bắt đầu ghi hình"}
                
        except Exception as e:
            logger.error(f"Start QC recording error: {e}")
            return {"success": False, "message": str(e)}
    
    def stop_qc_recording(self):
        """Stop QC recording and queue upload to server"""
        try:
            camera = self.camera_manager.get_primary_camera()
            if not camera:
                return {"success": False, "message": "Camera không có"}
            
            video_path = camera.stop_recording()
            if not video_path:
                logger.warning("No recording to stop")
                return {"success": False, "message": "Không có video đang ghi"}
            
            video_path = Path(video_path)
            logger.info(f"QC recording stopped: {video_path}")
            
            order_id = getattr(self, '_qc_recording_order_id', None)
            item_id = getattr(self, '_qc_recording_item_id', None)
            
            # Clear recording IDs
            self._qc_recording_order_id = None
            self._qc_recording_item_id = None
            
            if not order_id or not item_id:
                logger.warning("No order/item ID for recording")
                return {"success": False, "message": "Không có order/item ID"}
            
            # Add to upload queue
            self._queue_upload(video_path, order_id, item_id)
            
            try:
                eel.onRecordingStatus(False, 0)
            except:
                pass
            
            return {"success": True, "message": "Đang upload video..."}
            
        except Exception as e:
            logger.error(f"Stop QC recording error: {e}")
            return {"success": False, "message": str(e)}
    
    def start_packing_recording(self, order_id: int, total_items: int, first_item_id: int):
        """Start recording for Packing - called on first item scan
        
        Recording duration = base (15s) + (total_items - 1) * per_item (10s)
        Example: 1 item = 15s, 2 items = 25s, 3 items = 35s, 4 items = 45s
        """
        try:
            if not self._camera_active:
                logger.warning("Camera not active, cannot start packing recording")
                return {"success": False, "message": "Camera không hoạt động"}
            
            # Calculate recording limit based on items
            recording_limit = self._packing_recording_base + (total_items - 1) * self._packing_recording_per_item
            
            # Store for later
            self._packing_recording_order_id = order_id
            self._packing_recording_first_item_id = first_item_id  # Save for upload
            self._packing_recording_total_items = total_items
            self._packing_recording_limit = recording_limit
            
            self._recording_start_time = datetime.now()
            
            # Start camera recording
            video_filename = f"packing_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            video_path = self.settings.get_temp_videos_path() / video_filename
            
            camera = self.camera_manager.get_primary_camera()
            if camera and camera.start_recording(str(video_path)):
                logger.info(f"Packing recording started: {video_path} (limit: {recording_limit}s for {total_items} items)")
                
                # Start timer with packing-specific limit
                self._start_packing_recording_timer(recording_limit)
                
                return {"success": True, "video_path": str(video_path), "limit": recording_limit}
            else:
                logger.error("Failed to start camera recording for packing")
                return {"success": False, "message": "Không thể bắt đầu ghi hình"}
                
        except Exception as e:
            logger.error(f"Start packing recording error: {e}")
            return {"success": False, "message": str(e)}
    
    def _start_packing_recording_timer(self, limit: int):
        """Start timer for packing recording with specific limit"""
        def update_timer():
            import time
            while self._recording_start_time:
                duration = int((datetime.now() - self._recording_start_time).total_seconds())
                try:
                    eel.onRecordingStatus(True, duration)
                except:
                    break
                
                # Check if limit reached
                if duration >= limit:
                    logger.info(f"Packing recording limit reached: {duration}s >= {limit}s")
                    self.stop_packing_recording()
                    try:
                        eel.onPackingRecordingComplete(self._packing_recording_order_id, limit)
                    except:
                        pass
                    break
                
                time.sleep(1)
        
        timer_thread = threading.Thread(target=update_timer)
        timer_thread.daemon = True
        timer_thread.start()
    
    def stop_packing_recording(self):
        """Stop Packing recording and queue upload to server"""
        try:
            camera = self.camera_manager.get_primary_camera()
            if not camera:
                return {"success": False, "message": "Camera không có"}
            
            video_path = camera.stop_recording()
            self._recording_start_time = None
            
            if not video_path:
                logger.warning("No packing recording to stop")
                return {"success": False, "message": "Không có video đang ghi"}
            
            video_path = Path(video_path)
            logger.info(f"Packing recording stopped: {video_path}")
            
            order_id = self._packing_recording_order_id
            first_item_id = getattr(self, '_packing_recording_first_item_id', None)
            
            # Clear recording state
            self._packing_recording_order_id = None
            self._packing_recording_first_item_id = None
            
            if not order_id:
                logger.warning("No order ID for packing recording")
                return {"success": False, "message": "Không có order ID"}
            
            # Add to upload queue with first_item_id
            self._queue_upload(video_path, order_id, first_item_id or 0)
            
            try:
                eel.onRecordingStatus(False, 0)
            except:
                pass
            
            return {"success": True, "message": "Đang upload video packing..."}
            
        except Exception as e:
            logger.error(f"Stop packing recording error: {e}")
            return {"success": False, "message": str(e)}
    
    def set_packing_recording_settings(self, base_seconds: int, per_item_seconds: int):
        """Set packing recording time settings"""
        self._packing_recording_base = base_seconds
        self._packing_recording_per_item = per_item_seconds
        logger.info(f"Packing recording settings: base={base_seconds}s, per_item={per_item_seconds}s")
        return {"success": True, "base": base_seconds, "per_item": per_item_seconds}
    
    def get_packing_recording_settings(self):
        """Get packing recording time settings"""
        return {
            "base": self._packing_recording_base,
            "per_item": self._packing_recording_per_item
        }

    def _queue_upload(self, video_path: Path, order_id: int, item_id: int):
        """Add video to upload queue"""
        with self._upload_lock:
            queue_item = {
                'video_path': video_path,
                'order_id': order_id,
                'item_id': item_id
            }
            self._upload_queue.append(queue_item)
            queue_size = len(self._upload_queue)
            logger.info(f"Video queued for upload. Queue size: {queue_size}")
            
            # Notify frontend about queue
            try:
                eel.onUploadQueued(order_id, item_id, queue_size)
            except:
                pass
        
        # Start processing if not already running
        if not self._upload_in_progress:
            upload_thread = threading.Thread(target=self._process_upload_queue, daemon=True)
            upload_thread.start()
    
    def _process_upload_queue(self):
        """Process upload queue sequentially"""
        self._upload_in_progress = True
        
        while True:
            # Get next item from queue
            with self._upload_lock:
                if not self._upload_queue:
                    self._upload_in_progress = False
                    return
                queue_item = self._upload_queue.pop(0)
                remaining = len(self._upload_queue)
            
            video_path = queue_item['video_path']
            order_id = queue_item['order_id']
            item_id = queue_item['item_id']
            
            try:
                self._upload_video(video_path, order_id, item_id, remaining)
            except Exception as e:
                logger.error(f"Upload error: {e}")
                try:
                    eel.onUploadError(order_id, item_id, str(e))
                except:
                    pass
    
    def _upload_video(self, video_path: Path, order_id: int, item_id: int, remaining_in_queue: int):
        """Upload a single video to server API"""
        token = self.auth_manager.token
        if not token:
            logger.error("Not logged in, cannot upload video")
            try:
                eel.onUploadError(order_id, item_id, "Chưa đăng nhập")
            except:
                pass
            return
        
        logger.info(f"Uploading video to API: {video_path}")
        
        # Get file size for progress
        file_size = video_path.stat().st_size
        
        # Notify start
        try:
            eel.onUploadStart(order_id, item_id, file_size)
        except:
            pass
        
        # Upload file using multipart form with progress tracking
        try:
            with open(video_path, 'rb') as video_file:
                files = {
                    'video': (video_path.name, video_file, 'video/mp4')
                }
                data = {
                    'order_id': str(order_id),
                    'order_item_id': str(item_id)
                }
                logger.info(f"Video API payload: order_id={order_id}, order_item_id={item_id}, file={video_path.name}, size={file_size}")
                
                response = requests.post(
                    f"{self.settings.api_base_url}/orders/upload-video",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {token}"
                    },
                    files=files,
                    data=data,
                    timeout=120  # Longer timeout for large files
                )
                
            logger.info(f"Video API response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                video_url = result.get('data', {}).get('video', '') if isinstance(result, dict) else ''
                logger.info(f"Video saved successfully: {video_url}")
                
                # Notify frontend - success
                try:
                    eel.onVideoUploaded(order_id, item_id, video_url, remaining_in_queue)
                except:
                    pass
            else:
                logger.error(f"Video API error body: {response.text}")
                try:
                    eel.onUploadError(order_id, item_id, f"API error: {response.status_code}")
                except:
                    pass
            
            # Clean up local file
            try:
                video_path.unlink()
            except:
                pass
                
        except Exception as e:
            logger.error(f"Upload error: {e}")
            try:
                eel.onUploadError(order_id, item_id, str(e))
            except:
                pass


# Create app instance
app = EelApp()


# ===== Exposed Eel Functions =====
@eel.expose
def login(email: str, password: str):
    app.login(email, password)

@eel.expose
def checkAuth():
    app.check_auth()

@eel.expose
def logout():
    app.logout()

@eel.expose
def searchOrder(order_id: str):
    app.search_order(order_id)

@eel.expose
def changeOrderStatus(order_id: str, new_status: str):
    app.change_order_status(order_id, new_status)

@eel.expose
def changeFulfillStatus(order_id: int, new_status: str):
    return app.change_fulfill_status(order_id, new_status)

@eel.expose
def activateQCItem(order_id: int, item_id: int, positions: list = None):
    return app.activate_qc_item(order_id, item_id, positions)

@eel.expose
def activatePackingItems(order_id: int, items_with_positions: list):
    return app.activate_packing_items(order_id, items_with_positions)

@eel.expose
def activateShipoutItem(order_id: int, item_id: int):
    return app.activate_shipout_item(order_id, item_id)

@eel.expose
def activateShipoutOrder(order_id: int, items: list):
    """Activate shipout for all items and positions in order"""
    return app.activate_shipout_order(order_id, items)

@eel.expose
def getConnectedPrinters():
    """Get list of connected printers"""
    return app.get_connected_printers()

@eel.expose
def preloadLabel(label_url: str):
    """Pre-download label for faster printing"""
    return app.preload_label(label_url)

@eel.expose
def printLabel(label_url: str, printer_name: str = None):
    """Print label from URL"""
    return app.print_label(label_url, printer_name)

@eel.expose
def uploadVideoAndSave(order_id: int, item_id: int, video_data: str):
    return app.upload_video_and_save(order_id, item_id, video_data)

@eel.expose
def getOrderWithItem(order_id: str, item_id: str):
    return app.get_order_with_item(order_id, item_id)

@eel.expose
def getOrderData(order_id: str):
    return app.get_order_data(order_id)

@eel.expose
def getTrackData(track_url: str):
    return app.get_track_data(track_url)

@eel.expose
def getComPorts():
    return app.get_com_ports()

@eel.expose
def toggleScanner(enabled: bool, port: str):
    app.toggle_scanner(enabled, port)

@eel.expose
def toggleCamera(enabled: bool):
    app.toggle_camera(enabled)

@eel.expose
def refreshScanner():
    return app.refresh_scanner()

@eel.expose
def refreshCamera():
    return app.refresh_camera()

@eel.expose
def getAvailableCameras():
    return app.get_available_cameras()

@eel.expose
def fetchDesignPreview(json_url: str):
    return app.fetch_design_preview(json_url)

@eel.expose
def selectCamera(camera_index: int):
    return app.select_camera(camera_index)

@eel.expose
def setRecordingLimit(seconds: int):
    return app.set_recording_limit(seconds)

@eel.expose
def setAutoRecord(enabled: bool):
    return app.set_auto_record(enabled)

@eel.expose
def syncDeviceState():
    return app.sync_device_state()

@eel.expose
def startQCRecording(order_id: int, item_id: int):
    """Start recording for QC scan"""
    return app.start_qc_recording(order_id, item_id)

@eel.expose
def stopQCRecording():
    """Stop recording and upload"""
    return app.stop_qc_recording()

@eel.expose
def startPackingRecording(order_id: int, total_items: int, first_item_id: int):
    """Start recording for Packing - called on first item scan"""
    return app.start_packing_recording(order_id, total_items, first_item_id)

@eel.expose
def stopPackingRecording():
    """Stop packing recording and upload"""
    return app.stop_packing_recording()

@eel.expose
def setPackingRecordingSettings(base_seconds: int, per_item_seconds: int):
    """Set packing recording time settings"""
    return app.set_packing_recording_settings(base_seconds, per_item_seconds)

@eel.expose
def getPackingRecordingSettings():
    """Get packing recording time settings"""
    return app.get_packing_recording_settings()


def main():
    """Main entry point
    
    Usage:
        python app_eel.py          # Auto-detect browser (chrome-app > edge > chrome > default)
        python app_eel.py --web    # Web mode - open in default browser
        python app_eel.py --app    # App mode - try chrome-app first
        python app_eel.py --server # Server only - no browser, just print URL
        python app_eel.py --role QC      # Start QC instance (port 8081)
        python app_eel.py --role Packing # Start Packing instance (port 8082)
        python app_eel.py --role Shipout # Start Shipout instance (port 8083)
    """
    import argparse
    from config.roles_config import INSTANCE_CONFIG
    
    parser = argparse.ArgumentParser(description='Lemiex Order Manager')
    parser.add_argument('--web', action='store_true', help='Open in default web browser')
    parser.add_argument('--app', action='store_true', help='Open as desktop app (chrome-app mode)')
    parser.add_argument('--server', action='store_true', help='Server only, no browser')
    parser.add_argument('--port', type=int, default=None, help='Port number (auto-assigned if --role is used)')
    parser.add_argument('--role', type=str, choices=['QC', 'Packing', 'Shipout', 'Admin'], 
                        help='Start instance for specific role (enables multi-instance)')
    args = parser.parse_args()
    
    logger.info("Starting Lemiex Order Manager (Eel UI)")
    
    # Determine port based on role or explicit port
    if args.role and args.role in INSTANCE_CONFIG:
        role_config = INSTANCE_CONFIG[args.role]
        port = args.port or role_config['port']
        window_title = role_config['window_title']
        logger.info(f"Starting as {args.role} instance on port {port}")
    else:
        port = args.port or 8080
        window_title = "Lemiex QC"
    
    if args.server:
        # Server only mode
        logger.info(f"Starting in server-only mode. Open http://localhost:{port}/index.html")
        print(f"\n{'='*50}")
        print(f"  Lemiex Order Manager")
        print(f"  Open: http://localhost:{port}/index.html")
        print(f"{'='*50}\n")
        eel.start(
            'index.html',
            port=port,
            host='localhost',
            mode=None,
            block=True
        )
    elif args.web:
        # Web browser mode
        logger.info("Starting in web browser mode")
        import webbrowser
        webbrowser.open(f'http://localhost:{port}/index.html')
        eel.start(
            'index.html',
            port=port,
            host='localhost',
            mode=None,
            block=True
        )
    elif args.app:
        # Desktop app mode - use Edge with app mode
        _start_as_app(port, args.role)
    else:
        # Auto mode - try app first
        _start_as_app(port, args.role)


def _find_edge_path():
    """Find Microsoft Edge executable path"""
    possible_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def _find_chrome_path():
    """Find Google Chrome executable path"""
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def _start_as_app(port: int, role: str = None):
    """Start app in desktop app mode using Edge or Chrome
    
    Args:
        port: Port number for the server
        role: Role name for separate browser profile (QC, Packing, Shipout, Admin)
    """
    import subprocess
    import tempfile
    
    edge_path = _find_edge_path()
    chrome_path = _find_chrome_path()
    
    browser_path = edge_path or chrome_path
    
    if browser_path:
        browser_name = "Edge" if edge_path else "Chrome"
        logger.info(f"Starting as desktop app using {browser_name}")
        
        # Create separate user data directory for each role (allows multi-instance)
        if role:
            user_data_dir = os.path.join(tempfile.gettempdir(), f"LemiexQC_{role}")
            os.makedirs(user_data_dir, exist_ok=True)
            logger.info(f"Using separate profile for {role}: {user_data_dir}")
        else:
            user_data_dir = None
        
        # Start Eel server in background
        def start_server():
            eel.start(
                'index.html',
                port=port,
                host='localhost',
                mode=None,
                block=True
            )
        
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        
        # Wait for server to start
        import time
        time.sleep(1)
        
        # Launch browser in app mode
        url = f'http://localhost:{port}/index.html'
        cmd = [
            browser_path,
            f'--app={url}',
            '--new-window',
            '--disable-extensions',
            '--disable-gpu',
            f'--window-size=1400,900',
        ]
        
        # Add separate user data dir for multi-instance support
        if user_data_dir:
            cmd.append(f'--user-data-dir={user_data_dir}')
        
        try:
            process = subprocess.Popen(cmd)
            role_info = f" ({role})" if role else ""
            logger.info(f"Desktop app{role_info} launched with PID: {process.pid}")
            print(f"\n{'='*50}")
            print(f"  Lemiex {role or 'QC'} App")
            print(f"  Port: {port}")
            print(f"  URL: {url}")
            print(f"{'='*50}\n")
            
            # Keep main thread running
            server_thread.join()
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            server_thread.join()
    else:
        # Fallback to web mode
        logger.warning("No Edge or Chrome found, falling back to web mode")
        import webbrowser
        webbrowser.open(f'http://localhost:{port}/index.html')
        eel.start(
            'index.html',
            port=port,
            host='localhost',
            mode=None,
            block=True
        )


if __name__ == "__main__":
    main()
