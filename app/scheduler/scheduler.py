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
