#!/usr/bin/env python3
"""
Manual RAG Cache Clearing Guide

The RAG cache is stored in memory, so the simplest way to clear it is:

METHOD 1: Restart the RAG API service
1. Stop the current RAG API process (Ctrl+C in the terminal)
2. Start it again with: python main.py

METHOD 2: Use the admin API endpoint (if you have admin access)
-- POST request to: http://localhost:8001/api/v1/admin/cache/clear
- Requires admin authentication

METHOD 3: File-based cache clearing (if implemented)
- The cache could also be cleared by restarting the service

This script provides automated clearing via API call.
"""

import requests
import json
import sys

def clear_cache_via_api():
    """Attempt to clear cache via API endpoint"""
    print("Attempting to clear RAG cache via API...")
    
    try:
        url = "http://localhost:8001/api/v1/admin/cache/clear"
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Cache cleared successfully via API!")
            print(f"   Items cleared: {result.get('items_cleared', 'unknown')}")
            return True
        elif response.status_code in [401, 403]:
            print("❌ Authentication required for admin endpoint")
            return False
        else:
            print(f"❌ API Error: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to RAG API server")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("RAG Cache Clearing Tool")
    print("=" * 40)
    
    # Try API method first
    if clear_cache_via_api():
        return
    
    print("\nAPI method failed. Manual instructions:")
    print("=" * 40)
    print("1. Stop the RAG API service (Ctrl+C)")
    print("2. Restart it with: python main.py")
    print("3. This will clear the in-memory cache")
    print("\nNote: The cache stores query responses to improve performance.")
    print("Clearing it will force fresh responses for all queries.")

if __name__ == "__main__":
    main()