import sys
import os
import re
import logging

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))

import writer.article_generator as ag

logging.basicConfig(level=logging.DEBUG)

def test_parser_standalone():
    raw_text = """
1. PM Kisan Status Check 2026
2. Meta desc for PM Kisan check.
3. pm-kisan-slug
4. tags1, tags2
5. category-slug
---CONTENT_START---
## Title H2
Article content here.
---CONTENT_END---
    """
    
    print("--- 🧪 TEST 1: LABELED OUTPUT ---")
    result = ag._parse_article_output(raw_text, matched_keyword="test", topic_title="test topic")
    if result:
        print(f"✅ Title: {result.get('title')}")
        print(f"✅ Category: {result.get('category')}")
        print(f"✅ Content Length: {len(result.get('full_content', ''))}")
    else:
        print("❌ Test 1 FAILED!")

    raw_text_no_labels = """
PM Kisan Status Check 2026
Meta desc for PM Kisan check.
pm-kisan-slug
tags1, tags2
category-slug
This is the intro of the article after the category.
It has multiple lines.
    """
    
    print("\n--- 🧪 TEST 2: NO LABELS OUTPUT ---")
    result = ag._parse_article_output(raw_text_no_labels, matched_keyword="test", topic_title="test topic")
    if result:
        print(f"✅ Title: {result.get('title')}")
        print(f"✅ Desc: {result.get('meta_description')}")
        print(f"✅ Slug: {result.get('slug')}")
        print(f"✅ Content Preview: {result.get('full_content', '')[:100]}")
    else:
        print("❌ Test 2 FAILED!")

if __name__ == "__main__":
    test_parser_standalone()
