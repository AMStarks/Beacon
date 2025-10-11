# 🚀 Beacon 2 - Complete Rebuild Plan

## 📋 Overview
Beacon 2 is a complete architectural overhaul of the AI news desk system, addressing all critical flaws identified in the original codebase.

**Start Date**: October 3, 2025
**Target Completion**: 6 weeks (November 14, 2025)
**Status**: ✅ Backed up, 🔄 In Development

---

## 🎯 Core Objectives

### ✅ MUST HAVE (Week 1-2)
- **Reliable Article Processing**: System processes articles without crashing
- **Neutral Content Generation**: LLM-enhanced titles and excerpts with fallbacks
- **Basic Clustering**: Simple content similarity matching
- **Web Interface**: Clean, error-free user interface

### 🎯 SHOULD HAVE (Week 3-4)
- **Production Monitoring**: Health checks, logging, metrics
- **Performance Optimization**: Sub-5s response times
- **Error Recovery**: Comprehensive error handling
- **Input Validation**: Secure against malicious inputs

### 🚀 COULD HAVE (Week 5-6)
- **Advanced Clustering**: LLM-enhanced similarity detection
- **Real-time Updates**: WebSocket integration
- **API Endpoints**: RESTful API for external integrations
- **Analytics Dashboard**: Usage and performance metrics

---

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐
│   Article URLs  │───▶│  Async Processor │
└─────────────────┘    └──────────────────┘
                               │
┌─────────────────┐    ┌──────▼──────┐
│   LLM Service   │◀───┤  Content     │
│   (Enhanced)    │    │  Extractor   │
└─────────────────┘    └─────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│   Clustering    │    │   Database       │
│   Service       │    │   (Normalized)   │
└─────────────────┘    └──────────────────┘
                               │
┌─────────────────┐    ┌──────▼──────┐
│   Web Interface │◀───┤  API Layer   │
│   (React/Flask) │    │  (RESTful)   │
└─────────────────┘    └─────────────┘
```

---

## 📅 Detailed Development Plan

### **PHASE 1: Foundation (Week 1)**
*Duration: 5-7 days*

#### **1.1 Project Structure** ✅
- [ ] Create proper package structure (`src/beacon2/`)
- [ ] Set up virtual environment with new dependencies
- [ ] Configure logging and error handling
- [ ] Create database schema (normalized)

#### **1.2 Core Services**
- [ ] `content_extractor.py` - Robust article content extraction
- [ ] `llm_service.py` - Async LLM integration with fallbacks ✅
- [ ] `database_service.py` - Clean database operations
- [ ] `clustering_service.py` - Simplified similarity matching

#### **1.3 Basic Processing Pipeline**
- [ ] `article_processor.py` - Main processing logic
- [ ] Async queue management
- [ ] Error handling and recovery
- [ ] Basic web interface

**Milestone**: System can process 1 article end-to-end

---

### **PHASE 2: Enhancement (Week 2-3)**
*Duration: 7-10 days*

#### **2.1 Advanced LLM Integration**
- [ ] Circuit breaker pattern for LLM calls
- [ ] Response caching and optimization
- [ ] A/B testing framework for LLM vs fallback
- [ ] Performance monitoring

#### **2.2 Clustering Improvements**
- [ ] TF-IDF similarity scoring
- [ ] Content-based clustering
- [ ] Cluster quality validation
- [ ] Automatic cluster splitting

#### **2.3 Database Optimization**
- [ ] Connection pooling
- [ ] Query optimization
- [ ] Database migrations
- [ ] Backup strategies

**Milestone**: System processes 10 articles reliably with clustering

---

### **PHASE 3: Production Readiness (Week 4)**
*Duration: 5-7 days*

#### **3.1 Monitoring & Observability**
- [ ] Health check endpoints
- [ ] Metrics collection (Prometheus)
- [ ] Structured logging (JSON)
- [ ] Error alerting

#### **3.2 Security & Validation**
- [ ] Input sanitization
- [ ] Rate limiting
- [ ] CORS configuration
- [ ] Environment variable management

#### **3.3 Performance Optimization**
- [ ] Response time optimization (<5s)
- [ ] Memory usage monitoring
- [ ] Concurrent processing limits
- [ ] Database indexing

**Milestone**: Production-ready system with monitoring

---

### **PHASE 4: Polish (Week 5-6)**
*Duration: 7-10 days*

#### **4.1 Advanced Features**
- [ ] WebSocket real-time updates
- [ ] RESTful API endpoints
- [ ] Analytics dashboard
- [ ] User authentication

#### **4.2 Testing & Documentation**
- [ ] Unit tests (pytest)
- [ ] Integration tests
- [ ] API documentation (OpenAPI)
- [ ] Deployment guides

#### **4.3 Deployment & DevOps**
- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Environment management
- [ ] Rollback procedures

**Milestone**: Fully production-ready system

---

## 🛠️ Technical Specifications

### **Core Technologies**
- **Backend**: Python 3.11+, asyncio, aiohttp
- **Database**: SQLite with SQLAlchemy ORM
- **Web Framework**: Flask with async support
- **LLM**: Ollama (gemma:2b) with fallback algorithms
- **Frontend**: HTML/CSS/JS (initial), React (future)

### **Key Dependencies**
```txt
Flask==3.0.0
SQLAlchemy==2.0.0
aiohttp==3.9.0
beautifulsoup4==4.12.0
nltk==3.8.0  # For text processing
scikit-learn==1.3.0  # For similarity scoring
pytest==7.4.0
prometheus-client==0.19.0
```

### **Performance Targets**
- **Response Time**: <5 seconds per article
- **Throughput**: 100 articles/hour
- **Uptime**: 99.9%
- **Error Rate**: <0.1%

---

## 🚨 Risk Management

### **Critical Risks**
1. **LLM Dependency**: Mitigated by fallback algorithms
2. **Database Corruption**: Prevented by proper transactions
3. **Memory Leaks**: Monitored with health checks
4. **External API Failures**: Handled with retries and caching

### **Rollback Plan**
- **Immediate**: Switch to fallback algorithms
- **Short-term**: Deploy previous version
- **Long-term**: Database backup restoration

---

## 📊 Success Metrics

### **Functional Metrics**
- [ ] System processes articles without crashing
- [ ] LLM generates quality neutral content (when available)
- [ ] Clustering groups similar articles correctly
- [ ] Web interface loads and functions properly

### **Performance Metrics**
- [ ] Average response time <5 seconds
- [ ] 99%+ system uptime
- [ ] <1% error rate in processing
- [ ] Proper resource utilization

### **Quality Metrics**
- [ ] LLM content scores >80% neutrality rating
- [ ] Fallback content maintains readability
- [ ] Clustering accuracy >90%
- [ ] No data loss or corruption

---

## 🎯 Next Steps

1. **Immediate** (Today):
   - [ ] Complete Phase 1.1 setup
   - [ ] Create basic project structure
   - [ ] Set up development environment

2. **Week 1 Focus**:
   - [ ] Implement core article processing
   - [ ] Test end-to-end article flow
   - [ ] Deploy to development environment

3. **Week 2 Focus**:
   - [ ] Add LLM integration with fallbacks
   - [ ] Implement basic clustering
   - [ ] Create web interface

**Ready to start implementation?**
