"""
Smart Reminder Generator Module
Uses Gemini AI to generate personalized, contextual reminder messages
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from ...utils.genai_client import make_client
    from .reminder_storage import ReminderStorage
except ImportError:
    from reminder_storage import ReminderStorage
    from microbot.utils.genai_client import make_client


class SmartReminderGenerator:
    """Generates personalized reminder messages using Gemini AI"""
    
    def __init__(self):
        self.client = make_client()
        self.model = "gemini-flash-lite-latest"  # Correct model name
        
        # Message templates for fallback
        self.fallback_templates = {
            "english": {
                "general": "⏰ Reminder: Time to {task}! Hope you're ready! 😊",
                "urgent": "🚨 Important reminder: {task} - this is time-sensitive!",
                "gentle": "💭 Just a gentle reminder: {task}. Take your time! 🌟",
                "friendly": "👋 Hey! Remember you wanted me to remind you to {task}!"
            },
            "hinglish": {
                "general": "⏰ Yaad dilane aaya hun: {task} ka time ho gaya! Ready ho? 😊",
                "urgent": "🚨 Important reminder: {task} - ye urgent hai!",
                "gentle": "💭 Pyaar se yaad dila raha hun: {task}. Tension mat lo! 🌟",
                "friendly": "👋 Arre! Yaad hai na - {task} karna tha!"
            }
        }
    
    def generate_reminder_message(self, reminder: Dict[str, Any], 
                                current_context: str = "", 
                                conversation_history: list = None) -> str:
        """Generate a smart, contextual reminder message with robust error handling"""
        
        # Extract reminder details with safe defaults
        task = reminder.get("task", "reminder")
        language = reminder.get("context", {}).get("language", "hinglish")
        urgency = reminder.get("context", {}).get("urgency", "medium")
        
        # Try simple fallback first (faster and more reliable)
        try:
            return self._generate_fallback_message(task, language, urgency)
        except Exception as e:
            print(f"❌ Error generating reminder message: {e}")
            # Ultimate fallback
            if language.lower() == "english":
                return f"⏰ Reminder: {task}"
            else:
                return f"⏰ Yaad dilana: {task}"
    
    def _build_context_info(self, reminder: Dict[str, Any], 
                          current_context: str, 
                          conversation_history: list) -> Dict[str, Any]:
        """Build context information for better message generation"""
        
        # Time context
        trigger_time = datetime.fromisoformat(reminder["trigger_time"])
        now = datetime.now()
        delay_minutes = int((now - trigger_time).total_seconds() / 60)
        
        # Conversation context
        is_in_conversation = bool(current_context.strip())
        conversation_topic = self._extract_conversation_topic(current_context)
        
        return {
            "delay_minutes": delay_minutes,
            "is_in_conversation": is_in_conversation,
            "conversation_topic": conversation_topic,
            "current_user_input": current_context,
            "time_of_day": self._get_time_of_day(),
            "reminder_age": self._get_reminder_age(reminder)
        }
    
    def _generate_with_gemini(self, task: str, language: str, urgency: str, 
                            category: str, context: Dict[str, Any]) -> Optional[str]:
        """Generate reminder message using Gemini AI"""
        
        try:
            # Build prompt based on language
            if language.lower() == "english":
                prompt = self._build_english_prompt(task, urgency, category, context)
            else:
                prompt = self._build_hinglish_prompt(task, urgency, category, context)
            
            # Generate with Gemini
            from google.genai import types
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
            )
            
            if response and response.text:
                # Clean and format the response
                message = response.text.strip()
                
                # Add appropriate emoji if not present
                if not any(emoji in message for emoji in ["⏰", "🔔", "💭", "👋", "🚨"]):
                    message = "⏰ " + message
                
                return message
            
        except Exception as e:
            print(f"❌ Gemini generation error: {e}")
        
        return None
    
    def _build_english_prompt(self, task: str, urgency: str, category: str, 
                            context: Dict[str, Any]) -> str:
        """Build English prompt for Gemini"""
        
        base_prompt = f"""You are a friendly, caring AI assistant reminding someone about a task. 

Task to remind about: "{task}"
Urgency level: {urgency}
Category: {category}
Time of day: {context['time_of_day']}

Context:
- User is currently {"in conversation" if context['is_in_conversation'] else "not chatting"}
- Current topic: {context.get('conversation_topic', 'none')}
- Reminder delay: {context['delay_minutes']} minutes late

Create a natural, caring reminder message that:
1. Feels personal and friendly (like a caring friend)
2. Integrates smoothly with ongoing conversation if applicable
3. Matches the urgency level ({urgency})
4. Is concise but warm (1-2 sentences max)
5. Uses appropriate tone for the time of day
6. NO emojis (I'll add them)

Examples of good style:
- "Just a gentle reminder - time to call mom! Hope she's doing well."
- "Hey! Your meeting starts in 2 minutes. You've got this!"
- "Medicine time! Don't forget to take it with water."

Generate ONLY the reminder message, nothing else:"""
        
        return base_prompt
    
    def _build_hinglish_prompt(self, task: str, urgency: str, category: str, 
                             context: Dict[str, Any]) -> str:
        """Build Hinglish prompt for Gemini"""
        
        base_prompt = f"""You are a friendly, caring AI assistant (like a helpful friend) reminding someone about a task in Hinglish.

Task to remind about: "{task}"
Urgency level: {urgency}
Category: {category}
Time of day: {context['time_of_day']}

Context:
- User is currently {"in conversation" if context['is_in_conversation'] else "not chatting"}
- Current topic: {context.get('conversation_topic', 'none')}
- Reminder delay: {context['delay_minutes']} minutes late

Create a natural, caring reminder message in Hinglish that:
1. Feels personal and friendly (jaise koi dost yaad dila raha ho)
2. Mixes Hindi and English naturally
3. Matches the urgency level ({urgency})
4. Is concise but warm (1-2 sentences max)
5. Uses appropriate tone for time of day
6. NO emojis (main add kar dunga)

Examples of good Hinglish style:
- "Yaad dilane aaya hun - mom ko call karne ka time ho gaya!"
- "Arre! Meeting 2 minute mein start hone wali hai. All the best!"
- "Medicine lene ka time ho gaya. Paani ke saath lena mat bhoolna."

Generate ONLY the reminder message in Hinglish, nothing else:"""
        
        return base_prompt
    
    def _generate_fallback_message(self, task: str, language: str, urgency: str) -> str:
        """Generate fallback message using templates"""
        
        lang_key = "english" if language.lower() == "english" else "hinglish"
        urgency_key = urgency if urgency in ["urgent", "gentle", "friendly"] else "general"
        
        template = self.fallback_templates[lang_key][urgency_key]
        return template.format(task=task)
    
    def _extract_conversation_topic(self, current_context: str) -> str:
        """Extract main topic from current conversation context"""
        if not current_context:
            return "none"
        
        # Simple keyword extraction
        context_lower = current_context.lower()
        
        topics = {
            "weather": ["weather", "rain", "sunny", "cold", "hot", "mausam"],
            "food": ["food", "eat", "hungry", "khana", "dinner", "lunch"],
            "work": ["work", "office", "meeting", "project", "kaam"],
            "health": ["health", "medicine", "doctor", "sick", "sehat"],
            "family": ["family", "mom", "dad", "brother", "sister", "ghar"],
            "entertainment": ["movie", "song", "music", "game", "fun", "maza"]
        }
        
        for topic, keywords in topics.items():
            if any(keyword in context_lower for keyword in keywords):
                return topic
        
        return "general"
    
    def _get_time_of_day(self) -> str:
        """Get current time of day description"""
        hour = datetime.now().hour
        
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
    
    def _get_reminder_age(self, reminder: Dict[str, Any]) -> str:
        """Get how old the reminder is"""
        created_at = datetime.fromisoformat(reminder["created_at"])
        age_hours = (datetime.now() - created_at).total_seconds() / 3600
        
        if age_hours < 1:
            return "recent"
        elif age_hours < 24:
            return "today"
        else:
            return "old"
    
    def generate_confirmation_message(self, task: str, trigger_time: datetime, 
                                    language: str = "hinglish") -> str:
        """Generate confirmation message when reminder is set"""
        
        try:
            # Calculate time until reminder
            now = datetime.now()
            time_diff = trigger_time - now
            
            # Build confirmation prompt
            if language.lower() == "english":
                prompt = f"""Generate a friendly confirmation message for setting a reminder.

Task: "{task}"
Time until reminder: {self._format_time_diff(time_diff)}
Language: English

Create a short, friendly confirmation (1 sentence) that:
1. Confirms the reminder is set
2. Mentions when it will trigger
3. Sounds encouraging and helpful
4. NO emojis (I'll add them)

Example: "Reminder set! I'll remind you to call John in 5 minutes."

Generate ONLY the confirmation message:"""
            else:
                prompt = f"""Generate a friendly confirmation message for setting a reminder in Hinglish.

Task: "{task}"
Time until reminder: {self._format_time_diff(time_diff)}
Language: Hinglish

Create a short, friendly confirmation (1 sentence) that:
1. Confirms the reminder is set
2. Mentions when it will trigger  
3. Sounds encouraging and helpful
4. Mix Hindi and English naturally
5. NO emojis (main add kar dunga)

Example: "Reminder set kar diya! 5 minute mein call John ka yaad dila dunga."

Generate ONLY the confirmation message in Hinglish:"""
            
            from google.genai import types
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
            )
            
            if response and response.text:
                message = response.text.strip()
                return "✅ " + message
            
        except Exception as e:
            print(f"❌ Error generating confirmation: {e}")
        
        # Fallback confirmation
        if language.lower() == "english":
            return f"✅ Reminder set! I'll remind you to {task} {self._format_time_diff(time_diff)}."
        else:
            return f"✅ Reminder set kar diya! {self._format_time_diff(time_diff)} {task} ka yaad dila dunga."
    
    def _format_time_diff(self, time_diff) -> str:
        """Format time difference in natural language"""
        total_seconds = int(time_diff.total_seconds())
        
        if total_seconds < 60:
            return "in a few seconds"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"in {minutes} minute{'s' if minutes != 1 else ''}"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"in {hours} hour{'s' if hours != 1 else ''}"
        else:
            days = total_seconds // 86400
            return f"in {days} day{'s' if days != 1 else ''}"
