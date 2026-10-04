import asyncio

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "queue_manager",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


@celery_app.task
def expire_due_tickets_task():
    from app.workers.ticket_expiration import expire_due_tickets

    return asyncio.run(expire_due_tickets())


celery_app.conf.beat_schedule = {
    "expire-due-tickets-every-minute": {
        "task": "app.workers.celery_app.expire_due_tickets_task",
        "schedule": 60.0,
    },
}

celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True