import os
import io
import sys
import logging
from google import genai
from google.genai import types

# Force UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imagen_config():
    print(f"--- 🤖 Testing Imagen with key: ...{config.GEMINI_API_KEY[-5:]} ---")
    print(f"    Model: {config.IMAGEN_MODEL}")
    
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    
    prompt = "Cinematic photography of a beautiful Indian field, National Geographic style."
    
    try:
        response = client.models.generate_images(
            model=config.IMAGEN_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9"
            )
        )
        
        if response.generated_images:
            out = "test_imagen_final.png"
            response.generated_images[0].image.save(out)
            print(f"✅ SUCCESS! Saved to {out}")
        else:
            print("❌ No images.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_imagen_config()
