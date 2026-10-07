from celery import Celery

from app.core.config import settings

celery_app = Celery("slotwise", broker=settings.redis_url, include=["app.tasks.bookings"])

celery_app.conf.update(
    timezone="UTC",
    # In tests, run tasks immediately in the same process instead of queueing them
    task_always_eager=settings.celery_task_always_eager,
    # Acknowledge a task only after it finishes, so a worker crash re-runs it
    task_acks_late=True,
    beat_schedule={
        "release-expired-holds": {
            "task": "app.tasks.bookings.release_expired_holds",
            "schedule": 30.0,  # seconds
        },
    },
)
