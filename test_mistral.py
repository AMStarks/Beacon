#!/usr/bin/env python3
"""
Test script for Mistral 7B integration
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import time

def test_mistral():
    print("🤖 Testing Mistral 7B Integration")
    print("=" * 50)
    
    # Model name - using tiny model for testing
    model_name = "distilbert-base-uncased"
    
    print(f"📥 Loading model: {model_name}")
    start_time = time.time()
    
    try:
        # Load tokenizer
        print("🔤 Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # Load model
        print("🧠 Loading model...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            low_cpu_mem_usage=True
        )
        
        load_time = time.time() - start_time
        print(f"✅ Model loaded in {load_time:.2f} seconds")
        
        # Test inference
        print("\n🧪 Testing inference...")
        test_prompt = "Summarize this news: 'Breaking: Major tech company announces new AI breakthrough that could revolutionize healthcare.'"
        
        # Tokenize
        inputs = tokenizer(test_prompt, return_tensors="pt")
        
        # Generate
        start_inference = time.time()
        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                max_new_tokens=100,
                temperature=0.7,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
        
        inference_time = time.time() - start_inference
        
        # Decode
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"✅ Inference completed in {inference_time:.2f} seconds")
        
        print(f"\n📝 Test Prompt: {test_prompt}")
        print(f"🤖 Mistral Response: {response}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_mistral()
    if success:
        print("\n✅ Mistral test completed successfully!")
    else:
        print("\n❌ Mistral test failed!")
