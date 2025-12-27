"""
Gemini AI Client Module
Provides a centralized client for Google Gemini AI
"""

import os
import google.generativeai as genai


def make_client():
    """
    Create and return a Google Gemini AI client
    
    Returns:
        genai.GenerativeModel: Configured Gemini AI model
        
    Raises:
        ValueError: If API key is not found in environment variables
    """
    # Get API key from environment variables
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not key:
        raise ValueError(
            "Gemini API key not found! Please set GEMINI_API_KEY or GOOGLE_API_KEY "
            "in your .env file. Get your free API key from: "
            "https://aistudio.google.com/app/apikey"
        )
    
    # Configure the API
    genai.configure(api_key=key)
    
    # Available models (as of Dec 2024):
    # - gemini-2.5-flash (newest, recommended)
    # - gemini-2.5-pro (more capable)
    # - gemini-2.0-flash-exp (experimental)
    # 
    # Note: gemini-1.5-flash and older models have been retired!
    # Default to gemini-2.5-flash for best compatibility
    model_name = os.getenv("GENAI_MODEL", "gemini-2.5-flash")
    
    # Try the requested model first, then fallbacks
    models_to_try = [
        model_name,
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash-exp",
    ]
    
    for try_model in models_to_try:
        try:
            model = genai.GenerativeModel(try_model)
            # Test if model works by checking it can be used
            print(f"✅ Using Gemini model: {try_model}")
            return model
        except Exception as e:
            print(f"⚠️ Model {try_model} not available: {e}")
            continue
    
    raise ValueError(f"Could not initialize any Gemini model. Please check your API key and available models.")
