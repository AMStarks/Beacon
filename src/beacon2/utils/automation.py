#!/usr/bin/env python3
"""
Beacon 2 Automation - Autonomous operation with monitoring and error recovery
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Ensure logging is initialized if entrypoint forgot
try:
    if not logging.getLogger().handlers:
        from ..logging_config import setup_logging
        setup_logging()
except Exception:
    pass

from ..core.article_processor import ArticleProcessor
from ..models.database import Beacon2Database

logger = logging.getLogger(__name__)

class Beacon2Automation:
    """Autonomous operation with monitoring and error recovery"""

    def __init__(self):
        self.processor = ArticleProcessor()
        self.db = self.processor.db
        self.is_running = False
        self.processed_count = 0
        self.error_count = 0
        self.max_errors = 10
        self.check_interval = 60  # Check for new work every minute

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.is_running = False

    async def health_check(self) -> bool:
        """Perform health checks"""
        try:
            # Check database connectivity
            stats = self.db.get_stats()
            if stats is None:
                logger.error("❌ Database health check failed")
                return False

            # Check system status
            status = self.db.get_system_status()
            if not status:
                logger.error("❌ System status check failed")
                return False

            logger.debug("✅ Health check passed")
            return True

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

    async def maintenance_tasks(self):
        """Perform routine maintenance"""
        try:
            # Update system activity timestamp
            self.db.update_system_status(is_running=True)

            # Clean up old failed queue items (older than 24 hours)
            cutoff = datetime.now() - timedelta(hours=24)
            with self.db.db_path as conn:  # Use context manager if available
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM processing_queue
                    WHERE status = 'failed' AND created_at < ?
                ''', (cutoff.isoformat(),))
                conn.commit()

            logger.debug("✅ Maintenance tasks completed")

        except Exception as e:
            logger.error(f"❌ Maintenance tasks failed: {e}")

    async def run_autonomous_mode(self):
        """Run in autonomous mode - process articles continuously"""
        self.is_running = True
        logger.info("🚀 Beacon 2 starting in autonomous mode")

        try:
            while self.is_running:
                try:
                    # Health check
                    if not await self.health_check():
                        logger.error("❌ Health check failed, attempting recovery...")
                        await asyncio.sleep(30)  # Wait before retry
                        continue

                    # Check for articles to process
                    if await self.processor.process_next_article():
                        self.processed_count += 1
                        logger.info(f"✅ Processed article #{self.processed_count}")
                    else:
                        # No articles in queue, wait before checking again
                        await asyncio.sleep(self.check_interval)

                    # Run maintenance tasks every 10 cycles
                    if self.processed_count % 10 == 0:
                        await self.maintenance_tasks()

                    # Check error threshold
                    if self.error_count >= self.max_errors:
                        logger.error(f"❌ Too many errors ({self.error_count}), entering recovery mode")
                        await asyncio.sleep(300)  # Wait 5 minutes
                        self.error_count = 0

                except Exception as e:
                    self.error_count += 1
                    logger.error(f"❌ Processing error #{self.error_count}: {e}")
                    await asyncio.sleep(10)  # Brief pause before retry

        except KeyboardInterrupt:
            logger.info("⏹️ Received interrupt signal")
        except Exception as e:
            logger.error(f"❌ Critical error in autonomous mode: {e}")
        finally:
            self.is_running = False
            self.db.update_system_status(is_running=False)
            logger.info(f"🏁 Autonomous mode stopped. Processed: {self.processed_count}, Errors: {self.error_count}")

    async def seed_with_sample_articles(self):
        """Add some sample articles for testing"""
        sample_urls = [
            "https://www.bbc.com/news/articles/cj4y159190go",
            "https://www.cnn.com/2024/09/29/climate/china-climate-emissions/index.html",
            "https://www.theguardian.com/environment/2024/sep/29/china-climate-pledge-analysis",
        ]

        logger.info("🌱 Seeding with sample articles...")
        for url in sample_urls:
            try:
                article_id = await self.processor.submit_article(url)
                logger.info(f"✅ Added sample article: {article_id}")
            except Exception as e:
                logger.error(f"❌ Failed to add sample article {url}: {e}")

    async def get_detailed_status(self) -> dict:
        """Get detailed status for monitoring"""
        basic_status = await self.processor.get_status()
        stats = self.db.get_stats()

        return {
            **basic_status,
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'uptime': 'Running' if self.is_running else 'Stopped',
            'last_activity': datetime.now().isoformat(),
            'health_status': 'healthy' if await self.health_check() else 'unhealthy'
        }

async def main():
    """Main entry point"""
    # Ensure centralized logging setup
    try:
        from logging_config import setup_logging
        setup_logging()
    except Exception:
        pass

    # Create logs directory
    os.makedirs('logs', exist_ok=True)

    automation = Beacon2Automation()

    try:
        # Optional: Seed with sample articles for testing
        if len(sys.argv) > 1 and sys.argv[1] == '--seed':
            await automation.seed_with_sample_articles()
            return

        # Run autonomous mode
        await automation.run_autonomous_mode()

    except KeyboardInterrupt:
        logger.info("⏹️ Shutdown requested")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
