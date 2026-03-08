import os
import io
import sys
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Force UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def test_imagen_minimal():
    api_key = os.getenv("GOOGLE_API_KEY")
    print(f"--- 🤖 Testing Imagen Minimal ---")
    client = genai.Client(api_key=api_key)
    
    model_id = "imagen-4.0-fast-generate-001"
    prompt = "A simple green field in India."
    
    print(f">> Calling {model_id} with NO config...")
    try:
        # Minimal call
        response = client.models.generate_images(
            model=model_id,
            prompt=prompt
        )
        if response.generated_images:
            print(f"✅ SUCCESS with {model_id}!")
            response.generated_images[0].image.save("minimal_test.png")
        else:
            print("❌ No images.")
    except Exception as e:
        print(f"❌ Error with minimal call: {e}")

    # If that fails, try 3.0-generate-001 which was also in the list
    model_id_v2 = "imagen-3.0-generate-001"
    print(f"\n>> Calling {model_id_v2} with NO config...")
    try:
        response = client.models.generate_images(
            model=model_id_v2,
            prompt=prompt
        )
        if response.generated_images:
            print(f"✅ SUCCESS with {model_id_v2}!")
            response.generated_images[0].image.save("minimal_test_v2.png")
        else:
            print("❌ No images.")
    except Exception as e:
        print(f"❌ Error with v2 minimal call: {e}")

if __name__ == "__main__":
    test_imagen_minimal()
