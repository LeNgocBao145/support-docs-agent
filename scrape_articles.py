#!/usr/bin/env python3
"""Fetch articles from support.optisigns.com using the Zendesk API"""

import os
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
import time
from urllib.parse import urljoin
from html2text import HTML2Text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OUTPUT_DIR = Path("articles")
OUTPUT_DIR.mkdir(exist_ok=True)

ZENDESK_API_URL = os.getenv("ZENDESK_API_URL")
SUPPORT_BASE_URL = os.getenv("ZENDESK_SUPPORT_BASE_URL")


def fetch_articles_from_api(max_articles=30):
    """Fetch articles from Zendesk API."""
    articles = []
    page = 1
    per_page = 30
    
    while len(articles) < max_articles:
        params = {
            "page": page,
            "per_page": per_page,
            "sort_by": "created_at",
            "sort_order": "desc"
        }
        
        try:
            print(f"Fetching page {page}...")
            response = requests.get(ZENDESK_API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("articles"):
                break
            
            articles.extend(data["articles"])
            print(f"  → Got {len(data['articles'])} articles, total: {len(articles)}")
            
            # Check if there are more pages
            if not data.get("next_page") or len(articles) >= max_articles:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching articles: {e}")
            break
    
    return articles[:max_articles]


def html_to_markdown(html_string):
    """Convert HTML to clean Markdown."""
    if not html_string:
        return ""
    
    h = HTML2Text()
    h.ignore_links = False
    h.body_width = 0  # Don't wrap lines
    h.ignore_emphasis = False
    h.unicode_snob = True
    
    # Handle HTML entities
    html_string = html_string.replace("\\u003C", "<").replace("\\u003E", ">")
    html_string = html_string.replace("\\u003D", "=").replace("\\u0022", '"')
    
    markdown = h.handle(html_string)
    
    # Clean up excessive newlines
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    # Remove lines with only whitespace
    markdown = re.sub(r'^\s+$', '', markdown, flags=re.MULTILINE)
    # Remove multiple spaces
    markdown = re.sub(r'  +', ' ', markdown)
    
    return markdown.strip()


def sanitize_filename(text):
    """Convert text to safe filename slug."""
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def main():
    print("=" * 70)
    print("Zendesk Article Fetcher & Markdown Converter")
    print("=" * 70)
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print()
    
    # Fetch articles from API
    print("Fetching articles from Zendesk API...")
    articles = fetch_articles_from_api(max_articles=30)
    
    if not articles:
        print("No articles found!")
        return
    
    print(f"Successfully fetched {len(articles)} articles")
    print()
    print("Converting to Markdown...")
    print("-" * 70)
    
    saved = 0
    for idx, article in enumerate(articles, 1):
        try:
            article_id = article.get("id")
            title = article.get("title") or article.get("name", f"Article {article_id}")
            body_html = article.get("body", "")
            html_url = article.get("html_url", "")
            created_at = article.get("created_at", "")
            updated_at = article.get("updated_at", "")
            
            print(f"[{idx:2d}/{len(articles)}] {title}")
            
            # Create slug from title
            slug = sanitize_filename(title)
            if not slug:
                slug = f"article-{article_id}"
            
            # Convert HTML body to Markdown
            markdown_body = html_to_markdown(body_html)
            
            # Create frontmatter (YAML-style metadata)
            frontmatter = f"""---
title: {title}
article_id: {article_id}
url: {html_url}
created_at: {created_at}
updated_at: {updated_at}
---

# {title}

"""
            
            # Combine frontmatter, title heading, and content
            full_content = frontmatter + markdown_body
            
            # Save to file
            output_file = OUTPUT_DIR / f"{slug}.md"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            print(f"       Saved: {output_file.name}")
            saved += 1
            
        except Exception as e:
            print(f"       Error: {e}")
            continue
    
    print("-" * 70)
    print()
    print("=" * 70)
    print(f"Successfully saved {saved}/{len(articles)} articles")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
