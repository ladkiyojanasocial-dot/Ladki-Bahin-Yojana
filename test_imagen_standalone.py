import os
import io
import sys
from google import genai
from google.genai import types

# Force UTF-8 for windows console
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_imagen_standalone():
    # DIRECTLY USE THE KEY FROM .ENV (I saw this earlier: AIzaSyCxV2w396jDHzJV4mVEOM49er)
    api_key = "AIzaSyCxV2w396jDHzJV4mVEOM49er"
    
    print(f"--- 🤖 Standalone Imagen Test ---")
    
    try:
        client = genai.Client(api_key=api_key)
        
        # Try both models
        models = ["imagen-3.0-generate-002", "imagen-3.0-fast-001"]
        
        for m in models:
            print(f"\n>> Trying model: {m}")
            try:
                response = client.models.generate_images(
                    model=m,
                    prompt="High-quality cinematic photo of a lush green rice field in India, National Geographic style, professional lighting.",
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                    )
                )
                
                if response.generated_images:
                    out = f"standalone_{m.replace('.', '_')}.png"
                    response.generated_images[0].image.save(out)
                    print(f"✅ SUCCESS! Saved to {out}")
                    return
                else:
                    print("❌ No images generated.")
            except Exception as ex:
                print(f"❌ Error with {m}: {ex}")
                
    except Exception as e:
        print(f"❌ Client setup error: {e}")

if __name__ == "__main__":
    test_imagen_standalone()
