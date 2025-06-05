#!/usr/bin/env python3
"""
MANUAL TEST SCRIPT - OpenAI Connection Testing

This is a manual debugging script for verifying OpenAI API connectivity.
It is NOT part of the automated test suite and should be run manually for debugging.

Direct test script for OpenAI API connection using environment variables.
This tests the same configuration that CIRIS Engine should be using.
"""

import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

async def test_openai_connection():
    """Test OpenAI API connection directly."""
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get environment variables
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
    
    print("=== OpenAI API Configuration Test ===")
    print(f"API Key: {'***' + api_key[-4:] if api_key else 'NOT SET'}")
    print(f"Base URL: {base_url or 'DEFAULT (https://api.openai.com/v1)'}")
    print(f"Model: {model_name}")
    print()
    
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY is not set in environment variables")
        return False
    
    # Create client
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0
        )
        print("✅ OpenAI client created successfully")
    except Exception as e:
        print(f"❌ ERROR creating OpenAI client: {e}")
        return False
    
    # Test simple completion
    try:
        print("\n🔄 Testing chat completion...")
        print(f"   Using model: {model_name}")
        print(f"   Using endpoint: {base_url or 'default OpenAI'}")
        
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'Hello, this is a test!' and nothing else."}
                ],
                max_tokens=50,
                temperature=0.0
            ),
            timeout=45.0  # 45 second timeout
        )
        
        content = response.choices[0].message.content
        print(f"✅ SUCCESS! Response: {content}")
        return True
        
    except asyncio.TimeoutError:
        print(f"❌ ERROR: Request timed out after 45 seconds")
        print("   This suggests the API endpoint is not responding properly.")
        return False
        
    except Exception as e:
        print(f"❌ ERROR making API call: {e}")
        print(f"   Error type: {type(e).__name__}")
        
        # Check for specific error types
        if "503" in str(e):
            print("   This appears to be a 503 Service Unavailable error.")
            print("   This usually means:")
            print("   - The API endpoint is temporarily down")
            print("   - The model is overloaded")
            print("   - Rate limiting or quota issues")
            print("   - The specific model might not be available")
            
        if "401" in str(e):
            print("   This appears to be a 401 Unauthorized error.")
            print("   Check your API key is correct.")
            
        if "404" in str(e):
            print("   This appears to be a 404 Not Found error.")
            print("   Check your base URL and model name are correct.")
        
        return False

async def check_available_models():
    """Check what models are available on the API."""
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
    
    if not api_key or not base_url:
        print("❌ Skipping model check - missing API key or base URL")
        return False
    
    print("\n=== Checking Available Models ===")
    
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0
        )
        
        # Try to list models
        models = await asyncio.wait_for(
            client.models.list(),
            timeout=30.0
        )
        
        print(f"✅ Found {len(models.data)} available models:")
        llama_models = [m for m in models.data if 'llama' in m.id.lower()]
        
        if llama_models:
            print("   Llama models available:")
            for model in llama_models[:10]:  # Show first 10
                print(f"   - {model.id}")
            if len(llama_models) > 10:
                print(f"   ... and {len(llama_models) - 10} more")
        else:
            print("   No Llama models found. Showing all models:")
            for model in models.data[:20]:  # Show first 20
                print(f"   - {model.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Could not fetch models: {e}")
        return False

async def test_alternative_model():
    """Test with a more common Together.ai model."""
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
    
    if not api_key or not base_url:
        print("❌ Skipping alternative model test - missing API key or base URL")
        return False
    
    print("\n=== Testing Alternative Model ===")
    # Try a more common Together.ai model
    alt_model = "meta-llama/Llama-3-8b-chat-hf"
    print(f"Testing with alternative model: {alt_model}")
    
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0
        )
        
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=alt_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'Hello from alternative model!' and nothing else."}
                ],
                max_tokens=50,
                temperature=0.0
            ),
            timeout=45.0
        )
        
        content = response.choices[0].message.content
        print(f"✅ SUCCESS with alternative model! Response: {content}")
        return True
        
    except Exception as e:
        print(f"❌ Alternative model also failed: {e}")
        return False

async def test_ciris_config():
    """Test how CIRIS Engine loads the configuration."""
    print("\n=== CIRIS Engine Configuration Test ===")
    
    try:
        # Test CIRIS config loading
        from ciris_engine.config.config_manager import get_config
        from ciris_engine.config.env_utils import get_env_var
        
        print("✅ CIRIS modules imported successfully")
        
        # Test environment variable loading
        api_key = get_env_var("OPENAI_API_KEY")
        api_base = get_env_var("OPENAI_API_BASE")
        base_url = get_env_var("OPENAI_BASE_URL")
        model_name = get_env_var("OPENAI_MODEL_NAME")
        
        print(f"ENV - API Key: {'***' + api_key[-4:] if api_key else 'NOT SET'}")
        print(f"ENV - API Base: {api_base or 'NOT SET'}")
        print(f"ENV - Base URL: {base_url or 'NOT SET'}")
        print(f"ENV - Model: {model_name or 'NOT SET'}")
        
        # Test config loading
        config = get_config()
        print(f"CONFIG - API Key: {'***' + config.llm_services.openai.api_key[-4:] if config.llm_services.openai.api_key else 'NOT SET'}")
        print(f"CONFIG - Base URL: {config.llm_services.openai.base_url or 'NOT SET'}")
        print(f"CONFIG - Model: {config.llm_services.openai.model_name}")
        
        # Test if load_env_vars is working
        test_config = config.llm_services.openai
        print(f"\nBefore load_env_vars: base_url = {test_config.base_url}")
        test_config.load_env_vars()
        print(f"After load_env_vars: base_url = {test_config.base_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR testing CIRIS config: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests."""
    print("Testing OpenAI API configuration and connectivity...\n")
    
    # Check available models first
    await check_available_models()
    
    # Test direct connection
    direct_success = await test_openai_connection()
    
    # Test alternative model if primary failed
    alt_success = False
    if not direct_success:
        alt_success = await test_alternative_model()
    
    # Test CIRIS config
    ciris_success = await test_ciris_config()
    
    print("\n=== Summary ===")
    print(f"Direct OpenAI test: {'✅ PASS' if direct_success else '❌ FAIL'}")
    if not direct_success:
        print(f"Alternative model test: {'✅ PASS' if alt_success else '❌ FAIL'}")
    print(f"CIRIS config test: {'✅ PASS' if ciris_success else '❌ FAIL'}")
    
    if not direct_success and not alt_success:
        print("\n🔍 Troubleshooting suggestions:")
        print("1. Check your .env file contains the correct values")
        print("2. Verify your API key is valid and has sufficient credits")
        print("3. If using a custom endpoint, verify the URL is correct")
        print("4. Try a different model name if the current one is unavailable")
        print("5. Check the service status of your API provider")
        print("6. The model 'meta-llama/Llama-4-Scout-17B-16E-Instruct' might not exist")
        print("   Try: 'meta-llama/Llama-3-8b-chat-hf' or 'meta-llama/Llama-3-70b-chat-hf'")
    elif alt_success:
        print(f"\n✅ Solution: Use the alternative model instead")
        print(f"   Update OPENAI_MODEL_NAME=meta-llama/Llama-3-8b-chat-hf")

if __name__ == "__main__":
    asyncio.run(main())
