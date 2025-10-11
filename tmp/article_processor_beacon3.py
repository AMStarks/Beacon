#!/usr/bin/env python3
"""
Beacon 3 Article Processor - Main processing pipeline
"""

import asyncio
import re
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from .database import Beacon3Database
from .content_extractor import ContentExtractor
from .llm_service import LLMService
from .clustering_service import ClusteringService

logger = logging.getLogger(__name__)

def sanitize_title(raw: Optional[str]) -> str:
    """Remove markdown headers, HTML tags, boilerplate prefixes, and stray quotes/stars."""
    if not raw:
        return ""
    text = str(raw).strip()
    # Strip leading markdown hashes like '## '
    text = re.sub(r'^\s*#{1,6}\s*', '', text)
    # Strip simple HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove common prefaces like 'Title:'/'Headline:'
    text = re.sub(r'^(title|headline)\s*[:\-]\s*', '', text, flags=re.IGNORECASE)
    # Trim surrounding quotes or asterisks
    text = text.strip().strip('"\'\u201c\u201d\u2018\u2019').strip('*').strip()
    return text

class ArticleProcessor:
    """Main article processing pipeline for Beacon 3"""

    def __init__(self, db_path: str = "beacon3_articles.db"):
        logger.info(f"🚀 Initializing Beacon 3 Article Processor")
        
        self.db = Beacon3Database(db_path)
        self.content_extractor = ContentExtractor()
        self.llm_service = LLMService()
        self.clustering_service = ClusteringService(self.db)
        self.is_running = False
        
        logger.info(f"✅ Beacon 3 Article Processor initialized")

    async def submit_article(self, url: str, priority: int = 1) -> int:
        """Submit article for processing"""
        logger.info(f"📝 Submitting article: {url}")
        
        # Check if URL already exists
        existing_articles = self.db.get_recent_articles(1000)
        for article in existing_articles:
            if article['url'] == url:
                logger.info(f"⚠️ Article already exists: {url}")
                return article['article_id']

        # Add to database
        article_id = self.db.add_article(url)

        # Add to processing queue
        self.db.add_to_queue(article_id, priority)

        logger.info(f"✅ Submitted article {article_id}: {url}")
        return article_id

    async def process_next_article(self) -> bool:
        """Process the next article in queue"""
        logger.info(f"🔄 Processing next article")
        
        # Get next item from queue
        queue_item = self.db.get_queue_item()
        if not queue_item:
            logger.info(f"📭 No articles in queue")
            return False

        article_id = queue_item['article_id']
        url = queue_item['url']
        logger.info(f"🎯 Processing article {article_id}: {url}")

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
            logger.info(f"✅ Title generated: {generated_title[:50]}...")

            # Step 3: Generate excerpt
            logger.info(f"📝 Step 3: Generating excerpt for article {article_id}")
            excerpt = await self.llm_service.generate_excerpt(
                content_result['content'],
                content_result['title']
            )
            logger.info(f"✅ Excerpt generated: {excerpt[:50]}...")

            # Step 4: Update article in database
            logger.info(f"💾 Step 4: Updating database for article {article_id}")
            clean_title = sanitize_title(generated_title)
            if clean_title != generated_title:
                logger.debug(f"🧹 Title sanitized: '{generated_title[:60]}' -> '{clean_title[:60]}'")
            self.db.update_article_status(
                article_id,
                'completed',
                generated_title=clean_title,
                excerpt=excerpt,
                content=content_result['content'],
                source_domain=content_result.get('source_domain'),
                processed_at=datetime.now().isoformat()
            )
            logger.info(f"✅ Article {article_id} updated in database")

            # Step 5: Cluster article
            logger.info(f"🔗 Step 5: Processing clustering for article {article_id}")
            # Use richer base text for clustering to avoid asymmetry: title + excerpt + content preview
            content_preview = content_result['content'][:1500] if content_result.get('content') else ''
            combined_content = f"{generated_title} {excerpt} {content_preview}".strip()
            cluster_id = await self.clustering_service.cluster_article(article_id, combined_content)
            if cluster_id:
                logger.info(f"✅ Clustering completed for article {article_id} -> cluster {cluster_id}")
            else:
                logger.warning(f"⚠️ Clustering failed for article {article_id}")

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

            logger.info(f"🎉 Successfully processed article {article_id}")
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
        logger.info(f"🚀 Starting continuous article processor (max_articles: {max_articles})")
        
        self.is_running = True
        processed = 0

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
        logger.info("⏹️ Stopping processor...")
        self.is_running = False

    async def get_status(self) -> Dict[str, Any]:
        """Get processor status"""
        logger.debug(f"📊 Getting processor status")
        
        stats = self.db.get_stats()
        system_status = self.db.get_system_status()

        status = {
            'is_running': self.is_running,
            'stats': stats,
            'system_status': system_status,
            'uptime': 'Running' if self.is_running else 'Stopped'
        }
        
        logger.debug(f"📊 Processor status: {status}")
        return status

# Standalone functions for easy testing
async def test_article_processing():
    """Test the complete article processing pipeline"""
    logger.info(f"🧪 Testing Beacon 3 Article Processing")
    
    processor = ArticleProcessor()

    # Test URL
    test_url = "https://edition.cnn.com/2025/09/30/us/what-we-know-michigan-church-shooting"

    print("🧪 Testing Beacon 3 Article Processing")
    print("=" * 50)

    # Submit article
    article_id = await processor.submit_article(test_url)
    print(f"✅ Submitted: {test_url} -> Article ID: {article_id}")

    # Process article
    print("\n🔄 Processing article...")
    success = await processor.process_next_article()
    print(f"✅ Processed article: {'Success' if success else 'Failed'}")

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
    asyncio.run(test_article_processing())
