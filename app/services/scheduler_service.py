import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.uploader_service import execute_post_upload

class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def schedule_post(self, post_id: int, run_at: datetime):
        job_id = f"post_{post_id}"
        # If job already exists, replace it
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            execute_post_upload,
            trigger="date",
            run_date=run_at,
            args=[post_id],
            id=job_id,
            misfire_grace_time=3600
        )

    def cancel_post(self, post_id: int):
        job_id = f"post_{post_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

scheduler_service = SchedulerService()
