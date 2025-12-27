"""
Flow Manager Module
Handles multi-turn conversation flows like name/password management
"""

from __future__ import annotations
import re
from typing import Optional, Dict, Any, List

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "legacy_code"))

try:
    from ..utils import ConfigStore
except ImportError:
    from microbot.utils import ConfigStore


class FlowState:
    """Represents the current state of a conversation flow"""
    
    def __init__(self, flow_type: str, step: str, data: Dict[str, Any] = None):
        self.flow_type = flow_type
        self.step = step
        self.data = data or {}
        self.created_at = None  # Could add timestamp if needed
    
    def __repr__(self):
        return f"FlowState(type={self.flow_type}, step={self.step}, data={self.data})"


class FlowManager:
    """
    Manages multi-turn conversation flows for name/password management
    """
    
    def __init__(self, config_store: ConfigStore):
        self.config = config_store
        self.current_flow: Optional[FlowState] = None
        
        # Predefined security questions
        self.security_questions = [
            "What is your mother's name?",
            "What was the name of your first school?", 
            "What is your best friend's name?",
            "What is your favorite color?",
            "What city were you born in?",
            "What is your pet's name?",
            "What is your favorite food?",
            "What is your father's name?"
        ]
        
        # Flow definitions
        self.flow_definitions = {
            "name_change": {
                "steps": ["await_password", "await_new_name"],
                "messages": {
                    "await_password": {
                        "english": "Please enter your password to change the name.",
                        "hinglish": "Naam badalne ke liye password bolo."
                    },
                    "await_new_name": {
                        "english": "Password correct! What name would you like to set?",
                        "hinglish": "Password sahi. Kaunsa naya naam rakhna hai?"
                    },
                    "success": {
                        "english": "Name changed successfully to '{name}'.",
                        "hinglish": "Naam badal diya: '{name}'."
                    },
                    "wrong_password": {
                        "english": "Wrong password. Try again or say 'cancel'.",
                        "hinglish": "Password galat hai. Dobara koshish karo ya 'cancel' bolo."
                    }
                }
            },
            "password_change": {
                "steps": ["await_current_password", "await_new_password"],
                "messages": {
                    "await_current_password": {
                        "english": "Please enter your current password.",
                        "hinglish": "Pehle current password bolo."
                    },
                    "await_new_password": {
                        "english": "Current password correct! Enter your new password.",
                        "hinglish": "Sahi password. Naya password bolo (e.g., 'new password Dev456')."
                    },
                    "success": {
                        "english": "Password updated successfully.",
                        "hinglish": "Password update ho gaya."
                    },
                    "wrong_password": {
                        "english": "Wrong password. Try again or say 'cancel'.",
                        "hinglish": "Password galat hai. Dobara koshish karo ya 'cancel' bolo."
                    }
                }
            },
            "first_time_setup": {
                "steps": ["await_name", "await_password", "await_security_setup"],
                "messages": {
                    "await_name": {
                        "english": "What name would you like me to use?",
                        "hinglish": "Konsa naam rakhna hai? Naam batao."
                    },
                    "await_password": {
                        "english": "Please set a password (e.g., 'password Dev123').",
                        "hinglish": "Password set karo (e.g., 'password Dev123')."
                    },
                    "await_security_setup": {
                        "english": "Would you like to set up security questions for password recovery? Say 'yes' or 'no'.",
                        "hinglish": "Kya aap password recovery ke liye security questions set karna chahte hain? 'yes' ya 'no' boliye."
                    },
                    "success": {
                        "english": "Setup complete! Name set to '{name}'. Password required for future changes.",
                        "hinglish": "Naam set ho gaya '{name}'. Ab se change ke liye password chahiye."
                    }
                }
            },
            "password_recovery": {
                "steps": ["await_security_answer", "await_new_password"],
                "messages": {
                    "await_security_answer": {
                        "english": "{question}",
                        "hinglish": "{question}"
                    },
                    "await_new_password": {
                        "english": "Security answer correct! Please set your new password.",
                        "hinglish": "Security answer sahi hai! Naya password set kariye."
                    },
                    "success": {
                        "english": "Password reset successfully!",
                        "hinglish": "Password reset ho gaya!"
                    },
                    "wrong_answer": {
                        "english": "Wrong answer. Try again or say 'cancel'.",
                        "hinglish": "Galat jawab. Dobara koshish karo ya 'cancel' bolo."
                    },
                    "no_security": {
                        "english": "No security questions set up. Cannot recover password.",
                        "hinglish": "Security questions set nahi hain. Password recover nahi kar sakte."
                    }
                }
            },
            "security_setup": {
                "steps": ["await_question_selection", "await_answer"],
                "messages": {
                    "await_question_selection": {
                        "english": "Choose a security question by number:\n{questions}",
                        "hinglish": "Security question choose kariye number se:\n{questions}"
                    },
                    "await_answer": {
                        "english": "Please provide your answer to: {question}",
                        "hinglish": "Is sawal ka jawab dijiye: {question}"
                    },
                    "success": {
                        "english": "Security question set up successfully!",
                        "hinglish": "Security question set ho gaya!"
                    },
                    "invalid_choice": {
                        "english": "Invalid choice. Please select a number from the list.",
                        "hinglish": "Galat choice. List mein se number select kariye."
                    }
                }
            }
        }
    
    def check_flow_triggers(self, user_input: str) -> Optional[str]:
        """
        Check if user input triggers a new flow using AI detection
        Returns response message if flow is triggered, None otherwise
        """
        # Use AI to detect flow triggers instead of patterns
        try:
            from ..utils.genai_client import make_client
            client = make_client()
            
            # AI prompt to detect flow intentions
            prompt = f"""Analyze this user input and determine if they want to:
1. Change bot name (respond: "NAME_CHANGE")
2. Change password (respond: "PASSWORD_CHANGE") 
3. Recover/reset forgotten password (respond: "PASSWORD_RECOVERY")
4. Set up security questions (respond: "SECURITY_SETUP")
5. None of the above (respond: "NONE")

User input: "{user_input}"

Respond with only one of the exact keywords above."""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            
            intent = response.text.strip().upper()
            
            if intent == "NAME_CHANGE":
                return self._start_name_change_flow()
            elif intent == "PASSWORD_CHANGE":
                return self._start_password_change_flow()
            elif intent == "PASSWORD_RECOVERY":
                return self._start_password_recovery_flow()
            elif intent == "SECURITY_SETUP":
                return self._start_security_setup_flow()
            
        except Exception:
            # Fallback: no flow triggered
            pass
        
        return None
    
    def handle_flow_input(self, user_input: str) -> Optional[str]:
        """
        Handle input when a flow is active
        Returns response message if input is handled, None if no active flow
        """
        if not self.current_flow:
            return None
        
        # Check for cancellation
        if self._is_cancel_command(user_input):
            return self._cancel_current_flow()
        
        # Handle based on current flow and step
        if self.current_flow.flow_type == "name_change":
            return self._handle_name_change_flow(user_input)
        elif self.current_flow.flow_type == "password_change":
            return self._handle_password_change_flow(user_input)
        elif self.current_flow.flow_type == "first_time_setup":
            return self._handle_first_time_setup_flow(user_input)
        elif self.current_flow.flow_type == "password_recovery":
            return self._handle_password_recovery_flow(user_input)
        elif self.current_flow.flow_type == "security_setup":
            return self._handle_security_setup_flow(user_input)
        
        return None
    
    def get_current_flow(self) -> Optional[str]:
        """Get current active flow type"""
        return self.current_flow.flow_type if self.current_flow else None
    
    def _start_name_change_flow(self) -> str:
        """Start name change flow"""
        if self.config.has_password():
            self.current_flow = FlowState("name_change", "await_password")
            return self._get_message("name_change", "await_password")
        else:
            self.current_flow = FlowState("first_time_setup", "await_name")
            return self._get_message("first_time_setup", "await_name")
    
    def _start_password_change_flow(self) -> str:
        """Start password change flow"""
        if self.config.has_password():
            self.current_flow = FlowState("password_change", "await_current_password")
            return self._get_message("password_change", "await_current_password")
        else:
            self.current_flow = FlowState("first_time_setup", "await_password")
            return self._get_message("first_time_setup", "await_password")
    
    def _handle_name_change_flow(self, user_input: str) -> str:
        """Handle name change flow steps"""
        if self.current_flow.step == "await_password":
            password = self._extract_password(user_input)
            if self.config.check_password(password):
                self.current_flow.step = "await_new_name"
                return self._get_message("name_change", "await_new_name")
            else:
                return self._get_message("name_change", "wrong_password")
        
        elif self.current_flow.step == "await_new_name":
            new_name = self._extract_name(user_input)
            self.config.set_name(new_name)
            self._complete_flow()
            return self._get_message("name_change", "success").format(name=new_name)
        
        return "Flow error occurred."
    
    def _handle_password_change_flow(self, user_input: str) -> str:
        """Handle password change flow steps"""
        if self.current_flow.step == "await_current_password":
            password = self._extract_password(user_input)
            if self.config.check_password(password):
                self.current_flow.step = "await_new_password"
                return self._get_message("password_change", "await_new_password")
            else:
                return self._get_message("password_change", "wrong_password")
        
        elif self.current_flow.step == "await_new_password":
            new_password = self._extract_password(user_input)
            self.config.set_password(new_password)
            self._complete_flow()
            return self._get_message("password_change", "success")
        
        return "Flow error occurred."
    
    def _handle_first_time_setup_flow(self, user_input: str) -> str:
        """Handle first time setup flow steps"""
        if self.current_flow.step == "await_name":
            name = self._extract_name(user_input)
            self.current_flow.data["new_name"] = name
            self.current_flow.step = "await_password"
            return self._get_message("first_time_setup", "await_password")
        
        elif self.current_flow.step == "await_password":
            password = self._extract_password(user_input)
            name = self.current_flow.data.get("new_name", self.config.data["bot_name"])
            
            self.config.set_name(name)
            self.config.set_password(password)
            self._complete_flow()
            
            return self._get_message("first_time_setup", "success").format(name=name)
        
        return "Setup error occurred."
    
    def _start_password_recovery_flow(self) -> str:
        """Start password recovery flow"""
        if not self.config.has_security_questions():
            return self._get_message("password_recovery", "no_security")
        
        # Get a random security question
        questions = self.config.get_security_questions()
        if questions:
            question = questions[0]  # Use first available question
            self.current_flow = FlowState("password_recovery", "await_security_answer", {"question": question})
            return self._get_message("password_recovery", "await_security_answer").format(question=question)
        
        return self._get_message("password_recovery", "no_security")
    
    def _start_security_setup_flow(self) -> str:
        """Start security question setup flow"""
        questions_list = "\n".join([f"{i+1}. {q}" for i, q in enumerate(self.security_questions)])
        self.current_flow = FlowState("security_setup", "await_question_selection")
        return self._get_message("security_setup", "await_question_selection").format(questions=questions_list)
    
    def _handle_password_recovery_flow(self, user_input: str) -> str:
        """Handle password recovery flow steps"""
        if self.current_flow.step == "await_security_answer":
            question = self.current_flow.data.get("question")
            if self.config.check_security_answer(question, user_input):
                self.current_flow.step = "await_new_password"
                return self._get_message("password_recovery", "await_new_password")
            else:
                return self._get_message("password_recovery", "wrong_answer")
        
        elif self.current_flow.step == "await_new_password":
            new_password = self._extract_password(user_input)
            self.config.reset_password_with_security(new_password)
            self._complete_flow()
            return self._get_message("password_recovery", "success")
        
        return "Recovery error occurred."
    
    def _handle_security_setup_flow(self, user_input: str) -> str:
        """Handle security question setup flow steps"""
        if self.current_flow.step == "await_question_selection":
            try:
                choice = int(user_input.strip()) - 1
                if 0 <= choice < len(self.security_questions):
                    selected_question = self.security_questions[choice]
                    self.current_flow.step = "await_answer"
                    self.current_flow.data["selected_question"] = selected_question
                    return self._get_message("security_setup", "await_answer").format(question=selected_question)
                else:
                    return self._get_message("security_setup", "invalid_choice")
            except ValueError:
                return self._get_message("security_setup", "invalid_choice")
        
        elif self.current_flow.step == "await_answer":
            question = self.current_flow.data.get("selected_question")
            answer = user_input.strip()
            self.config.set_security_question(question, answer)
            self._complete_flow()
            return self._get_message("security_setup", "success")
        
        return "Security setup error occurred."
    
    def _extract_password(self, user_input: str) -> str:
        """Extract password from user input"""
        # Try quoted password first
        quoted_match = re.search(r"['\"]([^'\"]+)['\"]", user_input)
        if quoted_match:
            return quoted_match.group(1).strip()
        
        # Try keyword-based extraction
        keyword_patterns = [r"password\s*[:=]?\s*([\w _-]{1,32})", r"pass\s*[:=]?\s*([\w _-]{1,32})"]
        for pattern in keyword_patterns:
            match = re.search(pattern, user_input, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback to entire input
        return user_input.strip()
    
    def _extract_name(self, user_input: str) -> str:
        """Extract name from user input"""
        # Try quoted name first
        quoted_match = re.search(r"['\"]([^'\"]+)['\"]", user_input)
        if quoted_match:
            return quoted_match.group(1).strip()
        
        # Try keyword-based extraction
        keyword_patterns = [r"name\s*[:=]?\s*([\w _-]{1,32})", r"naam\s*[:=]?\s*([\w _-]{1,32})"]
        for pattern in keyword_patterns:
            match = re.search(pattern, user_input, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback to entire input
        return user_input.strip()
    
    def _is_cancel_command(self, user_input: str) -> bool:
        """Check if user wants to cancel current flow using AI"""
        try:
            from ..utils.genai_client import make_client
            client = make_client()
            
            prompt = f"""Does this user input indicate they want to cancel or stop the current operation?
User input: "{user_input}"

Respond with only "YES" or "NO"."""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            
            return response.text.strip().upper() == "YES"
        except Exception:
            # Fallback to simple check
            cancel_words = ["cancel", "no", "nahi", "nahin", "stop", "quit", "exit"]
            return user_input.strip().lower() in cancel_words
    
    def _cancel_current_flow(self) -> str:
        """Cancel current flow and return appropriate message"""
        self.current_flow = None
        
        # Return cancellation message based on language preference
        if self._is_hinglish_preferred():
            return "Theek hai, cancel kar diya."
        else:
            return "Okay, cancelled the operation."
    
    def _complete_flow(self):
        """Complete current flow"""
        self.current_flow = None
    
    def _get_message(self, flow_type: str, message_key: str) -> str:
        """Get message for flow and key based on language preference"""
        language = "hinglish" if self._is_hinglish_preferred() else "english"
        
        try:
            return self.flow_definitions[flow_type]["messages"][message_key][language]
        except KeyError:
            # Fallback to English if message not found
            return self.flow_definitions[flow_type]["messages"][message_key].get("english", "Message not found")
    
    def _is_hinglish_preferred(self) -> bool:
        """Check if Hinglish is the preferred language"""
        return self.config.language().lower() == "hinglish"
    
    def get_flow_status(self) -> Dict[str, Any]:
        """Get current flow status for debugging/monitoring"""
        if not self.current_flow:
            return {"active": False}
        
        return {
            "active": True,
            "flow_type": self.current_flow.flow_type,
            "current_step": self.current_flow.step,
            "data_keys": list(self.current_flow.data.keys())
        }
