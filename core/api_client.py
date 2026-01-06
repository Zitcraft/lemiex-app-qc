"""
API Client - HTTP client for Lemiex API communication.
"""

import logging
from typing import Any, Dict, Optional, Callable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import get_settings

logger = logging.getLogger(__name__)


class APIClient:
    """HTTP client for Lemiex API."""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize API client."""
        self.settings = get_settings()
        self.base_url = base_url or self.settings.api_base_url
        self._token: Optional[str] = None
        self._session = self._create_session()
        
        # Callbacks for auth events
        self.on_token_expired: Optional[Callable] = None
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def set_token(self, token: str) -> None:
        """Set the authentication token."""
        self._token = token
    
    def clear_token(self) -> None:
        """Clear the authentication token."""
        self._token = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        
        return headers
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and errors."""
        try:
            data = response.json() if response.text else {}
        except ValueError:
            data = {"raw_response": response.text}
        
        if response.status_code == 401:
            logger.warning("Token expired or invalid")
            if self.on_token_expired:
                self.on_token_expired()
            raise AuthenticationError("Token đã hết hạn. Vui lòng đăng nhập lại.")
        
        if response.status_code == 404:
            raise NotFoundError(data.get("message", "Không tìm thấy dữ liệu"))
        
        if response.status_code >= 400:
            error_msg = data.get("message", data.get("error", f"Lỗi {response.status_code}"))
            raise APIError(error_msg, status_code=response.status_code)
        
        return data
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"GET {url}")
        
        try:
            response = self._session.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            return self._handle_response(response)
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Không thể kết nối đến server. Kiểm tra kết nối mạng.")
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timeout. Server không phản hồi.")
    
    def post(self, endpoint: str, data: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make POST request."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"POST {url}")
        
        try:
            response = self._session.post(
                url,
                headers=self._get_headers(),
                data=data,
                json=json_data,
                timeout=30
            )
            return self._handle_response(response)
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Không thể kết nối đến server. Kiểm tra kết nối mạng.")
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timeout. Server không phản hồi.")
    
    def put(self, endpoint: str, data: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make PUT request."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"PUT {url}")
        
        try:
            response = self._session.put(
                url,
                headers=self._get_headers(),
                data=data,
                json=json_data,
                timeout=30
            )
            return self._handle_response(response)
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Không thể kết nối đến server. Kiểm tra kết nối mạng.")
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timeout. Server không phản hồi.")
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"DELETE {url}")
        
        try:
            response = self._session.delete(
                url,
                headers=self._get_headers(),
                timeout=30
            )
            return self._handle_response(response)
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Không thể kết nối đến server. Kiểm tra kết nối mạng.")
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timeout. Server không phản hồi.")


class APIError(Exception):
    """API error exception."""
    
    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(APIError):
    """Authentication error exception."""
    pass


class NotFoundError(APIError):
    """Resource not found exception."""
    pass
