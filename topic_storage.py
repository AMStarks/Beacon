"""
Topic Storage Layer
Implements the third layer of the Beacon architecture - managing and storing topics
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json

class TopicStorage:
    """Manages topic storage and retrieval"""
    
    def __init__(self):
        self.topics = {}
        self.topic_counter = 0
    
    def store_topic(self, topic: Dict[str, Any]) -> str:
        """Store a topic and return its ID"""
        topic_id = topic.get('id', f"topic_{self.topic_counter}")
        self.topic_counter += 1
        
        # Ensure required fields
        topic['id'] = topic_id
        topic['last_updated'] = datetime.now().isoformat()
        if 'created_at' not in topic:
            topic['created_at'] = datetime.now().isoformat()
        
        # Store the topic
        self.topics[topic_id] = topic
        
        print(f"💾 Stored topic: {topic['title']} (ID: {topic_id})")
        return topic_id
    
    def get_topic(self, topic_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific topic by ID"""
        return self.topics.get(topic_id)
    
    def get_all_topics(self) -> List[Dict[str, Any]]:
        """Get all topics"""
        return list(self.topics.values())
    
    def update_topic(self, topic_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing topic"""
        if topic_id not in self.topics:
            return False
        
        # Update fields
        for key, value in updates.items():
            self.topics[topic_id][key] = value
        
        # Update timestamp
        self.topics[topic_id]['last_updated'] = datetime.now().isoformat()
        
        print(f"🔄 Updated topic: {topic_id}")
        return True
    
    def delete_topic(self, topic_id: str) -> bool:
        """Delete a topic"""
        if topic_id not in self.topics:
            return False
        
        del self.topics[topic_id]
        print(f"🗑️ Deleted topic: {topic_id}")
        return True
    
    def search_topics(self, query: str) -> List[Dict[str, Any]]:
        """Search topics by title or content"""
        query_lower = query.lower()
        results = []
        
        for topic in self.topics.values():
            if (query_lower in topic.get('title', '').lower() or 
                query_lower in topic.get('summary', '').lower()):
                results.append(topic)
        
        return results
    
    def get_topics_by_source(self, source: str) -> List[Dict[str, Any]]:
        """Get topics that include a specific source"""
        results = []
        
        for topic in self.topics.values():
            if source in topic.get('source_names', []):
                results.append(topic)
        
        return results
    
    def get_topic_stats(self) -> Dict[str, Any]:
        """Get statistics about stored topics"""
        total_topics = len(self.topics)
        total_sources = sum(len(topic.get('source_names', [])) for topic in self.topics.values())
        total_articles = sum(topic.get('source_count', 0) for topic in self.topics.values())
        
        return {
            'total_topics': total_topics,
            'total_sources': total_sources,
            'total_articles': total_articles,
            'average_sources_per_topic': total_sources / total_topics if total_topics > 0 else 0,
            'average_articles_per_topic': total_articles / total_topics if total_topics > 0 else 0
        }
    
    def export_topics(self) -> str:
        """Export all topics as JSON"""
        return json.dumps(self.topics, indent=2, default=str)
    
    def import_topics(self, json_data: str) -> bool:
        """Import topics from JSON"""
        try:
            imported_topics = json.loads(json_data)
            self.topics.update(imported_topics)
            print(f"📥 Imported {len(imported_topics)} topics")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ Failed to import topics: {e}")
            return False
