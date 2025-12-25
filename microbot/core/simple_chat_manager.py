"""
Simple Chat Manager Module
CMD-only chatbot with AI-generated responses
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

# Add legacy code to path
sys.path.append(str(Path(__file__).parent.parent.parent / "legacy_code"))

from google.genai import types

try:
    from ..features.language import LanguageSelector, SupportedLanguage
    from .conversation_handler import ConversationHandler
    from .flow_manager import FlowManager
    from ..features.reminders import ReminderManager, SmartReminderGenerator
    from ..features.notes import NotesManager
    from ..features.voice import VoiceManager
    from ..utils.genai_client import make_client
    from ..utils.persona import build_persona, childify, looks_serious, want_expanded
    from ..utils import ConfigStore
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


class SimpleChatManager:
    """
    Simple CMD-only chat manager with AI-generated responses
    """
    
    def __init__(self, external_reminder_manager=None):
        """Initialize the chat manager
        
        Args:
            external_reminder_manager: Optional external ReminderManager instance
                                      If provided, this will be used instead of creating a new one.
                                      This prevents duplicate scheduler conflicts.
        """
        # Initialize core components
        self.config = ConfigStore()
        self.language_selector = LanguageSelector(
            SupportedLanguage.HINGLISH if self.config.language() == "hinglish" 
            else SupportedLanguage.ENGLISH
        )
        self.conversation_handler = ConversationHandler()
        self.flow_manager = FlowManager(self.config)
        
        # Initialize reminder system
        self.smart_reminder_generator = SmartReminderGenerator()
        if external_reminder_manager:
            # Use external reminder manager (from API server)
            self.reminder_manager = external_reminder_manager
            print("✅ Using shared reminder manager (no duplicate scheduler)")
        else:
            # Create own reminder manager (standalone mode)
            self.reminder_manager = ReminderManager(self._handle_reminder_trigger)
        self.pending_reminders = []
        self._last_user_input = ""
        
        # Initialize notes system
        self.notes_manager = NotesManager()
        
        # Initialize voice system (lazy loading - only if AWS credentials available)
        self.voice_manager = None
        self.voice_mode_active = False
        try:
            self.voice_manager = VoiceManager(config_store=self.config)
            if self.voice_manager.is_available():
                print("✅ Voice system available (STT/TTS ready)")
                self.config.set_aws_configured(True)
            else:
                print("⚠️ Voice system partially available")
        except Exception as e:
            print(f"ℹ️ Voice system not available: {e}")
            print("   To enable voice mode, set MICROBOT_AWS_ACCESS_KEY and MICROBOT_AWS_SECRET_KEY")
            self.voice_manager = None
        
        # Mode states - restore from config (but NEVER auto-start voice mode)
        saved_mode = self.config.get_current_mode()
        self.notes_mode_active = (saved_mode == "notes")
        
        # IMPORTANT: Voice mode should ONLY be started from UI, never auto-start
        self.voice_mode_active = False
        
        # Reset voice mode to normal if it was saved (voice mode is UI-controlled only)
        if saved_mode == "voice":
            self.config.set_mode("normal")
        
        # Initialize AI client with speed optimization
        self.client = make_client()
        self.model = os.getenv("GENAI_MODEL", "gemini-flash-lite-latest")  # Fastest model
        self.fast_model = "gemini-flash-lite-latest"  # Ultra-fast smallest model
        
        # Conversation history
        self.history: List[types.Content] = []
        
        # Chat state
        self.is_running = False
    
    def start_chat(self):
        """Start the interactive chat session"""
        self.is_running = True
        
        # Simple welcome message (no AI delay - instant start like legacy)
        bot_name = self.config.data.get("bot_name", "Microbot")
        language = self.config.language()
        
        if language == "hinglish":
            welcome_msg = f"Hello! I'm {bot_name}. How can I help you today?"
        elif language == "marathi":
            welcome_msg = f"नमस्कार! मी {bot_name} आहे. मी तुम्हाला कशी मदत करू शकतो?"
        else:
            welcome_msg = f"Hello! I'm {bot_name}. How can I help you today?"
        
        print(welcome_msg)
        
        # Start reminder system ONLY if we created our own (not using external)
        if not external_reminder_manager:
            try:
                self.reminder_manager.start()
            except Exception as e:
                print(f"Note: Reminder system not available ({e})")
        else:
            print("ℹ️ Reminder system managed externally (already started)")
        
        # Main chat loop
        self._run_chat_loop()
    
    def stop_chat(self):
        """Stop the chat session"""
        self.is_running = False
        self.reminder_manager.stop()
        
        # Simple goodbye message (no AI delay)
        language = self.config.language()
        if language == "hinglish":
            goodbye_msg = "Bye! Phir milenge!"
        elif language == "marathi":
            goodbye_msg = "अलविदा! पुन्हा भेटू!"
        else:
            goodbye_msg = "Goodbye! Take care!"
        
        print(goodbye_msg)
    
    def _run_chat_loop(self):
        """Main chat interaction loop with voice support"""
        import time
        
        while self.is_running:
            try:
                # Get user input (voice or text)
                if self.voice_mode_active and self.voice_manager:
                    # Voice input - natural conversation flow
                    print("\n🎤 Listening...")
                    success, user_input = self.voice_manager.listen_for_input(timeout=20)
                    
                    if not success:
                        # Check what kind of error
                        error_msg = user_input
                        print(f"   {error_msg}")
                        
                        # If it's timeout (no speech at all), wait a bit before trying again
                        # This prevents rapid looping when no one is speaking
                        if "Timeout" in error_msg or "No speech" in error_msg:
                            time.sleep(2)  # Wait 2 seconds before listening again
                        # If it's unclear speech, someone tried to speak, so try again quickly
                        # No delay needed - they're ready to speak
                        
                        continue
                    
                    # user_input already printed by STT manager
                else:
                    # Text input
                    user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                
                # Check for exit commands
                if user_input.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                    break
                
                # Process the input and get response
                response = self.process_message(user_input)
                
                # Display response
                print(f"\n🤖 {response}")
                
                # Speak response if in voice mode
                if self.voice_mode_active and self.voice_manager:
                    print("🔊 Speaking...")
                    success = self.voice_manager.speak_response(response)
                    if not success:
                        print("   ⚠️ Voice output unavailable (AWS credentials not set)")
                    
                    # Small natural pause after speaking (like a human would)
                    time.sleep(0.5)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                error_msg = f"Error: {e}"
                print(error_msg)
    
    def process_message(self, user_input: str) -> str:
        """Process user message and return response"""
        self._last_user_input = user_input
        
        # Check for pending reminders first
        if self.pending_reminders:
            reminder_response = self._handle_pending_reminders()
            if reminder_response:
                return reminder_response
        
        # Handle flow states (name/password changes, etc.)
        # First check if we're in an active flow
        flow_response = self.flow_manager.handle_flow_input(user_input)
        if flow_response:
            return self._append_reminder_if_due(flow_response)
        
        # Then check if input triggers a new flow
        flow_trigger_response = self.flow_manager.check_flow_triggers(user_input)
        if flow_trigger_response:
            return self._append_reminder_if_due(flow_trigger_response)
        
        # Check for settings view command
        user_lower = user_input.lower()
        if any(phrase in user_lower for phrase in ["show settings", "view settings", "settings dikhao", "current mode"]):
            return self._append_reminder_if_due(self._show_current_settings())
        
        # Check for special deterministic responses
        special_response = self.conversation_handler.get_special_response(user_input)
        if special_response:
            return self._append_reminder_if_due(special_response)
        
        # Handle reminders FIRST - BEFORE language switching
        # This prevents "timer" queries from being misdetected as language commands
        user_lower_check = user_input.lower()
        reminder_keywords = ["remind", "reminder", "याद", "याद दिलाना", "timer", "alarm", "set a timer", "मिनट में", "minutes", "घंटे", "bacha", "बचा", "kitna time", "कितना", "remaining", "left", "बचा है", "time left"]
        
        if any(keyword in user_lower_check for keyword in reminder_keywords):
            reminder_response = self._handle_reminder_requests(user_input)
            if reminder_response:
                return self._append_reminder_if_due(reminder_response)
        
        # Handle language switching - BLOCKED in voice mode (app-only feature)
        language_response = self._handle_language_switching_ai(user_input)
        if language_response:
            return self._append_reminder_if_due(language_response)
        
        # Handle notes mode activation/deactivation and commands
        notes_response = self._handle_notes_mode(user_input)
        if notes_response:
            return self._append_reminder_if_due(notes_response)
        
        # Handle voice mode activation/deactivation and commands
        voice_response = self._handle_voice_mode(user_input)
        if voice_response:
            return self._append_reminder_if_due(voice_response)
        
        # Generate AI response
        ai_response = self._generate_ai_response(user_input)
        
        # CRITICAL: Check if reminder is due and append to response
        return self._append_reminder_if_due(ai_response)
    
    def _handle_pending_reminders(self) -> Optional[str]:
        """Handle any pending reminders"""
        if not self.pending_reminders:
            return None
        
        reminder = self.pending_reminders.pop(0)
        return reminder.get('message', 'You have a reminder!')
    
    def _append_reminder_if_due(self, response: str) -> str:
        """
        Check if any reminder is due (within 10 seconds or overdue) and append to response
        This ensures users get reminded even while having a conversation
        ALSO speaks the reminder via TTS if in voice mode
        """
        try:
            from datetime import datetime
            
            # Get all active reminders (NOT triggered ones)
            storage = self.reminder_manager.get_storage()
            all_reminders = storage.data.get("reminders", [])
            active_reminders = [r for r in all_reminders if r.get("status") == "active"]
            
            if not active_reminders:
                return response
            
            now = datetime.now()
            language = self.config.language()
            
            # Check for reminders that are due (within 10 seconds or overdue)
            due_reminders = []
            for reminder in active_reminders:
                trigger_time = datetime.fromisoformat(reminder["trigger_time"])
                time_diff = (trigger_time - now).total_seconds()
                
                # If reminder is within 10 seconds or already overdue
                if time_diff <= 10:
                    due_reminders.append(reminder)
            
            if not due_reminders:
                return response
            
            # Build reminder notification
            reminder_texts = []
            for reminder in due_reminders:
                task = reminder.get('task', 'reminder')
                reminder_id = reminder.get('id')
                trigger_time = datetime.fromisoformat(reminder["trigger_time"])
                time_diff = (trigger_time - now).total_seconds()
                
                if time_diff <= 0:
                    # Overdue - remind immediately
                    if language == "english":
                        reminder_text = f"REMINDER: {task}"
                    else:
                        reminder_text = f"Yaad dilana: {task}"
                    
                    reminder_texts.append(reminder_text)
                    
                    # Mark as triggered so it doesn't show again
                    storage.mark_reminder_triggered(reminder_id, f"Reminder: {task}")
                    
                    print(f"🔔 REMINDER INJECTED INTO CONVERSATION: {task}")
                else:
                    # Within 10 seconds
                    seconds = int(time_diff)
                    if language == "english":
                        reminder_texts.append(f"By the way, reminder in {seconds}s: {task}")
                    else:
                        reminder_texts.append(f"Waise, {seconds} second mein reminder: {task}")
            
            # Append reminders to response
            if reminder_texts:
                reminder_notice = "\n\n" + "\n".join(reminder_texts)
                return response + reminder_notice
            
            return response
            
        except Exception as e:
            print(f"Error checking due reminders: {e}")
            return response
    
    
    def _handle_language_switching_ai(self, user_input: str) -> Optional[str]:
        """Handle language switching using AI detection - BLOCKED in voice mode"""
        if self.language_selector.is_language_command(user_input):
            # BLOCK language switching in voice mode - must use app
            if self.voice_mode_active:
                current_lang = self.config.language()
                if current_lang == "hinglish":
                    return "मैं अभी Hinglish में बात कर रहा हूं। Language change करने के लिए कृपया app use करें। अभी के लिए मैं Hinglish में ही बात करूंगा।"
                else:
                    return "I'm currently speaking in English. To change my language, please use the app. For now, I'll continue speaking in English only."
            
            # Allow language switching in text mode only
            preference = self.language_selector.detect_language_preference(user_input)
            
            if preference == SupportedLanguage.HINGLISH and not self.language_selector.is_hinglish():
                self.language_selector.set_language(SupportedLanguage.HINGLISH)
                self.config.set_language("hinglish")
                return self._generate_language_switch_message_ai("hinglish")
            elif preference == SupportedLanguage.ENGLISH and not self.language_selector.is_english():
                self.language_selector.set_language(SupportedLanguage.ENGLISH)
                self.config.set_language("english")
                return self._generate_language_switch_message_ai("english")
        
        return None
    
    def _generate_language_switch_message_ai(self, language: str) -> str:
        """Generate language switch confirmation - INSTANT (no AI)"""
        if language == "hinglish":
            return "Theek hai! Ab main Hinglish mein baat karunga."
        elif language == "marathi":
            return "ठीक आहे! आता मी मराठीत बोलेन."
        else:
            return "Okay! I'll speak in English now."
    
    def _handle_reminder_requests(self, user_input: str) -> Optional[str]:
        """Handle reminder creation and status requests - FAST keyword detection"""
        try:
            # Quick keyword-based detection (no AI = faster)
            user_lower = user_input.lower()
            
            # Check if asking about reminder/timer status FIRST (highest priority)
            status_keywords = [
                "kitna", "bacha", "remaining", "left", "कितना", "बचा", 
                "lagega", "लगेगा", "lagta", "time left", "how much time",
                "कितना टाइम", "टाइम बचा", "time remaining", "बचा है",
                "how long", "when will", "kab", "कब"
            ]
            has_status_query = any(word in user_lower for word in status_keywords)
            
            # Also check if it contains "timer" or "reminder" word
            has_timer_word = any(word in user_lower for word in ["timer", "reminder", "याद", "टाइमर", "रिमाइंडर", "remind", "alarm"])
            
            # ENHANCED: Also detect indirect questions about reminders
            asking_about_reminder = (
                has_status_query and has_timer_word
            ) or (
                # Detect questions like "I am asking about the reminder"
                any(phrase in user_lower for phrase in [
                    "asking about", "asking you about", "about the reminder",
                    "about reminder", "reminder ka", "याद के बारे में"
                ])
            )
            
            # If asking about timer/reminder status, check immediately
            if asking_about_reminder:
                print(f"🔔 Checking reminder status for: {user_input}")
                return self.reminder_manager.get_remaining_time_for_reminders(self.config.language())
            
            # Expanded reminder keywords for better detection
            reminder_keywords = [
                # English
                "remind", "reminder", "alarm", "timer", "set a timer", "set timer",
                "in minutes", "in hours", "after", "later",
                # Hindi/Hinglish
                "याद", "याद दिलाना", "रिमाइंडर", "टाइमर", "मिनट", "घंटे",
                "baad", "mein", "minute", "minutes", "hour", "hours",
                # Common patterns
                "set a", "बाद में"
            ]
            
            # More aggressive reminder detection
            has_reminder_keyword = any(word in user_lower for word in reminder_keywords)
            has_time_reference = any(char.isdigit() for char in user_input)  # Contains numbers
            
            if has_reminder_keyword or has_time_reference:
                # Check for list/show queries
                if any(word in user_lower for word in ["list", "show", "sabhi", "all", "सभी", "दिखाओ"]):
                    return self.reminder_manager.list_reminders(self.config.language())
                # Check for cancel queries
                elif any(word in user_lower for word in ["cancel", "stop", "band", "khatam", "बंद", "रद्द"]):
                    cancel_success, cancel_message = self.reminder_manager.cancel_reminder(user_input)
                    return cancel_message
                else:
                    # Try to create reminder
                    success, message = self.reminder_manager.add_reminder(user_input, self.config.language())
                    if success:
                        return message
                    # If failed, let AI handle it
            
        except Exception as e:
            print(f"❌ Error handling reminder request: {e}")
        
        # Let AI handle if no specific reminder action detected
        return None
    
    def _generate_ai_response(self, user_input: str) -> str:
        """
        Generate AI response - ULTRA FAST (exactly like legacy code)
        
        STRICT LANGUAGE ENFORCEMENT:
        - Bot ALWAYS responds in configured language (English or Hinglish)
        - Never switches language based on user input
        - Language changes only through app/config
        
        Speed Optimizations (legacy-inspired):
        - Use legacy build_persona() for optimal instructions
        - MINIMAL context (4-8 messages only)
        - Direct response (no streaming)
        - Gemini Flash Lite
        - No verbose config
        """
        try:
            language = self.config.language()
            
            # Use legacy persona builder for MAXIMUM speed and quality
            # This is the exact persona from legacy code (lines 188-191)
            base_persona = build_persona(language)
            
            # STRICT LANGUAGE ENFORCEMENT: Add explicit instruction
            if language == "hinglish":
                persona = base_persona + " IMPORTANT: You MUST respond ONLY in Hinglish (Hindi-English mix). Never switch to pure English or pure Hindi. Maintain Hinglish throughout the conversation regardless of what language the user speaks in."
            else:
                persona = base_persona + " IMPORTANT: You MUST respond ONLY in English. Never switch to Hindi or Hinglish. Maintain English throughout the conversation regardless of what language the user speaks in."
            
            # TECHNICAL QUESTION HANDLING: Detect and respond appropriately
            user_lower = user_input.lower()
            technical_keywords = [
                # Question words
                "what is", "how does", "how to", "why does", "explain", "define", "meaning of",
                # Technical domains
                "code", "programming", "algorithm", "function", "api", "database", "server",
                "python", "javascript", "java", "c++", "html", "css", "sql",
                "machine learning", "ai", "artificial intelligence", "neural network",
                "computer", "software", "hardware", "network", "internet",
                "error", "bug", "debug", "compile", "syntax", "variable",
                # Hinglish technical
                "kaise", "kya hai", "samjhao", "bataiye", "explain karo"
            ]
            
            is_technical_question = any(keyword in user_lower for keyword in technical_keywords)
            
            if is_technical_question:
                # For technical questions: SHORT, direct answer, NO follow-up questions
                if language == "hinglish":
                    persona += "\n\nIMPORTANT INSTRUCTION: User ne technical question pucha hai. Answer SHORT aur DIRECT do (1-2 sentences maximum). Follow-up question BILKUL mat poocho. Bas answer do aur ruk jao."
                else:
                    persona += "\n\nIMPORTANT INSTRUCTION: User asked a technical question. Give a SHORT and DIRECT answer (1-2 sentences maximum). DO NOT ask follow-up questions. Just answer and stop."
            
            
            # Check if user wants expanded response (legacy line 190)
            if want_expanded(user_input):
                persona += " Give a more complete answer in one message, but keep it clear and focused."
            
            # Create system message (legacy style)
            system_msg = types.Content(role="user", parts=[types.Part.from_text(text=persona)])
            
            # Build contents list with MINIMAL context for SPEED
            contents: List[types.Content] = [system_msg]
            
            # ULTRA MINIMAL history for MAXIMUM speed
            if self.voice_mode_active:
                # Voice: NO HISTORY AT ALL for instant responses!
                recent_history = []
            else:
                # Text: Only last 2 messages (1 exchange) for speed
                recent_history = self.history[-2:] if len(self.history) > 2 else self.history
            
            contents.extend(recent_history)
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))
            
            # Generate response (legacy style - minimal config, line 200-205)
            try:
                # Determine max tokens based on query type
                user_lower = user_input.lower()
                
                # Technical questions: VERY SHORT (just the answer)
                if is_technical_question:
                    max_tokens = 30  # ULTRA-short: 1 sentence only
                
                # Long-form content: Allow more tokens
                elif any(keyword in user_lower for keyword in [
                    "story", "kahani", "कहानी", "tell me about", 
                    "समझाओ", "बताओ", "detail", "poem", "कविता",
                    "rhyme", "song", "sing"
                ]):
                    max_tokens = 60  # Short stories
                
                # Casual conversation: Short with follow-up
                else:
                    max_tokens = 20  # Short response + question (15-20 words)
                
                response = self.client.models.generate_content(
                    model=self.fast_model,  # Use configured fast model
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=2.0,  # MAXIMUM temperature = FASTEST generation
                        max_output_tokens=max_tokens,
                        top_k=1,  # Greedy decoding = fastest
                        top_p=1.0,  # Full probability range for speed
                        candidate_count=1,  # Only one candidate for speed
                    ),
                )
                final_text = response.text.strip()
                
                if not final_text:
                    raise Exception("Empty response from AI")
                    
            except Exception as api_error:
                error_str = str(api_error)
                
                # Check if it's a rate limit error
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                    print(f"⚠️ Rate Limit: API quota exceeded. Please wait 30 seconds.")
                    if self.config.language() == "hinglish":
                        final_text = "⚠️ Thoda slow down karo! API limit exceed ho gaya. 30 second wait karo, phir baat karte hain."
                    else:
                        final_text = "⚠️ Please slow down! API rate limit exceeded. Wait 30 seconds and try again."
                else:
                    print(f"❌ AI API Error: {api_error}")
                    # Fallback to simple response based on user input
                    if self.config.language() == "hinglish":
                        final_text = "Thoda technical issue aa raha hai, but main yahan hoon! Kya baat karni hai?"
                    else:
                        final_text = "Having a small technical issue, but I'm here! What would you like to talk about?"
            
            # Apply childification like legacy (only for hinglish, not serious queries)
            # Legacy code lines 221-222
            if not looks_serious(user_input):
                final_text = childify(final_text, self.config.language())
            
            # Update conversation history (legacy style)
            self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))
            self.history.append(types.Content(role="model", parts=[types.Part.from_text(text=final_text)]))
            
            # ULTRA SPEED: Minimal history for instant responses
            # Keep only last 4 messages (2 exchanges) for maximum speed
            max_history = 4
            
            if len(self.history) > max_history:
                # Remove oldest messages to keep history small and fast
                self.history = self.history[-max_history:]
            
            return final_text
            
        except Exception as e:
            # Fallback response
            return f"I'm having trouble understanding right now. Could you try again? (Error: {str(e)})"
    
    def _create_summarized_context(self, history: List[types.Content]) -> List[types.Content]:
        """Create a summarized context by condensing older messages"""
        try:
            # Keep last 40 messages (20 exchanges) in full detail
            recent_messages = history[-40:]
            
            # If we have older messages, create a summary
            if len(history) > 40:
                older_messages = history[:-40]
                
                # Extract key information from older messages
                summary_parts = []
                emotional_keywords = []
                important_topics = []
                
                for msg in older_messages:
                    if hasattr(msg, 'parts') and msg.parts:
                        text = msg.parts[0].text.lower()
                        
                        # Extract emotional context
                        emotions = ['sad', 'happy', 'upset', 'problem', 'dukhi', 'khush', 'pareshan', 
                                   'girlfriend', 'boyfriend', 'friend', 'family', 'attacked', 'police']
                        for emotion in emotions:
                            if emotion in text and emotion not in emotional_keywords:
                                emotional_keywords.append(emotion)
                                if len(emotional_keywords) < 5:  # Keep top 5
                                    summary_parts.append(text[:80])
                
                # Build concise summary
                if emotional_keywords:
                    summary_text = f"Previous context: Discussed {', '.join(emotional_keywords[:5])}."
                else:
                    summary_text = "Previous conversation covered various personal and general topics."
                
                if summary_parts:
                    # Add 1-2 key emotional excerpts
                    summary_text += f" Key points: {'; '.join(summary_parts[:2])}"
                
                # Create summary message
                summary_msg = types.Content(
                    role="user", 
                    parts=[types.Part.from_text(text=f"[Summary: {summary_text[:200]}...]")]
                )
                
                print(f"📝 Context summarized: {len(older_messages)} old messages → 1 summary + {len(recent_messages)} recent")
                
                # Return summary + recent messages
                return [summary_msg] + recent_messages
            
            return recent_messages
            
        except Exception as e:
            print(f"❌ Error creating summary: {e}")
            # Fallback: just keep recent messages
            return history[-40:] if len(history) > 40 else history
    
    def _handle_reminder_trigger(self, reminder_data: Dict[str, Any]):
        """Handle when a reminder is triggered"""
        try:
            # Generate simple, reliable reminder message
            task = reminder_data.get('task', 'reminder')
            language = self.config.language()
            
            if language == "hinglish":
                message = f"Yaad dilana: {task}!"
            else:
                message = f"Reminder: {task}!"
            
            # Add to pending reminders for display
            self.pending_reminders.append({"message": message, "data": reminder_data})
            
            # Print immediately for user to see
            print(f"\n{message}")
            
        except Exception as e:
            print(f"❌ Error in reminder callback: {e}")
            # Ultimate fallback
            print(f"Reminder: {reminder_data.get('task', 'Something important!')}")
    
    
    def _show_current_settings(self) -> str:
        """Display current bot settings"""
        settings = self.config.get_all_settings()
        language = self.config.language()
        
        if language == "english":
            return f"""⚙️ Current Settings:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bot Name: {settings['bot_name']}
Language: {settings['language'].title()}
Current Mode: {settings['current_mode'].title()}
Password Protected: {'Yes' if settings['has_password'] else 'No'}
Security Questions: {'Yes' if settings['has_security_questions'] else 'No'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        else:
            mode_hindi = {
                "normal": "Normal",
                "notes": "Notes",
                "voice": "Voice"
            }
            return f"""⚙️ Current Settings:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bot Name: {settings['bot_name']}
Language: {settings['language'].title()}
Current Mode: {mode_hindi.get(settings['current_mode'], settings['current_mode'])}
Password: {'Hai' if settings['has_password'] else 'Nahi'}
Security Questions: {'Hai' if settings['has_security_questions'] else 'Nahi'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    
    def _handle_notes_mode(self, user_input: str) -> Optional[str]:
        """Handle notes mode activation/deactivation and commands"""
        try:
            language = self.config.language()
            user_lower = user_input.lower()
            
            # Block mode switching in voice mode (only allow exit)
            notes_activation_phrases = [
                "switch to notes",
                "notes mode activate",
                "notes mode start",
                "activate notes mode",
                "start notes mode"
            ]
            
            if self.voice_mode_active and any(phrase in user_lower for phrase in notes_activation_phrases):
                if language == "english":
                    return "Please switch modes using the phone app."
                else:
                    return "Kripya phone app se mode switch karein."
            
            # Check if user wants to exit notes mode
            if self.notes_mode_active:
                if any(word in user_lower for word in ["exit notes", "notes band", "notes mode band", "close notes"]):
                    self.notes_mode_active = False
                    self.config.set_mode("normal")
                    return "Notes mode deactivated" if language == "english" else "Notes mode band ho gaya"
                
                # Process notes command
                return self._handle_notes_requests(user_input)
            
            # Check if user wants to activate notes mode (ONLY explicit activation)
            if any(phrase in user_lower for phrase in notes_activation_phrases):
                self.notes_mode_active = True
                self.config.set_mode("notes")
                if language == "english":
                    return """Notes Mode Activated!

Commands:
- Add note: "note this: [content]"
- Show notes: "show notes"
- Search: "search notes [query]"
- Add journal: "journal: [entry]"
- Show journal: "show journal"
- Exit: "exit notes mode"
"""
                else:
                    return """Notes Mode Activate Ho Gaya!

Commands:
- Note add: "note this: [content]"
- Notes dikhao: "show notes"
- Search: "search notes [query]"
- Journal: "journal: [entry]"
- Exit: "exit notes mode"
"""
        
        except Exception as e:
            print(f"❌ Error handling notes mode: {e}")
        
        return None
    
    def _handle_notes_requests(self, user_input: str) -> Optional[str]:
        """Handle notes and journal requests using AI detection (optimized for speed)"""
        try:
            # Quick keyword check first (faster than AI)
            user_lower = user_input.lower()
            language = self.config.language()
            
            # Fast checks for common commands
            if any(word in user_lower for word in ["note", "yaad", "likh", "write", "journal"]):
                # Use quick AI prompt to determine intent
                prompt = f'User: "{user_input}". Intent: ADD_NOTE, SHOW_NOTES, SEARCH_NOTES, ADD_JOURNAL, SHOW_JOURNAL, or NONE?'
                
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                
                intent = response.text.strip().upper()
                
                if "ADD_NOTE" in intent:
                    # Extract note content using AI
                    extract_prompt = f'Extract the note content from: "{user_input}". Return only the note text.'
                    extract_response = self.client.models.generate_content(
                        model=self.model,
                        contents=extract_prompt
                    )
                    content = extract_response.text.strip()
                    success, message = self.notes_manager.add_note(content)
                    return message
                
                elif "SHOW_NOTES" in intent:
                    recent = self.notes_manager.get_recent_notes(limit=5)
                    return self.notes_manager.format_notes_for_voice(recent, language)
                
                elif "SEARCH_NOTES" in intent:
                    # Extract search query
                    search_prompt = f'Extract search keywords from: "{user_input}". Return only keywords.'
                    search_response = self.client.models.generate_content(
                        model=self.model,
                        contents=search_prompt
                    )
                    query = search_response.text.strip()
                    results = self.notes_manager.search_notes(query)
                    if results:
                        return self.notes_manager.format_notes_for_voice(results[:3], language)
                    else:
                        return "No matching notes found." if language == "english" else "Koi matching notes nahi mile."
                
                elif "ADD_JOURNAL" in intent:
                    # Extract journal content
                    extract_prompt = f'Extract the journal entry from: "{user_input}". Return only the entry text.'
                    extract_response = self.client.models.generate_content(
                        model=self.model,
                        contents=extract_prompt
                    )
                    content = extract_response.text.strip()
                    success, message = self.notes_manager.add_journal_entry(content)
                    return message
                
                elif "SHOW_JOURNAL" in intent:
                    recent = self.notes_manager.get_recent_journal(limit=3)
                    return self.notes_manager.format_journal_for_voice(recent, language)
        
        except Exception as e:
            print(f"❌ Error handling notes request: {e}")
        
        return None
    
    
    def _handle_voice_mode(self, user_input: str) -> Optional[str]:
        """Handle voice mode activation/deactivation and voice change commands"""
        try:
            language = self.config.language()
            user_lower = user_input.lower()
            
            # Check if user wants to exit voice mode
            if self.voice_mode_active:
                if any(word in user_lower for word in ["exit voice", "voice band", "voice mode band", "close voice", "stop voice"]):
                    self.voice_mode_active = False
                    self.config.set_mode("normal")
                    if self.voice_manager:
                        self.voice_manager.deactivate_voice_mode()
                    return "Voice mode deactivated" if language == "english" else "Voice mode band ho gaya"
            
            # Check if user wants to change voice
            voice_change_patterns = ["change voice to", "voice badlo", "set voice to", "use voice"]
            if any(pattern in user_lower for pattern in voice_change_patterns):
                # Extract voice name using AI or simple matching
                for voice_name in ["matthew", "justin", "salli", "aditi"]:
                    if voice_name in user_lower:
                        if self.voice_manager:
                            success, message = self.voice_manager.set_voice(voice_name)
                            
                            # Update config based on language
                            if language in ["hinglish", "marathi", "hindi"]:
                                self.config.set_hinglish_voice(voice_name)
                            else:
                                self.config.set_english_voice(voice_name)
                            
                            return message
                        else:
                            return "Voice system not available" if language == "english" else "Voice system available nahi hai"
                
                # No voice name found
                return "Please specify a voice: matthew, justin, salli, or aditi" if language == "english" else "Voice specify kariye: matthew, justin, salli, ya aditi"
            
            # Check if user wants to activate voice mode (ONLY explicit activation)
            voice_activation_phrases = [
                "activate voice mode",
                "voice mode activate",
                "voice mode start",
                "start voice mode",
                "enable voice mode",
                "voice mode on"
            ]
            
            if any(phrase in user_lower for phrase in voice_activation_phrases):
                if not self.voice_manager:
                    return "Voice system not available. Please configure AWS credentials." if language == "english" else "Voice system available nahi hai. AWS credentials configure kariye."
                
                # Activate voice mode
                success, message = self.voice_manager.activate_voice_mode(language)
                
                if success:
                    self.voice_mode_active = True
                    self.config.set_mode("voice")
                    # Auto-set voice based on language
                    self.voice_manager.update_language(language)
                
                return message
        
        except Exception as e:
            print(f"❌ Error handling voice mode: {e}")
        
        return None
    
