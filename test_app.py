#!/usr/bin/env python3
"""
Test script to verify Beacon application works
"""

import sys
import os

def test_imports():
    """Test if all required modules can be imported"""
    try:
        print("🧪 Testing imports...")
        
        # Test basic imports
        import fastapi
        print("✅ FastAPI imported")
        
        import httpx
        print("✅ httpx imported")
        
        import bs4
        print("✅ BeautifulSoup imported")
        
        # Test our modules
        from news_collector import NewsCollector
        print("✅ NewsCollector imported")
        
        from topic_processor import TopicProcessor
        print("✅ TopicProcessor imported")
        
        from topic_storage import TopicStorage
        print("✅ TopicStorage imported")
        
        print("✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_app_creation():
    """Test if the FastAPI app can be created"""
    try:
        print("🧪 Testing app creation...")
        
        # Set environment variables for testing
        os.environ['GROK_API_KEY'] = 'test-key'
        os.environ['LLM_TITLES'] = '1'
        os.environ['LLM_SUMMARIES'] = '1'
        
        from app import app
        print("✅ FastAPI app created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ App creation error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Beacon Application")
    print("=" * 50)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test app creation
    if not test_app_creation():
        success = False
    
    print("=" * 50)
    if success:
        print("✅ All tests passed! Application is ready for deployment.")
    else:
        print("❌ Some tests failed. Please fix the issues before deployment.")
        sys.exit(1)
