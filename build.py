"""
Build script for Lemiex QC App distribution
Creates a portable distribution package
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path
from datetime import datetime

# Configuration
APP_NAME = "LemiexQC"
VERSION = "1.0.0"
BUILD_DIR = Path("dist")
PACKAGE_DIR = BUILD_DIR / f"{APP_NAME}_v{VERSION}"

# Files and folders to include
INCLUDE_FOLDERS = [
    "web",
    "config", 
    "updater",
]

INCLUDE_FILES = [
    "app_eel.py",
    "version.json",
    "requirements.txt",
]

# Files to exclude
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    ".git",
    ".env",
    "*.log",
    "recordings",  # Don't include user recordings
]


def clean_build():
    """Clean previous build"""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    PACKAGE_DIR.mkdir(parents=True)


def copy_app_files():
    """Copy application files"""
    print("Copying application files...")
    
    for folder in INCLUDE_FOLDERS:
        src = Path(folder)
        if src.exists():
            dst = PACKAGE_DIR / folder
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS))
            print(f"  ✓ {folder}/")
    
    for file in INCLUDE_FILES:
        src = Path(file)
        if src.exists():
            shutil.copy2(src, PACKAGE_DIR / file)
            print(f"  ✓ {file}")


def create_launcher_bat():
    """Create simple batch launcher (default)"""
    launcher_content = f'''@echo off
title {APP_NAME}
cd /d "%~dp0"

:: Check for Python in the portable folder
if exist "python\\python.exe" (
    echo Using portable Python...
    set PYTHON=python\\python.exe
) else (
    echo Using system Python...
    set PYTHON=python
)

:: Check for updates (optional)
if exist "updater\\auto_update.py" (
    echo Checking for updates...
    %PYTHON% updater\\auto_update.py --check-only 2>nul
)

:: Run the app
echo Starting {APP_NAME}...
%PYTHON% app_eel.py

:: Keep window open on error
if errorlevel 1 (
    echo.
    echo Application exited with error!
    pause
)
'''
    
    launcher_path = PACKAGE_DIR / f"{APP_NAME}.bat"
    with open(launcher_path, 'w') as f:
        f.write(launcher_content)
    print(f"  ✓ {APP_NAME}.bat")


def create_role_launchers():
    """Create separate launchers for each role (multi-instance support)"""
    roles = [
        ("QC", 8081, "#10B981"),
        ("Packing", 8082, "#F59E0B"),
        ("Shipout", 8083, "#3B82F6"),
    ]
    
    for role_name, port, color in roles:
        launcher_content = f'''@echo off
title Lemiex {role_name} - Port {port}
cd /d "%~dp0"

:: Check for Python
if exist "python\\python.exe" (
    set PYTHON=python\\python.exe
) else (
    set PYTHON=python
)

echo ==========================================
echo   Lemiex {role_name}
echo   Port: {port}
echo ==========================================
echo.

:: Run the app with role-specific settings
%PYTHON% app_eel.py --role {role_name}

if errorlevel 1 (
    echo.
    echo Application exited with error!
    pause
)
'''
        
        launcher_path = PACKAGE_DIR / f"Lemiex_{role_name}.bat"
        with open(launcher_path, 'w') as f:
            f.write(launcher_content)
        print(f"  ✓ Lemiex_{role_name}.bat (port {port})")


def create_multi_instance_bat():
    """Create launcher to start multiple roles at once"""
    content = f'''@echo off
title Lemiex Multi-Instance Launcher
cd /d "%~dp0"

echo ==========================================
echo   Lemiex Multi-Instance Launcher
echo ==========================================
echo.
echo This will start multiple instances:
echo   - QC (port 8081)
echo   - Packing (port 8082)
echo   - Shipout (port 8083)
echo.
echo Press any key to start all instances...
pause > nul

echo Starting QC...
start "Lemiex QC" Lemiex_QC.bat

timeout /t 2 /nobreak > nul

echo Starting Packing...
start "Lemiex Packing" Lemiex_Packing.bat

timeout /t 2 /nobreak > nul

echo Starting Shipout...
start "Lemiex Shipout" Lemiex_Shipout.bat

echo.
echo All instances started!
echo.
pause
'''
    
    launcher_path = PACKAGE_DIR / "Start_All_Instances.bat"
    with open(launcher_path, 'w') as f:
        f.write(content)
    print(f"  ✓ Start_All_Instances.bat")


def create_updater_bat():
    """Create update checker batch file"""
    updater_content = f'''@echo off
title {APP_NAME} Updater
cd /d "%~dp0"

if exist "python\\python.exe" (
    set PYTHON=python\\python.exe
) else (
    set PYTHON=python
)

echo ==========================================
echo {APP_NAME} - Update Checker
echo ==========================================
echo.

%PYTHON% updater\\auto_update.py

pause
'''
    
    updater_path = PACKAGE_DIR / "Update.bat"
    with open(updater_path, 'w') as f:
        f.write(updater_content)
    print(f"  ✓ Update.bat")


def create_install_deps_bat():
    """Create dependencies installer"""
    install_content = '''@echo off
title Install Dependencies
cd /d "%~dp0"

echo Installing Python dependencies...
echo.

if exist "python\\python.exe" (
    python\\python.exe -m pip install -r requirements.txt
) else (
    pip install -r requirements.txt
)

echo.
echo Done! You can now run LemiexQC.bat
pause
'''
    
    install_path = PACKAGE_DIR / "Install_Dependencies.bat"
    with open(install_path, 'w') as f:
        f.write(install_content)
    print(f"  ✓ Install_Dependencies.bat")


def create_readme():
    """Create README for users"""
    readme_content = f'''# {APP_NAME} - Ứng dụng QC Lemiex

## Phiên bản: {VERSION}
## Ngày build: {datetime.now().strftime('%Y-%m-%d')}

---

## 📦 Cài đặt lần đầu

### Cách 1: Sử dụng Python đã cài sẵn
1. Đảm bảo máy tính đã cài Python 3.9+
2. Chạy `Install_Dependencies.bat` để cài các thư viện cần thiết
3. Chạy `{APP_NAME}.bat` để khởi động ứng dụng

### Cách 2: Sử dụng Portable Python (không cần cài đặt)
1. Tải Python Embeddable từ: https://www.python.org/downloads/windows/
2. Giải nén vào thư mục `python/` trong thư mục này
3. Chạy `{APP_NAME}.bat`

---

## 🚀 Khởi động

Double-click vào `{APP_NAME}.bat` hoặc shortcut trên Desktop.

---

## 🔄 Cập nhật

Chạy `Update.bat` để kiểm tra và tải phiên bản mới (nếu có).

---

## ⚙️ Cấu hình

- **config/roles_config.py** - Cấu hình vai trò và tính năng
- **web/js/config.js** - Cấu hình frontend

---

## 🆘 Hỗ trợ

Liên hệ: [Email/Slack/Teams của bạn]

---

## 📋 Yêu cầu hệ thống

- Windows 10/11
- Python 3.9+ (hoặc sử dụng Portable Python đi kèm)
- Kết nối mạng nội bộ
- Webcam (nếu sử dụng tính năng quay video)
- Máy in nhiệt 4x6 inch (nếu sử dụng tính năng in nhãn)
'''
    
    readme_path = PACKAGE_DIR / "README.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"  ✓ README.txt")


def create_zip():
    """Create distribution zip file"""
    print("\nCreating zip package...")
    zip_name = f"{APP_NAME}_v{VERSION}.zip"
    zip_path = BUILD_DIR / zip_name
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PACKAGE_DIR):
            # Skip excluded folders
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git']]
            
            for file in files:
                file_path = Path(root) / file
                arc_name = file_path.relative_to(BUILD_DIR)
                zf.write(file_path, arc_name)
    
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  ✓ {zip_name} ({size_mb:.1f} MB)")
    return zip_path


def create_update_package():
    """Create update-only package (code only, no Python runtime)"""
    print("\nCreating update package...")
    update_dir = BUILD_DIR / "update"
    update_dir.mkdir(exist_ok=True)
    
    # Copy only code folders
    for folder in ["web", "config"]:
        src = Path(folder)
        if src.exists():
            dst = update_dir / folder
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS))
    
    # Copy main app file
    shutil.copy2("app_eel.py", update_dir / "app_eel.py")
    
    # Create update zip
    update_zip = BUILD_DIR / f"update_v{VERSION}.zip"
    with zipfile.ZipFile(update_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(update_dir):
            dirs[:] = [d for d in dirs if d not in ['__pycache__']]
            for file in files:
                file_path = Path(root) / file
                arc_name = file_path.relative_to(update_dir)
                zf.write(file_path, arc_name)
    
    size_mb = update_zip.stat().st_size / (1024 * 1024)
    print(f"  ✓ update_v{VERSION}.zip ({size_mb:.1f} MB)")
    
    # Cleanup
    shutil.rmtree(update_dir)
    
    return update_zip


def build():
    """Main build process"""
    print("=" * 50)
    print(f"Building {APP_NAME} v{VERSION}")
    print("=" * 50)
    
    clean_build()
    copy_app_files()
    
    print("\nCreating launcher scripts...")
    create_launcher_bat()
    create_role_launchers()      # NEW: Separate launchers for each role
    create_multi_instance_bat()  # NEW: Start all instances at once
    create_updater_bat()
    create_install_deps_bat()
    create_readme()
    
    full_zip = create_zip()
    update_zip = create_update_package()
    
    print("\n" + "=" * 50)
    print("✅ Build complete!")
    print("=" * 50)
    print(f"\n📦 Distribution packages:")
    print(f"   Full install: {full_zip}")
    print(f"   Update only:  {update_zip}")
    print(f"\n📁 Folder:       {PACKAGE_DIR}")
    print(f"\n🚀 Multi-instance launchers:")
    print(f"   Lemiex_QC.bat      (port 8081)")
    print(f"   Lemiex_Packing.bat (port 8082)")
    print(f"   Lemiex_Shipout.bat (port 8083)")
    print(f"   Start_All_Instances.bat")
    
    return True


if __name__ == "__main__":
    build()
