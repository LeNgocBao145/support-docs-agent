#!/usr/bin/env python3

import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv

from openai import OpenAI

# =====================================================
# Load environment variables
# =====================================================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

ARTICLES_DIR = Path("articles")
LOGS_DIR = Path("logs")
UPLOAD_HISTORY_FILE = Path(os.getenv("UPLOAD_HISTORY_FILE", "upload_history.json"))
VECTOR_STORE_MAPPING_FILE = Path(
    os.getenv("VECTOR_STORE_MAPPING_FILE", "vector_store_mapping.json")
)

VECTOR_STORE_ID_ENV = os.getenv("VECTOR_STORE_ID", "").strip()

# =====================================================
# Setup logging
# =====================================================
LOGS_DIR.mkdir(exist_ok=True)

# Logger will be injected from main.py
logger = None

def set_logger(external_logger):
    """Set the logger from main.py to use the same handlers."""
    global logger
    logger = external_logger

# If running as __main__, create local logger (for testing)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "upload.log"),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger(__name__)

# =====================================================
# Utilities
# =====================================================
def initialize_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=OPENAI_API_KEY)


def calculate_file_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_json(path: Path) -> Dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: Dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_markdown_files() -> List[Path]:
    if not ARTICLES_DIR.exists():
        logger.warning(f"Articles directory not found: {ARTICLES_DIR}")
        return []
    return sorted(ARTICLES_DIR.glob("*.md"))


# =====================================================
# Vector Store helpers
# =====================================================
def get_or_create_vector_store(client: OpenAI) -> str:    
    if VECTOR_STORE_ID_ENV:
        try:
            vs = client.vector_stores.retrieve(VECTOR_STORE_ID_ENV)
            logger.info(f"Using existing vector store: {VECTOR_STORE_ID_ENV}")
            return VECTOR_STORE_ID_ENV
        except Exception as e:
            logger.error(f"Vector store {VECTOR_STORE_ID_ENV} not found: {e}")
            logger.info("Creating new vector store instead...")

    if ENVIRONMENT == "production":
        raise RuntimeError(
            "VECTOR_STORE_ID must be set in production environment"
        )

    logger.info("Creating new vector store...")
    vs = client.vector_stores.create(name="OptiSigns Support Docs")
    logger.info(f"Created new vector store: {vs.id}")
    return vs.id


def delete_old_file_from_vector_store(
    client: OpenAI, vector_store_id: str, mapping: Dict, file_name: str
):
    """
    If file was previously uploaded, delete old file from vector store
    to avoid duplicate content in vector store.
    """
    old = mapping.get(file_name)
    if not old:
        return

    old_file_id = old.get("file_id")
    if not old_file_id:
        return

    try:
        client.vector_stores.files.delete(vector_store_id, old_file_id)
        logger.info(f"Deleted old file from vector store: {old_file_id}")
    except Exception as e:
        logger.warning(f"Failed to delete old file {old_file_id}: {e}")


# =====================================================
# Main workflow
# =====================================================
def main():
    logger.info("=" * 70)
    logger.info("OpenAI Vector Store Upload Job")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info("=" * 70)

    client = initialize_client()

    upload_history = load_json(UPLOAD_HISTORY_FILE)
    vector_store_mapping = load_json(VECTOR_STORE_MAPPING_FILE)

    markdown_files = get_markdown_files()
    logger.info(f"Found {len(markdown_files)} markdown files")

    if not markdown_files:
        logger.warning("No markdown files found, exiting.")
        return {
            "uploaded_files": 0,
            "updated_files": 0,
            "skipped_files": 0,
            "new_files": 0,
            "total_chunks": 0,
            "vector_store_id": None,
            "upload_log": str(LOGS_DIR / "upload.log"),
        }

    vector_store_id = get_or_create_vector_store(client)

    uploaded = 0
    updated = 0
    skipped = 0

    for file_path in markdown_files:
        file_name = file_path.name
        current_hash = calculate_file_hash(file_path)
        previous_hash = upload_history.get(file_name)

        if previous_hash == current_hash:
            skipped += 1
            logger.info(f"SKIP  {file_name} (unchanged)")
            continue

        if previous_hash:
            logger.info(f"UPDATE {file_name}")
            delete_old_file_from_vector_store(client, vector_store_id, vector_store_mapping, file_name)
            updated += 1
        else:
            logger.info(f"NEW    {file_name}")
            uploaded += 1

        try:
            # upload + embed + index (blocking)
            batch = client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=[file_path],
            )

            if batch.status != "completed":
                raise RuntimeError(f"Upload batch failed: {batch.status}")

            # Query vector store files to get the file_id
            vs_files = client.vector_stores.files.list(vector_store_id)
            file_id = None
            
            # Find the most recently added file (should be our upload)
            if vs_files.data:
                # Get the first file (most recent in the vector store)
                file_id = vs_files.data[0].id
                logger.info(f"Uploaded and indexed: {file_name} (file_id: {file_id})")
            else:
                logger.warning(f"Could not find file_id for {file_name}, continuing...")
                file_id = f"unknown_{file_path.stem}"

            upload_history[file_name] = current_hash
            vector_store_mapping[file_name] = {
                "file_id": file_id,
                "uploaded_at": datetime.utcnow().isoformat() + "Z",
                "vector_store_id": vector_store_id,
            }

        except Exception as e:
            logger.error(f"Failed processing {file_name}: {e}")
            continue

    save_json(UPLOAD_HISTORY_FILE, upload_history)
    save_json(VECTOR_STORE_MAPPING_FILE, vector_store_mapping)

    logger.info("-" * 70)
    logger.info("Upload summary:")
    logger.info(f"  New files:     {uploaded}")
    logger.info(f"  Updated files: {updated}")
    logger.info(f"  Skipped files: {skipped}")
    logger.info(f"  Vector Store:  {vector_store_id}")
    logger.info("-" * 70)

    upload_log = LOGS_DIR / "upload.log"
    
    return {
        "uploaded_files": uploaded,
        "updated_files": updated,
        "skipped_files": skipped,
        "new_files": uploaded,
        "total_chunks": uploaded + updated,
        "vector_store_id": vector_store_id,
        "upload_log": str(upload_log),
    }


if __name__ == "__main__":
    exit(main())