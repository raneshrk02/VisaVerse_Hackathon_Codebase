#!/usr/bin/env python3
"""
Wait for backend to be ready by checking if it's responding on port 8001
"""

import sys
import socket
import time

def is_port_open(host, port, timeout=1):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def wait_for_backend(max_wait_seconds=120):
    """Wait for backend to be ready"""
    host = "127.0.0.1"  # Use localhost instead of 172.31.16.1
    port = 8001
    start_time = time.time()
    
    print(f"Waiting for backend on {host}:{port}...")
    
    while time.time() - start_time < max_wait_seconds:
        if is_port_open(host, port):
            print("Backend is ready!")
            return 0
        
        time.sleep(1)
        elapsed = int(time.time() - start_time)
        if elapsed % 10 == 0:  # Print every 10 seconds
            print(f"Still waiting... ({elapsed}s)")
    
    print("Timeout waiting for backend to start")
    return 1

if __name__ == "__main__":
    sys.exit(wait_for_backend(120))
