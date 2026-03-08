import os
import io
import sys
from google import genai
from dotenv import load_dotenv

# Force UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def list_all_models():
    api_key = "AIzaSyCxV2w396jDHzJV4mVEOM49erXB0Grb6UrtE"
    if not api_key:
        print("❌ No API key provided")
        return

    print(f"--- 📋 Listing all models for key ending in ...{api_key[-5:]} ---")
    try:
        client = genai.Client(api_key=api_key)
        for model in client.models.list():
            print(f"  - {model.name} (Support: {model.supported_generation_methods})")
    except Exception as e:
        print(f"❌ Error listing models: {e}")

def test_pollinations_direct():
    import urllib.request
    import urllib.parse
    print("\n--- 🧪 Testing Pollinations.ai Direct ---")
    prompt = "Professional agricultural photo, green fields, high resolution."
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1200&height=630&nologo=true&model=flux"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            print(f"✅ Received {len(data)} bytes from Pollinations.")
            with open("test_pollinations.jpg", "wb") as f:
                f.write(data)
            print("✅ Saved to test_pollinations.jpg")
    except Exception as e:
        print(f"❌ Pollinations failed: {e}")

if __name__ == "__main__":
    list_all_models()
    test_pollinations_direct()
