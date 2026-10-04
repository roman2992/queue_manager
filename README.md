# Queue Manager

MVP monorepo for virtual queues in auto services.

## Backend

Python 3.13 + FastAPI + SQLAlchemy async + PostgreSQL/PostGIS + Redis + Celery.

### Local API

```bash
cd apps/api
pip install -e '.[dev]'
PYTHONPATH=. pytest -q
alembic upgrade head
uvicorn app.main:app --reload
```

### Core flow

1. Admin registers with `role=ADMIN`.
2. Admin creates business and service; service gets a queue automatically.
3. Customer registers with `role=CUSTOMER` and joins a queue.
4. Ticket receives a persistent `queue_sequence`.
5. Position is calculated from active tickets, never stored as source of truth.
6. Customer can check in without changing queue order.
7. Admin calls next → starts service → completes ticket.
8. Expired tickets resolve the same way as completed tickets for TTL chaining.

## MVP rules

- First ticket TTL: 3h30m from creation.
- Every following ticket TTL: 2h from predecessor `resolved_at`.
- Active queue statuses: WAITING, CHECKED_IN, CALLED, IN_SERVICE.
- Historical tickets are retained; they are not deleted.
