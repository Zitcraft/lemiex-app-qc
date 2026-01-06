"""
Auto-updater for Lemiex QC App
Downloads and applies updates automatically
"""

import os
import sys
import zipfile
import shutil
import tempfile
import requests
from pathlib import Path

from version import check_for_updates, save_version, get_current_version

APP_DIR = Path(__file__).parent.parent
BACKUP_DIR = APP_DIR / "backup"
UPDATE_FOLDERS = ["web", "config"]  # Folders to update (exclude python runtime)
UPDATE_FILES = ["app_eel.py"]  # Root files to update


def download_update(url, dest_path):
    """Download update zip file"""
    print(f"Downloading update from: {url}")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size:
                percent = (downloaded / total_size) * 100
                print(f"\rProgress: {percent:.1f}%", end='', flush=True)
    
    print("\nDownload complete!")
    return True


def copy_from_network(source_path, dest_path):
    """Copy update from network folder"""
    print(f"Copying from network: {source_path}")
    if os.path.isfile(source_path):
        shutil.copy2(source_path, dest_path)
    else:
        # If it's a folder, zip it first or copy directly
        update_zip = os.path.join(source_path, "update.zip")
        if os.path.exists(update_zip):
            shutil.copy2(update_zip, dest_path)
        else:
            # Create zip from folder
            shutil.make_archive(dest_path.replace('.zip', ''), 'zip', source_path)
    return True


def backup_current():
    """Backup current app before update"""
    print("Creating backup...")
    BACKUP_DIR.mkdir(exist_ok=True)
    
    for folder in UPDATE_FOLDERS:
        src = APP_DIR / folder
        dst = BACKUP_DIR / folder
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
    
    for file in UPDATE_FILES:
        src = APP_DIR / file
        if src.exists():
            shutil.copy2(src, BACKUP_DIR / file)
    
    print("Backup complete!")
    return True


def apply_update(zip_path):
    """Extract and apply update"""
    print("Applying update...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_dir)
        
        # Find the extracted content
        extracted = Path(temp_dir)
        contents = list(extracted.iterdir())
        
        # If there's a single folder, use its contents
        if len(contents) == 1 and contents[0].is_dir():
            extracted = contents[0]
        
        # Copy updated folders
        for folder in UPDATE_FOLDERS:
            src = extracted / folder
            dst = APP_DIR / folder
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                print(f"  Updated: {folder}/")
        
        # Copy updated files
        for file in UPDATE_FILES:
            src = extracted / file
            if src.exists():
                shutil.copy2(src, APP_DIR / file)
                print(f"  Updated: {file}")
    
    print("Update applied successfully!")
    return True


def rollback():
    """Rollback to backup if update fails"""
    print("Rolling back to previous version...")
    
    for folder in UPDATE_FOLDERS:
        src = BACKUP_DIR / folder
        dst = APP_DIR / folder
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
    
    for file in UPDATE_FILES:
        src = BACKUP_DIR / file
        if src.exists():
            shutil.copy2(src, APP_DIR / file)
    
    print("Rollback complete!")


def run_update():
    """Main update process"""
    print("=" * 50)
    print("Lemiex QC App - Auto Updater")
    print("=" * 50)
    print(f"Current version: {get_current_version()}")
    
    # Check for updates
    print("\nChecking for updates...")
    update_info = check_for_updates()
    
    if not update_info or not update_info.get('available'):
        print("No updates available. You have the latest version!")
        return False
    
    print(f"\n🆕 New version available: {update_info['latest']}")
    print(f"   Source: {update_info['source']}")
    if update_info.get('release_notes'):
        print(f"\n📝 Release notes:\n{update_info['release_notes'][:500]}")
    
    # Ask user
    response = input("\nDo you want to update now? (y/n): ").strip().lower()
    if response != 'y':
        print("Update cancelled.")
        return False
    
    try:
        # Create backup
        backup_current()
        
        # Download/copy update
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
        
        if update_info['source'] == 'network_folder':
            copy_from_network(update_info['download_path'], tmp_path)
        else:
            download_update(update_info['download_url'], tmp_path)
        
        # Apply update
        apply_update(tmp_path)
        
        # Save new version
        save_version(update_info['latest'])
        
        # Cleanup
        os.unlink(tmp_path)
        
        print("\n" + "=" * 50)
        print("✅ Update complete!")
        print(f"   Version: {update_info['current']} → {update_info['latest']}")
        print("   Please restart the application.")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Update failed: {e}")
        rollback()
        return False


if __name__ == "__main__":
    run_update()
    input("\nPress Enter to exit...")
