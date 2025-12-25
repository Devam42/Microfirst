"""
Time Parser Module
Parses natural language time expressions into datetime objects
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta, time
from typing import Optional, Tuple
from dateutil.relativedelta import relativedelta


class TimeParser:
    """Parses natural language time expressions"""
    
    def __init__(self):
        # Time patterns for different languages
        self.patterns = {
            # Relative time patterns
            "minutes": [
                r"(\d+)\s*(?:minute|min|minutes)\s*(?:later|baad|mein)?",
                r"(?:in|after)\s*(\d+)\s*(?:minute|min|minutes)",
                r"(\d+)\s*(?:minute|min)\s*(?:baad|mein)"
            ],
            "hours": [
                r"(\d+)\s*(?:hour|hours|ghante|ghanta)\s*(?:later|baad|mein)?",
                r"(?:in|after)\s*(\d+)\s*(?:hour|hours)",
                r"(\d+)\s*(?:ghante|ghanta)\s*(?:baad|mein)"
            ],
            "days": [
                r"(\d+)\s*(?:day|days|din)\s*(?:later|baad|mein)?",
                r"(?:in|after)\s*(\d+)\s*(?:day|days)",
                r"(\d+)\s*din\s*(?:baad|mein)"
            ],
            # Specific time patterns
            "time_today": [
                r"(?:at|@)\s*(\d{1,2})(?::(\d{2}))?\s*(?:am|pm|AM|PM)?",
                r"(\d{1,2})(?::(\d{2}))?\s*(?:am|pm|AM|PM)\s*(?:today|aaj)?",
                r"(?:aaj|today)\s*(\d{1,2})(?::(\d{2}))?\s*(?:baje|am|pm)"
            ],
            # Tomorrow patterns
            "tomorrow": [
                r"(?:tomorrow|kal)\s*(?:at|@)?\s*(\d{1,2})(?::(\d{2}))?\s*(?:am|pm|AM|PM|baje)?",
                r"kal\s*(?:subah|morning|shaam|evening)?\s*(\d{1,2})(?::(\d{2}))?\s*(?:baje|am|pm)?"
            ],
            # Day names
            "weekdays": [
                r"(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
                r"(?:agle\s+)?(somwar|mangalwar|budhwar|gurwar|shukrwar|shaniwar|raviwar)"
            ]
        }
        
        # Day name mappings
        self.day_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
            "somwar": 0, "mangalwar": 1, "budhwar": 2, "gurwar": 3,
            "shukrwar": 4, "shaniwar": 5, "raviwar": 6
        }
        
        # Time keywords
        self.time_keywords = {
            "morning": (6, 0), "subah": (6, 0),
            "afternoon": (14, 0), "dopahar": (14, 0),
            "evening": (18, 0), "shaam": (18, 0),
            "night": (21, 0), "raat": (21, 0)
        }
    
    def parse_time(self, text: str) -> Optional[datetime]:
        """Parse natural language time expression with fast fallback"""
        # Try fast pattern matching first
        result = self._parse_time_fallback(text)
        if result:
            return result
        
        # Only use AI for complex cases
        try:
            current_time = datetime.now()
            
            # Simplified AI prompt for speed
            prompt = f"""Time now: {current_time.strftime('%H:%M')}. Parse: "{text}". Format: YYYY-MM-DD HH:MM:SS or NONE"""

            # Import AI client
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent.parent / "legacy_code"))
            from .genai_client import make_client
            
            client = make_client()
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt
            )
            
            result = response.text.strip()
            
            if result == "NONE":
                return None
            
            # Parse the AI response
            try:
                return datetime.strptime(result, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return None
                
        except Exception:
            return None
    
    def _parse_time_fallback(self, text: str) -> Optional[datetime]:
        """Fast fallback time parsing"""
        now = datetime.now()
        text_lower = text.lower()
        
        import re
        
        # Handle common Hindi/Hinglish patterns quickly
        # "2 min baad", "5 minute mein", etc.
        patterns = [
            (r'(\d+)\s*min(?:ute)?\s*(?:baad|mein|later)', lambda m: int(m.group(1))),
            (r'(?:do|two)\s*min(?:ute)?\s*(?:baad|mein)', lambda m: 2),
            (r'(?:teen|three)\s*min(?:ute)?\s*(?:baad|mein)', lambda m: 3),
            (r'(?:char|four)\s*min(?:ute)?\s*(?:baad|mein)', lambda m: 4),
            (r'(?:paanch|five)\s*min(?:ute)?\s*(?:baad|mein)', lambda m: 5),
        ]
        
        for pattern, extract_func in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    minutes = extract_func(match)
                    return now + timedelta(minutes=minutes)
                except:
                    continue
        
        # Handle hours
        hour_match = re.search(r'(\d+)\s*(?:hour|ghante)', text_lower)
        if hour_match:
            try:
                hours = int(hour_match.group(1))
                return now + timedelta(hours=hours)
            except:
                pass
        
        # Handle tomorrow
        if "tomorrow" in text_lower or "kal" in text_lower:
            return now + timedelta(days=1)
        
        return None
    
    def _parse_relative_time(self, text: str) -> Optional[datetime]:
        """Parse relative time expressions like 'in 5 minutes'"""
        now = datetime.now()
        
        # Minutes
        for pattern in self.patterns["minutes"]:
            match = re.search(pattern, text)
            if match:
                minutes = int(match.group(1))
                return now + timedelta(minutes=minutes)
        
        # Hours
        for pattern in self.patterns["hours"]:
            match = re.search(pattern, text)
            if match:
                hours = int(match.group(1))
                return now + timedelta(hours=hours)
        
        # Days
        for pattern in self.patterns["days"]:
            match = re.search(pattern, text)
            if match:
                days = int(match.group(1))
                return now + timedelta(days=days)
        
        return None
    
    def _parse_specific_time(self, text: str) -> Optional[datetime]:
        """Parse specific time today like 'at 3 PM'"""
        today = datetime.now().date()
        
        for pattern in self.patterns["time_today"]:
            match = re.search(pattern, text)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                
                # Handle AM/PM
                if "pm" in text.lower() and hour != 12:
                    hour += 12
                elif "am" in text.lower() and hour == 12:
                    hour = 0
                elif "baje" in text and hour < 12 and ("shaam" in text or "evening" in text):
                    hour += 12
                
                target_time = datetime.combine(today, time(hour, minute))
                
                # If time has passed today, schedule for tomorrow
                if target_time <= datetime.now():
                    target_time += timedelta(days=1)
                
                return target_time
        
        return None
    
    def _parse_tomorrow(self, text: str) -> Optional[datetime]:
        """Parse tomorrow time expressions"""
        tomorrow = datetime.now().date() + timedelta(days=1)
        
        for pattern in self.patterns["tomorrow"]:
            match = re.search(pattern, text)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                
                # Handle AM/PM and Hindi time expressions
                if "pm" in text.lower() and hour != 12:
                    hour += 12
                elif "am" in text.lower() and hour == 12:
                    hour = 0
                elif "baje" in text:
                    if "subah" in text or "morning" in text:
                        pass  # Keep as is for morning
                    elif "shaam" in text or "evening" in text:
                        if hour < 12:
                            hour += 12
                
                return datetime.combine(tomorrow, time(hour, minute))
        
        return None
    
    def _parse_weekday(self, text: str) -> Optional[datetime]:
        """Parse weekday expressions like 'next Monday'"""
        for pattern in self.patterns["weekdays"]:
            match = re.search(pattern, text)
            if match:
                day_name = match.group(1).lower()
                if day_name in self.day_names:
                    target_weekday = self.day_names[day_name]
                    return self._get_next_weekday(target_weekday)
        
        return None
    
    def _parse_time_keywords(self, text: str) -> Optional[datetime]:
        """Parse time keywords like 'tomorrow morning'"""
        for keyword, (hour, minute) in self.time_keywords.items():
            if keyword in text:
                if "tomorrow" in text or "kal" in text:
                    tomorrow = datetime.now().date() + timedelta(days=1)
                    return datetime.combine(tomorrow, time(hour, minute))
                else:
                    today = datetime.now().date()
                    target_time = datetime.combine(today, time(hour, minute))
                    
                    # If time has passed, schedule for tomorrow
                    if target_time <= datetime.now():
                        target_time += timedelta(days=1)
                    
                    return target_time
        
        return None
    
    def _get_next_weekday(self, target_weekday: int) -> datetime:
        """Get next occurrence of a weekday"""
        today = datetime.now()
        days_ahead = target_weekday - today.weekday()
        
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        target_date = today + timedelta(days=days_ahead)
        return target_date.replace(hour=9, minute=0, second=0, microsecond=0)  # Default to 9 AM
    
    def _extract_task_fast(self, text: str) -> Tuple[Optional[str], Optional[datetime]]:
        """Fast extraction for common reminder patterns"""
        now = datetime.now()
        text_lower = text.lower()
        
        # Try to extract minutes first
        time_match = re.search(r'(\d+)\s*min(?:ute)?s?', text_lower)
        
        if time_match:
            try:
                minutes = int(time_match.group(1))
                trigger_time = now + timedelta(minutes=minutes)
                
                # Extract task - find what comes AFTER the time + reminder keywords
                # Pattern: "[time] [reminder words] TASK"
                # Examples: 
                #   "2 minutes remind me that I have to eat" -> "eat"
                #   "in 2 minutes can you remind me that I have to eat" -> "eat"
                
                # First, remove everything before and including the time reference
                parts = text_lower.split(time_match.group(0), 1)
                if len(parts) > 1:
                    after_time = parts[1].strip()
                    
                    # Remove reminder-related phrases in order of specificity
                    reminder_phrases = [
                        "can you remind me that i have to",
                        "can you remind me to",
                        "can you remind me that",
                        "remind me that i have to",
                        "remind me i have to",
                        "remind me to",
                        "remind me that",
                        "yaad dilana ki",
                        "yaad dilana",
                    ]
                    
                    task = after_time
                    for phrase in reminder_phrases:
                        if phrase in task:
                            # Split at this phrase and take what comes after
                            split_parts = task.split(phrase, 1)
                            if len(split_parts) > 1:
                                task = split_parts[1].strip()
                                break
                    
                    # Remove leading filler words
                    filler_words = ["that", "to", "ki", "can", "you"]
                    while task:
                        stripped = False
                        for word in filler_words:
                            if task.startswith(word + " "):
                                task = task[len(word):].strip()
                                stripped = True
                                break
                        if not stripped:
                            break
                    
                    # Check for common specific tasks
                    if "eat" in task or "lunch" in task or "khana" in task:
                        task = "eat" if "eat" in task else ("lunch" if "lunch" in task else "khana khana")
                    elif "sleep" in task or "so" in task:
                        task = "sleep"
                    elif "call" in task:
                        task = "call"
                    elif "meeting" in task:
                        task = "meeting"
                    
                    if task and len(task) > 1:  # Ensure task is meaningful
                        return task, trigger_time
            except:
                pass
        
        return None, None
    
    def extract_task_from_reminder(self, text: str) -> Tuple[Optional[str], Optional[datetime]]:
        """Extract both task and time from reminder text - FAST with fallback"""
        
        # FAST PATH: Try simple regex patterns first
        fast_result = self._extract_task_fast(text)
        if fast_result[0] and fast_result[1]:
            return fast_result
        
        # AI PATH: Use AI only if fast path fails
        try:
            current_time = datetime.now()
            
            prompt = f"""Extract task and time from reminder request.

Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}

Input: "{text}"

Examples:
- "Remind me in 5 minutes to call John" → Task: "call John", Time: [5 min from now]
- "set timer 2 minutes I have to sleep" → Task: "sleep", Time: [2 min from now]
- "5 minute baad yaad dilana medicine" → Task: "medicine", Time: [5 min from now]
- "2 min mein khana khana" → Task: "khana khana", Time: [2 min from now]

Hindi numbers: do=2, teen=3, char=4, paanch=5
"baad"/"mein" means "after"/"in"
"yaad dilana" means "remind"

Calculate exact time from current: {current_time}

Respond in this exact format:
TASK: [extracted task]
TIME: YYYY-MM-DD HH:MM:SS

If no valid task or time can be extracted, respond with:
TASK: NONE
TIME: NONE"""

            # Import AI client
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent.parent / "legacy_code"))
            from .genai_client import make_client
            
            client = make_client()
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt
            )
            
            result = response.text.strip()
            
            # Parse the AI response
            task = None
            time_obj = None
            
            for line in result.split('\n'):
                if line.startswith('TASK:'):
                    task_str = line.replace('TASK:', '').strip()
                    if task_str != "NONE":
                        task = task_str
                elif line.startswith('TIME:'):
                    time_str = line.replace('TIME:', '').strip()
                    if time_str != "NONE":
                        try:
                            time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            pass
            
            return task, time_obj
            
        except Exception:
            # Fallback: try simple parsing
            parsed_time = self.parse_time(text)
            if parsed_time:
                task = self._clean_task_text(text)
                return task, parsed_time
            return None, None
    
    def _clean_task_text(self, text: str) -> str:
        """Clean task text by removing time-related words"""
        # Words to remove from task description
        time_words = [
            r"\d+\s*(?:minute|min|minutes|hour|hours|day|days)",
            r"(?:in|after|at|tomorrow|today|kal|aaj)",
            r"(?:am|pm|baje|subah|shaam|morning|evening)",
            r"(?:remind|yaad\s+dilana|alarm|set)",
            r"(?:me|mujhe|ko)"
        ]
        
        cleaned = text
        for word_pattern in time_words:
            cleaned = re.sub(word_pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Clean up extra spaces and common words
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = re.sub(r'^(?:to|ki|ka|ke)\s+', '', cleaned, flags=re.IGNORECASE)
        
        return cleaned if cleaned else "reminder"
    
    def format_time_naturally(self, dt: datetime, language: str = "hinglish") -> str:
        """Format datetime in natural language"""
        now = datetime.now()
        diff = dt - now
        
        if language.lower() == "english":
            if diff.days == 0:
                if diff.seconds < 3600:  # Less than 1 hour
                    minutes = diff.seconds // 60
                    return f"in {minutes} minutes"
                else:
                    return f"at {dt.strftime('%I:%M %p')} today"
            elif diff.days == 1:
                return f"tomorrow at {dt.strftime('%I:%M %p')}"
            else:
                return f"on {dt.strftime('%A, %B %d at %I:%M %p')}"
        else:  # Hinglish
            if diff.days == 0:
                if diff.seconds < 3600:
                    minutes = diff.seconds // 60
                    return f"{minutes} minute mein"
                else:
                    return f"aaj {dt.strftime('%I:%M')} baje"
            elif diff.days == 1:
                return f"kal {dt.strftime('%I:%M')} baje"
            else:
                return f"{dt.strftime('%A')} ko {dt.strftime('%I:%M')} baje"
