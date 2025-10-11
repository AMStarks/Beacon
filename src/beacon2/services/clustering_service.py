#!/usr/bin/env python3
"""
Clustering Service - Simple content-based similarity clustering
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple
from collections import Counter
from ..models.database import Beacon2Database

logger = logging.getLogger(__name__)

class ClusteringService:
    """Simple, reliable content-based clustering"""

    def __init__(self, db: Beacon2Database):
        self.db = db

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple content similarity"""
        if not text1 or not text2:
            return 0.0

        # Normalize texts
        text1 = self._normalize_text(text1)
        text2 = self._normalize_text(text2)

        # Get word sets
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        if union == 0:
            return 0.0

        similarity = intersection / union

        # Boost for high similarity
        if similarity >= 0.8:
            return 1.0
        elif similarity >= 0.6:
            return 0.9
        elif similarity >= 0.3:
            return 0.7
        else:
            return similarity

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text

    def _clean_title_for_comparison(self, title: str) -> str:
        """Clean title for similarity comparison"""
        if not title:
            return ""

        # Remove LLM prefixes and artifacts
        title = title.replace("Sure, here is the headline:", "")
        title = title.replace("**", "")
        title = title.strip()

        # Remove common stopwords and normalize
        words = title.lower().split()
        meaningful_words = [w for w in words if len(w) > 3]  # Keep only meaningful words

        return " ".join(meaningful_words)

    def _clean_excerpt_for_comparison(self, excerpt: str) -> str:
        """Clean excerpt for similarity comparison"""
        if not excerpt:
            return ""

        # Remove metadata and clean
        lines = excerpt.split('\n')
        clean_lines = [line.strip() for line in lines if len(line.strip()) > 20 and not line.startswith(('EXPLAINER', 'News|', 'Author', 'View image'))]

        text = " ".join(clean_lines[:3])  # Take first 3 meaningful lines

        # Remove common stopwords and normalize
        words = text.lower().split()
        meaningful_words = [w for w in words if len(w) > 3 and w not in ['illustration', 'image', 'fullscreen']]

        return " ".join(meaningful_words)

    async def find_similar_articles(self, article_id: int, content: str, threshold: float = 0.10) -> List[Tuple[int, float]]:
        """Find similar articles based on content"""
        logger.info(f"🔍 Starting similarity search for article {article_id}")

        # Get recent articles (including currently processing) for clustering
        logger.debug(f"📋 Getting recent articles for article {article_id} (including processing)")
        recent_articles = self.db.get_recent_articles(100, include_processing=True)
        logger.info(f"📋 Found {len(recent_articles)} recent articles (including processing)")

        similar = []
        skipped_articles = []

        for i, article in enumerate(recent_articles):
            logger.debug(f"🔎 Checking article {article['article_id']} ({i+1}/{len(recent_articles)})")

            if article['article_id'] == article_id:
                logger.debug(f"⏭️ Skipping self (article {article_id})")
                skipped_articles.append(f"self-{article_id}")
                continue  # Skip self

            # Use cleaned title + full excerpt + content for comparison (enhanced)
            logger.debug(f"🧹 Processing content for article {article['article_id']}")
            existing_title = self._clean_title_for_comparison(article.get('generated_title', ''))
            existing_excerpt = self._clean_excerpt_for_comparison(article.get('excerpt', ''))
            existing_content_full = article.get('content', '')[:1500]  # Use up to 1500 chars of full content
            existing_content = f"{existing_title} {existing_excerpt} {existing_content_full}"

            logger.debug(f"📝 Article {article['article_id']} processed content length: {len(existing_content)} chars")

            if not existing_content.strip():
                logger.debug(f"⚠️ Article {article['article_id']} has no processable content")
                skipped_articles.append(f"empty-{article['article_id']}")
                continue

            logger.debug(f"⚖️ Calculating similarity between article {article_id} and {article['article_id']}")
            similarity = self.calculate_similarity(content, existing_content)
            logger.debug(f"📊 Similarity result: {similarity:.4f} (threshold: {threshold})")

            if similarity >= threshold:
                similar.append((article['article_id'], similarity))
                logger.info(f"✅ Found similar article {article['article_id']} with similarity {similarity:.4f}")
                logger.info(f"   Title: {(article.get('generated_title', '') or '')[:60]}...")
            else:
                logger.debug(f"❌ Article {article['article_id']} below threshold (sim: {similarity:.4f})")

        # Sort by similarity (highest first)
        similar.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"🏁 Similarity search complete for article {article_id}")
        logger.info(f"   Total similar articles found: {len(similar)}")
        logger.info(f"   Articles skipped: {len(skipped_articles)} ({', '.join(skipped_articles[:5])})")
        logger.info(f"   Top similar: {[(aid, f'{sim:.3f}') for aid, sim in similar[:3]]}")

        return similar[:10]  # Limit to top 10

    async def cluster_article(self, article_id: int, content: str) -> Optional[int]:
        """Add article to appropriate cluster or create new one"""
        logger.info(f"🎯 Starting clustering process for article {article_id}")

        try:
            # Enhance content for better similarity detection
            enhanced_content = content
            logger.debug(f"📝 Getting article {article_id} from database")
            article = self.db.get_article(article_id)

            if article and article.get('content'):
                article_content = article.get('content', '')[:1500]  # Use up to 1500 chars
                enhanced_content = f"{content} {article_content}"
                logger.debug(f"✨ Enhanced content length: {len(enhanced_content)} characters")

            logger.info(f"🔍 Clustering article {article_id} with enhanced content ({len(enhanced_content)} words)")

            # Find similar articles
            logger.info(f"🔎 Calling find_similar_articles for article {article_id}")
            similar = await self.find_similar_articles(article_id, enhanced_content)

            logger.info(f"📊 Similar articles result: {len(similar)} found")

            if not similar:
                logger.info(f"🚫 No similar articles found for article {article_id}, creating new cluster")
                # No similar articles, create new cluster
                return await self._create_new_cluster(article_id, content)

            logger.info(f"✅ Found {len(similar)} similar articles for article {article_id}")
            logger.info(f"🔝 Top similar articles: {[(aid, f'{sim:.3f}') for aid, sim in similar[:3]]}")

            # Check if any similar articles are already in clusters
            cluster_found = False
            for i, (similar_id, similarity) in enumerate(similar):
                logger.info(f"🔍 Checking similar article {similar_id} (#{i+1}/{len(similar)}, similarity: {similarity:.3f})")

                logger.debug(f"📋 Getting clusters for article {similar_id}")
                clusters = self.db.get_article_clusters(similar_id)
                logger.debug(f"📋 Article {similar_id} is in {len(clusters)} clusters")

                if clusters:
                    # Add to existing cluster
                    cluster_id = clusters[0]['cluster_id']  # Use first cluster
                    cluster_title = clusters[0]['title']
                    logger.info(f"🎉 Found existing cluster {cluster_id}: '{cluster_title}' for similar article {similar_id}")
                    logger.info(f"➕ Adding article {article_id} to existing cluster {cluster_id}")

                    try:
                        logger.debug(f"💾 Calling add_to_cluster({article_id}, {cluster_id}, {similarity})")
                        self.db.add_to_cluster(article_id, cluster_id, similarity)
                        logger.info(f"✅ Successfully added article {article_id} to cluster {cluster_id} ('{cluster_title}')")
                        cluster_found = True

                        # Verify the addition worked
                        verify_clusters = self.db.get_article_clusters(article_id)
                        logger.info(f"🔍 Verification: Article {article_id} now in {len(verify_clusters)} clusters")
                        for cluster in verify_clusters:
                            logger.info(f"   Cluster {cluster['cluster_id']}: {cluster['title']} (sim: {cluster['similarity_score']:.3f})")

                        return cluster_id

                    except Exception as e:
                        logger.error(f"❌ Failed to add article {article_id} to cluster {cluster_id}: {e}")
                        logger.error(f"🔍 Error type: {type(e).__name__}")
                        import traceback
                        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
                        # Continue to next similar article instead of failing
                        continue
                else:
                    logger.debug(f"📭 Article {similar_id} is not in any clusters yet")

            # No existing clusters found among similar articles, create new one
            if not cluster_found:
                logger.info(f"🏗️ No existing clusters found for similar articles, creating new cluster for article {article_id}")
                logger.info(f"📋 Similar articles to include: {len(similar)}")
                return await self._create_new_cluster(article_id, content, similar[:3])  # Include top 3 similar

        except Exception as e:
            logger.error(f"💥 Critical error in cluster_article for article {article_id}: {e}")
            logger.error(f"🔍 Error type: {type(e).__name__}")
            import traceback
            logger.error(f"🔍 Full traceback: {traceback.format_exc()}")

            # As a fallback, try to create a new cluster
            try:
                logger.info(f"🛟 Attempting fallback cluster creation for article {article_id}")
                return await self._create_new_cluster(article_id, content)
            except Exception as fallback_error:
                logger.error(f"💥 Fallback cluster creation also failed: {fallback_error}")
                logger.error(f"🔍 Fallback error type: {type(fallback_error).__name__}")
                return None

    async def _create_new_cluster(self, article_id: int, content: str, similar_articles: List[Tuple[int, float]] = None) -> Optional[int]:
        """Create a new cluster"""
        # Generate cluster title from content
        cluster_title = self._generate_cluster_title(content)

        # Generate LLM-powered cluster summary
        cluster_summary = await self._generate_llm_cluster_summary(article_id, content, similar_articles)

        # Create cluster
        cluster_id = self.db.create_cluster(cluster_title, cluster_summary)

        if not cluster_id:
            return None

        # Add main article to cluster
        self.db.add_to_cluster(article_id, cluster_id, 1.0)

        # Add similar articles if provided
        if similar_articles:
            for similar_id, similarity in similar_articles:
                self.db.add_to_cluster(similar_id, cluster_id, similarity)

        logger.info(f"Created new cluster {cluster_id} for article {article_id}")
        return cluster_id

    async def _generate_llm_cluster_summary(self, article_id: int, content: str, similar_articles: List[Tuple[int, float]] = None) -> str:
        """Generate LLM-powered cluster summary using all articles in the cluster"""
        try:
            # Collect all articles in the cluster (main article + similar ones)
            all_article_ids = [article_id]
            if similar_articles:
                all_article_ids.extend([sid for sid, _ in similar_articles])

            # Get all articles from database
            articles_data = []
            logger.info(f"🔍 Collecting {len(all_article_ids)} articles for LLM summary generation")
            for aid in all_article_ids:
                logger.debug(f"📋 Fetching article {aid} from database")
                article = self.db.get_article(aid)
                if article:
                    logger.debug(f"✅ Found article {aid}: title='{article.get('generated_title', '')[:50]}...', excerpt_length={len(article.get('excerpt', ''))}")
                    articles_data.append({
                        'title': article.get('generated_title', ''),
                        'excerpt': article.get('excerpt', ''),
                        'url': article.get('url', '')
                    })
                else:
                    logger.warning(f"⚠️ Article {aid} not found in database")

            logger.info(f"📊 Collected {len(articles_data)} articles for summary generation")

            if not articles_data:
                logger.error(f"❌ No articles found for LLM summary generation")
                # Don't fall back to old method - use enhanced summary with available content
                logger.info("🔄 Using enhanced summary generation with main article content")
                return self._generate_cluster_summary(content)  # This is now the enhanced method

            # Extract key themes and topics from articles for cluster summary
            # Focus on common themes rather than combining article content
            themes = []
            entities = []
            locations = []
            key_events = []

            for article in articles_data[:3]:  # Limit to 3 articles to avoid token limits
                # Extract key topics from titles
                title_words = article['title'].lower().split()
                themes.extend([word for word in title_words if len(word) > 4 and word not in ['update', 'report', 'breaking']])  # Longer words likely to be key terms, exclude common news words

                # Extract entities and key facts from content
                content_text = article.get('content', article.get('excerpt', ''))
                if content_text:
                    excerpt_words = content_text.split()
                    # Look for potential entities (proper nouns, locations, organizations)
                    for word in excerpt_words:
                        if word.istitle() and len(word) > 3 and word.lower() not in ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'had', 'has', 'have', 'this', 'will', 'with', 'they', 'from']:
                            if any(char.isdigit() for char in word):  # Skip words with numbers (likely dates)
                                continue
                            if word.lower() in ['michigan', 'church', 'police', 'shooting', 'killed', 'attacker']:
                                entities.append(word)
                            elif word.lower() in ['sunday', 'monday', 'tuesday', 'yesterday', 'today']:
                                continue  # Skip time references
                            else:
                                entities.append(word)

            # Get unique themes and entities
            unique_themes = list(set(themes))[:8]  # Top 8 themes
            unique_entities = list(set(entities))[:12]  # Top 12 entities

            theme_text = ", ".join(unique_themes) if unique_themes else "current events"
            entity_text = ", ".join(unique_entities) if unique_entities else ""

            # Generate LLM summary focused on the topic
            try:
                from ..services.llm_service import LLMService
            except ImportError:
                from beacon2.services.llm_service import LLMService
            llm_service = LLMService()

            prompt = f"""Create a comprehensive, neutral summary of this news topic cluster.

Topic elements: {theme_text}
Key entities: {entity_text}

Requirements:
- Write a 80-120 word cohesive summary of the entire topic
- Focus on the main event and its core facts
- Include key details, context, and significance
- Be completely neutral and factual
- Structure as one unified topic summary
- Do NOT copy the input text verbatim
- Do NOT include metadata like dates, times, or source names
- Exclude phrases like "Article 1", "Topic:", "In short:", or similar

Return only the summary text:"""

            # Try LLM first, but fallback to intelligent combination if LLM fails
            try:
                # Use the title as original_title for better context
                article_title = articles_data[0].get('title', '') if articles_data else ''
                logger.debug(f"🎭 Calling LLM for cluster summary with title: '{article_title}'")

                # Use a more targeted approach - generate summary from combined article data
                combined_content = "\n".join([
                    f"Title: {article['title']}\nContent: {article.get('content', article.get('excerpt', ''))[:800]}"
                    for article in articles_data[:2]  # Limit to 2 articles
                ])

                logger.debug(f"📝 Combined content length for LLM: {len(combined_content)} chars")

                summary = await llm_service.generate_excerpt(combined_content, "Cluster Summary")
                if summary and len(summary.strip()) > 50:  # Require longer, more substantial summary
                    # More intelligent validation: check if LLM actually generated new content
                    # rather than just echoing the input
                    content_words = set(combined_content.lower().split()[:15])  # First 15 words of input
                    summary_words = set(summary.lower().split()[:15])  # First 15 words of output
                    overlap_ratio = len(content_words & summary_words) / len(content_words) if content_words else 0

                    # Accept if there's reasonable difference (less than 90% overlap) and sufficient length
                    if overlap_ratio < 0.9 and len(summary.split()) > 40:  # Require 40+ words for enhanced summary
                        logger.info(f"✅ Generated enhanced LLM cluster summary ({len(summary.split())} words): {summary[:80]}...")
                        return summary.strip()

                logger.info(f"⚠️ LLM generated insufficient content ({len(summary.split()) if summary else 0} words), using enhanced fallback")
            except Exception as e:
                logger.warning(f"❌ LLM summary generation failed: {e}")
                logger.warning(f"🔍 Error type: {type(e).__name__}")

            # Enhanced fallback: Use our improved summary generation
            logger.info("🔄 Using enhanced fallback for cluster summary")
            # Try to use the enhanced summary method if we have article data
            if articles_data and len(articles_data) > 0:
                logger.info(f"📊 Using {len(articles_data)} articles for enhanced summary generation")
                # Generate enhanced summary from multiple articles - use full content instead of excerpt
                combined_titles = " | ".join([article['title'] for article in articles_data[:3]])
                # Use full content instead of excerpt for better summary generation
                combined_content = " ".join([article.get('content', article.get('excerpt', '')) for article in articles_data[:3]])
                summary = self._generate_cluster_summary(combined_content or content)
            else:
                logger.warning("⚠️ No article data available for enhanced summary, using basic content")
                summary = self._generate_cluster_summary(content)

        except Exception as e:
            logger.warning(f"LLM cluster summary generation failed: {e}")

        # Fallback to old method
        return self._generate_cluster_summary(content)

    def _generate_cluster_title(self, content: str) -> str:
        """Generate cluster title from content"""
        # Look for high-priority keywords in the content for better titles
        content_lower = content.lower()

        # High-priority title keywords
        title_keywords = {
            'shooting': ['shooting', 'shot', 'killed', 'fatally'],
            'attack': ['attack', 'attacker', 'assault'],
            'incident': ['incident', 'crash', 'explosion'],
            'death': ['death', 'dies', 'fatality'],
            'arrest': ['arrest', 'suspect', 'police'],
            'disaster': ['disaster', 'emergency', 'crisis']
        }

        # Find the most relevant keyword category
        best_category = None
        best_count = 0

        for category, keywords in title_keywords.items():
            count = sum(1 for keyword in keywords if keyword in content_lower)
            if count > best_count:
                best_count = count
                best_category = category

        if best_category:
            # Look for location or specific terms - check both the best category and high-priority keywords
            sentences = re.split(r'[.!?]+', content)
            all_title_keywords = set()
            for keywords in title_keywords.values():
                all_title_keywords.update(keywords)
            # Also include high-priority summary keywords
            all_title_keywords.update(['killed', 'dead', 'injured', 'wounded', 'fatally', 'critical', 'victims'])

            for sentence in sentences[:15]:  # Check more sentences
                sentence_lower = sentence.lower()
                if any(word in sentence_lower for word in all_title_keywords):
                    # Extract key capitalized words from this sentence
                    words = re.findall(r'\b[A-Z][a-z]+\b', sentence)
                    if len(words) >= 2:
                        # Use the two most relevant capitalized words
                        key_words = words[:2]
                        return f"{' '.join(key_words)} {best_category.title()}"

        # Fallback to original logic if no good keywords found
        words = re.findall(r'\b[A-Z][a-z]+\b', content)
        if len(words) >= 3:
            key_words = words[:3]
            return f"{' '.join(key_words)} Update"
        elif len(words) >= 1:
            return f"{words[0]} News"

        return "News Update"

    def _generate_cluster_summary(self, content: str) -> str:
        """Generate comprehensive cluster summary (50-100 words) focused on key facts"""
        # Extract key information for a detailed topic-focused summary
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

        if not sentences:
            return content[:300] + '...' if len(content) > 300 else content

        # Look for sentences with key information (casualties, events, locations, actions)
        # Prioritize high-value sentences first
        priority_sentences = []
        regular_sentences = []

        for sentence in sentences[:20]:  # Check more sentences for comprehensive summary
            sentence_lower = sentence.lower()
            # High-priority keywords (casualties, main events)
            high_priority = ['killed', 'dead', 'injured', 'wounded', 'fatally', 'critical', 'victims']
            # Regular priority keywords
            regular_priority = ['shooting', 'attack', 'incident', 'people', 'police', 'authorities', 'suspect', 'shooter', 'church', 'mormon', 'michigan', 'marine', 'veteran', 'responded', 'investigation', 'shot', 'building', 'service', 'congregation', 'worship']

            if any(word in sentence_lower for word in high_priority):
                priority_sentences.append(sentence)
            elif any(word in sentence_lower for word in regular_priority):
                regular_sentences.append(sentence)
            elif any(char.isdigit() for char in sentence):  # Sentences with numbers
                priority_sentences.append(sentence)  # Treat numbers as high priority

        # Combine with priority sentences first
        key_sentences = priority_sentences + regular_sentences

        # Build a comprehensive summary (50-100 words)
        summary_parts = []
        current_words = 0
        target_min = 50
        target_max = 100

        for sentence in key_sentences[:8]:  # Use up to 8 key sentences for longer summary
            sentence_words = len(sentence.split())
            if current_words + sentence_words <= target_max:
                summary_parts.append(sentence)
                current_words += sentence_words

        if summary_parts:
            combined = ' '.join(summary_parts)
            # Ensure we're in the 50-100 word range
            word_count = len(combined.split())
            if word_count < target_min:
                # Add more sentences if we're too short
                remaining_sentences = [s for s in sentences if s not in summary_parts][:3]
                for sentence in remaining_sentences:
                    sentence_words = len(sentence.split())
                    if current_words + sentence_words <= target_max:
                        summary_parts.append(sentence)
                        current_words += sentence_words

            combined = ' '.join(summary_parts)
            final_word_count = len(combined.split())

            # Trim if too long
            if final_word_count > target_max:
                words = combined.split()[:target_max]
                combined = ' '.join(words)
            elif final_word_count < target_min:
                # If still too short, add introductory context
                if sentences and sentences[0] not in summary_parts:
                    intro = sentences[0] + ' '
                    if len(intro.split()) + final_word_count <= target_max:
                        combined = intro + combined

            return combined

        # Enhanced fallback: Use first few meaningful sentences to reach word target
        fallback_parts = []
        fallback_words = 0
        for sentence in sentences:
            if len(sentence) > 20 and not sentence.startswith(('In', 'The', 'A', 'An', 'According', 'Following', 'However', 'Meanwhile')):
                sentence_words = len(sentence.split())
                if fallback_words + sentence_words <= target_max:
                    fallback_parts.append(sentence)
                    fallback_words += sentence_words

        if fallback_parts:
            combined = ' '.join(fallback_parts)
            word_count = len(combined.split())
            if word_count < target_min:
                # If still too short, add the first sentence anyway
                if sentences and sentences[0] not in fallback_parts:
                    combined = sentences[0] + ' ' + combined
            return combined[:600]  # Allow longer fallback

        # Final fallback - use first meaningful content
        first_sentence = sentences[0] if sentences else content
        return first_sentence[:400]  # Allow longer final fallback
