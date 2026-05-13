import requests
import json

BASE_URL = "http://localhost:5000" # Assuming local dev

def test_attendance():
    # Mock user
    email = "test@example.com"
    event = "Inter-house Meet"
    
    # 1. Try to check in
    print("Checking in...")
    res = requests.post(f"{BASE_URL}/api/attendance", json={
        "email": email,
        "event_title": event,
        "type": "check_in",
        "timestamp": "2026-05-12T10:00:00Z"
    })
    print(f"Status: {res.status_code}, Body: {res.json()}")

    # 2. Try to check in again (should fail)
    print("\nChecking in again...")
    res = requests.post(f"{BASE_URL}/api/attendance", json={
        "email": email,
        "event_title": event,
        "type": "check_in",
        "timestamp": "2026-05-12T11:00:00Z"
    })
    print(f"Status: {res.status_code}, Body: {res.json()}")

if __name__ == "__main__":
    # Note: This requires the server to be running.
    # Since I can't guarantee that, I'll just check the code again.
    pass
