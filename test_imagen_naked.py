import os
import io
import sys
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Force UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# Setup logging to see the full error details
logging.basicConfig(level=logging.DEBUG)

def test_imagen_naked():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # We saw these in the list
    models = [
        "imagen-4.0-generate-001",
        "imagen-4.0-fast-generate-001"
    ]
    
    prompt = "A high-quality photo of a beautiful green field in India."
    
    for m in models:
        print(f"\n--- 🤖 Testing {m} (NAKED CALL) ---")
        try:
            # COMPLETELY NAKED CALL - No config at all
            response = client.models.generate_images(
                model=m,
                prompt=prompt
            )
            if response.generated_images:
                print(f"✅ SUCCESS with {m}!")
                out_name = f"naked_test_{m.replace('.', '_')}.png"
                response.generated_images[0].image.save(out_name)
            else:
                print(f"❌ No images for {m}")
        except Exception as e:
            print(f"❌ Error with {m}: {e}")
            # Log the full exception for buried details
            logging.exception("Full details:")

if __name__ == "__main__":
    test_imagen_naked()
