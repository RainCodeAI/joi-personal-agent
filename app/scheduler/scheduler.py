import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.scheduler.jobs import check_mood_trends, check_habits, morning_brief
import atexit

log = logging.getLogger(__name__)

_scheduler = None

def start_scheduler():
    """Start the global background scheduler if not already running."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler()
    
    # Add jobs
    # Check mood every 4 hours
    _scheduler.add_job(
        check_mood_trends,
        trigger=IntervalTrigger(hours=4),
        id="check_mood_trends",
        name="Check Mood Trends",
        replace_existing=True
    )
    
    # Check habits every 12 hours
    _scheduler.add_job(
        check_habits,
        trigger=IntervalTrigger(hours=12),
        id="check_habits",
        name="Check Habits",
        replace_existing=True
    )
    
    # Morning brief at 8 AM daily
    _scheduler.add_job(
        morning_brief,
        trigger="cron",
        hour=8,
        minute=0,
        id="morning_brief",
        name="Morning Brief",
        replace_existing=True
    )

    _scheduler.start()
    log.info("Proactive Scheduler started.")
    
    # Shut down on exit
    atexit.register(lambda: _scheduler.shutdown())

def get_scheduler():
    return _scheduler

def toggle_scheduler(enabled: bool):
    """Pause or resume the scheduler."""
    global _scheduler
    if _scheduler:
        if enabled:
            if _scheduler.state == 2: # PAUSED
                _scheduler.resume()
                log.info("Scheduler resumed.")
        else:
            if _scheduler.running:
                _scheduler.pause()
                log.info("Scheduler paused.")

def run_job_now(job_id: str):
    """Trigger a job immediately."""
    global _scheduler
    if _scheduler and _scheduler.get_job(job_id):
        _scheduler.modify_job(job_id, next_run_time=None) # Run now
        # OR:
        # _scheduler.get_job(job_id).func()
        # But correctly:
        job = _scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=None) # Scheduled for now
            # But BackgroundScheduler needs to wake up.
            # Simpler: just call the function directly?
            # No, user wants the job logic.
            # Force run:
            job.func()

