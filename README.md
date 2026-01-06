# Support Docs Agent

Automated scraper and vector store manager for OptiSigns support documentation.

## Setup

Install dependencies:
```bash
pip install -r requirements.txt
```

Configure environment variables by creating `.env` file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```
OPENAI_API_KEY=sk-...
ZENDESK_API_URL=https://support.optisigns.com/api/v2/help_center/en-us/articles.json
ZENDESK_SUPPORT_BASE_URL=https://support.optisigns.com
VECTOR_STORE_ID=vs_...
ASSISTANT_ID=asst_...
```

## How to Run Locally

Run the complete scraper and uploader job:
```bash
python main.py
```

Or run individual components:
```bash
python scrape_articles.py              # Only scrape articles
python upload_to_vector_store.py       # Only upload to vector store
```


## Chunking Strategy & Vector Store Upload

### Chunking Strategy

This project relies on **OpenAI-managed automatic chunking** when uploading Markdown files to the Vector Store.

Rationale:
- The support articles are already well-structured with semantic Markdown headings (`#`, `##`, `###`).
- OpenAI’s native chunking is optimized for retrieval performance and respects document structure.
- This avoids overfitting chunk sizes or introducing incorrect manual splits that could degrade answer quality.

No manual chunk size or overlap is specified in code. Each Markdown file is uploaded as a single logical document, and OpenAI handles internal segmentation during embedding.

### Files & Chunks Logging

OpenAI’s Vector Store API does **not currently expose**:
- The exact number of chunks generated per file
- The internal chunk boundaries or token counts

Because of this limitation:
- The application logs **file-level operations only** (added, updated, skipped).
- Any attempt to locally estimate chunk counts would be inaccurate and misleading.

The following metrics are reliably logged:
- Number of Markdown files uploaded
- Number of files updated (content hash changed)
- Number of files skipped (no change detected)

This ensures correctness and transparency while respecting API constraints.


## Daily Job Logs

Job execution logs are automatically uploaded to DigitalOcean Spaces and accessible via signed URLs:

### Local Development
Logs are stored in the `logs/` directory:
- `upload.log` - Detailed upload operations
- `last_run.log` - Last run job-specific execution log

### Production (DigitalOcean App Platform)
Logs are uploaded to DigitalOcean Spaces with 7-day expiring URLs:

**Latest Job Logs (Updated: 2026-01-01 10:31:00)**
- **Last Run Log**: [View Log](https://sgp1.digitaloceanspaces.com/optisigns-support-agent-logs/last_run.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=DO801UXACG4AU68J47MG%2F20260101%2Fsgp1%2Fs3%2Faws4_request&X-Amz-Date=20260101T033059Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=da879805e63d31c176b7178bd9f579b4d62675b3afaf075278d42b9f0ca389a0)
- **Daily Log**: [View Log](https://sgp1.digitaloceanspaces.com/optisigns-support-agent-logs/daily.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=DO801UXACG4AU68J47MG%2F20260106%2Fsgp1%2Fs3%2Faws4_request&X-Amz-Date=20260106T043615Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=40c792a372e833d245dfd72ebaf7840ac6e68645ea2ff3dd52e576c8fc0d677e)

View real-time logs during deployment:
```bash
doctl apps logs --app-id APP_ID --follow
```

The application automatically generates and logs the signed URLs for easy access to historical logs.

## Playground Answer

![Playground Answer](image.png)