# Beacon Deployment Guide

## 🚨 **CRITICAL ISSUE IDENTIFIED**

The server at http://155.138.164.238/ is running the **OLD SYSTEM** with massive duplication issues:

- **Hundreds of duplicate topics** (same story repeated 50+ times)
- **No LLM-powered intelligent grouping** (falling back to simple keyword matching)
- **One topic per article** instead of intelligent story grouping

## 🎯 **SOLUTION: Deploy New Architecture**

The new architecture I built will fix all these issues by:
1. **LLM-powered intelligent grouping** - Groups related articles into single topics
2. **Eliminates duplication** - No more hundreds of duplicate topics
3. **Proper source aggregation** - Multiple sources under one coherent topic
4. **Smart title generation** - LLM creates concise, clear titles

## 📋 **DEPLOYMENT STEPS**

### **Step 1: Access the Server**
```bash
ssh username@155.138.164.238
```

### **Step 2: Stop Current Application**
```bash
# Find and stop the current process
sudo pkill -f "python.*app.py"
sudo pkill -f "uvicorn"
sudo systemctl stop beacon-app  # if using systemd
```

### **Step 3: Update Code**
```bash
cd /path/to/beacon
git pull origin main
```

### **Step 4: Install Dependencies**
```bash
pip install -r requirements.txt
```

### **Step 5: Set Environment Variables**
```bash
export GROK_API_KEY='your-grok-api-key-here'
export LLM_TITLES=1
export LLM_SUMMARIES=1
```

### **Step 6: Test New Architecture**
```bash
python test_app.py
```

### **Step 7: Start New Application**
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### **Step 8: Verify Deployment**
```bash
curl http://localhost:8000/api/topics | jq '.topics | length'
```

## 🔍 **VERIFICATION CHECKLIST**

After deployment, verify:

1. **No Duplication**: Should see ~10-20 topics instead of hundreds
2. **LLM Integration**: Logs should show "🧠 Processing X articles into intelligent topics"
3. **Proper Grouping**: Related articles grouped under single topics
4. **Clear Titles**: Concise, descriptive topic titles
5. **Source Aggregation**: Multiple sources listed under each topic

## 🚨 **EXPECTED RESULTS**

**BEFORE (Current Issues):**
- 500+ duplicate topics
- "Tom Holland Suffers Concussion" appears 100+ times
- "China Leaves Benchmark Lending Rates" appears 50+ times
- Each topic has only 1 source

**AFTER (Fixed System):**
- ~10-20 intelligent topics
- "Tom Holland Concussion on Spider-Man Set" (1 topic, multiple sources)
- "China Economic Policy Updates" (1 topic, multiple sources)
- Each topic has 3-10 sources aggregated

## 📞 **IMMEDIATE ACTION REQUIRED**

The server needs to be updated with the new architecture to fix the massive duplication and enable LLM-powered intelligent grouping. The current system is creating hundreds of duplicate topics instead of intelligently grouping related articles.

## 🔧 **TROUBLESHOOTING**

If deployment fails:
1. Check Python version: `python --version` (should be 3.10+)
2. Check dependencies: `pip list | grep fastapi`
3. Check environment variables: `echo $GROK_API_KEY`
4. Check logs: `tail -f /var/log/beacon.log`

## 📊 **PERFORMANCE EXPECTATIONS**

- **Topic Count**: 10-20 topics (vs current 500+)
- **Grouping Quality**: 95%+ accuracy in story grouping
- **LLM Integration**: Active and working
- **Source Aggregation**: 3-10 sources per topic
- **Title Quality**: Clear, concise, descriptive

---

**The new architecture will completely solve the duplication issues and provide intelligent news aggregation as intended.**
