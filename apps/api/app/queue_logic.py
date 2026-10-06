from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Queue, Service, Ticket, TicketStatus

async def fill_available_slots(
    db: AsyncSession,
    queue: Queue,
    now: datetime | None = None,
) -> list[Ticket]:
    """
    Заполняет свободные боксы очереди самыми ранними CHECKED_IN клиентами.

    Инвариант:
        IN_SERVICE + CALLED <= Service.capacity

    Предполагается, что Queue уже заблокирована через SELECT ... FOR UPDATE.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    capacity = await db.scalar(
        select(Service.capacity)
        .where(Service.id == queue.service_id)
    )

    if capacity is None:
        return []

    occupied = await db.scalar(
        select(func.count(Ticket.id))
        .where(
            Ticket.queue_id == queue.id,
            Ticket.status.in_([
                TicketStatus.CALLED.value,
                TicketStatus.IN_SERVICE.value,
            ]),
        )
    )

    available_slots = max(0, capacity - (occupied or 0))

    if available_slots == 0:
        return []

    candidates = (
        await db.scalars(
            select(Ticket)
            .where(
                Ticket.queue_id == queue.id,
                Ticket.status == TicketStatus.CHECKED_IN.value,
            )
            .order_by(Ticket.queue_sequence)
            .with_for_update()
        )
    ).all()

    if not candidates:
        return []

    selected: list[Ticket] = []

    # Сначала выбираем клиентов, которых не нужно пропускать.
    for ticket in candidates:
        if len(selected) >= available_slots:
            break

        if not ticket.skip_once:
            selected.append(ticket)

    # Если свободных боксов осталось, добираем пропущенных клиентов.
    if len(selected) < available_slots:
        for ticket in candidates:
            if len(selected) >= available_slots:
                break

            if ticket in selected:
                continue

            ticket.skip_once = False
            selected.append(ticket)

    # Все CHECKED_IN, которых мы реально обошли,
    # больше не должны сохранять skip_once.
    if selected:
        last_selected_sequence = selected[-1].queue_sequence

        for ticket in candidates:
            if (
                ticket.queue_sequence < last_selected_sequence
                and ticket not in selected
            ):
                ticket.skip_once = False

    for ticket in selected:
        ticket.status = TicketStatus.CALLED.value
        ticket.called_at = now
        ticket.call_attempts += 1
        ticket.expires_at = now + timedelta(minutes=5)

    return selected