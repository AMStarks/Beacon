# Beacon News Aggregation Architecture

## Overview
Beacon is an AI-powered news aggregation system that intelligently groups news articles by story and presents them as consolidated topics with multiple sources.

## Core Architecture

### 1. News Collection Layer
**Purpose**: Gather news articles from multiple sources

**Components**:
- **Web Crawler**: Scans news websites (BBC, CNN, AP, Reuters, etc.)
- **API Sources**: Fetches from news APIs (NewsAPI, NewsData.io, etc.)
- **RSS Feeds**: Aggregates from RSS feeds
- **Enhanced Crawler**: Uses Playwright, BeautifulSoup, trafilatura for content extraction

**Output**: Raw articles with:
- Title
- Content
- Source
- URL
- Timestamp
- Category
- Country
- Language

### 2. Topic Detection & Grouping Layer
**Purpose**: Use LLM to intelligently group articles by story

**Components**:
- **LLM-Powered Analysis**: Use Grok (x.ai) to analyze all collected articles
- **Intelligent Grouping**: LLM determines which articles belong to the same story/topic
- **Topic Creation**: Create one topic per story with a clear, neutral heading
- **Source Aggregation**: Group all sources reporting on the same story under one topic

**Key Principles**:
- **One topic per story** (not one topic per article)
- **Neutral, descriptive headings** (not clickbait)
- **Source aggregation** (multiple sources per topic)
- **LLM-powered intelligence** (not simple keyword matching)

### 3. Topic Management Layer
**Purpose**: Manage and store topics with their aggregated sources

**Components**:
- **Topic Database**: Store topics with their aggregated sources
- **Deduplication**: Prevent duplicate topics for the same story
- **Source Hierarchy**: Weight sources by reliability (BBC > CNN > niche blogs)
- **Hot Updates**: Detect breaking news updates to existing topics
- **Topic Manager**: Handles topic creation, updates, and search

**Source Tiers**:
- **Tier 1**: Major news outlets (BBC, AP, Reuters, Guardian, NPR) - Weight: 1.0
- **Tier 2**: Secondary outlets (CNN, Fox, ABC, CBS, NBC, ESPN, Bloomberg) - Weight: 0.8
- **Tier 3**: Specialized/niche outlets (TechCrunch, Wired, Politico) - Weight: 0.6
- **Default**: Unknown sources - Weight: 0.5

### 4. API & Display Layer
**Purpose**: Serve topics to frontend and display them

**Components**:
- **REST API**: Serve topics to frontend via FastAPI
- **Topic Cards**: Display topic title, source count, confidence, timestamp
- **Source Lists**: Show all sources reporting on each topic
- **Web Interface**: Clean, modern UI for topic discovery

## Data Flow

### 1. Article Collection
```
News Sources → Web Crawler/APIs → Raw Articles → Article Database
```

### 2. Topic Processing
```
Raw Articles → LLM Analysis → Topic Grouping → Topic Database
```

### 3. Topic Display
```
Topic Database → API → Frontend → User Interface
```

## Example Flow

### Input Articles:
- "Charlie Kirk Memorial Service Held in Texas" (AP)
- "Trump Attends Kirk Memorial Service" (BBC)
- "Kirk Memorial Draws Political Attention" (CNN)

### LLM Analysis:
- LLM identifies these are all about the same story
- Creates topic: "Charlie Kirk Memorial Service"
- Groups all 3 articles under this topic

### Output:
- **Topic**: "Charlie Kirk Memorial Service"
- **Sources**: AP, BBC, CNN (3 sources)
- **Confidence**: 90%
- **Timestamp**: Current time

## Key Features

### Intelligent Grouping
- Uses LLM to understand article content and context
- Groups related articles regardless of source
- Prevents duplicate topics for the same story

### Source Aggregation
- Multiple sources per topic
- Source reliability weighting
- Comprehensive coverage display

### Neutral Presentation
- Politically neutral topic headings
- Factual, descriptive titles
- No editorial bias

### Real-time Updates
- Continuous news collection
- Hot update detection
- Fresh topic generation

## Technical Implementation

### LLM Integration
- **Provider**: Grok (x.ai)
- **Model**: grok-4-latest
- **Purpose**: Article analysis and topic grouping
- **Caching**: Results cached to avoid redundant API calls

### Database
- **Type**: In-memory storage (temporary)
- **Future**: Database integration planned
- **Storage**: Topics, articles, sources, facts

### API
- **Framework**: FastAPI
- **Endpoints**: `/api/topics`, `/api/articles`
- **Format**: JSON responses
- **Rate Limiting**: Built-in rate limiting for external APIs

## Success Metrics

### Topic Quality
- **Consolidation**: Multiple articles per topic (not 1:1)
- **Deduplication**: No duplicate topics for same story
- **Clarity**: Clear, neutral topic headings

### Source Coverage
- **Diversity**: Multiple sources per topic
- **Reliability**: Weighted by source credibility
- **Completeness**: All relevant articles grouped appropriately

### User Experience
- **Clarity**: Easy to understand topic structure
- **Completeness**: All sources visible per topic
- **Neutrality**: No editorial bias in presentation
