# Architecture

The system is a monorepo with a FastAPI backend and one Flutter app containing customer and admin modes.

The backend separates three domains:
- Queue Engine: ordering, lifecycle, TTL, check-in and position.
- ETA Engine: waiting-time estimation (next implementation step).
- Load Engine: active queue counts and percentile-based map marker colors.

PostgreSQL/PostGIS is the source of truth. Redis is used for caching, distributed locks and event fan-out. Celery handles delayed/background work such as expiration and notifications. WebSocket will push queue state changes to mobile clients.
