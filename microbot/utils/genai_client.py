"""
Gemini AI Client Module
Provides a centralized client for Google Gemini AI
"""

import os
from google import genai


def make_client():
    """
    Create and return a Google Gemini AI client
    
    Returns:
        genai.Client: Configured Gemini AI client
        
    Raises:
        ValueError: If API key is not found in environment variables
    """
    # Get API key from environment variables
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not key:
        raise ValueError(
            "Gemini API key not found! Please set GEMINI_API_KEY or GOOGLE_API_KEY "
            "in your .env file. Get your free API key from: "
            "https://makersuite.google.com/app/apikey"
        )
    
    # Create and return the client
    client = genai.Client(api_key=key)
    return client

