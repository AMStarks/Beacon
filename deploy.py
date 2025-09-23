#!/usr/bin/env python3
"""
Deployment script for Beacon News Aggregation System
"""

import os
import sys
import subprocess
import time

def check_requirements():
    """Check if all requirements are met"""
    print("🔍 Checking requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Check if required files exist
    required_files = ['app.py', 'news_collector.py', 'topic_processor.py', 'topic_storage.py', 'requirements.txt']
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Required file {file} not found")
            return False
        print(f"✅ {file} found")
    
    return True

def install_dependencies():
    """Install Python dependencies"""
    print("📦 Installing dependencies...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def test_application():
    """Test the application"""
    print("🧪 Testing application...")
    try:
        # Set environment variables for testing
        os.environ['GROK_API_KEY'] = 'test-key'
        os.environ['LLM_TITLES'] = '1'
        os.environ['LLM_SUMMARIES'] = '1'
        
        # Test imports
        import app
        print("✅ Application imports successfully")
        
        # Test app creation
        from app import app as fastapi_app
        print("✅ FastAPI app created successfully")
        
        return True
    except Exception as e:
        print(f"❌ Application test failed: {e}")
        return False

def main():
    """Main deployment function"""
    print("🚀 Beacon News Aggregation System - Deployment")
    print("=" * 60)
    
    # Check requirements
    if not check_requirements():
        print("❌ Requirements check failed")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Dependency installation failed")
        sys.exit(1)
    
    # Test application
    if not test_application():
        print("❌ Application test failed")
        sys.exit(1)
    
    print("=" * 60)
    print("✅ Deployment preparation complete!")
    print("📋 Next steps:")
    print("1. Set environment variables (GROK_API_KEY, LLM_TITLES, LLM_SUMMARIES)")
    print("2. Start the application with: python app.py")
    print("3. Access the API at: http://localhost:8000")
    print("4. View the dashboard at: http://localhost:8000/")

if __name__ == "__main__":
    main()
