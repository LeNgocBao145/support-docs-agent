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
- **Daily Log**: [View Log](https://sgp1.digitaloceanspaces.com/optisigns-support-agent-logs/logs/2026-01-01.log?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=DO801UXACG4AU68J47MG%2F20260101%2Fsgp1%2Fs3%2Faws4_request&X-Amz-Date=20260101T033100Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=8504bc54f30e8650daafc47715b05db20b2a91209ae03bb0c9bbcc44d2fba02f)

View real-time logs during deployment:
```bash
doctl apps logs --app-id APP_ID --follow
```

The application automatically generates and logs the signed URLs for easy access to historical logs.

## Playground Answer

![Playground Answer](image.png)