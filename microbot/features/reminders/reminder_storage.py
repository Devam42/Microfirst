"""
Reminder Storage Module
JSON-based storage system for reminders and alarms
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


class ReminderStorage:
    """Manages reminder storage in JSON format"""
    
    def __init__(self, storage_path: str = "reminders.json", retention_days: int = 7):
        self.storage_path = Path(storage_path)
        self.retention_days = retention_days  # Keep completed reminders for N days
        self.data = {
            "reminders": [],
            "active_reminders": [],
            "settings": {
                "voice_reminders": False,
                "smart_messages": True,
                "default_language": "hinglish",
                "retention_days": retention_days
            }
        }
        self.load()
    
    def load(self):
        """Load reminders from JSON file"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    
                    # Handle both dict and list formats
                    if isinstance(loaded_data, dict):
                        self.data.update(loaded_data)
                    elif isinstance(loaded_data, list):
                        # Legacy format: list of reminders
                        # Convert to new format
                        self.data["reminders"] = loaded_data
                        self.data["active_reminders"] = loaded_data
                    else:
                        print(f"⚠️ Unknown reminders format, using defaults")
            except Exception as e:
                print(f"Error loading reminders: {e}")
        
        # Ensure required keys exist
        self.data.setdefault("reminders", [])
        self.data.setdefault("active_reminders", [])
        self.data.setdefault("settings", {})
        
        # Auto-cleanup on load
        self.cleanup_old_reminders()
    
    def save(self):
        """Save reminders to JSON file"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"Error saving reminders: {e}")
    
    def add_reminder(self, task: str, trigger_time: datetime, original_request: str, 
                    reminder_type: str = "once", language: str = "hinglish", 
                    urgency: str = "medium") -> str:
        """Add a new reminder"""
        reminder_id = str(uuid.uuid4())[:8]  # Short ID
        
        reminder = {
            "id": reminder_id,
            "task": task,
            "trigger_time": trigger_time.isoformat(),
            "original_request": original_request,
            "type": reminder_type,  # once, daily, weekly, monthly
            "context": {
                "urgency": urgency,
                "language": language,
                "category": self._categorize_task(task)
            },
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
        
        self.data["reminders"].append(reminder)
        self.save()
        return reminder_id
    
    def get_active_reminders(self) -> List[Dict[str, Any]]:
        """Get all active reminders"""
        return [r for r in self.data["reminders"] if r.get("status") == "active"]
    
    def get_pending_reminders(self) -> List[Dict[str, Any]]:
        """Get reminders that should trigger now"""
        now = datetime.now()
        pending = []
        
        for reminder in self.get_active_reminders():
            trigger_time = datetime.fromisoformat(reminder["trigger_time"])
            if trigger_time <= now:
                pending.append(reminder)
        
        return pending
    
    def mark_reminder_triggered(self, reminder_id: str, generated_message: str):
        """Mark a reminder as triggered and store the generated message"""
        # Move to active_reminders for tracking
        triggered_reminder = {
            "id": reminder_id,
            "triggered_at": datetime.now().isoformat(),
            "message_generated": generated_message
        }
        
        self.data["active_reminders"].append(triggered_reminder)
        
        # Update original reminder status
        # CHANGED: Mark as "triggered" instead of "completed" so it can still be queried
        reminder_found = False
        for reminder in self.data["reminders"]:
            if reminder["id"] == reminder_id:
                reminder_found = True
                if reminder["type"] == "once":
                    reminder["status"] = "triggered"  # Changed from "completed"
                    reminder["triggered_at"] = datetime.now().isoformat()
                    print(f"✅ Marked reminder {reminder_id} as triggered (awaiting acknowledgment)")
                else:
                    # For recurring reminders, update next trigger time
                    self._update_recurring_reminder(reminder)
                break
        
        if not reminder_found:
            print(f"⚠️ Warning: Reminder {reminder_id} not found when marking as triggered")
        
        self.save()
    
    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a reminder by ID"""
        for reminder in self.data["reminders"]:
            if reminder["id"] == reminder_id and reminder["status"] == "active":
                reminder["status"] = "cancelled"
                self.save()
                return True
        return False
    
    def acknowledge_triggered_reminder(self, reminder_id: str) -> bool:
        """Mark a triggered reminder as completed (acknowledged by user)"""
        for reminder in self.data["reminders"]:
            if reminder["id"] == reminder_id and reminder["status"] == "triggered":
                reminder["status"] = "completed"
                reminder["acknowledged_at"] = datetime.now().isoformat()
                print(f"✅ Reminder {reminder_id} acknowledged and completed")
                self.save()
                return True
        return False
    
    def find_reminder_by_task(self, task_keywords: str) -> Optional[Dict[str, Any]]:
        """Find reminder by task description keywords"""
        task_lower = task_keywords.lower()
        
        for reminder in self.get_active_reminders():
            if task_lower in reminder["task"].lower():
                return reminder
        
        return None
    
    def get_reminders_summary(self) -> Dict[str, Any]:
        """Get summary of all reminders"""
        active_reminders = self.get_active_reminders()
        
        return {
            "total_active": len(active_reminders),
            "upcoming_today": len([r for r in active_reminders 
                                 if datetime.fromisoformat(r["trigger_time"]).date() == datetime.now().date()]),
            "reminders": active_reminders[:5]  # Show first 5
        }
    
    def cleanup_old_reminders(self, days_old: int = 7):
        """Clean up old completed/cancelled reminders"""
        cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        
        # Clean completed/cancelled reminders
        self.data["reminders"] = [
            r for r in self.data["reminders"]
            if r["status"] == "active" or 
            datetime.fromisoformat(r["created_at"]).timestamp() > cutoff_date
        ]
        
        # Clean old active reminders
        self.data["active_reminders"] = [
            r for r in self.data["active_reminders"]
            if datetime.fromisoformat(r["triggered_at"]).timestamp() > cutoff_date
        ]
        
        self.save()
    
    def _categorize_task(self, task: str) -> str:
        """Categorize task for better context"""
        task_lower = task.lower()
        
        if any(word in task_lower for word in ["call", "phone", "contact"]):
            return "communication"
        elif any(word in task_lower for word in ["medicine", "pill", "doctor", "health"]):
            return "health"
        elif any(word in task_lower for word in ["meeting", "work", "office", "project"]):
            return "work"
        elif any(word in task_lower for word in ["wake", "alarm", "sleep", "morning"]):
            return "personal"
        elif any(word in task_lower for word in ["eat", "food", "lunch", "dinner"]):
            return "meal"
        else:
            return "general"
    
    def _update_recurring_reminder(self, reminder: Dict[str, Any]):
        """Update recurring reminder for next occurrence"""
        from datetime import timedelta
        
        current_time = datetime.fromisoformat(reminder["trigger_time"])
        
        if reminder["type"] == "daily":
            next_time = current_time + timedelta(days=1)
        elif reminder["type"] == "weekly":
            next_time = current_time + timedelta(weeks=1)
        elif reminder["type"] == "monthly":
            next_time = current_time + timedelta(days=30)  # Approximate
        else:
            return
        
        reminder["trigger_time"] = next_time.isoformat()
    
    def get_settings(self) -> Dict[str, Any]:
        """Get reminder settings"""
        return self.data.get("settings", {})
    
    def update_settings(self, **kwargs):
        """Update reminder settings"""
        if "settings" not in self.data:
            self.data["settings"] = {}
        
        self.data["settings"].update(kwargs)
        self.save()
    
    def cleanup_stuck_reminders(self):
        """Clean up reminders that are stuck in pending state"""
        now = datetime.now()
        cleaned_count = 0
        
        for reminder in self.data["reminders"]:
            if reminder.get("status") == "active":
                trigger_time_str = reminder.get("trigger_time")
                if trigger_time_str:
                    trigger_time = datetime.fromisoformat(trigger_time_str)
                    # Only clean up VERY old stuck reminders (more than 1 hour overdue)
                    # Recently triggered reminders (< 1 hour) are kept so user can query them
                    if (now - trigger_time).total_seconds() > 3600:  # Changed from 60 to 3600 seconds (1 hour)
                        reminder["status"] = "completed"
                        cleaned_count += 1
                        print(f"🧹 Cleaned up old stuck reminder: {reminder.get('task', 'Unknown')}")
        
        if cleaned_count > 0:
            self.save()
            print(f"✅ Cleaned up {cleaned_count} old stuck reminders")
    
    def cleanup_old_reminders(self):
        """
        Automatically remove completed reminders older than retention period
        This keeps storage lean by removing reminders that are no longer needed
        """
        try:
            now = datetime.now()
            retention_seconds = self.retention_days * 24 * 60 * 60
            
            initial_count = len(self.data["reminders"])
            
            # Remove completed reminders IMMEDIATELY (they were already spoken and acknowledged)
            # Keep "triggered" reminders for 5 minutes (in case of race condition)
            self.data["reminders"] = [
                reminder for reminder in self.data["reminders"]
                if not (
                    # Remove completed reminders IMMEDIATELY (they were spoken and acknowledged)
                    reminder.get("status") == "completed"
                    or
                    # Remove triggered (but not acknowledged) reminders after 5 minutes
                    # This handles edge cases where acknowledgment failed
                    (reminder.get("status") == "triggered" and 
                     reminder.get("triggered_at") and
                     (now - datetime.fromisoformat(reminder["triggered_at"])).total_seconds() > 300)  # 5 minutes
                )
            ]
            
            # Clean up old triggered reminders from active list
            self.data["active_reminders"] = [
                active for active in self.data["active_reminders"]
                if "triggered_at" in active and  # Check if field exists
                   (now - datetime.fromisoformat(active["triggered_at"])).total_seconds() < retention_seconds
            ]
            
            removed_count = initial_count - len(self.data["reminders"])
            
            if removed_count > 0:
                self.save()
                print(f"🧹 Auto-cleanup: Removed {removed_count} old completed reminders (>{self.retention_days} days)")
                
        except Exception as e:
            print(f"⚠️ Error during reminder cleanup: {e}")
