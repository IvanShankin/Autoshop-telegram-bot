from datetime import timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def init_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(
        timezone=timezone.utc,
        job_defaults={
            "misfire_grace_time": 3600,
            "max_instances": 1,
            "coalesce": True,
        }
    )
    return scheduler