"""
Voice Journal & Notes Manager
Fast, voice-friendly note taking and journaling system
"""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


class NotesManager:
    """Manages voice notes and journal entries"""
    
    def __init__(self, storage_path: str = "notes.json", retention_days: int = 30):
        """Initialize notes manager with auto-cleanup"""
        self.storage_path = Path(storage_path)
        self.retention_days = retention_days  # Keep notes for N days
        self.data: Dict[str, Any] = {
            "notes": [],
            "journal_entries": [],
            "settings": {
                "retention_days": retention_days
            }
        }
        self.load()
    
    def load(self):
        """Load notes from storage"""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
        except Exception as e:
            print(f"⚠️ Could not load notes: {e}")
            self.data = {"notes": [], "journal_entries": [], "settings": {}}
        
        # Ensure required keys
        self.data.setdefault("notes", [])
        self.data.setdefault("journal_entries", [])
        self.data.setdefault("settings", {})
        
        # Auto-cleanup on load
        self.cleanup_old_notes()
    
    def save(self):
        """Save notes to storage"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Error saving notes: {e}")
    
    def add_note(self, content: str, tags: List[str] = None) -> tuple[bool, str]:
        """Add a quick note"""
        try:
            note = {
                "id": len(self.data["notes"]) + 1,
                "content": content,
                "tags": tags or [],
                "created_at": datetime.now().isoformat(),
                "type": "note"
            }
            
            self.data["notes"].append(note)
            self.save()
            
            return True, f"✅ Note saved! You have {len(self.data['notes'])} notes total."
        
        except Exception as e:
            return False, f"Failed to save note: {str(e)}"
    
    def add_journal_entry(self, content: str, mood: Optional[str] = None) -> tuple[bool, str]:
        """Add a journal entry"""
        try:
            entry = {
                "id": len(self.data["journal_entries"]) + 1,
                "content": content,
                "mood": mood,
                "created_at": datetime.now().isoformat(),
                "type": "journal"
            }
            
            self.data["journal_entries"].append(entry)
            self.save()
            
            return True, f"✅ Journal entry saved!"
        
        except Exception as e:
            return False, f"Failed to save journal entry: {str(e)}"
    
    def get_recent_notes(self, limit: int = 5) -> List[Dict]:
        """Get recent notes"""
        return self.data["notes"][-limit:] if self.data["notes"] else []
    
    def get_recent_journal(self, limit: int = 3) -> List[Dict]:
        """Get recent journal entries"""
        return self.data["journal_entries"][-limit:] if self.data["journal_entries"] else []
    
    def search_notes(self, query: str) -> List[Dict]:
        """Search notes by content"""
        query_lower = query.lower()
        results = [
            note for note in self.data["notes"]
            if query_lower in note["content"].lower()
        ]
        return results
    
    def delete_note(self, note_id: int) -> tuple[bool, str]:
        """Delete a note by ID"""
        try:
            self.data["notes"] = [n for n in self.data["notes"] if n["id"] != note_id]
            self.save()
            return True, f"✅ Note deleted!"
        except Exception as e:
            return False, f"Failed to delete note: {str(e)}"
    
    def get_all_count(self) -> Dict[str, int]:
        """Get count of all notes and entries"""
        return {
            "notes": len(self.data["notes"]),
            "journal": len(self.data["journal_entries"])
        }
    
    def format_notes_for_voice(self, notes: List[Dict], language: str = "hinglish") -> str:
        """Format notes for voice reading (optimized for audio)"""
        if not notes:
            if language == "hinglish":
                return "Koi notes nahi hain."
            return "You have no notes."
        
        # Voice-friendly format
        response_parts = []
        
        if language == "hinglish":
            response_parts.append(f"Aapke paas {len(notes)} notes hain.")
        else:
            response_parts.append(f"You have {len(notes)} notes.")
        
        for i, note in enumerate(notes, 1):
            content = note.get("content", "")
            created = note.get("created_at", "")
            
            # Parse date for voice
            try:
                dt = datetime.fromisoformat(created)
                time_str = dt.strftime("%B %d at %I:%M %p")
            except:
                time_str = "recently"
            
            if language == "hinglish":
                response_parts.append(f"Note {i}: {content}")
            else:
                response_parts.append(f"Note {i}: {content}")
        
        return " ".join(response_parts)
    
    def format_journal_for_voice(self, entries: List[Dict], language: str = "hinglish") -> str:
        """Format journal entries for voice reading"""
        if not entries:
            if language == "hinglish":
                return "Koi journal entries nahi hain."
            return "You have no journal entries."
        
        response_parts = []
        
        if language == "hinglish":
            response_parts.append(f"Aapki {len(entries)} journal entries hain.")
        else:
            response_parts.append(f"You have {len(entries)} journal entries.")
        
        for i, entry in enumerate(entries, 1):
            content = entry.get("content", "")
            mood = entry.get("mood", "")
            created = entry.get("created_at", "")
            
            try:
                dt = datetime.fromisoformat(created)
                date_str = dt.strftime("%B %d")
            except:
                date_str = "recently"
            
            mood_text = f" Mood: {mood}." if mood else ""
            
            if language == "hinglish":
                response_parts.append(f"Entry {i} from {date_str}:{mood_text} {content}")
            else:
                response_parts.append(f"Entry {i} from {date_str}:{mood_text} {content}")
        
        return " ".join(response_parts)
    
    def cleanup_old_notes(self):
        """
        Automatically remove notes older than retention period
        Keeps storage lean while preserving recent notes
        """
        try:
            now = datetime.now()
            retention_seconds = self.retention_days * 24 * 60 * 60
            
            initial_notes = len(self.data["notes"])
            initial_journal = len(self.data["journal_entries"])
            
            # Remove old notes
            self.data["notes"] = [
                note for note in self.data["notes"]
                if (now - datetime.fromisoformat(note["created_at"])).total_seconds() < retention_seconds
            ]
            
            # Remove old journal entries
            self.data["journal_entries"] = [
                entry for entry in self.data["journal_entries"]
                if (now - datetime.fromisoformat(entry["created_at"])).total_seconds() < retention_seconds
            ]
            
            removed_notes = initial_notes - len(self.data["notes"])
            removed_journal = initial_journal - len(self.data["journal_entries"])
            total_removed = removed_notes + removed_journal
            
            if total_removed > 0:
                self.save()
                print(f"🧹 Auto-cleanup: Removed {removed_notes} old notes and {removed_journal} old journal entries (>{self.retention_days} days)")
                
        except Exception as e:
            print(f"⚠️ Error during notes cleanup: {e}")

