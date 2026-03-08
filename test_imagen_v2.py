import os
import io
import sys
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Force UTF-8 for windows console
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def test_imagen_direct_v2():
    api_key = os.getenv("GOOGLE_API_KEY")
    print(f"--- 🤖 Testing Imagen Direct v2 ---")
    print(f"Key ends in: ...{api_key[-5:] if api_key else 'NONE'}")
    
    if not api_key:
        print("❌ GOOGLE_API_KEY not found")
        return

    client = genai.Client(api_key=api_key)
    
    # Try the most robust Imagen model name from AI Studio
    model_id = "imagen-3.0-generate-002" 
    
    prompt = "A high-quality cinematic photo of a sunset over a lush green rice field in India, 8k resolution, highly detailed, professional photography style."
    
    print(f">> Calling Imagen with prompt: {prompt}")
    
    try:
        response = client.models.generate_images(
            model=model_id,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9"
            )
        )
        
        if response.generated_images:
            image_data = response.generated_images[0]
            # Save the raw bytes directly first
            with open("raw_imagen_output.png", "wb") as f:
                f.write(image_data.image.image_bytes)
            print(f"✅ SUCCESS! Raw image saved to: raw_imagen_output.png")
            
            # Now try saving via PIL to check if it's readable
            from PIL import Image
            img = Image.open(io.BytesIO(image_data.image.image_bytes))
            img.save("processed_imagen_output.jpg", "JPEG", quality=95)
            print(f"✅ SUCCESS! Processed image saved to: processed_imagen_output.jpg")
            print(f"Image properties: {img.size}, {img.mode}")
        else:
            print("❌ No images generated in response.")
            print(f"Response: {response}")
            
    except Exception as e:
        print(f"❌ Imagen Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_imagen_direct_v2()
