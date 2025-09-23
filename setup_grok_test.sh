#!/bin/bash

# Setup script for testing Grok LLM integration
echo "🔧 Setting up Grok LLM test environment..."

# Check if GROK_API_KEY is set
if [ -z "$GROK_API_KEY" ]; then
    echo "❌ GROK_API_KEY not found!"
    echo "Please set your Grok API key:"
    echo "export GROK_API_KEY='your-api-key-here'"
    echo ""
    echo "You can get a Grok API key from: https://x.ai/"
    exit 1
fi

echo "✅ GROK_API_KEY is set"

# Set environment variables for LLM testing
export LLM_TITLES=1
export LLM_SUMMARIES=1
export GROK_MODEL="grok-4-latest"

echo "✅ Environment variables configured:"
echo "   LLM_TITLES=1 (enabled)"
echo "   LLM_SUMMARIES=1 (enabled)"
echo "   GROK_MODEL=grok-4-latest"

echo ""
echo "🧪 To test the title improvements, run:"
echo "   python test_title_improvement.py"
echo ""
echo "🚀 To run the full application with LLM improvements:"
echo "   python app.py"

