"""
Configuration Store Module
Centralized settings management for Microbot
Stores all bot settings in config.json at workspace root
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Optional


# Config file at workspace root (not in legacy_code)
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = WORKSPACE_ROOT / "config.json"

# Legacy paths for migration only
LEGACY_CONFIG_PATH = WORKSPACE_ROOT / "legacy_code" / "config.json"
LEGACY_STATE_PATH = WORKSPACE_ROOT / "legacy_code" / "state.json"


class ConfigStore:
    """Centralized configuration store for all bot settings"""
    
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self._info = None  # Store documentation field separately
        self.data = {
            "bot_name": "Microbot",
            "password_hash": None,
            "language": "hinglish",  # english | hinglish | marathi
            "security_questions": {},  # Store security questions and their hashed answers
            "current_mode": "normal",  # normal | notes | pomodoro | voice
            "mode_states": {
                "notes_active": False,
                "pomodoro_active": False,
                "voice_active": False
            },
            "voice_settings": {
                "enabled": True,
                "english_voice": "justin",  # matthew | justin | salli
                "hinglish_voice": "aditi",   # aditi (Indian female voice)
                "aws_configured": False
            }
        }
        self.load()

    def load(self):
        """Load configuration from file, migrating from legacy if needed"""
        # Try new location first
        if self.path.exists():
            try:
                loaded_data = json.loads(self.path.read_text(encoding="utf-8"))
                # Preserve _info field if it exists
                if "_info" in loaded_data:
                    self._info = loaded_data.pop("_info")
                else:
                    self._info = None
                self.data.update(loaded_data)
            except Exception:
                pass
        # Migrate from legacy config.json
        elif LEGACY_CONFIG_PATH.exists():
            try:
                legacy = json.loads(LEGACY_CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(legacy, dict):
                    self.data.update(legacy)
                print(f"📦 Migrated config from legacy_code to {self.path}")
                self.save()  # Save to new location
            except Exception:
                pass
        # Migrate from legacy state.json
        elif LEGACY_STATE_PATH.exists():
            try:
                legacy = json.loads(LEGACY_STATE_PATH.read_text(encoding="utf-8"))
                if isinstance(legacy, dict):
                    self.data["bot_name"] = legacy.get("bot_name", self.data["bot_name"])
                    self.data["password_hash"] = legacy.get("password_hash", self.data["password_hash"])
                print(f"📦 Migrated config from legacy state.json to {self.path}")
                self.save()  # Save to new location
            except Exception:
                pass
        
        # Ensure defaults
        self.data.setdefault("bot_name", "Microbot")
        self.data.setdefault("password_hash", None)
        self.data.setdefault("language", "hinglish")
        self.data.setdefault("security_questions", {})
        self.data.setdefault("current_mode", "normal")
        self.data.setdefault("mode_states", {
            "notes_active": False,
            "pomodoro_active": False,
            "voice_active": False
        })
        self.data.setdefault("voice_settings", {
            "enabled": True,
            "english_voice": "justin",
            "hinglish_voice": "aditi",
            "current_voice": "aditi",
            "aws_configured": False
        })

    def save(self):
        """Save configuration to file, preserving documentation"""
        try:
            # Create output dict with _info first (if it exists)
            output = {}
            if hasattr(self, '_info') and self._info:
                output["_info"] = self._info
            
            # Add all config data
            output.update(self.data)
            
            self.path.write_text(
                json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"💾 Config saved to {self.path.name}")
        except Exception as e:
            print(f"⚠️ Warning: Could not save config: {e}")

    # Password helpers
    @staticmethod
    def _hash(pw: str) -> str:
        return hashlib.sha256(pw.encode("utf-8")).hexdigest()

    def has_password(self) -> bool:
        return bool(self.data.get("password_hash"))

    def check_password(self, pw: str) -> bool:
        ph = self.data.get("password_hash")
        return bool(ph) and self._hash(pw) == ph

    def set_password(self, pw: str):
        self.data["password_hash"] = self._hash(pw)
        self.save()

    # Name helpers
    def set_name(self, name: str):
        self.data["bot_name"] = name.strip()
        self.save()

    # Language helpers
    def set_language(self, lang: str):
        lang = (lang or "").strip().lower()
        if lang in {"english", "hinglish", "marathi"}:
            self.data["language"] = lang
            self.save()
            print(f"✅ Language saved to config: {lang}")

    def language(self) -> str:
        return (self.data.get("language") or "hinglish").lower()

    # Security question helpers
    def has_security_questions(self) -> bool:
        """Check if security questions are set up"""
        return bool(self.data.get("security_questions"))
    
    def set_security_question(self, question: str, answer: str):
        """Set a security question and its hashed answer"""
        if "security_questions" not in self.data:
            self.data["security_questions"] = {}
        
        # Normalize the answer (lowercase, strip spaces)
        normalized_answer = answer.strip().lower()
        self.data["security_questions"][question] = self._hash(normalized_answer)
        self.save()
    
    def check_security_answer(self, question: str, answer: str) -> bool:
        """Check if the answer to a security question is correct"""
        if "security_questions" not in self.data:
            return False
        
        stored_hash = self.data["security_questions"].get(question)
        if not stored_hash:
            return False
        
        # Normalize the provided answer
        normalized_answer = answer.strip().lower()
        return self._hash(normalized_answer) == stored_hash
    
    def get_security_questions(self) -> list:
        """Get list of security questions"""
        if "security_questions" not in self.data:
            return []
        return list(self.data["security_questions"].keys())
    
    def clear_security_questions(self):
        """Clear all security questions"""
        self.data["security_questions"] = {}
        self.save()
    
    def reset_password_with_security(self, new_password: str):
        """Reset password after security question verification"""
        self.set_password(new_password)
    
    # Mode management helpers
    def get_current_mode(self) -> str:
        """Get the current active mode"""
        return self.data.get("current_mode", "normal")
    
    def set_mode(self, mode: str):
        """Set the current mode (normal, notes, pomodoro, voice)"""
        if mode in {"normal", "notes", "pomodoro", "voice"}:
            self.data["current_mode"] = mode
            # Update mode states
            if "mode_states" not in self.data:
                self.data["mode_states"] = {}
            self.data["mode_states"]["notes_active"] = (mode == "notes")
            self.data["mode_states"]["pomodoro_active"] = (mode == "pomodoro")
            self.data["mode_states"]["voice_active"] = (mode == "voice")
            self.save()
            print(f"✅ Mode saved to config: {mode}")
    
    def get_mode_states(self) -> dict:
        """Get all mode states"""
        return self.data.get("mode_states", {
            "notes_active": False,
            "pomodoro_active": False,
            "voice_active": False
        })
    
    def get_all_settings(self) -> dict:
        """Get all settings in a readable format"""
        return {
            "bot_name": self.data.get("bot_name", "Microbot"),
            "language": self.language(),
            "current_mode": self.get_current_mode(),
            "has_password": self.has_password(),
            "has_security_questions": self.has_security_questions(),
            "mode_states": self.get_mode_states(),
            "voice_settings": self.get_voice_settings()
        }
    
    # Voice settings helpers
    def get_voice_settings(self) -> dict:
        """Get voice settings"""
        return self.data.get("voice_settings", {
            "enabled": True,
            "english_voice": "justin",
            "hinglish_voice": "aditi",
            "current_voice": "aditi",
            "aws_configured": False
        })
    
    def set_english_voice(self, voice: str):
        """Set English voice (matthew, justin, salli)"""
        if voice.lower() in {"matthew", "justin", "salli"}:
            if "voice_settings" not in self.data:
                self.data["voice_settings"] = {}
            self.data["voice_settings"]["english_voice"] = voice.lower()
            self.save()
            print(f"✅ English voice set to: {voice}")
    
    def set_hinglish_voice(self, voice: str):
        """Set Hinglish voice (currently only aditi)"""
        if voice.lower() == "aditi":
            if "voice_settings" not in self.data:
                self.data["voice_settings"] = {}
            self.data["voice_settings"]["hinglish_voice"] = voice.lower()
            self.save()
            print(f"✅ Hinglish voice set to: {voice}")
    
    def get_voice_for_language(self, language: Optional[str] = None) -> str:
        """Get appropriate voice for language"""
        if language is None:
            language = self.language()
        
        voice_settings = self.get_voice_settings()
        
        if language.lower() in ["hinglish", "marathi", "hindi"]:
            return voice_settings.get("hinglish_voice", "aditi")
        else:
            return voice_settings.get("english_voice", "justin")
    
    def set_voice_enabled(self, enabled: bool):
        """Enable/disable voice mode"""
        if "voice_settings" not in self.data:
            self.data["voice_settings"] = {}
        self.data["voice_settings"]["enabled"] = enabled
        self.save()
        print(f"✅ Voice mode {'enabled' if enabled else 'disabled'}")
    
    def is_voice_enabled(self) -> bool:
        """Check if voice mode is enabled"""
        voice_settings = self.get_voice_settings()
        return voice_settings.get("enabled", True)
    
    def set_aws_configured(self, configured: bool):
        """Mark AWS credentials as configured"""
        if "voice_settings" not in self.data:
            self.data["voice_settings"] = {}
        self.data["voice_settings"]["aws_configured"] = configured
        self.save()
    
    def is_aws_configured(self) -> bool:
        """Check if AWS credentials are configured"""
        voice_settings = self.get_voice_settings()
        return voice_settings.get("aws_configured", False)
    
    def get_current_voice(self) -> str:
        """Get the currently active voice"""
        voice_settings = self.get_voice_settings()
        return voice_settings.get("current_voice", "aditi")
    
    def set_current_voice(self, voice: str):
        """Set the current active voice"""
        if voice.lower() in {"matthew", "justin", "salli", "aditi"}:
            if "voice_settings" not in self.data:
                self.data["voice_settings"] = {}
            self.data["voice_settings"]["current_voice"] = voice.lower()
            self.save()
            print(f"✅ Current voice updated to: {voice}")

