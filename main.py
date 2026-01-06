#!/usr/bin/env python3
"""
Main orchestration script for scraping articles and uploading to OpenAI Vector Store.
Handles:
- Scraping support.optisigns.com for new/updated articles
- Delta detection (new, updated, deleted)
- Uploading to OpenAI Vector Store
- Logging and reporting
- Uploading logs to DigitalOcean Spaces
"""

import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

try:
    import boto3
    from botocore.config import Config
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    Config = None

# Import scraper and uploader modules
sys.path.insert(0, str(Path(__file__).parent))

from scrape_articles import fetch_articles_from_api, html_to_markdown, sanitize_filename
import upload_to_vector_store as uploader
import shutil

# Load environment variables
load_dotenv()

# Configure logging
def setup_logging():
    """Configure logging for the job."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("optisigns_job")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler for last_run.log (overwrite each time)
    last_run_log = logs_dir / "last_run.log"
    last_run_handler = logging.FileHandler(last_run_log, mode='w')  # 'w' = overwrite
    last_run_handler.setLevel(logging.INFO)
    last_run_handler.setFormatter(formatter)
    logger.addHandler(last_run_handler)
    
    # File handler for upload.log (append forever)
    upload_log = logs_dir / "upload.log"
    upload_handler = logging.FileHandler(upload_log, mode='a')  # 'a' = append
    upload_handler.setLevel(logging.INFO)
    upload_handler.setFormatter(formatter)
    logger.addHandler(upload_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger, last_run_log


def upload_logs_to_spaces(logger, last_run_log):
    """Upload logs to DigitalOcean Spaces."""
    if not HAS_BOTO3:
        logger.warning("boto3 not installed, skipping upload to Spaces")
        return None
    
    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Check if logs directory has any content
    log_files = list(logs_dir.glob("*.log"))
    if not log_files:
        logger.warning(f"No log files found in {logs_dir}, skipping upload")
        return None
    
    # Get credentials from environment
    spaces_key = os.getenv("DO_SPACES_KEY")
    spaces_secret = os.getenv("DO_SPACES_SECRET")
    spaces_bucket = os.getenv("DO_SPACES_BUCKET")
    spaces_region = os.getenv("DO_SPACES_REGION", "nyc3")
    
    if not all([spaces_key, spaces_secret, spaces_bucket]):
        logger.warning("DigitalOcean Spaces credentials not set, skipping upload")
        return None
    
    try:
        # Initialize S3 client with S3v4 signature for DigitalOcean Spaces
        s3 = boto3.client(
            's3',
            region_name=spaces_region,
            endpoint_url=f'https://{spaces_region}.digitaloceanspaces.com',
            aws_access_key_id=spaces_key,
            aws_secret_access_key=spaces_secret,
            config=Config(signature_version='s3v4')
        )
        
        urls = {}
        
        # Flush all log handlers to ensure logs are written to disk
        for handler in logger.handlers:
            handler.flush()
        
        # Upload last_run.log (overwrite)
        if last_run_log.exists() and last_run_log.stat().st_size > 0:
            logger.info(f"Uploading {last_run_log.name} ({last_run_log.stat().st_size} bytes)")
            s3.upload_file(
                str(last_run_log),
                spaces_bucket,
                'last_run.log'
            )
            # Generate signed URL (valid for 7 days)
            last_run_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': spaces_bucket, 'Key': 'last_run.log'},
                ExpiresIn=7*24*60*60  # 7 days
            )
            
            urls['last_run_url'] = last_run_url
            logger.info(f"✓ Uploaded last_run.log to Spaces")
        else:
            logger.warning(f"last_run.log not found or empty, skipping")
        
        # Upload upload.log with date prefix (for daily logs)
        upload_log = logs_dir / "upload.log"
        if upload_log.exists() and upload_log.stat().st_size > 0:
            logger.info(f"Uploading {upload_log.name} ({upload_log.stat().st_size} bytes)")
            s3.upload_file(
                str(upload_log),
                spaces_bucket,
                f'daily.log'
            )
            # Generate signed URL (valid for 7 days - max allowed by DigitalOcean)
            daily_log_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': spaces_bucket, 'Key': f'daily.log'},
                ExpiresIn=7*24*60*60  # 7 days (604800 seconds - max allowed)
            )
            
            urls['daily_log_url'] = daily_log_url
            logger.info(f"✓ Uploaded upload.log to Spaces")
        else:
            logger.warning(f"upload.log not found or empty, skipping")
        
        logger.info(f"Successfully uploaded {len(urls)} log files to Spaces")
        return urls
    except Exception as e:
        logger.error(f"Failed to upload logs to Spaces: {e}", exc_info=True)
        return None
        


def scrape_and_save_articles():
    """Scrape articles from Zendesk and save as markdown."""
    logger = logging.getLogger(__name__)
    
    articles_dir = Path("articles")
    
    # Clean up old articles before scraping
    if articles_dir.exists():
        shutil.rmtree(articles_dir)
        logger.info(f"Cleaned up old articles directory: {articles_dir}")
    
    articles_dir.mkdir(exist_ok=True)
    logger.info("Starting article scraping...")
    
    # Fetch articles
    articles = fetch_articles_from_api(max_articles=30)
    
    if not articles:
        logger.warning("No articles fetched!")
        return 0
    
    saved_count = 0
    for idx, article in enumerate(articles, 1):
        try:
            article_id = article.get("id")
            title = article.get("title") or article.get("name", f"Article {article_id}")
            body_html = article.get("body", "")
            html_url = article.get("html_url", "")
            created_at = article.get("created_at", "")
            updated_at = article.get("updated_at", "")
            
            # Convert HTML to Markdown
            markdown_body = html_to_markdown(body_html)
            
            # Create filename slug
            slug = sanitize_filename(title)
            if not slug:
                slug = f"article-{article_id}"
            
            # Create frontmatter
            frontmatter = f"""---
title: {title}
article_id: {article_id}
url: {html_url}
created_at: {created_at}
updated_at: {updated_at}
---

# {title}

"""
            
            # Combine content
            full_content = frontmatter + markdown_body
            
            # Save file
            output_file = articles_dir / f"{slug}.md"
            
            # Handle duplicates
            if output_file.exists():
                counter = 1
                base_slug = slug
                while (articles_dir / f"{slug}-{counter}.md").exists():
                    counter += 1
                slug = f"{base_slug}-{counter}"
                output_file = articles_dir / f"{slug}.md"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            saved_count += 1
            logger.debug(f"Saved: {output_file.name}")
            
        except Exception as e:
            logger.error(f"Error processing article {article.get('id')}: {e}")
            continue
    
    return saved_count


def main():
    """Main job orchestrator."""
    logger, log_file = setup_logging()
    
    # Validate required environment variables
    required_vars = [
        'OPENAI_API_KEY',
        'ZENDESK_API_URL', 
        'ZENDESK_SUPPORT_BASE_URL'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set all required environment variables and try again.")
        return 1
    
    # Log optional configurations
    optional_vars = {
        'VECTOR_STORE_ID': 'Will auto-create if not provided',
        'ASSISTANT_ID': 'Optional for vector store operations',
        'DO_SPACES_KEY': 'Logs will not be uploaded to Spaces',
        'DO_SPACES_SECRET': 'Logs will not be uploaded to Spaces',
        'DO_SPACES_BUCKET': 'Logs will not be uploaded to Spaces'
    }
    
    for var, description in optional_vars.items():
        if not os.getenv(var):
            logger.info(f"Optional: {var} not set - {description}")
    
    # Pass logger to uploader module
    uploader.set_logger(logger)
    
    logger.info("=" * 80)
    logger.info("OptiSigns Scraper & Vector Store Upload Job")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    try:
        # Step 1: Scrape articles
        logger.info("\n[STEP 1/2] Scraping articles...")
        scraped_count = scrape_and_save_articles()
        logger.info(f"Scraped {scraped_count} articles")
        
        # Step 2: Upload to Vector Store
        logger.info("\n[STEP 2/2] Uploading to Vector Store...")
        upload_result = uploader.main()
        
        # Step 3: Cleanup - Remove articles folder to optimize storage
        logger.info("\n[STEP 3/3] Cleaning up temporary files...")
        articles_dir = Path("articles")
        if articles_dir.exists():
            shutil.rmtree(articles_dir)
            logger.info(f"Cleaned up: {articles_dir} (kept upload_history.json + vector_store_mapping.json for delta detection)")
        
        # Summary (before upload to ensure it's captured)
        logger.info("\n" + "=" * 80)
        logger.info("JOB COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Articles scraped: {scraped_count}")
        logger.info(f"Files uploaded: {upload_result['uploaded_files']}")
        logger.info(f"Total chunks embedded: {upload_result['total_chunks']}")
        logger.info(f"New files: {upload_result['new_files']}")
        logger.info(f"Updated files: {upload_result['updated_files']}")
        logger.info(f"Skipped: {upload_result['skipped_files']}")
        logger.info(f"Vector Store ID: {upload_result['vector_store_id']}")
        logger.info("-" * 80)
        
        # Step 4: Upload logs to DigitalOcean Spaces (if configured)
        logger.info("\n[STEP 4/4] Uploading logs to DigitalOcean Spaces...")            
        
        
        spaces_result = upload_logs_to_spaces(logger, log_file)
        # Final output with URLs
        logger.info("LOG FILES & ARTIFACTS:")
        logger.info(f"Last run (local): {log_file}")
        logger.info(f"History (local): {upload_result['upload_log']}")
        if spaces_result:
            if spaces_result.get('last_run_url'):
                logger.info(f"Last run (S3): {spaces_result['last_run_url']}")
            if spaces_result.get('daily_log_url'):
                logger.info(f"Daily log (S3): {spaces_result['daily_log_url']}")
        logger.info("=" * 80)                
        
        return 0
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error("JOB FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}", exc_info=True)
        logger.info(f"Log file: {log_file}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
