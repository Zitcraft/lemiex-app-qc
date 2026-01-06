"""
Auth Manager - Handle user authentication and token management.
"""

import logging
import json
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class UserInfo:
    """Authenticated user information."""
    id: str
    email: str
    name: str
    role: str = ""
    avatar_url: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInfo":
        """Create UserInfo from dictionary."""
        return cls(
            id=str(data.get("id", "")),
            email=data.get("email", ""),
            name=data.get("name", data.get("full_name", "")),
            role=data.get("role", ""),
            avatar_url=data.get("avatar_url", data.get("avatar", ""))
        )


class AuthManager:
    """Manages user authentication and token storage."""
    
    TOKEN_FILE = "auth_token.json"
    
    def __init__(self, api_client=None):
        """Initialize auth manager."""
        self.settings = get_settings()
        self._api_client = api_client
        self._token: Optional[str] = None
        self._user: Optional[UserInfo] = None
        self._token_file = self.settings.base_path / self.TOKEN_FILE
        
        # Callbacks
        self.on_login: Optional[Callable[[UserInfo], None]] = None
        self.on_logout: Optional[Callable[[], None]] = None
        self.on_auth_error: Optional[Callable[[str], None]] = None
        
        # Try to load saved token
        self._load_saved_token()
    
    def set_api_client(self, api_client) -> None:
        """Set the API client."""
        self._api_client = api_client
        if self._token:
            self._api_client.set_token(self._token)
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self._token is not None and self._user is not None
    
    @property
    def current_user(self) -> Optional[UserInfo]:
        """Get current authenticated user."""
        return self._user
    
    @property
    def token(self) -> Optional[str]:
        """Get current token."""
        return self._token
    
    def login(self, email: str, password: str) -> bool:
        """
        Login with email and password.
        Returns True if successful, False otherwise.
        """
        if not self._api_client:
            logger.error("API client not set")
            return False
        
        try:
            response = self._api_client.post(
                "/auth/login",
                json_data={
                    "email": email,
                    "password": password
                }
            )
            
            # API response structure: { code, status, data: { token, user } }
            data = response.get("data", response)
            
            # Extract token from response
            token = data.get("token", data.get("access_token"))
            if not token:
                raise ValueError("Token không được trả về từ server")
            
            # Extract user info
            user_data = data.get("user", data)
            self._user = UserInfo.from_dict(user_data)
            self._token = token
            
            # Update API client with token
            self._api_client.set_token(self._token)
            
            # Save token
            self._save_token()
            
            logger.info(f"User logged in: {self._user.email}")
            
            if self.on_login:
                self.on_login(self._user)
            
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            if self.on_auth_error:
                self.on_auth_error(str(e))
            return False
    
    def logout(self) -> None:
        """Logout and clear token."""
        self._token = None
        self._user = None
        
        if self._api_client:
            self._api_client.clear_token()
        
        # Remove saved token
        self._clear_saved_token()
        
        logger.info("User logged out")
        
        if self.on_logout:
            self.on_logout()
    
    def validate_token(self) -> bool:
        """
        Validate current token by making a test request.
        Returns True if token is valid.
        """
        if not self._token or not self._api_client:
            return False
        
        try:
            # Make a simple request to validate token
            response = self._api_client.get("/auth/me")
            
            # API response structure: { code, status, data: { user } }
            data = response.get("data", response)
            
            # Update user info
            self._user = UserInfo.from_dict(data.get("user", data))
            
            if self.on_login:
                self.on_login(self._user)
            
            return True
            
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            self._token = None
            self._user = None
            self._clear_saved_token()
            return False
    
    def _save_token(self) -> None:
        """Save token to file."""
        try:
            data = {
                "token": self._token,
                "user": {
                    "id": self._user.id,
                    "email": self._user.email,
                    "name": self._user.name,
                    "role": self._user.role
                } if self._user else None,
                "saved_at": datetime.now().isoformat()
            }
            
            with open(self._token_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Token saved to file")
            
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
    
    def _load_saved_token(self) -> None:
        """Load token from file."""
        if not self._token_file.exists():
            return
        
        try:
            with open(self._token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._token = data.get("token")
            
            user_data = data.get("user")
            if user_data:
                self._user = UserInfo.from_dict(user_data)
            
            # Set token to API client if available
            if self._token and self._api_client:
                self._api_client.set_token(self._token)
            
            logger.debug("Token loaded from file")
            
        except Exception as e:
            logger.error(f"Failed to load saved token: {e}")
            self._token = None
            self._user = None
    
    def _clear_saved_token(self) -> None:
        """Remove saved token file."""
        try:
            if self._token_file.exists():
                self._token_file.unlink()
                logger.debug("Token file removed")
        except Exception as e:
            logger.error(f"Failed to remove token file: {e}")
