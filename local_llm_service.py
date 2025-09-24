import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import asyncio
import logging

class LocalLLMService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.model_name = 'gpt2'
        self.is_loaded = False
        
    async def load_model(self):
        """Load the local LLM model with timeout protection"""
        if self.is_loaded:
            return
            
        print(f'🤖 Loading local LLM: {self.model_name}')
        try:
            # Add timeout protection for model loading
            await asyncio.wait_for(self._load_model_internal(), timeout=60.0)
            self.is_loaded = True
            print(f'✅ Local LLM loaded successfully')
            
        except asyncio.TimeoutError:
            print(f'⏰ LLM model loading timed out')
            raise Exception("LLM model loading timed out")
        except Exception as e:
            print(f'❌ Failed to load local LLM: {e}')
            raise
    
    async def _load_model_internal(self):
        """Internal model loading with proper async handling"""
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
        
        # Set pad token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
    
    async def generate_summary(self, articles_text: str) -> str:
        """Generate a summary using the local LLM"""
        if not self.is_loaded:
            await self.load_model()
            
        try:
            # Create a prompt for summarization
            prompt = f"Summarize these news articles in a neutral tone:\n\n{articles_text[:1000]}\n\nSummary:"
            
            inputs = self.tokenizer.encode(prompt, return_tensors='pt')
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_length=inputs.shape[1] + 100,
                    num_return_sequences=1,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract just the summary part
            if 'Summary:' in response:
                summary = response.split('Summary:')[-1].strip()
            else:
                summary = response[len(prompt):].strip()
                
            return summary[:500]  # Limit to 500 characters
            
        except Exception as e:
            print(f'❌ Error generating summary: {e}')
            return f'Summary generation failed: {e}'
    
    async def generate_topic_title(self, articles_text: str) -> str:
        """Generate a concise topic title using the local LLM"""
        if not self.is_loaded:
            await self.load_model()
            
        try:
            prompt = f"Create a brief, concise title (under 50 characters) for these news articles:\n\n{articles_text[:500]}\n\nTitle:"
            
            inputs = self.tokenizer.encode(prompt, return_tensors='pt')
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_length=inputs.shape[1] + 20,
                    num_return_sequences=1,
                    temperature=0.8,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract just the title part
            if 'Title:' in response:
                title = response.split('Title:')[-1].strip()
            else:
                title = response[len(prompt):].strip()
                
            # Clean up and limit length
            title = title.replace('\n', ' ').strip()
            if len(title) > 50:
                title = title[:47] + '...'
                
            return title
            
        except Exception as e:
            print(f'❌ Error generating title: {e}')
            return 'News Update'

# Global instance
local_llm = LocalLLMService()
