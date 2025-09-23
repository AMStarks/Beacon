from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
from datetime import datetime
import asyncio
import json
from news_service import NewsService, TopicCluster
from enhanced_crawler import EnhancedCrawlerService, CrawledArticle
from topic_manager import TopicManager
from simple_topic_detector import SimpleTopicDetector

# Initialize FastAPI app
app = FastAPI(
    title="Beacon - AI-Powered News Aggregation",
    description="Intelligent topic discovery and fact-synthesis platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic models
class UserPreferences(BaseModel):
    categories: List[str] = []
    sources: List[str] = []
    languages: List[str] = ["en"]
    regions: List[str] = ["us"]

class TopicReport(BaseModel):
    id: str
    title: str
    summary: str
    facts: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    confidence_score: float
    last_updated: datetime
    topic_status: str  # "active", "resolved", "evolving"

class NewsArticle(BaseModel):
    id: str
    title: str
    content: str
    source: str
    url: str
    published_at: datetime
    sentiment: str
    topics: List[str]

# In-memory storage (will be replaced with database)
users_db = {}
topics_db = {}
articles_db = {}

# Authentication
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Simple token validation (replace with proper JWT validation)
    token = credentials.credentials
    if token not in users_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return users_db[token]

# API Routes
@app.get("/")
async def root(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "topics": list(topics_db.values()),
        "recent_articles": list(articles_db.values())[-10:]
    })

@app.post("/api/register")
async def register_user(username: str, password: str):
    """Register a new user"""
    user_id = f"user_{len(users_db) + 1}"
    token = f"token_{user_id}"
    
    users_db[token] = {
        "id": user_id,
        "username": username,
        "preferences": UserPreferences(),
        "created_at": datetime.now()
    }
    
    return {"message": "User registered successfully", "token": token}

@app.post("/api/login")
async def login_user(username: str, password: str):
    """Login user"""
    # Simple authentication (replace with proper auth)
    for token, user in users_db.items():
        if user["username"] == username:
            return {"message": "Login successful", "token": token}
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/topics")
async def get_topics(limit: int = 20):
    """Get all active topics with enhanced management"""
    # Use topic manager for active topics
    active_topics = topic_manager.get_active_topics(limit)
    return {"topics": active_topics}

@app.get("/api/topics/{topic_id}")
async def get_topic(topic_id: str):
    """Get specific topic details"""
    if topic_id not in topics_db:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topics_db[topic_id]

@app.get("/api/search")
async def search_news(query: str, limit: int = 20):
    """Search news articles and topics with enhanced topic management"""
    # Use topic manager for intelligent search
    matching_topics = topic_manager.search_topics(query)
    
    results = {
        "articles": [],
        "topics": matching_topics[:limit]
    }
    
    # If no topics, trigger background fetch for this query (fire-and-forget)
    if not results["topics"]:
        async def _trigger():
            try:
                api_articles = await news_service.fetch_all_news()
                detected_topics = simple_topic_detector.detect_topics(api_articles)
                for topic in detected_topics:
                    summary = f"Topic with {topic.source_count} sources covering {topic.title}"
                    facts = [{"fact": f"Topic: {topic.title}", "confidence": 0.8, "source": "System"}]
                    sources = [{"name": a.source, "url": a.url, "reliability": "0.8"} for a in topic.articles]
                    topic_id = topic_manager.create_or_update_topic(topic.title, summary, sources, facts)
                    topics_db[topic_id] = topic_manager.topics_db[topic_id]
            except Exception:
                pass
        asyncio.create_task(_trigger())
    return results

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": "1.0.0"
    }

# Initialize services
news_service = NewsService()
crawler_service = EnhancedCrawlerService()
topic_manager = TopicManager()
simple_topic_detector = SimpleTopicDetector()

# Background task for news aggregation
async def news_aggregation_task():
    """Background task for continuous news aggregation"""
    while True:
        try:
            print("Running news aggregation...")
            
            # Fetch news from APIs
            api_articles = await news_service.fetch_all_news()
            print(f"Fetched {len(api_articles)} articles from APIs")
            
            # Crawl additional news sources
            crawled_articles = await crawler_service.crawl_news_sources()
            print(f"Crawled {len(crawled_articles)} articles from web sources")
            
            # Combine all articles
            all_articles = api_articles + crawled_articles
            print(f"Total articles: {len(all_articles)}")
            
            if all_articles:
                # Detect topics using simple detector
                detected_topics = simple_topic_detector.detect_topics(all_articles)
                print(f"Detected {len(detected_topics)} topics")
                
                # Update topics using enhanced topic manager
                for topic in detected_topics:
                    # Create simple summary from articles
                    summary = f"Topic with {topic.source_count} sources covering {topic.title}"
                    facts = [{"fact": f"Topic: {topic.title}", "confidence": 0.8, "source": "System"}]
                    sources = [{"name": article.source, "url": article.url, "reliability": "0.8"} for article in topic.articles]
                    
                    # Try to refine title and summary with Grok LLM
                    try:
                        # Convert to TopicCluster format for LLM refinement
                        from news_service import TopicCluster
                        topic_cluster = TopicCluster(
                            id=topic.id,
                            title=topic.title,
                            summary=summary,
                            articles=topic.articles,
                            confidence_score=0.8,
                            last_updated=datetime.now(),
                            status="active"
                        )
                        
                        # Refine with Grok LLM
                        refined_topic = await news_service.refine_with_llm(topic_cluster)
                        topic.title = refined_topic.title
                        summary = refined_topic.summary
                        print(f"LLM refined title: {topic.title}")
                    except Exception as e:
                        print(f"LLM refinement failed: {e}, using original title")
                    
                    # Use topic manager to create or update topic
                    topic_id = topic_manager.create_or_update_topic(
                        title=topic.title,
                        content=summary,
                        sources=sources,
                        facts=facts
                    )
                    
                    # Update the legacy topics_db for compatibility
                    topic_report = {
                        "id": topic_id,
                        "title": topic_manager.topics_db[topic_id]["title"],
                        "summary": topic_manager.topics_db[topic_id]["summary"],
                        "facts": facts,
                        "sources": sources,
                        "confidence_score": topic_manager.topics_db[topic_id]["confidence_score"],
                        "last_updated": topic_manager.topics_db[topic_id]["last_updated"],
                        "topic_status": topic_manager.topics_db[topic_id]["topic_status"]
                    }
                    
                    topics_db[topic_id] = topic_report
                    print(f"Added/Updated topic: {topic_manager.topics_db[topic_id]['title']}")
            
            await asyncio.sleep(300)  # Run every 5 minutes
        except Exception as e:
            print(f"Error in news aggregation: {e}")
            await asyncio.sleep(60)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    print("Starting Beacon News Aggregation Platform...")
    
    # Create sample data for demonstration
    sample_topic = TopicReport(
        id="topic_1",
        title="49ers Win NFL Game",
        summary="The San Francisco 49ers defeated their opponent in a decisive victory, improving their season record and advancing their playoff position.",
        facts=[
            {"fact": "49ers won the game", "confidence": 0.95, "source": "ESPN"},
            {"fact": "Final score was 28-14", "confidence": 0.90, "source": "NFL.com"},
            {"fact": "Game played at Levi's Stadium", "confidence": 0.85, "source": "Local News"}
        ],
        sources=[
            {"name": "ESPN", "url": "https://espn.com", "reliability": "0.9"},
            {"name": "NFL.com", "url": "https://nfl.com", "reliability": "0.95"},
            {"name": "Local News", "url": "https://localnews.com", "reliability": "0.8"}
        ],
        confidence_score=0.90,
        last_updated=datetime.now(),
        topic_status="active"
    )
    
    topics_db["topic_1"] = sample_topic.dict()
    
    # Start background task
    asyncio.create_task(news_aggregation_task())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
