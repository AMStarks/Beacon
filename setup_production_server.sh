#!/bin/bash

echo "🚀 Setting up Beacon Production Server on Port 80"
echo "================================================"

# Kill any existing processes
echo "🛑 Stopping existing processes..."
pkill -f "python.*web_interface" || true
pkill -f "ollama" || true
systemctl stop beacon-news || true

# Wait for processes to stop
sleep 3

# Start Ollama service
echo "🤖 Starting Ollama service..."
systemctl start ollama || true
sleep 3

# Check if Ollama is running
echo "🔍 Checking Ollama status..."
if curl -s http://127.0.0.1:11434/api/tags > /dev/null; then
    echo "✅ Ollama is running"
else
    echo "❌ Starting Ollama manually..."
    nohup ollama serve > /dev/null 2>&1 &
    sleep 5
fi

# Pre-warm the model
echo "🔥 Pre-warming Llama 3.1 8B model..."
ollama list | grep -q "llama3.1:8b" || {
    echo "📥 Pulling Llama 3.1 8B model..."
    ollama pull llama3.1:8b
}

# Create systemd service for Beacon
echo "⚙️ Creating systemd service..."
cat > /etc/systemd/system/beacon-news.service << 'EOF'
[Unit]
Description=Beacon AI News Desk
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/Beacon
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 web_interface.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Update web_interface.py to use port 80
echo "🔧 Configuring for port 80..."
cd /root/Beacon
sed -i 's/port=8000/port=80/' web_interface.py

# Enable and start the service
echo "🚀 Starting Beacon service..."
systemctl daemon-reload
systemctl enable beacon-news
systemctl start beacon-news

# Wait for startup
sleep 5

# Test the service
echo "🔍 Testing Beacon service..."
if curl -s http://localhost/api/sample-article > /dev/null; then
    echo "✅ Beacon is running at http://45.77.232.238/"
    echo "📊 Check status: systemctl status beacon-news"
    echo "📋 Check logs: journalctl -u beacon-news -f"
else
    echo "❌ Beacon failed to start"
    echo "📋 Check logs: journalctl -u beacon-news"
fi

echo "🎉 Beacon production setup complete!"


