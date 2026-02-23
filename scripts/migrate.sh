#!/bin/bash
# Pre-deployment script that applies D1 migrations
# This script is called by wrangler during the build process

set -e

echo "🗄️  Applying D1 database migrations..."

# Database name from wrangler.toml
DATABASE_NAME="${DATABASE_NAME:-blt-api}"

# Check if we're in local development mode
# Skip migrations for local dev - developers should run migrations manually
if [ "$CF_PAGES" != "1" ] && [ -z "$CLOUDFLARE_API_TOKEN" ] && [ -z "$CF_ACCOUNT_ID" ]; then
    echo "Detected local development mode - skipping automatic migrations"
    echo "   To apply migrations locally, run:"
    echo "   wrangler d1 migrations apply $DATABASE_NAME --local"
    exit 0
fi

# Check that database_id is configured with a real UUID (not the placeholder)
DATABASE_ID=$(grep 'database_id' wrangler.toml 2>/dev/null | head -1 | sed 's/.*=\s*"\([^"]*\)".*/\1/')
if [ -z "$DATABASE_ID" ] || [ "$DATABASE_ID" = "your_database_id_here" ]; then
    echo "⚠️  Warning: database_id is not configured in wrangler.toml"
    echo "   Please replace 'your_database_id_here' with a valid D1 database UUID"
    echo "   Skipping remote migrations..."
    exit 0
fi
if ! echo "$DATABASE_ID" | grep -qE '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'; then
    echo "⚠️  Warning: database_id '$DATABASE_ID' is not a valid UUID"
    echo "   Please set a valid D1 database UUID in wrangler.toml"
    echo "   Skipping remote migrations..."
    exit 0
fi

# Apply migrations to the remote database (production/staging)
echo "📡 Applying migrations to remote database..."
if ! wrangler d1 migrations apply "$DATABASE_NAME" --remote; then
    echo "❌ Error: Failed to apply migrations to database '$DATABASE_NAME'"
    echo "   Make sure the database exists and wrangler is properly authenticated"
    exit 1
fi

echo "✅ Migrations applied successfully!"
