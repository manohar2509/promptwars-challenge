#!/bin/bash
# Deploy Travel Planning Engine to Google Cloud Run
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="travel-engine"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: Set GOOGLE_CLOUD_PROJECT environment variable"
    exit 1
fi

echo "🚀 Deploying $SERVICE_NAME to Cloud Run ($REGION)..."

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory 512Mi \
    --max-instances 3 \
    --set-env-vars "ENVIRONMENT=production" \
    --set-secrets "GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_MAPS_API_KEY=google-maps-api-key:latest"

echo "✅ Deployed! Getting service URL..."
gcloud run services describe "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --format 'value(status.url)'
