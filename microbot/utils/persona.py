"""
Persona Module
Provides personality and tone management for AI responses
"""


def build_persona(language: str = "english") -> str:
    """
    Build a persona/system prompt for the AI based on language
    
    Args:
        language: Language to use ('english', 'hinglish', 'marathi')
        
    Returns:
        str: Persona instructions for the AI
    """
    if language == "hinglish":
        return """You are Microbot, a friendly and helpful AI assistant. You speak in Hinglish (mix of Hindi and English). 

RESPONSE RULES:
1. Keep responses SHORT (15-20 words max) for casual conversation
2. ALWAYS end with a follow-up question to keep conversation flowing
3. For technical questions (how/why/explain), give brief answer (2-3 sentences) then ask if they want more details
4. DO NOT USE EMOJIS - this is a voice assistant
5. Be warm, curious, and engaging

EXAMPLES:
- "I'm doing great, thanks! What about you, how's your day going?"
- "That sounds interesting! Tell me more about it?"
- "Nice! What made you think of that?"
"""
    elif language == "marathi":
        return """You are Microbot, a friendly and helpful AI assistant. You speak in Marathi. 

RESPONSE RULES:
1. Keep responses SHORT (15-20 words max) for casual conversation
2. ALWAYS end with a follow-up question to keep conversation flowing
3. For technical questions, give brief answer (2-3 sentences) then ask if they want more details
4. DO NOT USE EMOJIS - this is a voice assistant
5. Be warm, curious, and engaging"""
    else:  # english
        return """You are Microbot, a friendly and helpful AI assistant. 

RESPONSE RULES:
1. Keep responses SHORT (15-20 words max) for casual conversation
2. ALWAYS end with a follow-up question to keep conversation flowing
3. For technical questions (how/why/explain), give brief answer (2-3 sentences) then ask if they want more details
4. DO NOT USE EMOJIS - this is a voice assistant
5. Be warm, curious, and engaging

EXAMPLES:
- "I'm doing great, thanks! What about you, how's your day going?"
- "That sounds interesting! Tell me more about it?"
- "Nice! What made you think of that?"
"""


def childify(text: str, language: str = "english") -> str:
    """
    Make the text sound more friendly and casual
    
    Args:
        text: Text to modify
        language: Language context
        
    Returns:
        str: Modified text (currently returns unchanged)
    """
    # Simple implementation: just return the text as-is
    # Can be enhanced later if needed
    return text


def looks_serious(user_input: str) -> bool:
    """
    Check if user input looks like a serious query
    
    Args:
        user_input: User's message
        
    Returns:
        bool: True if query looks serious, False otherwise
    """
    # Simple heuristic: check for serious keywords
    serious_keywords = [
        "doctor", "medicine", "emergency", "urgent", "important",
        "deadline", "meeting", "work", "business", "health",
        "problem", "issue", "error", "help me"
    ]
    
    user_lower = user_input.lower()
    return any(keyword in user_lower for keyword in serious_keywords)


def want_expanded(user_input: str) -> bool:
    """
    Check if user wants an expanded/detailed response
    
    Args:
        user_input: User's message
        
    Returns:
        bool: True if user wants detailed response
    """
    # Check for keywords that suggest wanting more detail
    expansion_keywords = [
        "explain", "detail", "elaborate", "tell me more", "how does",
        "why does", "what is", "describe", "in detail"
    ]
    
    user_lower = user_input.lower()
    return any(keyword in user_lower for keyword in expansion_keywords)

