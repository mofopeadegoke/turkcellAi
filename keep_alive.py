import requests
import time
from dotenv import load_dotenv
import os

load_dotenv()

API_BASE_URL = os.getenv('API_BASE_URL')
API_KEY = os.getenv('API_KEY')

def ping_api():
    """Ping API to keep it awake"""
    try:
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        response = requests.get(f"{API_BASE_URL}/health", headers=headers, timeout=30)
        print(f"✅ API pinged: {response.status_code} ({response.elapsed.total_seconds():.2f}s)")
        return True
    except Exception as e:
        print(f"❌ Ping failed: {e}")
        return False

if __name__ == '__main__':
    print("🏓 Pinging API to wake it up...")
    
    # First ping (might be slow if sleeping)
    print("\n1st ping (waking up)...")
    ping_api()
    
    # Wait a bit
    print("\nWaiting 5 seconds...")
    time.sleep(5)
    
    # Second ping (should be fast now)
    print("\n2nd ping (should be fast)...")
    ping_api()
    
    print("\n✅ API should be awake now. Try test_api.py again.")