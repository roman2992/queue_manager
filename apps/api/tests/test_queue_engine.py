from datetime import datetime, timezone, timedelta
from app.modules.queues.engine import *

def dt(h, m=0): return datetime(2026, 1, 1, h, m, tzinfo=timezone.utc)

def test_first_ticket_ttl():
    t = TicketSnapshot(0, 'WAITING', dt(10))
    assert expires_at_for(t, None) == dt(13) + timedelta(minutes=30)

def test_following_ticket_ttl():
    prev = TicketSnapshot(0, 'COMPLETED', dt(10), dt(11))
    cur = TicketSnapshot(1, 'WAITING', dt(10,))
    assert expires_at_for(cur, prev) == dt(13)

def test_position_ignores_resolved_tickets():
    tickets = [
      TicketSnapshot(0, 'COMPLETED', dt(9), dt(10)),
      TicketSnapshot(1, 'WAITING', dt(10)),
      TicketSnapshot(2, 'CHECKED_IN', dt(10)),
    ]
    assert queue_position(tickets, 2) == 2
    assert people_ahead(tickets, 2) == 1
