import os
import sys
import logging
import io
import google.generativeai as genai
from dotenv import load_dotenv

# Force UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))
import config

def test_legacy_sdk_models():
    api_key = config.GEMINI_API_KEY
    print(f"--- 📜 Listing Legacy SDK Models for key: ...{api_key[-5:]} ---")
    
    genai.configure(api_key=api_key)
    
    try:
        for m in genai.list_models():
            if "imagen" in m.name.lower() or "image" in m.name.lower():
                print(f"  - {m.name} (Methods: {m.supported_generation_methods})")
    except Exception as e:
        print(f"❌ Error listing: {e}")

    # Try one prompt with legacy
    print("\n>> Trying simple image with legacy SDK (imagen-3.0-generate-001)")
    try:
        model = genai.GenerativeModel("imagen-3.0-generate-001")
        # Legacy SDK doesn't have a direct 'generate_images' on GenerativeModel in same way
        # but let's see if it's even recognized.
        print(f"✅ Model object created for {model.model_name}")
    except Exception as e:
        print(f"❌ Legacy Error: {e}")

if __name__ == "__main__":
    test_legacy_sdk_models()
