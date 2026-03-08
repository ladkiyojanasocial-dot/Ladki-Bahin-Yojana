import os
import sys
import logging
import io
from dotenv import load_dotenv

# Force UTF-8
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))

import config
from google import genai
from google.genai import types

# Manually create client using the key from config
client = genai.Client(api_key=config.GOOGLE_API_KEY)
            
            if response.generated_images:
                output_path = f"test_{model_id.replace('.', '_')}.png"
                response.generated_images[0].image.save(output_path)
                print(f"✅ SUCCESS! Saved to {output_path}")
                return # Stop if one works
            else:
                print("❌ No images.")
        except Exception as e:
            print(f"❌ Error with {model_id}: {e}")

if __name__ == "__main__":
    test_imagen_via_client()
