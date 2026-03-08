import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from writer.article_generator import generate_article

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    test_topic = {
        "topic": "PM Kisan Beneficiary Status 2026",
        "matched_keyword": "pm-kisan-samman-nidhi",
        "stories": [{"summary": "Latest updates on PM Kisan scheme for farmers."}]
    }
    article = generate_article(test_topic)
    if article:
        with open("full_test_article.html", "w", encoding="utf-8") as f:
            f.write(article["full_content"])
        print("Success! Wrote to full_test_article.html")
