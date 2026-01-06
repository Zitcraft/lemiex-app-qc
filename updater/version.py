"""
Version management for Lemiex QC App
"""

import os
import json
import requests
from datetime import datetime

# Current version
CURRENT_VERSION = "1.0.0"
VERSION_FILE = "version.json"

# Update server configuration
UPDATE_CONFIG = {
    # Option 1: GitHub Releases (recommended for small team)
    "github": {
        "enabled": True,
        "repo": "Zitcraft/lemiex-app-qc",  # Your GitHub repo
        "api_url": "https://api.github.com/repos/{repo}/releases/latest",
        "download_url": "https://github.com/{repo}/releases/download/v{version}/update.zip"
    },
    
    # Option 2: Self-hosted server (simple HTTP)
    "self_hosted": {
        "enabled": False,
        "version_url": "https://your-server.com/lemiex-qc/version.json",
        "download_url": "https://your-server.com/lemiex-qc/releases/{version}/update.zip"
    },
    
    # Option 3: Shared network folder (simplest for internal)
    "network_folder": {
        "enabled": False,
        "path": r"\\server\shared\LemiexQC\updates",
        "version_file": "latest_version.json"
    }
}

def get_current_version():
    """Get current installed version"""
    version_path = os.path.join(os.path.dirname(__file__), '..', VERSION_FILE)
    if os.path.exists(version_path):
        with open(version_path, 'r') as f:
            data = json.load(f)
            return data.get('version', CURRENT_VERSION)
    return CURRENT_VERSION

def save_version(version):
    """Save version after update"""
    version_path = os.path.join(os.path.dirname(__file__), '..', VERSION_FILE)
    with open(version_path, 'w') as f:
        json.dump({
            'version': version,
            'updated_at': datetime.now().isoformat()
        }, f, indent=2)

def compare_versions(v1, v2):
    """Compare two version strings. Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal"""
    def parse(v):
        return tuple(map(int, v.replace('v', '').split('.')))
    try:
        p1, p2 = parse(v1), parse(v2)
        if p1 > p2: return 1
        if p1 < p2: return -1
        return 0
    except:
        return 0

def check_for_updates():
    """Check if updates are available"""
    current = get_current_version()
    
    # Try each update source
    for source, config in UPDATE_CONFIG.items():
        if not config.get('enabled'):
            continue
            
        try:
            if source == 'github':
                return check_github_update(current, config)
            elif source == 'self_hosted':
                return check_http_update(current, config)
            elif source == 'network_folder':
                return check_network_update(current, config)
        except Exception as e:
            print(f"Update check failed for {source}: {e}")
            continue
    
    return None

def check_github_update(current_version, config):
    """Check GitHub releases for updates"""
    url = config['api_url'].format(repo=config['repo'])
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        latest = data.get('tag_name', '').replace('v', '')
        if compare_versions(latest, current_version) > 0:
            return {
                'available': True,
                'current': current_version,
                'latest': latest,
                'download_url': config['download_url'].format(repo=config['repo'], version=latest),
                'release_notes': data.get('body', ''),
                'source': 'github'
            }
    return {'available': False, 'current': current_version}

def check_http_update(current_version, config):
    """Check self-hosted server for updates"""
    response = requests.get(config['version_url'], timeout=10)
    if response.status_code == 200:
        data = response.json()
        latest = data.get('version', current_version)
        if compare_versions(latest, current_version) > 0:
            return {
                'available': True,
                'current': current_version,
                'latest': latest,
                'download_url': config['download_url'].format(version=latest),
                'release_notes': data.get('changelog', ''),
                'source': 'self_hosted'
            }
    return {'available': False, 'current': current_version}

def check_network_update(current_version, config):
    """Check network folder for updates"""
    version_path = os.path.join(config['path'], config['version_file'])
    if os.path.exists(version_path):
        with open(version_path, 'r') as f:
            data = json.load(f)
            latest = data.get('version', current_version)
            if compare_versions(latest, current_version) > 0:
                return {
                    'available': True,
                    'current': current_version,
                    'latest': latest,
                    'download_path': os.path.join(config['path'], f"v{latest}"),
                    'release_notes': data.get('changelog', ''),
                    'source': 'network_folder'
                }
    return {'available': False, 'current': current_version}
