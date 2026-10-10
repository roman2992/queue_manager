
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Queue, Ticket, TicketStatus

from app.queue_logic import fill_available_slots

ACTIVE_STATUSES = [
    TicketStatus.WAITING.value,
    TicketStatus.CHECKED_IN.value,
    TicketStatus.CALLED.value,
    TicketStatus.IN_SERVICE.value,
]


async def _call_next_checked_in(db, queue_id: int, after_sequence: int):
    """Call the next checked-in customer after the given sequence."""
    candidates = (
        await db.scalars(
            select(Ticket)
            .where(
                Ticket.queue_id == queue_id,
                Ticket.queue_sequence > after_sequence,
                Ticket.status == TicketStatus.CHECKED_IN.value,
            )
            .order_by(Ticket.queue_sequence)
            .with_for_update()
        )
    ).all()

    if not candidates:
        return None

    # Prefer the first customer who is not marked to be skipped.
    ticket = next(
        (item for item in candidates if not item.skip_once),
        None,
    )

    if ticket:
        # Clear skip flags only for customers bypassed this time.
        for item in candidates:
            if item.queue_sequence >= ticket.queue_sequence:
                break
            if item.skip_once:
                item.skip_once = False
    else:
        # Do not leave the queue stuck if everyone is marked.
        ticket = candidates[0]
        ticket.skip_once = False

    now = datetime.now(timezone.utc)
    ticket.status = TicketStatus.CALLED.value
    ticket.called_at = now
    ticket.call_attempts += 1
    ticket.expires_at = now + timedelta(minutes=5)

    return ticket


async def expire_due_tickets():
    """Обработка тикетов CALLED и WAITING, у которых истек срок (5 минут для CALLED, 2 часа для WAITING),
    а также число попыток для CALLED: 1 - вызов след-го либо +5 минут, 2 - статус WAITING + 2 часа,
    3 - EXPIRED"""
    async with SessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Snapshot of potentially overdue tickets. Every ticket is
        # reloaded and validated under a row lock before modification.
        due_rows = (
            await db.execute(
                select(Ticket.id, Ticket.queue_id)
                .where(
                    Ticket.expires_at <= now,
                    Ticket.status.in_([
                        TicketStatus.CALLED.value,
                        TicketStatus.WAITING.value,
                    ]),
                )
                .order_by(Ticket.queue_id, Ticket.queue_sequence)
            )
        ).all()

        processed = 0
        touched_queues = set()

        for ticket_id, queue_id in due_rows:
            # Serialize worker transitions within a queue.
            queue = await db.scalar(
                select(Queue)
                .where(Queue.id == queue_id)
                .with_for_update()
            )

            if not queue:
                continue

            ticket = await db.scalar(
                select(Ticket)
                .where(Ticket.id == ticket_id)
                .with_for_update()
            )

            if (
                not ticket
                or ticket.status not in (
                    TicketStatus.CALLED.value,
                    TicketStatus.WAITING.value,
                )
                or ticket.expires_at is None
                or ticket.expires_at > now
            ):
                continue

            touched_queues.add(queue_id)

            if ticket.status == TicketStatus.WAITING.value:
                # Customer did not complete the QR check-in in time.
                ticket.status = TicketStatus.EXPIRED.value
                ticket.resolved_at = now
                ticket.resolved_reason = (
                    "QR_RESCAN_TTL"
                    if ticket.call_attempts >= 2
                    else "ARRIVAL_TTL"
                )
                ticket.expires_at = None
                processed += 1
                continue

            # CALLED: the five-minute service-start window expired.
            # Release the reserved service slot before promoting anyone.
            attempt = ticket.call_attempts

            if attempt == 1:
                # First failed call: return this ticket to CHECKED_IN,
                # but skip it once if another checked-in client is available.
                ticket.status = TicketStatus.CHECKED_IN.value
                ticket.expires_at = None
                ticket.skip_once = True

                called = await fill_available_slots(
                    db=db,
                    queue=queue,
                    now=now,
                )

                if not called:
                    # Nobody else could take the slot. Call the same
                    # customer for their second attempt.
                    ticket.status = TicketStatus.CALLED.value
                    ticket.skip_once = False
                    ticket.called_at = now
                    ticket.call_attempts = 2
                    ticket.expires_at = now + timedelta(minutes=5)

            elif attempt == 2:
                # Second failed call: allow two hours to rescan the QR.
                ticket.status = TicketStatus.WAITING.value
                ticket.expires_at = now + timedelta(hours=2)
                ticket.resolved_reason = None
                ticket.resolved_at = None
                ticket.skip_once = False

                await fill_available_slots(
                    db=db,
                    queue=queue,
                    now=now,
                )

            else:
                # Third failed call (or any later call).
                ticket.status = TicketStatus.EXPIRED.value
                ticket.resolved_at = now
                ticket.resolved_reason = "CALL_TIMEOUT"
                ticket.expires_at = None
                ticket.skip_once = False

                await fill_available_slots(
                    db=db,
                    queue=queue,
                    now=now,
                )

            processed += 1

        # Start the arrival timer for the first active WAITING ticket
        # if it has no earlier active ticket ahead of it.
        for queue_id in touched_queues:
            head = await db.scalar(
                select(Ticket)
                .where(
                    Ticket.queue_id == queue_id,
                    Ticket.status.in_(ACTIVE_STATUSES),
                )
                .order_by(Ticket.queue_sequence)
                .limit(1)
                .with_for_update()
            )

            if (
                head
                and head.status == TicketStatus.WAITING.value
                and head.expires_at is None
            ):
                head.expires_at = now + timedelta(hours=2)

        await db.commit()
        return processed
