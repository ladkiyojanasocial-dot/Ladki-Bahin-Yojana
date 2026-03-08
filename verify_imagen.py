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

def test_imagen_stable():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    model = "imagen-3.0-generate-001"
    prompt = "A cinematic photo of a thriving green wheat field in India, professional lighting, 8k."
    
    print(f"\n--- 🤖 Testing {model} ---")
    try:
        config = types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="16:9",
        )
        response = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=config
        )
        if response.generated_images:
            print(f"✅ SUCCESS with {model}!")
            out_name = f"verify_{model.replace('.', '_')}.png"
            response.generated_images[0].image.save(out_name)
            print(f"Saved to {out_name}")
        else:
            print(f"❌ No images for {model}")
    except Exception as e:
        print(f"❌ Error with {model}: {e}")

if __name__ == "__main__":
    test_imagen_stable()
