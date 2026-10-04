from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

FIRST_TICKET_TTL = timedelta(hours=3, minutes=30)
FOLLOWING_TICKET_TTL = timedelta(hours=2)

ACTIVE_STATUSES = {"WAITING", "CHECKED_IN", "CALLED", "IN_SERVICE"}

@dataclass(frozen=True)
class TicketSnapshot:
    sequence: int
    status: str
    created_at: datetime
    resolved_at: datetime | None = None


def expires_at_for(ticket: TicketSnapshot, predecessor: TicketSnapshot | None) -> datetime:
    if predecessor is None:
        return ticket.created_at + FIRST_TICKET_TTL
    if predecessor.resolved_at is None:
        raise ValueError("Predecessor must be resolved before starting the following ticket TTL")
    return predecessor.resolved_at + FOLLOWING_TICKET_TTL


def active_tickets(tickets: list[TicketSnapshot]) -> list[TicketSnapshot]:
    return sorted((t for t in tickets if t.status in ACTIVE_STATUSES), key=lambda t: t.sequence)


def queue_position(tickets: list[TicketSnapshot], sequence: int) -> int:
    active = active_tickets(tickets)
    ahead = sum(1 for t in active if t.sequence < sequence)
    return ahead + 1


def people_ahead(tickets: list[TicketSnapshot], sequence: int) -> int:
    return max(queue_position(tickets, sequence) - 1, 0)


def split_ahead(tickets: list[TicketSnapshot], sequence: int) -> tuple[int, int]:
    ahead = [t for t in active_tickets(tickets) if t.sequence < sequence]
    on_site = sum(t.status in {"CHECKED_IN", "CALLED", "IN_SERVICE"} for t in ahead)
    on_the_way = sum(t.status == "WAITING" for t in ahead)
    return on_site, on_the_way
