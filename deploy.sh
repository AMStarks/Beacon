#!/bin/bash

echo "🚀 Deploying Beacon to Vercel..."

# Set environment variables (set these in Vercel dashboard)
# export GROK_API_KEY='your-api-key-here'
# export LLM_TITLES=1
# export LLM_SUMMARIES=1

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Test the application locally first
echo "🧪 Testing application locally..."
python -c "import app; print('✅ Application imports successfully')"

echo "✅ Deployment preparation complete!"
echo "📋 Next steps:"
echo "1. Connect this repository to Vercel"
echo "2. Set environment variables in Vercel dashboard"
echo "3. Deploy from Vercel dashboard or GitHub integration"
