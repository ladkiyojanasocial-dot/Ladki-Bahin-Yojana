import os
import io
import sys
from google import genai
from dotenv import load_dotenv

# Force UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def list_available_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    print(f"--- 📋 Listing All Gemini Models for key: ...{api_key[-5:] if api_key else 'NONE'} ---")
    
    if not api_key:
        print("❌ GOOGLE_API_KEY not found")
        return

    client = genai.Client(api_key=api_key)
    
    try:
        print("Fetching models list...")
        # Get models iterator
        models_list = client.models.list()
        
        imagen_found = False
        for m in models_list:
            # Check if this model supports image generation or has 'imagen' in name
            methods = m.supported_generation_methods or []
            if "generate_images" in methods or "imagen" in m.name.lower():
                print(f"🌟 FOUND IMAGE MODEL: {m.name}")
                print(f"   - Display Name: {m.display_name}")
                print(f"   - Methods: {methods}")
                imagen_found = True
            else:
                # Still print all for debugging
                print(f"  - {m.name}")

        if not imagen_found:
            print("⚠️ No dedicated 'imagen' or 'generate_images' models found in this list.")
            
    except Exception as e:
        print(f"❌ Error listing models: {e}")

if __name__ == "__main__":
    list_available_models()
