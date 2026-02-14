from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.scheduler.jobs import morning_brief
from app.config import settings

scheduler = BackgroundScheduler()

def init_scheduler():
    # Run morning_brief at 6 AM daily
    scheduler.add_job(morning_brief, CronTrigger(hour=6, minute=0))
    scheduler.start()

def run_job_now(job_name: str):
    if job_name == "morning_brief":
        morning_brief()

def toggle_scheduler(enabled: bool):
    if enabled:
        if not scheduler.running:
            scheduler.start()
    else:
        if scheduler.running:
            scheduler.shutdown()
