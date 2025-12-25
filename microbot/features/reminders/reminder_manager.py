"""
Reminder Scheduler Module
Background service for scheduling and triggering reminders
"""

from __future__ import annotations
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

try:
    from .reminder_storage import ReminderStorage
except ImportError:
    from reminder_storage import ReminderStorage


class ReminderScheduler:
    """Background scheduler for reminders"""
    
    def __init__(self, storage: ReminderStorage, reminder_callback: Callable[[dict], None]):
        self.storage = storage
        self.reminder_callback = reminder_callback
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        
        # Thread for checking pending reminders
        self.check_thread = None
        self.stop_checking = False
    
    def start(self):
        """Start the reminder scheduler"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            
            # Start background thread for checking reminders
            self.stop_checking = False
            self.check_thread = threading.Thread(target=self._check_reminders_loop, daemon=True)
            self.check_thread.start()
            
            print("🔔 Reminder scheduler started")
    
    def stop(self):
        """Stop the reminder scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            self.stop_checking = True
            
            if self.check_thread:
                self.check_thread.join(timeout=1)
            
            print("🔔 Reminder scheduler stopped")
    
    def schedule_reminder(self, reminder_id: str, trigger_time: datetime):
        """Schedule a specific reminder"""
        try:
            # Add job to scheduler
            self.scheduler.add_job(
                func=self._trigger_reminder,
                trigger=DateTrigger(run_date=trigger_time),
                args=[reminder_id],
                id=f"reminder_{reminder_id}",
                replace_existing=True
            )
            
            print(f"✅ Scheduled reminder {reminder_id} for {trigger_time}")
            return True
            
        except Exception as e:
            print(f"❌ Error scheduling reminder {reminder_id}: {e}")
            return False
    
    def cancel_reminder(self, reminder_id: str):
        """Cancel a scheduled reminder"""
        try:
            job_id = f"reminder_{reminder_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                print(f"✅ Cancelled reminder {reminder_id}")
                return True
        except Exception as e:
            print(f"❌ Error cancelling reminder {reminder_id}: {e}")
        
        return False
    
    def reschedule_reminder(self, reminder_id: str, new_trigger_time: datetime):
        """Reschedule an existing reminder"""
        self.cancel_reminder(reminder_id)
        return self.schedule_reminder(reminder_id, new_trigger_time)
    
    def _trigger_reminder(self, reminder_id: str):
        """Trigger a reminder when its time comes"""
        try:
            # Get reminder details from storage
            reminders = self.storage.get_active_reminders()
            reminder = next((r for r in reminders if r["id"] == reminder_id), None)
            
            if reminder:
                print(f"\n{'🔔'*30}")
                print(f"🔔 TRIGGERING REMINDER NOW!")
                print(f"🔔 Task: {reminder['task']}")
                print(f"🔔 ID: {reminder_id}")
                print(f"{'🔔'*30}\n")
                
                # Call the callback function FIRST (before marking as triggered)
                # This ensures the message gets added to pending queue
                print(f"📣 Calling reminder callback...")
                self.reminder_callback(reminder)
                print(f"✅ Callback executed")
                
                # Mark as triggered AFTER callback
                self.storage.mark_reminder_triggered(reminder_id, f"Reminder: {reminder['task']}")
                print(f"✅ Marked as triggered in storage")
                
            else:
                print(f"⚠️ Reminder {reminder_id} not found in storage")
                
        except Exception as e:
            print(f"❌ Error triggering reminder {reminder_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def _check_reminders_loop(self):
        """Background loop to check for pending reminders"""
        while not self.stop_checking:
            try:
                # Check for pending reminders every 10 seconds (more frequent)
                pending_reminders = self.storage.get_pending_reminders()
                
                for reminder in pending_reminders:
                    reminder_id = reminder["id"]
                    
                    # Check if this reminder is already scheduled
                    job_id = f"reminder_{reminder_id}"
                    if not self.scheduler.get_job(job_id):
                        # Trigger immediately if not scheduled
                        print(f"🔔 Found unscheduled pending reminder: {reminder['task']}")
                        self._trigger_reminder(reminder_id)
                    else:
                        # Also check if scheduled job should have run by now
                        from datetime import datetime as dt
                        job = self.scheduler.get_job(job_id)
                        if job and job.next_run_time and job.next_run_time <= dt.now():
                            print(f"🔔 Triggering overdue reminder: {reminder['task']}")
                            self._trigger_reminder(reminder_id)
                
                # Clean up old reminders periodically
                if datetime.now().minute == 0:  # Once per hour
                    self.storage.cleanup_old_reminders()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"❌ Error in reminder check loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def load_existing_reminders(self):
        """Load and schedule existing reminders from storage"""
        try:
            active_reminders = self.storage.get_active_reminders()
            scheduled_count = 0
            
            for reminder in active_reminders:
                trigger_time = datetime.fromisoformat(reminder["trigger_time"])
                
                # Only schedule future reminders
                if trigger_time > datetime.now():
                    if self.schedule_reminder(reminder["id"], trigger_time):
                        scheduled_count += 1
                else:
                    # Mark past reminders as pending for immediate trigger
                    print(f"⏰ Found overdue reminder: {reminder['task']}")
            
            print(f"📅 Loaded {scheduled_count} existing reminders")
            
        except Exception as e:
            print(f"❌ Error loading existing reminders: {e}")
    
    def get_scheduled_jobs(self) -> list:
        """Get list of currently scheduled jobs"""
        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                if job.id.startswith("reminder_"):
                    reminder_id = job.id.replace("reminder_", "")
                    jobs.append({
                        "reminder_id": reminder_id,
                        "next_run": job.next_run_time,
                        "job_id": job.id
                    })
            return jobs
        except Exception as e:
            print(f"❌ Error getting scheduled jobs: {e}")
            return []
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            "is_running": self.is_running,
            "scheduled_jobs": len(self.get_scheduled_jobs()),
            "active_reminders": len(self.storage.get_active_reminders()),
            "pending_reminders": len(self.storage.get_pending_reminders())
        }


class ReminderManager:
    """High-level reminder management"""
    
    def __init__(self, reminder_callback: Callable[[dict], None]):
        self.storage = ReminderStorage()
        self.scheduler = ReminderScheduler(self.storage, reminder_callback)
        self.time_parser = None  # Will be imported when needed
    
    def start(self):
        """Start the reminder system"""
        # Clean up any stuck reminders first
        self.storage.cleanup_stuck_reminders()
        
        self.scheduler.start()
        self.scheduler.load_existing_reminders()
    
    def stop(self):
        """Stop the reminder system"""
        self.scheduler.stop()
    
    def add_reminder(self, user_input: str, language: str = "hinglish") -> tuple[bool, str]:
        """Add a new reminder from user input"""
        try:
            # Import time parser when needed
            if not self.time_parser:
                try:
                    from ...utils.time_parser import TimeParser
                except ImportError:
                    try:
                        from microbot.utils.time_parser import TimeParser
                    except ImportError:
                        # Fallback - create a simple parser
                        from datetime import datetime, timedelta
                        class SimpleTimeParser:
                            def extract_task_from_reminder(self, text):
                                # Simple fallback parsing
                                import re
                                if "min" in text.lower():
                                    match = re.search(r'(\d+)\s*min', text.lower())
                                    if match:
                                        minutes = int(match.group(1))
                                        trigger_time = datetime.now() + timedelta(minutes=minutes)
                                        # Extract task (simple approach)
                                        task = text.lower().replace("yaad dilana", "").replace("ki", "").strip()
                                        for word in ["min", "baad", "mein", "abhi", str(minutes)]:
                                            task = task.replace(word, "").strip()
                                        return task or "reminder", trigger_time
                                return None, None
                        self.time_parser = SimpleTimeParser()
                else:
                    self.time_parser = TimeParser()
            
            # Parse task and time from user input
            task, trigger_time = self.time_parser.extract_task_from_reminder(user_input)
            
            if not task or not trigger_time:
                return False, "Sorry, I couldn't understand the time or task. Please try again."
            
            # Add to storage
            reminder_id = self.storage.add_reminder(
                task=task,
                trigger_time=trigger_time,
                original_request=user_input,
                language=language
            )
            
            # Schedule the reminder
            if self.scheduler.schedule_reminder(reminder_id, trigger_time):
                time_str = self.time_parser.format_time_naturally(trigger_time, language)
                
                if language.lower() == "english":
                    return True, f"✅ Reminder set! I'll remind you to {task} {time_str}."
                else:
                    return True, f"✅ Reminder set kar diya! {time_str} {task} ka yaad dila dunga."
            else:
                return False, "Failed to schedule the reminder. Please try again."
                
        except Exception as e:
            print(f"❌ Error adding reminder: {e}")
            return False, "Sorry, there was an error setting up your reminder."
    
    def cancel_reminder(self, task_keywords: str) -> tuple[bool, str]:
        """Cancel a reminder by task keywords"""
        try:
            reminder = self.storage.find_reminder_by_task(task_keywords)
            
            if not reminder:
                return False, "I couldn't find a reminder matching that description."
            
            # Cancel in scheduler and storage
            self.scheduler.cancel_reminder(reminder["id"])
            self.storage.cancel_reminder(reminder["id"])
            
            return True, f"✅ Cancelled reminder: {reminder['task']}"
            
        except Exception as e:
            print(f"❌ Error cancelling reminder: {e}")
            return False, "Sorry, there was an error cancelling the reminder."
    
    def list_reminders(self, language: str = "hinglish") -> str:
        """List all active reminders"""
        try:
            summary = self.storage.get_reminders_summary()
            
            if summary["total_active"] == 0:
                if language.lower() == "english":
                    return "You don't have any active reminders."
                else:
                    return "Aapke paas koi active reminders nahi hain."
            
            # Format reminder list
            reminder_list = []
            for i, reminder in enumerate(summary["reminders"], 1):
                trigger_time = datetime.fromisoformat(reminder["trigger_time"])
                
                if not self.time_parser:
                    try:
                        from ...utils.time_parser import TimeParser
                        self.time_parser = TimeParser()
                    except ImportError:
                        # Use simple time formatting
                        self.time_parser = None
                
                if self.time_parser:
                    time_str = self.time_parser.format_time_naturally(trigger_time, language)
                else:
                    # Simple time formatting fallback
                    time_str = trigger_time.strftime('%H:%M on %d/%m')
                reminder_list.append(f"{i}. {reminder['task']} - {time_str}")
            
            if language.lower() == "english":
                header = f"📋 You have {summary['total_active']} active reminders:\n"
            else:
                header = f"📋 Aapke paas {summary['total_active']} active reminders hain:\n"
            
            return header + "\n".join(reminder_list)
            
        except Exception as e:
            print(f"❌ Error listing reminders: {e}")
            return "Sorry, there was an error getting your reminders."
    
    def get_storage(self) -> ReminderStorage:
        """Get storage instance for direct access"""
        return self.storage
    
    def get_scheduler(self) -> ReminderScheduler:
        """Get scheduler instance for direct access"""
        return self.scheduler
    
    def get_remaining_time_for_reminders(self, language: str = "hinglish") -> str:
        """Get remaining time for active (not triggered) reminders ONLY"""
        try:
            # Get ONLY active reminders (not triggered/completed)
            active_reminders = self.storage.get_active_reminders()
            
            if not active_reminders:
                if language.lower() == "english":
                    return "No active reminders right now."
                else:
                    return "Abhi koi active reminders nahi hain."
            
            # Find the next upcoming reminder
            now = datetime.now()
            upcoming_reminders = []
            
            for reminder in active_reminders:
                trigger_time = datetime.fromisoformat(reminder["trigger_time"])
                if trigger_time > now:
                    time_diff = trigger_time - now
                    upcoming_reminders.append({
                        "task": reminder["task"],
                        "time_diff": time_diff,
                        "trigger_time": trigger_time
                    })
            
            if not upcoming_reminders:
                if language.lower() == "english":
                    return "No upcoming reminders."
                else:
                    return "Koi upcoming reminders nahi hain."
            
            # Sort by time difference (closest first)
            upcoming_reminders.sort(key=lambda x: x["time_diff"])
            
            # Format the response for the closest reminder
            closest = upcoming_reminders[0]
            time_diff = closest["time_diff"]
            
            # Calculate precise time remaining
            total_seconds = int(time_diff.total_seconds())
            
            if total_seconds <= 0:
                if language.lower() == "english":
                    return f"Reminder for '{closest['task']}' should trigger any moment now!"
                else:
                    return f"'{closest['task']}' ka reminder abhi trigger hone wala hai!"
            
            # Format time remaining
            if total_seconds < 60:
                if language.lower() == "english":
                    return f"Next reminder: '{closest['task']}' in {total_seconds} seconds"
                else:
                    return f"Agla reminder: '{closest['task']}' - {total_seconds} seconds baaki"
            elif total_seconds < 3600:
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                if language.lower() == "english":
                    return f"Next reminder: '{closest['task']}' in {minutes}m {seconds}s"
                else:
                    return f"Agla reminder: '{closest['task']}' - {minutes} minute {seconds} second baaki"
            else:
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                if language.lower() == "english":
                    return f"Next reminder: '{closest['task']}' in {hours}h {minutes}m"
                else:
                    return f"Agla reminder: '{closest['task']}' - {hours} ghante {minutes} minute baaki"
                    
        except Exception as e:
            print(f"❌ Error getting remaining time: {e}")
            if language.lower() == "english":
                return "Sorry, couldn't check reminder status right now."
            else:
                return "Sorry, abhi reminder status check nahi kar sakte."