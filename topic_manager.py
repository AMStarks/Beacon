import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class TopicMetrics:
    view_count: int = 0
    source_count: int = 0
    last_viewed: Optional[datetime] = None
    activity_score: float = 0.0
    last_updated_at: Optional[datetime] = None

class TopicManager:
    def __init__(self):
        self.topics_db = {}
        self.topic_metrics = {}
        self.search_history = {}
    
    def improve_topic_title(self, title: str, content: str = "") -> str:
        """Improve topic title to be more concise and descriptive"""
        # Remove common filler words
        filler_words = ['fact', 'news', 'latest', 'breaking', 'update', 'report']
        
        # Clean the title
        clean_title = title.strip()
        
        # Extract key information from content if available
        if content:
            # Look for specific details like scores, names, locations
            score_match = re.search(r'(\d+)-(\d+)', content)
            if score_match and 'beat' in clean_title.lower():
                team1 = clean_title.split()[0]
                team2 = self.extract_opponent_from_content(content)
                if team2:
                    return f"{team1} beat {team2} {score_match.group(1)}-{score_match.group(2)}"
            
            # Look for names in content
            name_match = re.search(r'([A-Z][a-z]+ [A-Z][a-z]+)', content)
            if name_match and 'kirk' in clean_title.lower():
                return f"Charlie Kirk Memorial Service Updates"
        
        # Remove filler words
        words = clean_title.split()
        filtered_words = [word for word in words if word.lower() not in filler_words]
        
        # Capitalize properly
        if filtered_words:
            result = ' '.join(filtered_words)
            # Ensure proper capitalization
            result = ' '.join(word.capitalize() if len(word) > 2 else word.upper() 
                            for word in result.split())
            return result
        
        return clean_title
    
    def extract_opponent_from_content(self, content: str) -> Optional[str]:
        """Extract opponent team name from content"""
        # Common team name patterns
        team_patterns = [
            r'vs\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'defeated\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'beat\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        for pattern in team_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def create_topic_id(self, title: str, content: str = "") -> str:
        """Create a unique topic ID based on content"""
        # Use content if available, otherwise title
        text = content if content else title
        
        # Extract key terms
        key_terms = re.findall(r'\b[A-Z][a-z]+\b', text)
        key_terms = [term for term in key_terms if len(term) > 3][:5]
        
        # Create hash from key terms
        key_text = ' '.join(key_terms).lower()
        return hashlib.md5(key_text.encode()).hexdigest()[:8]
    
    def _looks_like_llm_refined(self, title: str) -> bool:
        """Check if title looks like it's been refined by LLM (has proper capitalization)"""
        if not title:
            return False
        
        # Check if the title has proper capitalization patterns
        # LLM-refined titles should have lowercase articles, prepositions, conjunctions
        proper_capitalization_indicators = [
            ' the ', ' a ', ' an ', ' in ', ' on ', ' at ', ' to ', ' for ', ' of ', ' with ', ' by ',
            ' and ', ' or ', ' but ', ' is ', ' are ', ' was ', ' were ', ' over ', ' under '
        ]
        
        # If the title contains these properly capitalized words, it's likely LLM-refined
        has_proper_capitalization = any(indicator in title for indicator in proper_capitalization_indicators)
        
        # Also check if it doesn't have the problematic patterns
        has_problematic_patterns = any([
            ' TO ' in title.upper(),
            ' OF ' in title.upper(), 
            ' IN ' in title.upper(),
            ' IS ' in title.upper(),
            ' BY ' in title.upper(),
            ' FOR ' in title.upper(),
            ' AND ' in title.upper()
        ])
        
        return has_proper_capitalization and not has_problematic_patterns
    
    def find_existing_topic(self, title: str, content: str = "") -> Optional[str]:
        """Find if a similar topic already exists"""
        new_id = self.create_topic_id(title, content)
        
        # Check for exact match
        if new_id in self.topics_db:
            return new_id
        
        # Check for similar topics using key terms
        key_terms = set(re.findall(r'\b[A-Z][a-z]+\b', content if content else title))
        
        for topic_id, topic in self.topics_db.items():
            topic_terms = set(re.findall(r'\b[A-Z][a-z]+\b', topic.get('title', '') + ' ' + topic.get('summary', '')))
            
            # If 60% of terms match, consider it the same topic
            if len(key_terms & topic_terms) / max(len(key_terms), 1) > 0.6:
                return topic_id
        
        return None
    
    def create_or_update_topic(self, title: str, content: str, sources: List[Dict], facts: List[Dict]) -> str:
        """Create new topic or update existing one"""
        # Check if topic already exists
        existing_id = self.find_existing_topic(title, content)
        
        if existing_id:
            # Update existing topic
            return self.update_topic(existing_id, title, content, sources, facts)
        else:
            # Create new topic
            return self.create_new_topic(title, content, sources, facts)
    
    def create_new_topic(self, title: str, content: str, sources: List[Dict], facts: List[Dict]) -> str:
        """Create a new topic"""
        topic_id = self.create_topic_id(title, content)
        # Use the title as-is if it's already been refined by LLM
        # If the title looks like it's already been processed by LLM (has proper capitalization),
        # don't apply our own fixes
        if self._looks_like_llm_refined(title):
            improved_title = title
        else:
            improved_title = self.improve_topic_title(title, content)
        
        topic = {
            "id": topic_id,
            "title": improved_title,
            "canonical_title": improved_title,
            "aliases": list({title, improved_title}),
            "entities": self.extract_entities(content or title),
            "summary": self.create_summary(content),
            "facts": facts,
            "sources": sources,
            "confidence_score": min(0.9, 0.5 + (len(sources) * 0.1)),
            "last_updated": datetime.now().isoformat(),
            "topic_status": "active",
            "created_at": datetime.now().isoformat(),
            "active_score": float(len(sources)) * 0.2
        }
        
        self.topics_db[topic_id] = topic
        self.topic_metrics[topic_id] = TopicMetrics(
            source_count=len(sources),
            activity_score=len(sources) * 0.2,
            last_updated_at=datetime.now()
        )
        
        return topic_id
    
    def update_topic(self, topic_id: str, title: str, content: str, sources: List[Dict], facts: List[Dict]) -> str:
        """Update existing topic with new information"""
        if topic_id not in self.topics_db:
            return self.create_new_topic(title, content, sources, facts)
        
        topic = self.topics_db[topic_id]
        
        # Merge sources (avoid duplicates)
        existing_sources = {s['url']: s for s in topic['sources']}
        for source in sources:
            if source['url'] not in existing_sources:
                topic['sources'].append(source)
        
        # Merge facts (avoid duplicates)
        existing_facts = {f['fact']: f for f in topic['facts']}
        for fact in facts:
            if fact['fact'] not in existing_facts:
                topic['facts'].append(fact)
        
        # Update metadata
        topic['last_updated'] = datetime.now().isoformat()
        topic['confidence_score'] = min(0.9, 0.5 + (len(topic['sources']) * 0.1))
        # Update canonical title/aliases/entities if improved
        # If the title looks like it's already been processed by LLM (has proper capitalization),
        # don't apply our own fixes
        if self._looks_like_llm_refined(title):
            new_title = title
        else:
            new_title = self.improve_topic_title(title, content)
            
        if new_title and new_title not in topic.get('aliases', []):
            topic.setdefault('aliases', []).append(new_title)
        # Prefer longest informative alias as canonical if significantly better
        best = max(topic.get('aliases', [topic['title']]), key=lambda t: len(t))
        if len(best) - len(topic.get('canonical_title', topic['title'])) >= 5:
            topic['canonical_title'] = best
        # Entities
        new_entities = self.extract_entities(content or title)
        if new_entities:
            topic.setdefault('entities', [])
            topic['entities'] = list({*topic['entities'], *new_entities})
        
        # Update metrics
        if topic_id in self.topic_metrics:
            self.topic_metrics[topic_id].source_count = len(topic['sources'])
            # Active score: sources (0.2 each) + recent views (0.1 each, decayed later)
            self.topic_metrics[topic_id].activity_score = len(topic['sources']) * 0.2
            self.topic_metrics[topic_id].last_updated_at = datetime.now()
        
        return topic_id
    
    def create_summary(self, content: str) -> str:
        """Create a neutral summary from content"""
        if not content:
            return "No summary available."
        
        # Extract first few sentences
        sentences = re.split(r'[.!?]+', content)
        summary_sentences = []
        
        for sentence in sentences[:3]:
            sentence = sentence.strip()
            if len(sentence) > 20:  # Reasonable sentence length
                summary_sentences.append(sentence)
        
        summary = '. '.join(summary_sentences).strip()
        if summary and not summary.endswith('.'):
            summary += '.'
        
        return summary or "Summary not available."
    
    def search_topics(self, query: str) -> List[Dict]:
        """Search for topics and create if not found"""
        query_lower = query.lower()
        matching_topics = []
        
        # Search existing topics
        for topic_id, topic in self.topics_db.items():
            title_match = query_lower in topic['title'].lower()
            summary_match = query_lower in topic.get('summary', '').lower()
            
            if title_match or summary_match:
                matching_topics.append(topic)
                # Increment view count
                if topic_id in self.topic_metrics:
                    self.topic_metrics[topic_id].view_count += 1
                    self.topic_metrics[topic_id].last_viewed = datetime.now()
                    self.topic_metrics[topic_id].activity_score += 0.1
        
        # If no matches found, create a placeholder topic
        if not matching_topics:
            topic_id = self.create_search_topic(query)
            if topic_id:
                matching_topics.append(self.topics_db[topic_id])
        
        return matching_topics
    
    def create_search_topic(self, query: str) -> Optional[str]:
        """Create a topic from search query"""
        # This would typically trigger a search for articles about the query
        # For now, create a placeholder
        topic_id = f"search_{hashlib.md5(query.encode()).hexdigest()[:8]}"
        
        topic = {
            "id": topic_id,
            "title": f"Search: {query.title()}",
            "summary": f"Search results for '{query}'. This topic will be populated as more information becomes available.",
            "facts": [],
            "sources": [],
            "confidence_score": 0.1,
            "last_updated": datetime.now().isoformat(),
            "topic_status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        self.topics_db[topic_id] = topic
        self.topic_metrics[topic_id] = TopicMetrics(activity_score=0.1)
        
        return topic_id
    
    def get_active_topics(self, limit: int = 20) -> List[Dict]:
        """Get most active topics based on sources and views"""
        # Apply time decay to activity score
        now = datetime.now()
        decayed_scores = {}
        for tid, metrics in self.topic_metrics.items():
            score = metrics.activity_score
            if metrics.last_viewed:
                hours = (now - metrics.last_viewed).total_seconds() / 3600.0
                score *= 0.85 ** max(0, hours / 6)  # decay per 6h
            decayed_scores[tid] = score
        sorted_topics = sorted(self.topics_db.items(), key=lambda x: decayed_scores.get(x[0], 0.0), reverse=True)
        # Write active_score for UI
        for tid, topic in self.topics_db.items():
            topic['active_score'] = float(decayed_scores.get(tid, 0.0))
        return [topic for _, topic in sorted_topics[:limit]]

    def extract_entities(self, text: str) -> List[str]:
        if not text:
            return []
        # Simple proper noun sequences
        ents = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text)
        return list(dict.fromkeys(ents))
    
    def get_topic_metrics(self, topic_id: str) -> TopicMetrics:
        """Get metrics for a specific topic"""
        return self.topic_metrics.get(topic_id, TopicMetrics())
