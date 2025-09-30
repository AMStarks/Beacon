#!/usr/bin/env python3
"""
Test exact prompt being sent to LLM
"""

import asyncio
import httpx

async def test_exact_prompt():
    """Test the exact prompt being sent"""
    print("🧪 Testing exact prompt...")
    
    content_preview = "China makes landmark pledge to cut its climate emissions 5 days ago Share Save Mark Poynting and Matt McGrath BBC News Climate and Science Share Save European Photopress Agency China, the world's biggest source of planet-warming gases, has for the first time committed to an absolute target to cut its emissions. In a video statement to the UN in New York, President Xi Jinping said that China would reduce its greenhouse gas emissions across the economy by 7-10% by 2035, while striving to peak emissions before 2030 and achieve carbon neutrality by 2060."
    
    prompt = f"""Write a 100-word summary of this news article:

{content_preview}

Summary:"""
    
    print(f"Prompt: {prompt}")
    
    messages = [
        {
            "role": "system",
            "content": "You are a neutral news editor. Write factual, unbiased summaries. Return only the summary."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": "llama3.1:8b",
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "max_tokens": 150,
                        "stop": ["Here's", "Sure,", "Let me", "I'll", "Here are"]
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('message', {}).get('content', '').strip()
                print(f"✅ LLM Response: {content}")
                print(f"Word count: {len(content.split())}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_exact_prompt())
