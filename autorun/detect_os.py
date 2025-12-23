#!/usr/bin/env python3
"""
OS Detection Script for USB Deployment
Detects the operating system and sets up environment accordingly
"""
import os
import sys
import platform
import subprocess
from pathlib import Path

def detect_os():
    """Detect the operating system"""
    system = platform.system().lower()
    if system == 'linux':
        return 'linux'
    elif system == 'windows':
        return 'windows'
    elif system == 'darwin':
        return 'macos'
    else:
        print(f"Unsupported OS: {system}")
        sys.exit(1)

def get_usb_root():
    """Get USB root directory (D: on Windows, current dir on Linux)"""
    if platform.system().lower() == 'windows':
        # Check if running from USB on D:
        if os.path.exists('D:\\'):
            return Path('D:/')
        else:
            # Fallback to current drive
            return Path(__file__).drive + '\\'
    else:
        # On Linux, assume script is run from USB mount point
        return Path(__file__).parent.parent

def get_python_path():
    """Get Python executable path from USB"""
    usb_root = get_usb_root()
    os_type = detect_os()
    
    if os_type == 'windows':
        python_path = usb_root / 'python' / 'python.exe'
    elif os_type == 'linux':
        python_path = usb_root / 'python' / 'bin' / 'python3'
    else:  # macOS
        python_path = usb_root / 'python' / 'bin' / 'python3'
    
    if python_path.exists():
        return str(python_path)
    else:
        # Fallback to system Python
        return sys.executable

def get_node_path():
    """Get Node executable path from USB"""
    usb_root = get_usb_root()
    os_type = detect_os()
    
    if os_type == 'windows':
        node_path = usb_root / 'node' / 'node.exe'
    else:
        node_path = usb_root / 'node' / 'bin' / 'node'
    
    if node_path.exists():
        return str(node_path)
    else:
        # Fallback to system Node
        return 'node'

def main():
    os_type = detect_os()
    usb_root = get_usb_root()
    python_path = get_python_path()
    node_path = get_node_path()
    
    print(f"✓ Detected OS: {os_type}")
    print(f"✓ USB Root: {usb_root}")
    print(f"✓ Python Path: {python_path}")
    print(f"✓ Node Path: {node_path}")
    
    # Verify critical directories exist
    backend_dir = usb_root / 'backend'
    frontend_dir = usb_root / 'frontend'
    
    if not backend_dir.exists():
        print(f"\n⚠ Warning: Backend directory not found at {backend_dir}")
    else:
        print(f"✓ Backend directory found")
    
    if not frontend_dir.exists():
        print(f"\n⚠ Warning: Frontend directory not found at {frontend_dir}")
    else:
        print(f"✓ Frontend directory found")
    
    # Create environment info file for later reference
    try:
        env_dir = usb_root / 'usb_deploy'
        env_dir.mkdir(parents=True, exist_ok=True)
        
        env_file = env_dir / 'env_info.txt'
        with open(env_file, 'w') as f:
            f.write(f"OS={os_type}\n")
            f.write(f"USB_ROOT={usb_root}\n")
            f.write(f"PYTHON_PATH={python_path}\n")
            f.write(f"NODE_PATH={node_path}\n")
        
        print(f"✓ Environment info saved to: {env_file}")
    except Exception as e:
        print(f"⚠ Could not save environment info: {e}")
    
    print("\n✓ OS detection completed successfully!")
    return os_type

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)