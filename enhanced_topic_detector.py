import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import Counter
# Optional imports for clustering; fall back gracefully if unavailable
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import AgglomerativeClustering
    _SKLEARN_AVAILABLE = True
except Exception:
    _SKLEARN_AVAILABLE = False

# Optional embedding-based clustering (preferred when available)
try:
    from sentence_transformers import SentenceTransformer
    import hdbscan  # type: ignore
    _EMB_AVAILABLE = True
except Exception:
    _EMB_AVAILABLE = False
import spacy
from entity_resolver import EntityResolver
import logging

logger = logging.getLogger(__name__)

@dataclass
class NewsArticle:
    title: str
    content: str
    url: str
    source: str
    published_at: datetime
    category: str = "general"
    country: str = "us"
    language: str = "en"

@dataclass
class TopicCluster:
    id: str
    title: str
    summary: str
    articles: List[NewsArticle]
    confidence_score: float
    last_updated: datetime
    status: str

class EnhancedTopicDetector:
    def __init__(self):
        # Common stop words to filter out
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his',
            'her', 'its', 'our', 'their', 'news', 'breaking', 'latest', 'update', 'report', 'story', 'article'
        }
        
        # Topic patterns for better title generation
        self.topic_patterns = {
            'sports': {
                'keywords': ['game', 'match', 'team', 'player', 'score', 'win', 'lose', 'championship', 'league'],
                'title_template': '{team1} vs {team2} - {event}'
            },
            'politics': {
                'keywords': ['president', 'election', 'vote', 'campaign', 'government', 'policy', 'bill', 'law'],
                'title_template': '{subject} - {action}'
            },
            'technology': {
                'keywords': ['tech', 'ai', 'software', 'app', 'company', 'launch', 'release', 'update'],
                'title_template': '{company} - {product/action}'
            },
            'business': {
                'keywords': ['company', 'market', 'stock', 'business', 'economy', 'financial', 'earnings'],
                'title_template': '{company} - {business_event}'
            },
            'world': {
                'keywords': ['country', 'international', 'global', 'world', 'nation', 'government'],
                'title_template': '{location} - {event}'
            }
        }

        # Lightweight spaCy model; if not available, fall back to simple regex
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except Exception:
            self.nlp = None
        self.entity_resolver = EntityResolver()

    def detect_topics(self, articles: List[NewsArticle]) -> List[TopicCluster]:
        """Enhanced topic detection using TF-IDF + Agglomerative clustering"""
        if not articles:
            return []
        
        # 1) Prefer embedding-based clustering if available
        clusters: Dict[int, List[NewsArticle]] = {}
        if _EMB_AVAILABLE and len(articles) >= 4:
            try:
                model = SentenceTransformer("all-MiniLM-L6-v2")
                texts = [f"{a.title}. {a.content}" for a in articles]
                emb = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
                clusterer = hdbscan.HDBSCAN(min_cluster_size=2, metric='euclidean')
                labels = clusterer.fit_predict(emb)
                for lbl, art in zip(labels, articles):
                    key = int(lbl) if lbl >= 0 else max(len(clusters), 10_000) + len(clusters)
                    clusters.setdefault(key, []).append(art)
            except Exception:
                clusters.clear()

        # 2) Fallback to TF-IDF + Agglomerative if available
        if not clusters and _SKLEARN_AVAILABLE and len(articles) >= 4:
            texts = [f"{a.title}. {a.content}" for a in articles]
            try:
                vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), stop_words='english')
                X = vectorizer.fit_transform(texts)
                n = max(1, min(len(articles) // 5, 15))
                clustering = AgglomerativeClustering(n_clusters=n, affinity='cosine', linkage='average')
                labels = clustering.fit_predict(X.toarray())
                for lbl, art in zip(labels, articles):
                    clusters.setdefault(int(lbl), []).append(art)
            except Exception:
                clusters.clear()
        
        if not clusters:
            # Fallback: simple Jaccard over key terms
            group_id = 0
            groups: List[Dict[str, Any]] = []
            for art in articles:
                terms = self.extract_key_terms(art.title, art.content)
                placed = False
                for g in groups:
                    sim = self.calculate_similarity(terms, g['terms'])
                    if sim >= 0.25:
                        g['items'].append(art)
                        g['terms'].update(terms)
                        placed = True
                        break
                if not placed:
                    groups.append({'id': group_id, 'items': [art], 'terms': set(terms)})
                    group_id += 1
            for g in groups:
                clusters[g['id']] = g['items']
        
        topics: List[TopicCluster] = []
        for lbl, group in clusters.items():
            key_terms = set()
            for art in group:
                key_terms.update(self.extract_key_terms(art.title, art.content))
            title = self.generate_topic_title(group, key_terms)
            summary = self.create_summary(group)
            confidence = self.calculate_confidence(group)
            topic_id = hashlib.md5((title + str(lbl)).encode()).hexdigest()[:8]
            topics.append(TopicCluster(
                id=topic_id,
                title=title,
                summary=summary,
                articles=group,
                confidence_score=confidence,
                last_updated=datetime.now(),
                status="active"
            ))
            logger.info(f"Created topic: {title}")
        return topics

    def extract_key_terms(self, title: str, content: str) -> set:
        """Extract meaningful key terms from title and content"""
        # Combine title and content
        text = f"{title} {content}".lower()
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Extract words (minimum 4 characters to avoid single letters)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text)
        
        # Filter out stop words and common words
        key_terms = set()
        for word in words:
            if (word not in self.stop_words and 
                len(word) > 3 and 
                word not in ['news', 'story', 'article', 'breaking', 'latest', 'update', 'report']):
                key_terms.add(word)
        
        return key_terms

    def calculate_similarity(self, terms1: set, terms2: set) -> float:
        """Calculate similarity between two sets of terms"""
        if not terms1 or not terms2:
            return 0.0
        
        intersection = len(terms1 & terms2)
        union = len(terms1 | terms2)
        
        return intersection / union if union > 0 else 0.0

    def generate_topic_title(self, articles: List[NewsArticle], key_terms: set) -> str:
        """Generate a meaningful topic title"""
        if not articles:
            return "Unknown Topic"
        
        # Try to identify topic category
        category = self.identify_topic_category(articles, key_terms)
        
        # Generate title based on category
        if category == 'sports':
            return self.generate_sports_title(articles, key_terms)
        elif category == 'politics':
            return self.generate_politics_title(articles, key_terms)
        elif category == 'technology':
            return self.generate_tech_title(articles, key_terms)
        elif category == 'business':
            return self.generate_business_title(articles, key_terms)
        else:
            return self.generate_general_title(articles, key_terms)

    def identify_topic_category(self, articles: List[NewsArticle], key_terms: set) -> str:
        """Identify the category of the topic"""
        category_scores = {}
        
        for category, data in self.topic_patterns.items():
            score = 0
            for keyword in data['keywords']:
                if keyword in key_terms:
                    score += 1
            category_scores[category] = score
        
        # Return category with highest score
        if category_scores:
            return max(category_scores, key=category_scores.get)
        return 'general'

    def extract_entities(self, text: str) -> List[str]:
        """Extract named entities when spaCy is available"""
        entities = self.entity_resolver.extract_entities(text)
        return self.entity_resolver.normalize_entities(entities)

    def generate_sports_title(self, articles: List[NewsArticle], key_terms: set) -> str:
        """Generate sports-specific title"""
        # Look for team names and scores in titles
        team_patterns = [
            r'(\w+)\s+(?:beat|defeated|won|lost)\s+(\w+)',
            r'(\w+)\s+vs\.?\s+(\w+)',
            r'(\w+)\s+(\d+)-(\d+)\s+(\w+)',
            r'(\w+)\s+(\d+)\s+(\w+)'
        ]
        
        for article in articles:
            content = f"{article.title} {article.content}"
            for pattern in team_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        # Make sure we have actual team names, not single letters
                        team1, team2 = groups[0], groups[1]
                        if len(team1) > 2 and len(team2) > 2:
                            return f"{team1} vs {team2}"
        
        # Look for common sports terms
        sports_terms = ['nfl', 'nba', 'mlb', 'nhl', 'soccer', 'football', 'basketball', 'baseball', 'hockey']
        for term in sports_terms:
            if term in key_terms:
                # Find related terms
                related_terms = [t for t in key_terms if t != term and len(t) > 3]
                if related_terms:
                    return f"{term.upper()} - {related_terms[0].title()}"
        
        # Fallback to meaningful key terms
        important_terms = [term for term in key_terms if len(term) > 4 and term.lower() not in ['beat', 'won', 'lost', 'game', 'match']]
        if important_terms:
            return ' '.join(important_terms[:2]).title()
        
        return "Sports News"

    def generate_politics_title(self, articles: List[NewsArticle], key_terms: set) -> str:
        """Generate politics-specific title"""
        # Look for political figures and events
        political_terms = ['trump', 'biden', 'president', 'election', 'vote', 'campaign']
        
        for term in political_terms:
            if term in key_terms:
                # Find related terms
                related_terms = [t for t in key_terms if t != term and len(t) > 4]
                if related_terms:
                    return f"{term.title()} - {related_terms[0].title()}"
        
        # Fallback
        important_terms = [term for term in key_terms if len(term) > 4]
        if important_terms:
            return ' '.join(important_terms[:2]).title()
        
        return "Political News"

    def generate_tech_title(self, articles: List[NewsArticle], key_terms: set) -> str:
        """Generate technology-specific title"""
        # Look for company names and products
        tech_companies = ['apple', 'google', 'microsoft', 'amazon', 'meta', 'tesla', 'openai']
        
        for company in tech_companies:
            if company in key_terms:
                # Find related terms
                related_terms = [t for t in key_terms if t != company and len(t) > 4]
                if related_terms:
                    return f"{company.title()} - {related_terms[0].title()}"
        
        # Fallback
        important_terms = [term for term in key_terms if len(term) > 4]
        if important_terms:
            return ' '.join(important_terms[:2]).title()
        
        return "Technology News"

    def generate_business_title(self, articles: List[NewsArticle], key_terms: set) -> str:
        """Generate business-specific title"""
        # Look for company names and business events
        business_terms = ['earnings', 'stock', 'market', 'company', 'business']
        
        for term in business_terms:
            if term in key_terms:
                # Find related terms
                related_terms = [t for t in key_terms if t != term and len(t) > 4]
                if related_terms:
                    return f"{term.title()} - {related_terms[0].title()}"
        
        # Fallback
        important_terms = [term for term in key_terms if len(term) > 4]
        if important_terms:
            return ' '.join(important_terms[:2]).title()
        
        return "Business News"

    def generate_general_title(self, articles: List[NewsArticle], key_terms: set) -> str:
        """Generate general topic title"""
        # Look for common patterns in article titles
        all_titles = [article.title for article in articles]
        
        # Find common meaningful words across titles
        common_words = set()
        for title in all_titles:
            # Extract proper nouns and important words
            words = re.findall(r'\b[A-Z][a-z]{2,}\b', title)
            common_words.update(words)
        
        # Filter out common words and get meaningful ones
        meaningful_words = []
        for word in common_words:
            if (len(word) > 3 and 
                word.lower() not in self.stop_words and 
                word not in ['News', 'Breaking', 'Latest', 'Update', 'Story', 'Article']):
                meaningful_words.append(word)
        
        if meaningful_words:
            # Take top 2-3 meaningful words, but avoid single letters
            filtered_words = [w for w in meaningful_words if len(w) > 3]
            if filtered_words:
                return ' '.join(filtered_words[:3])
        
        # Look for specific patterns in titles
        for title in all_titles:
            # Look for "X vs Y" patterns but filter out meaningless ones
            vs_match = re.search(r'(\w{3,})\s+vs\.?\s+(\w{3,})', title, re.IGNORECASE)
            if vs_match:
                team1, team2 = vs_match.groups()
                if len(team1) > 2 and len(team2) > 2:
                    return f"{team1} vs {team2}"
            
            # Look for "X - Y" patterns
            dash_match = re.search(r'(\w{3,})\s*-\s*(\w{3,})', title)
            if dash_match:
                part1, part2 = dash_match.groups()
                if len(part1) > 2 and len(part2) > 2:
                    return f"{part1} - {part2}"
        
        # Fallback to most important key terms (filter out single letters and common words)
        important_terms = [term for term in key_terms if len(term) > 4 and term.lower() not in ['beat', 'won', 'lost', 'game', 'match', 'news', 'story']]
        if important_terms:
            return ' '.join(important_terms[:2]).title()
        
        # Final fallback - use first meaningful words from first article title
        if articles:
            title = articles[0].title
            # Clean up the title and take first few meaningful words
            title = re.sub(r'[^\w\s]', ' ', title)
            words = [w for w in title.split() if len(w) > 3 and w.lower() not in self.stop_words][:4]
            if words:
                return ' '.join(words)
            else:
                # If no meaningful words, use first few words regardless
                words = [w for w in title.split() if len(w) > 1][:3]
                if words:
                    return ' '.join(words)
        
        return "News Update"

    def create_summary(self, articles: List[NewsArticle]) -> str:
        """Create a neutral summary from multiple articles"""
        if not articles:
            return "No information available."
        
        # Use the most recent article's content
        most_recent = max(articles, key=lambda x: x.published_at)
        content = most_recent.content or most_recent.title
        
        # Clean content
        content = re.sub(r'<[^>]+>', ' ', content)
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Extract first few sentences
        sentences = content.split('.')[:2]
        summary = '. '.join(sentences).strip()
        
        if not summary.endswith('.'):
            summary += '.'
        
        return summary

    def calculate_confidence(self, articles: List[NewsArticle]) -> float:
        """Calculate confidence score for topic"""
        base_confidence = 0.5
        
        # Increase confidence based on number of articles
        article_bonus = min(0.3, len(articles) * 0.05)
        
        # Increase confidence based on recency
        now = datetime.now()
        recency_bonus = 0.0
        for article in articles:
            age_hours = (now - article.published_at).total_seconds() / 3600
            if age_hours < 24:  # Recent articles
                recency_bonus += 0.1
        
        recency_bonus = min(0.2, recency_bonus)
        
        return min(0.95, base_confidence + article_bonus + recency_bonus)
