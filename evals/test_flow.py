import requests
import json

# Adjust the port if your FastAPI server runs on something other than 8000
API_URL = "http://localhost:8000/api/chat/"
def test_v_flow():
    print("🚀 Sending test message to V...")
    
    payload = {
        "message": "Hello V! What is your main purpose?",
        "session_id": "test_user_session_123"
    }
    
    try:
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ V's Response:")
            print(f"\n{data.get('v_response')}\n")
        else:
            print(f"🚨 Error {response.status_code}: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("🚨 Connection Error: Is your FastAPI server running?")

if __name__ == "__main__":
    test_v_flow()