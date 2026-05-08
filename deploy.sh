#!/usr/bin/env bash
# ==========================================================================
# Deploy Travel Planning Engine to Google Cloud Run
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - GOOGLE_CLOUD_PROJECT environment variable set
#   - Secret Manager secrets created: gemini-api-key, google-maps-api-key
# ==========================================================================
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="travel-engine"

# Validate required config
if [[ -z "$PROJECT_ID" ]]; then
    echo "❌ Error: Set GOOGLE_CLOUD_PROJECT environment variable" >&2
    exit 1
fi

# Trap to report failures
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo "❌ Deployment failed with exit code $exit_code" >&2
    fi
}
trap cleanup EXIT

echo "🚀 Deploying $SERVICE_NAME to Cloud Run ($REGION)..."

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory 256Mi \
    --min-instances 0 \
    --max-instances 3 \
    --set-env-vars "ENVIRONMENT=production,LOG_LEVEL=INFO" \
    --set-secrets "GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_MAPS_API_KEY=google-maps-api-key:latest" \
    --quiet

echo "✅ Deployed! Getting service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --format 'value(status.url)')

echo "🌍 Service URL: $SERVICE_URL"
echo "🔗 Health check: $SERVICE_URL/health"
