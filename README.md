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

Job execution logs are stored in the `logs/` directory:
- `upload.log` - Detailed upload operations
- `last_run.log` - Last run job-specific execution log

For production deployments on DigitalOcean App Platform, view logs with:
```bash
doctl apps logs --app-id APP_ID --follow
```

## Playground Answer

![Playground Answer](image.png)