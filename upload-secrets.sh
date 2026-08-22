#!/usr/bin/env bash
# filepath: /home/build/programming/website/test-zoho/upload-secrets.sh
# chmod +x upload-secrets.sh
# ./yourscript.sh

set -e

# Find all .env files in the current directory
ENV_FILES=$(find . -maxdepth 1 -name ".env*" -type f)

if [ -z "$ENV_FILES" ]; then
  echo "❌ No .env files found in current directory"
  exit 1
fi

echo "🔍 Found environment files:"
echo "$ENV_FILES"
echo ""

# Process each environment file
for ENV_FILE in $ENV_FILES; do
  # Extract environment name from filename
  if [[ "$ENV_FILE" == "./.env" ]]; then
    ENV="production"  # Default .env goes to production
  else
    ENV=$(basename "$ENV_FILE" | sed 's/^\.env\.//')  # Remove .env. prefix
  fi
  
  echo "🔐 Uploading secrets from $ENV_FILE to repository secrets..."
  
  # Read and process each line in the env file
  while IFS='=' read -r key value || [ -n "$key" ]; do
    # Skip empty lines and comments
    if [[ -n "$key" && "$key" != \#* && "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      # Remove quotes from value if present
      clean_value=$(echo "$value" | sed 's/^"//;s/"$//')
      
      # Upload secret to GitHub repository (not environment)
      if gh secret set "$key" --body "$clean_value" 2>/dev/null; then
        echo "✅ $key added to repository secrets"
      else
        echo "❌ Failed to add $key to repository secrets"
      fi
    fi
  done < "$ENV_FILE"
  
  echo "✨ Completed processing $ENV_FILE"
  echo ""
done

echo "🎉 All environment files processed successfully!"