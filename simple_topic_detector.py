import re
import hashlib
from typing import List, Dict, Set
from collections import Counter
import spacy
from dataclasses import dataclass
from news_service import NewsArticle


@dataclass
class SimpleTopic:
    id: str
    title: str
    articles: List[NewsArticle]
    source_count: int


class SimpleTopicDetector:
    """Simplified topic detector focused on generating meaningful titles."""
    
    def __init__(self):
        # Load spaCy model for entity recognition
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Fallback if model not installed
            self.nlp = None
        
        # Common stop words and patterns to ignore
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'cannot', 'shall',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs',
            'copyright', 'all rights reserved', 'ap', 'reuters', 'associated press', 'cnn', 'bbc', 'fox news',
            'vs', 'versus', 'vs.', 'v.', 'v', 'against', 'beats', 'defeats', 'wins', 'loses'
        }
        
        # Patterns to clean up titles
        self.cleanup_patterns = [
            r'\b\d{4}\b',  # Remove years
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # Remove dates
            r'\b\d{1,2}:\d{2}\b',  # Remove times
            r'\b(am|pm)\b',  # Remove am/pm
            r'\b(est|pst|gmt|utc)\b',  # Remove time zones
            r'\b(breaking|urgent|exclusive|live|updated)\b',  # Remove news tags
            r'\b(ap|reuters|cnn|bbc|fox|nbc|abc|cbs)\b',  # Remove news sources
            r'\b(copyright|all rights reserved)\b.*',  # Remove copyright notices
            r'\b(click here|read more|continue reading)\b.*',  # Remove call-to-action text
        ]

    def detect_topics(self, articles: List[NewsArticle]) -> List[SimpleTopic]:
        """Detect topics and generate meaningful titles."""
        if not articles:
            return []
        
        # Group articles by similarity
        clusters = self._cluster_articles(articles)
        
        topics = []
        for cluster_articles in clusters:
            if len(cluster_articles) == 1:
                # Single article - use its title directly
                topic = self._create_single_article_topic(cluster_articles[0])
            else:
                # Multiple articles - generate a meaningful title
                topic = self._create_cluster_topic(cluster_articles)
            
            topics.append(topic)
        
        return topics

    def _cluster_articles(self, articles: List[NewsArticle]) -> List[List[NewsArticle]]:
        """Simple clustering based on title similarity."""
        clusters = []
        used_articles = set()
        
        for i, article in enumerate(articles):
            if i in used_articles:
                continue
                
            # Find similar articles
            similar_articles = [article]
            used_articles.add(i)
            
            for j, other_article in enumerate(articles[i+1:], i+1):
                if j in used_articles:
                    continue
                    
                if self._are_similar(article, other_article):
                    similar_articles.append(other_article)
                    used_articles.add(j)
            
            clusters.append(similar_articles)
        
        return clusters

    def _are_similar(self, article1: NewsArticle, article2: NewsArticle) -> bool:
        """Check if two articles are about the same topic."""
        # Extract key entities from titles
        entities1 = self._extract_entities(article1.title)
        entities2 = self._extract_entities(article2.title)
        
        # Check for entity overlap
        overlap = len(entities1.intersection(entities2))
        total_entities = len(entities1.union(entities2))
        
        if total_entities == 0:
            return False
        
        # Articles are similar if they share significant entities
        similarity = overlap / total_entities
        return similarity > 0.3

    def _extract_entities(self, text: str) -> Set[str]:
        """Extract meaningful entities from text."""
        if not self.nlp:
            # Fallback to simple word extraction
            words = re.findall(r'\b[A-Z][a-z]+\b', text)
            return {word.lower() for word in words if len(word) > 2}
        
        doc = self.nlp(text)
        entities = set()
        
        for ent in doc.ents:
            if ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT', 'WORK_OF_ART']:
                # Clean and normalize entity
                clean_entity = self._clean_entity(ent.text)
                if clean_entity and len(clean_entity) > 2:
                    entities.add(clean_entity.lower())
        
        return entities

    def _clean_entity(self, entity: str) -> str:
        """Clean up entity text."""
        # Remove common prefixes/suffixes
        entity = re.sub(r'\b(the|a|an)\b', '', entity, flags=re.IGNORECASE).strip()
        entity = re.sub(r'\b(inc|ltd|corp|llc|co)\b\.?$', '', entity, flags=re.IGNORECASE).strip()
        
        # Remove punctuation
        entity = re.sub(r'[^\w\s]', '', entity).strip()
        
        return entity

    def _create_single_article_topic(self, article: NewsArticle) -> SimpleTopic:
        """Create topic from single article."""
        title = self._clean_title(article.title)
        
        return SimpleTopic(
            id=hashlib.sha256(article.title.encode()).hexdigest()[:12],
            title=title,
            articles=[article],
            source_count=1
        )

    def _create_cluster_topic(self, articles: List[NewsArticle]) -> SimpleTopic:
        """Create topic from multiple articles."""
        # Find the most common pattern in titles
        title_patterns = self._analyze_title_patterns(articles)
        
        if title_patterns:
            # Use the most common pattern
            title = title_patterns[0]
        else:
            # Fallback to the first article's title
            title = self._clean_title(articles[0].title)
        
        return SimpleTopic(
            id=hashlib.sha256(title.encode()).hexdigest()[:12],
            title=title,
            articles=articles,
            source_count=len(articles)
        )

    def _analyze_title_patterns(self, articles: List[NewsArticle]) -> List[str]:
        """Analyze article titles to find common patterns."""
        titles = [self._clean_title(article.title) for article in articles]
        
        # Look for common entities across titles
        all_entities = []
        for title in titles:
            entities = self._extract_entities(title)
            all_entities.extend(entities)
        
        # Count entity frequency
        entity_counts = Counter(all_entities)
        common_entities = [entity for entity, count in entity_counts.most_common(3) if count > 1]
        
        if common_entities:
            # Create title from common entities
            return [" ".join(common_entities)]
        
        # Look for common words (excluding stop words)
        all_words = []
        for title in titles:
            words = [word.lower() for word in title.split() if word.lower() not in self.stop_words]
            all_words.extend(words)
        
        word_counts = Counter(all_words)
        common_words = [word for word, count in word_counts.most_common(3) if count > 1 and len(word) > 2]
        
        if common_words:
            return [" ".join(common_words)]
        
        # Fallback to the shortest, cleanest title
        clean_titles = [title for title in titles if len(title) > 10 and len(title) < 100]
        if clean_titles:
            return [min(clean_titles, key=len)]
        
        return []

    def _clean_title(self, title: str) -> str:
        """Clean up article title."""
        if not title:
            return "Untitled"
        
        # Remove HTML tags
        title = re.sub(r'<[^>]+>', '', title)
        
        # Apply cleanup patterns
        for pattern in self.cleanup_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Remove leading/trailing punctuation
        title = title.strip('.,!?;:"\'()[]{}')
        
        # Normalize title case and optimize length
        title = self._normalize_title_case(title)
        title = self._optimize_title_length(title)
        
        return title or "Untitled"

    def _normalize_title_case(self, title: str) -> str:
        """Convert to proper title case, fixing common issues."""
        if not title:
            return title
        
        # Fix common all-caps words that should be lowercase
        title = re.sub(r'\b(TO|AS|IN|OF|AT|BY|FOR|WITH|ON|THE|A|AN|AND|OR|BUT|IS|WILL|BE|ARE|WAS|WERE|HAS|HAVE|HAD|DO|DOES|DID|CAN|COULD|SHOULD|MAY|MIGHT|MUST|SHALL)\b', 
                       lambda m: m.group(1).lower(), title, flags=re.IGNORECASE)
        
        # Proper title case
        title = title.title()
        
        # Fix articles and prepositions (should be lowercase except at start)
        # Include two-letter words and prepositions that should be lowercase
        small_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 
            'is', 'be', 'am', 'do', 'go', 'up', 'us', 'we', 'me', 'my', 'it', 'if', 'so', 'no', 'he', 'hi',
            'will', 'are', 'was', 'were', 'has', 'have', 'had', 'does', 'did', 'can', 'could', 'should', 
            'may', 'might', 'must', 'shall', 'from', 'over', 'under', 'above', 'below', 'between', 'among',
            'through', 'during', 'before', 'after', 'since', 'until', 'upon', 'within', 'without', 'against'
        }
        
        # Common acronyms that should stay uppercase
        acronyms = {'un', 'us', 'uk', 'eu', 'nato', 'fbi', 'cia', 'nba', 'nfl', 'mlb', 'nhl', 'npr', 'bbc', 'cnn', 'fox', 'abc', 'cbs', 'nbc'}
        words = title.split()
        
        if words:
            words[0] = words[0].title()  # First word always capitalized
            
            for i in range(1, len(words)):
                word_lower = words[i].lower()
                if word_lower in small_words:
                    words[i] = words[i].lower()
                elif word_lower in acronyms:
                    words[i] = words[i].upper()
        
        return ' '.join(words)

    def _optimize_title_length(self, title: str) -> str:
        """Make titles more concise while preserving meaning."""
        if not title:
            return title
        
        # Remove redundant phrases
        redundant_patterns = [
            r'\b(breaking|urgent|exclusive|live|updated)\b',
            r'\b(catch up on|get the|what to know|how to)\b',
            r'\b(here\'s what|here is what)\b',
            r'\b(the day\'s stories|today\'s news)\b',
            r':\s*(catch up|get the|what to know)',
            r'\|\s*$',  # Remove trailing pipe
        ]
        
        for pattern in redundant_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # Clean up extra punctuation and spacing
        title = re.sub(r'\s*:\s*$', '', title)  # Remove trailing colon
        title = re.sub(r'\s*\|\s*$', '', title)  # Remove trailing pipe
        title = re.sub(r'\s+', ' ', title).strip()  # Normalize whitespace
        
        # Truncate if too long (but try to break at word boundary)
        if len(title) > 60:  # Reduced from 80 to 60 for better LLM processing
            truncated = title[:57]
            # Find last space to avoid cutting words
            last_space = truncated.rfind(' ')
            if last_space > 40:  # Only if we don't lose too much
                truncated = truncated[:last_space]
            # Only add ellipses if we actually truncated
            if len(truncated) < len(title):
                title = truncated + "..."
            else:
                title = truncated
        
        return title.strip()
