# Queue rules

1. `queue_sequence` is assigned once and never changes.
2. Current position is derived from active tickets with lower sequence.
3. Active statuses: WAITING, CHECKED_IN, CALLED, IN_SERVICE.
4. First ticket expires 3h30m after creation.
5. Every following ticket expires 2h after its immediate predecessor resolves.
6. Resolution advances the queue when the predecessor is COMPLETED, EXPIRED, or CANCELLED.
7. COMPLETED/EXPIRED/CANCELLED tickets remain in history and leave the active queue.
8. `people_ahead` is split into `on_site` (CHECKED_IN/CALLED/IN_SERVICE) and `on_the_way` (WAITING).
9. Map queue count excludes completed, expired, cancelled and currently-in-service customers.
10. Map marker color is based on the service's queue count percentile among services considered at that moment.
11. Marker label is the exact count for 0..999 and `> 1 тыс.` for >=1000.
