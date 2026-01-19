"""
Settings module - Load and manage application configuration.
Loads from .env and config.yaml files.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv


def get_app_data_path() -> Path:
    """
    Get the appropriate data storage path.
    - When running as EXE (frozen): Use AppData/Local/LemiexQC
    - When running as script: Use project directory
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE (PyInstaller)
        # Store data in user's AppData folder for persistence
        app_data = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
        data_path = app_data / 'LemiexQC'
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path
    else:
        # Running as script - use project directory
        return Path(__file__).parent.parent


def get_executable_path() -> Path:
    """
    Get the path where the executable/script is located.
    - When frozen: Directory containing the EXE
    - When script: Project directory
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


@dataclass
class ScannerConfig:
    """Scanner configuration."""
    id: str
    com_port: str
    baud_rate: int = 9600
    enabled: bool = True


@dataclass
class CameraConfig:
    """Camera configuration."""
    id: str
    device_index: int
    resolution: tuple = (1280, 720)
    fps: int = 30
    enabled: bool = True


@dataclass
class RecordingConfig:
    """Recording configuration."""
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    timestamp_position: str = "top-left"
    video_codec: str = "mp4v"
    auto_upload: bool = True
    delete_after_upload: bool = True
    temp_directory: str = "temp_videos"


@dataclass
class UIConfig:
    """UI configuration."""
    theme: str = "dark"
    language: str = "vi"
    window_size: tuple = (1400, 900)
    camera_preview_size: tuple = (640, 360)


@dataclass
class Settings:
    """Application settings container."""
    
    # API Settings (from .env)
    api_base_url: str = ""
    b2_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    default_email: str = ""
    default_password: str = ""
    
    # Local Settings (from config.yaml)
    scanners: List[ScannerConfig] = field(default_factory=list)
    cameras: List[CameraConfig] = field(default_factory=list)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    
    # Paths
    base_path: Path = field(default_factory=Path)  # Data storage path
    exe_path: Path = field(default_factory=Path)   # Executable/assets path
    
    @classmethod
    def load(cls, base_path: Optional[Path] = None) -> "Settings":
        """Load settings from .env and config.yaml files."""
        # Get paths based on frozen/script mode
        data_path = get_app_data_path()       # For user data (auth, logs, etc.)
        exe_path = get_executable_path()      # For bundled assets (web, config templates)
        
        if base_path is None:
            base_path = data_path
        
        # Load .env file (from exe path for bundled files)
        env_path = exe_path / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            # Also check data path (user might have custom .env)
            env_path = data_path / ".env"
            if env_path.exists():
                load_dotenv(env_path)
        
        # Load config.yaml (from exe path for bundled files)
        config_path = exe_path / "config" / "config.yaml"
        yaml_config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f) or {}
        
        # Parse scanners
        scanners = []
        for s in yaml_config.get("scanners", []):
            scanners.append(ScannerConfig(
                id=s.get("id", ""),
                com_port=s.get("com_port", ""),
                baud_rate=s.get("baud_rate", 9600),
                enabled=s.get("enabled", True)
            ))
        
        # Parse cameras
        cameras = []
        for c in yaml_config.get("cameras", []):
            resolution = c.get("resolution", [1280, 720])
            cameras.append(CameraConfig(
                id=c.get("id", ""),
                device_index=c.get("device_index", 0),
                resolution=tuple(resolution),
                fps=c.get("fps", 30),
                enabled=c.get("enabled", True)
            ))
        
        # Parse recording config
        rec_cfg = yaml_config.get("recording", {})
        recording = RecordingConfig(
            timestamp_format=rec_cfg.get("timestamp_format", "%Y-%m-%d %H:%M:%S"),
            timestamp_position=rec_cfg.get("timestamp_position", "top-left"),
            video_codec=rec_cfg.get("video_codec", "mp4v"),
            auto_upload=rec_cfg.get("auto_upload", True),
            delete_after_upload=rec_cfg.get("delete_after_upload", True),
            temp_directory=rec_cfg.get("temp_directory", "temp_videos")
        )
        
        # Parse UI config
        ui_cfg = yaml_config.get("ui", {})
        window_size = ui_cfg.get("window_size", [1400, 900])
        preview_size = ui_cfg.get("camera_preview_size", [640, 360])
        ui = UIConfig(
            theme=ui_cfg.get("theme", "dark"),
            language=ui_cfg.get("language", "vi"),
            window_size=tuple(window_size),
            camera_preview_size=tuple(preview_size)
        )
        
        return cls(
            api_base_url=os.getenv("API_BASE_URL", "https://manage.lemiex.us/api"),
            b2_key_id=os.getenv("B2_KEY_ID", ""),
            b2_application_key=os.getenv("B2_APPLICATION_KEY", ""),
            b2_bucket_name=os.getenv("B2_BUCKET_NAME", ""),
            default_email=os.getenv("DEFAULT_EMAIL", ""),
            default_password=os.getenv("DEFAULT_PASSWORD", ""),
            scanners=scanners,
            cameras=cameras,
            recording=recording,
            ui=ui,
            base_path=base_path,
            exe_path=exe_path
        )
    
    def save_yaml(self) -> None:
        """Save current settings to config.yaml in user data folder."""
        config_dir = self.base_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yaml"
        
        data = {
            "scanners": [
                {
                    "id": s.id,
                    "com_port": s.com_port,
                    "baud_rate": s.baud_rate,
                    "enabled": s.enabled
                }
                for s in self.scanners
            ],
            "cameras": [
                {
                    "id": c.id,
                    "device_index": c.device_index,
                    "resolution": list(c.resolution),
                    "fps": c.fps,
                    "enabled": c.enabled
                }
                for c in self.cameras
            ],
            "recording": {
                "timestamp_format": self.recording.timestamp_format,
                "timestamp_position": self.recording.timestamp_position,
                "video_codec": self.recording.video_codec,
                "auto_upload": self.recording.auto_upload,
                "delete_after_upload": self.recording.delete_after_upload,
                "temp_directory": self.recording.temp_directory
            },
            "ui": {
                "theme": self.ui.theme,
                "language": self.ui.language,
                "window_size": list(self.ui.window_size),
                "camera_preview_size": list(self.ui.camera_preview_size)
            }
        }
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def get_temp_videos_path(self) -> Path:
        """Get the path to temp videos directory."""
        path = self.base_path / self.recording.temp_directory
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_logs_path(self) -> Path:
        """Get the path to logs directory."""
        path = self.base_path / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from files."""
    global _settings
    _settings = Settings.load()
    return _settings
