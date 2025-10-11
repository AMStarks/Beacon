#!/usr/bin/env python3
"""
Article Processor - Main processing pipeline that runs autonomously
"""

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from ..models.database import Beacon2Database
from ..services.content_extractor import ContentExtractor
from ..services.llm_service import LLMService
from ..services.clustering_service import ClusteringService

# Defensive logging init: ensure root logger has handlers if process entrypoint forgot
try:
    if not logging.getLogger().handlers:
        from ..logging_config import setup_logging
        setup_logging()
except Exception:
    # last-resort: do not crash on logging init failure
    pass

logger = logging.getLogger(__name__)

class ArticleProcessor:
    """Main article processing pipeline"""

    def __init__(self, db_path: str = "beacon2_articles.db"):
        self.db = Beacon2Database(db_path)
        self.content_extractor = ContentExtractor()
        self.llm_service = LLMService()
        self.clustering_service = ClusteringService(self.db)
        self.is_running = False

    async def submit_article(self, url: str, priority: int = 1) -> int:
        """Submit article for processing"""
        # Check if URL already exists
        existing_articles = self.db.get_recent_articles(1000)
        for article in existing_articles:
            if article['url'] == url:
                logger.info(f"Article already exists: {url}")
                return article['article_id']

        # Add to database
        article_id = self.db.add_article(url)

        # Add to processing queue
        self.db.add_to_queue(article_id, priority)

        logger.info(f"✅ Submitted article {article_id}: {url}")
        return article_id

    async def process_next_article(self) -> bool:
        """Process the next article in queue"""
        # Get next item from queue
        logger.debug(f"🔍 Looking for next article in queue")
        queue_item = self.db.get_queue_item()
        if not queue_item:
            logger.debug(f"📭 No articles in queue")
            return False

        article_id = queue_item['article_id']
        url = queue_item['url']
        logger.info(f"🎯 Found article {article_id} in queue: {url}")

        logger.info(f"🔄 Processing article {article_id}: {url}")

        try:
            # Step 1: Extract content
            logger.info(f"📄 Step 1: Extracting content for article {article_id}")
            content_result = await self.content_extractor.extract_content(url)
            if not content_result['success']:
                raise Exception(f"Content extraction failed: {content_result['error']}")
            logger.info(f"✅ Content extracted: {len(content_result['content'])} characters")

            # Step 2: Generate title
            logger.info(f"📝 Step 2: Generating title for article {article_id}")
            generated_title = await self.llm_service.generate_title(
                content_result['content'],
                content_result['title']
            )
            logger.info(f"✅ Title generated: {(generated_title or '')[:50]}...")

            # Step 3: Generate excerpt
            logger.info(f"📝 Step 3: Generating excerpt for article {article_id}")
            excerpt = await self.llm_service.generate_excerpt(
                content_result['content'],
                content_result['title']
            )
            logger.info(f"✅ Excerpt generated: {(excerpt or '')[:50]}...")

            # Step 4: Update article in database
            logger.info(f"💾 Step 4: Updating database for article {article_id}")
            self.db.update_article_status(
                article_id,
                'completed',
                generated_title=generated_title,
                excerpt=excerpt,
                content=content_result['content'],
                source_domain=content_result.get('source_domain'),
                processed_at=datetime.now().isoformat()
            )
            logger.info(f"✅ Article {article_id} updated in database")

            # Step 5: Cluster article
            logger.info(f"🔗 Step 5: Processing clustering for article {article_id}")
            # Use full content instead of just excerpt for better clustering
            combined_content = f"{generated_title} {article.get('content', excerpt)}"
            logger.info(f"📝 Clustering content length: {len(combined_content)} characters")
            try:
                cluster_id = await self.clustering_service.cluster_article(article_id, combined_content)
                logger.info(f"✅ Clustering completed for article {article_id} -> cluster {cluster_id}")
            except Exception as e:
                logger.error(f"❌ Clustering failed for article {article_id}: {e}")
                logger.error(f"🔍 Error type: {type(e).__name__}")
                logger.error(f"🔍 Traceback: {traceback.format_exc()}")
                # Don't re-raise - let processing continue

            # Step 6: Update system status
            logger.info(f"📊 Step 6: Updating system status for article {article_id}")
            self.db.update_system_status(
                last_processed_article=article_id,
                total_articles=self.db.get_stats()['total_articles']
            )
            logger.info(f"✅ System status updated for article {article_id}")

            # Mark queue item as completed
            logger.info(f"✅ Step 7: Completing queue item for article {article_id}")
            self.db.complete_queue_item(queue_item['queue_id'], success=True)
            logger.info(f"✅ Queue item completed for article {article_id}")

            logger.info(f"🎉 Successfully processed article {article_id} in {datetime.now().isoformat()}")
            return True

        except Exception as e:
            logger.error(f"💥 Critical error processing article {article_id}: {e}")
            logger.error(f"🔍 Error type: {type(e).__name__}")
            logger.error(f"🔍 Traceback: {traceback.format_exc()}")

            # Update article as failed
            logger.info(f"❌ Marking article {article_id} as failed")
            self.db.update_article_status(article_id, 'failed')

            # Mark queue item as failed
            logger.info(f"❌ Marking queue item as failed for article {article_id}")
            self.db.complete_queue_item(queue_item['queue_id'], success=False, error=str(e))

            logger.error(f"❌ Article {article_id} processing failed")
            return False

    async def run_continuous_processor(self, max_articles: int = 100):
        """Run continuous processing loop"""
        self.is_running = True
        processed = 0

        logger.info(f"🚀 Starting continuous article processor (max_articles: {max_articles})")

        try:
            while self.is_running and processed < max_articles:
                logger.debug(f"🔄 Processing loop iteration, processed so far: {processed}")
                if await self.process_next_article():
                    processed += 1
                    logger.info(f"📈 Articles processed: {processed}/{max_articles}")
                    # Small delay between articles
                    await asyncio.sleep(1)
                else:
                    # No articles in queue, wait a bit
                    logger.debug(f"⏳ No articles in queue, waiting 5 seconds")
                    await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("⏹️ Processor stopped by user")
        except Exception as e:
            logger.error(f"💥 Processor crashed: {e}")
            logger.error(f"🔍 Error type: {type(e).__name__}")
            logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        finally:
            self.is_running = False
            logger.info(f"🏁 Processor finished. Processed {processed} articles")

    def stop_processor(self):
        """Stop the continuous processor"""
        self.is_running = False
        logger.info("⏹️ Stopping processor...")

    async def get_status(self) -> Dict[str, Any]:
        """Get processor status"""
        stats = self.db.get_stats()
        system_status = self.db.get_system_status()

        return {
            'is_running': self.is_running,
            'stats': stats,
            'system_status': system_status,
            'uptime': 'Running' if self.is_running else 'Stopped'
        }

# Standalone functions for easy testing
async def test_article_processing():
    """Test the complete article processing pipeline"""
    processor = ArticleProcessor()

    # Test URLs
    test_urls = [
        "https://www.bbc.com/news/articles/cj4y159190go",
        "https://www.cnn.com/2024/09/29/climate/china-climate-emissions/index.html"
    ]

    print("🧪 Testing Beacon 2 Article Processing")
    print("=" * 50)

    # Submit articles
    for url in test_urls:
        article_id = await processor.submit_article(url)
        print(f"✅ Submitted: {url} -> Article ID: {article_id}")

    # Process articles
    print("\n🔄 Processing articles...")
    for i in range(len(test_urls)):
        success = await processor.process_next_article()
        print(f"✅ Processed article {i+1}: {'Success' if success else 'Failed'}")

    # Show results
    print("\n📊 Final Results:")
    status = await processor.get_status()
    print(f"Total Articles: {status['stats']['total_articles']}")
    print(f"Completed: {status['stats']['completed_articles']}")
    print(f"Clusters: {status['stats']['total_clusters']}")

    # Show recent articles
    recent = processor.db.get_recent_articles(5)
    print("\n📰 Recent Articles:")
    for article in recent:
        print(f"  • {article['generated_title']} (Cluster: {article.get('cluster_title', 'None')})")

if __name__ == "__main__":
    # Use centralized logging setup for consistency
    try:
        from logging_config import setup_logging
        setup_logging()
    except Exception:
        pass

    asyncio.run(test_article_processing())
