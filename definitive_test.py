import sys
import os
import logging
import json
import io
from dotenv import load_dotenv

load_dotenv()

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))

# Fix encoding
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import writer.article_generator as ag
from publisher import image_handler, wordpress_client

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def run_definitive_test():
    topic = {
        "topic": "PM Kisan Status Check 2026: Beneficiary List & Payment Update",
        "matched_keyword": "pm-kisan-samman-nidhi",
        "stories": [
            {
                "title": "PM Kisan 2026 Update",
                "summary": "The government has released the latest beneficiary list for PM Kisan Samman Nidhi. Farmers can now check their status online.",
                "url": "https://pmkisan.gov.in/",
                "source": "official"
            }
        ],
        "sources": ["official"],
        "top_url": "https://pmkisan.gov.in/"
    }

    print("--- 📝 STEP 1: GENERATING ARTICLE ---")
    try:
        article = ag.generate_article(topic)
        
        if not article:
            print("❌ Article generation returned None.")
            return

        print(f"✅ Article: {article['title']}")
        print(f"📁 Category Slug: {article['category']}")
        print(f"🔗 Slug: {article['slug']}")
        
        # Check for HTML formatting
        print("\n--- 🔍 FORMATTING CHECK ---")
        has_h2 = "<h2>" in article['full_content']
        has_ul = "<ul>" in article['full_content']
        has_strong = "<strong>" in article['full_content'] or "<b>" in article['full_content']
        
        print(f"   H2 Tags Found: {has_h2}")
        print(f"   UL/LI Tags Found: {has_ul}")
        print(f"   Strong Tags Found: {has_strong}")

        if not (has_h2 and has_ul):
             print("⚠️ FORMATTING MIGHT BE MISSING! Content preview:")
             print(article['full_content'][:1000])

        print("\n--- 🎨 STEP 2: GENERATING FEATURED IMAGE ---")
        webp_path, _ = image_handler.generate_featured_image(article['title'])
        if webp_path:
            print(f"✅ Image generated: {webp_path}")
        else:
            print("⚠️ Image generation failed.")

        print("\n--- 📤 STEP 3: PUBLISHING TO WORDPRESS AS DRAFT ---")
        result = wordpress_client.create_post(article, featured_image_path=webp_path, status="draft")

        if result:
            print("\n" + "="*40)
            print("🎉 DEFINITIVE TEST SUCCESSFUL")
            print(f"Post ID: {result['post_id']}")
            print(f"URL: {result['post_url']}")
            print(f"Status: {result['status']}")
            print("="*40)
        else:
            print("❌ Publishing failed.")
            
    except Exception as e:
        import traceback
        print("❌ EXCEPTION DURING TEST:")
        traceback.print_exc()

if __name__ == "__main__":
    run_definitive_test()
