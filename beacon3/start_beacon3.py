#!/usr/bin/env python3
"""
Beacon 3 Startup Script
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Initialize logging configuration
try:
    from logging_config import setup_logging
    setup_logging()
    print("✅ Beacon 3 logging initialized")
except Exception as e:
    print(f"⚠️ Logging initialization failed: {e}")

def print_banner():
    print("🚀 Beacon 3 - AI News Desk")
    print("=" * 40)
    print("✅ Reliable Content Extraction (trafilatura)")
    print("✅ LLM Enhancement (Gemma + Llama)")
    print("✅ TF-IDF Clustering (no LLM dependency)")
    print("✅ Production-Ready Architecture")
    print("=" * 40)

def print_menu():
    print("\nChoose startup mode:")
    print("1. Test Mode - Process sample articles")
    print("2. Web Interface - Start web server")
    print("3. Autonomous Mode - Continuous processing")
    print("4. Interactive Mode - Manual control")
    print("5. Exit")

async def run_test_mode():
    """Run test mode with sample articles"""
    print("\n🧪 Running Test Mode...")

    from src.article_processor import test_article_processing
    await test_article_processing()

def run_web_interface():
    """Start the web interface"""
    print("\n🌐 Starting Web Interface...")

    from src.web_interface import app
    app.run(host='0.0.0.0', port=5005, debug=False)

async def run_autonomous_mode():
    """Run autonomous processing"""
    print("\n🤖 Starting Autonomous Mode...")

    from src.article_processor import ArticleProcessor
    processor = ArticleProcessor()
    await processor.run_continuous_processor(max_articles=100)

async def run_interactive_mode():
    """Interactive mode for testing"""
    print("\n🎮 Interactive Mode")
    print("Commands: submit <url>, status, quit")

    from src.article_processor import ArticleProcessor

    processor = ArticleProcessor()

    while True:
        try:
            command = input("> ").strip()

            if command == "quit":
                break
            elif command == "status":
                status = await processor.get_status()
                print(f"Status: {status}")
            elif command.startswith("submit "):
                url = command[7:].strip()
                if url:
                    article_id = await processor.submit_article(url)
                    print(f"Submitted: {article_id}")
                else:
                    print("Please provide a URL")
            elif command == "process":
                success = await processor.process_next_article()
                print(f"Processed: {'Success' if success else 'No articles in queue'}")
            else:
                print("Commands: submit <url>, status, process, quit")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

async def main():
    """Main startup menu"""
    print_banner()

    while True:
        print_menu()
        choice = input("Enter choice (1-5): ").strip()

        if choice == "1":
            await run_test_mode()
        elif choice == "2":
            run_web_interface()
        elif choice == "3":
            await run_autonomous_mode()
        elif choice == "4":
            await run_interactive_mode()
        elif choice == "5":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    asyncio.run(main())
