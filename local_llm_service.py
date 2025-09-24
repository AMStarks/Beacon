import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import asyncio
import logging


PHI3_MODEL_ID = "microsoft/Phi-3-mini-4k-instruct"


class LocalLLMService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.model_name = PHI3_MODEL_ID
        self.generator = None
        self.is_loaded = False
        self.logger = logging.getLogger("LocalLLMService")
        
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
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float32,
            trust_remote_code=True,
            attn_implementation="eager"
        )
        self.model.eval()
        self.model.to("cpu")

        # Ensure pad token exists for generation
        if self.tokenizer.pad_token is None:
            if self.tokenizer.eos_token is None:
                self.tokenizer.add_special_tokens({"pad_token": "<|pad|>"})
                self.model.resize_token_embeddings(len(self.tokenizer))
            else:
                self.tokenizer.pad_token = self.tokenizer.eos_token

        if hasattr(self.model.config, "use_cache"):
            self.model.config.use_cache = False
        if hasattr(self.model.config, "return_dict_in_generate"):
            self.model.config.return_dict_in_generate = False
        if hasattr(self.model.config, "cache_implementation"):
            self.model.config.cache_implementation = "static"

        self.generator = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device="cpu"
        )

    async def generate_text(self, prompt: str, max_new_tokens: int = 64, temperature: float = 0.3) -> str:
        if not self.is_loaded:
            await self.load_model()

        outputs = self.generator(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id
        )

        return outputs[0]["generated_text"]
    
    async def generate_summary(self, articles_text: str) -> str:
        """Generate a summary using the local LLM"""
        if not self.is_loaded:
            await self.load_model()
            
        try:
            # Create a prompt for summarization
            prompt = (
                "You are a neutral news editor. Summarize the following news content "
                "in 2 concise sentences.\n\nContent:\n"
                f"{articles_text[:1200]}\n\nSummary:"
            )

            generated = await self.generate_text(
                prompt,
                max_new_tokens=150,
                temperature=0.2
            )

            summary = generated.split("Summary:")[-1].strip()

            return summary[:500] if summary else "News coverage of current events."
            
        except Exception as e:
            print(f'❌ Error generating summary: {e}')
            return f'Summary generation failed: {e}'
    
    async def generate_topic_title(self, articles_text: str) -> str:
        """Generate a concise topic title using the local LLM"""
        if not self.is_loaded:
            await self.load_model()
            
        try:
            prompt = (
                "You are a professional news editor. Write a 6-12 word headline "
                "describing the main news story based on the provided content.\n\n"
                f"Content:\n{articles_text[:800]}\n\nHeadline:"
            )

            generated = await self.generate_text(
                prompt,
                max_new_tokens=48,
                temperature=0.25
            )

            title = generated.split("Headline:")[-1].strip()

            title = title.replace('\n', ' ').strip()
            if len(title) > 80:
                title = title[:77] + '...'

            return title or "News Update"
            
        except Exception as e:
            print(f'❌ Error generating title: {e}')
            return 'News Update'

# Global instance
local_llm = LocalLLMService()
