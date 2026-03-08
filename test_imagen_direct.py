import os
import sys
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

import io
import sys

# Force UTF-8 for windows console
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_imagen_direct():
    api_key = "AIzaSyCxV2w396jDHzJV4mVEOM49er"
    if not api_key:
        print("❌ API key not provided")
        return

    client = genai.Client(api_key=api_key)
    
    # List models to see what we have
    print("--- 📋 Available models ---")
    try:
        for model in client.models.list():
            if "imagen" in model.name.lower():
                print(f"  - {model.name}")
    except Exception as e:
        print(f"  ❌ Error listing models: {e}")

    model_id = config.IMAGEN_MODEL # Check config.py
    print(f"\n--- 🤖 Testing Imagen with configured model: {model_id} ---")
    
    prompt = "Cinematic photo of a lush green rice field in India, National Geographic style, professional lighting."
    
    try:
        response = client.models.generate_images(
            model=model_id,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
            )
        )
        
        if response.generated_images:
            image_data = response.generated_images[0]
            output_path = "test_imagen_result.png"
            image_data.image.save(output_path)
            print(f"✅ SUCCESS! Image saved to: {output_path}")
        else:
            print("❌ No images generated.")
            
    except Exception as e:
        print(f"❌ Imagen API Error: {e}")

if __name__ == "__main__":
    test_imagen_direct()
