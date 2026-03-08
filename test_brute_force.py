import os
import sys
import logging
import io

# Force UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))
import config
from google import genai
from google.genai import types

def brute_force_imagen():
    api_key = config.GEMINI_API_KEY
    print(f"--- 🧪 Brute-forcing Imagen IDs with key: ...{api_key[-5:]} ---")
    
    client = genai.Client(api_key=api_key)
    
    models_to_try = [
        "imagen-3.0-generate-001",
        "imagen-3.0-generate-002",
        "imagen-3.0-fast-001",
        "imagen-4.0-generate-001",
        "imagen-4.0-fast-generate-001",
        "imagen-3.0-capability-001",
    ]
    
    for m in models_to_try:
        print(f"\n>> Testing model: {m}")
        try:
            response = client.models.generate_images(
                model=m,
                prompt="A simple green field in India.",
                config=types.GenerateImagesConfig(number_of_images=1)
            )
            if response.generated_images:
                print(f"✅ SUCCESS with {m}!")
                return m
            else:
                print(f"❓ Done with {m} but no images.")
        except Exception as e:
            err = str(e)
            if "404" in err or "not found" in err.lower():
                print(f"❌ {m}: Not found (404)")
            elif "API key" in err or "400" in err:
                print(f"❌ {m}: Permission/Key error (400)")
            else:
                print(f"❌ {m}: {err}")

if __name__ == "__main__":
    brute_force_imagen()
