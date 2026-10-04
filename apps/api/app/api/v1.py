from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import current_user, require_admin
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models import User, Business, Service, Queue, Ticket, TicketStatus, Role

router=APIRouter()
class AuthIn(BaseModel): phone:str; password:str=Field(min_length=6); role:Role=Role.CUSTOMER
class BusinessIn(BaseModel): name:str; address:str|None=None; latitude:float|None=None; longitude:float|None=None
class ServiceIn(BaseModel): name:str; avg_duration_minutes:int=30
class TicketOut(BaseModel): id:int; queue_sequence:int; status:str; people_ahead:int; expires_at:datetime|None

@router.post("/auth/register")
async def register(data:AuthIn, db:AsyncSession=Depends(get_db)):
    if await db.scalar(select(User).where(User.phone==data.phone)):
        raise HTTPException(409,"Phone already registered")
    user=User(phone=data.phone,password_hash=hash_password(data.password),role=data.role.value);
    db.add(user);
    await db.commit();
    await db.refresh(user)
    return {"access_token":create_access_token(str(user.id),user.role),"user_id":user.id,"role":user.role}

@router.post("/auth/login")
async def login(data:AuthIn, db:AsyncSession=Depends(get_db)):
    user=await db.scalar(select(User).where(User.phone==data.phone))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,"Invalid credentials")
    return {"access_token":create_access_token(str(user.id),user.role),"user_id":user.id,"role":user.role}

@router.post("/admin/businesses")
async def create_business(data:BusinessIn,user=Depends(require_admin),db:AsyncSession=Depends(get_db)):
    b=Business(owner_id=user.id,**data.model_dump());
    db.add(b);
    await db.commit();
    await db.refresh(b);
    return b

@router.post("/admin/businesses/{business_id}/services")
async def create_service(business_id:int,data:ServiceIn,user=Depends(require_admin),db:AsyncSession=Depends(get_db)):
    b=await db.scalar(select(Business).where(Business.id==business_id,Business.owner_id==user.id))
    if not b: raise HTTPException(404,"Business not found")
    s=Service(business_id=business_id,**data.model_dump()); db.add(s); await db.commit(); await db.refresh(s)
    q=Queue(service_id=s.id,name=s.name); db.add(q); await db.commit(); await db.refresh(q)
    return {"service":s,"queue":q}

@router.get("/businesses")
async def businesses(db:AsyncSession=Depends(get_db)): return (await db.scalars(select(Business))).all()

@router.post("/queues/{queue_id}/tickets",response_model=TicketOut)
async def join_queue(queue_id:int,user=Depends(current_user),db:AsyncSession=Depends(get_db)):
    q=await db.scalar(select(Queue).where(Queue.id==queue_id).with_for_update())
    if not q or not q.is_open:
        raise HTTPException(400,"Queue is closed")
    existing=await db.scalar(select(Ticket).where(
        Ticket.queue_id==queue_id,
        Ticket.user_id==user.id,
        Ticket.status.in_(
            [s.value for s in TicketStatus if s in {
                TicketStatus.WAITING,
                TicketStatus.CHECKED_IN,
                TicketStatus.CALLED,
                TicketStatus.IN_SERVICE}])))
    if existing:
        raise HTTPException(409,"Already in queue")
    seq = q.next_sequence
    q.next_sequence += 1

    now = datetime.now(timezone.utc)

    active_statuses = [
        TicketStatus.WAITING.value,
        TicketStatus.CHECKED_IN.value,
        TicketStatus.CALLED.value,
        TicketStatus.IN_SERVICE.value,
    ]

    earlier_active = await db.scalar(
        select(Ticket.id).where(
            Ticket.queue_id == queue_id,
            Ticket.queue_sequence < seq,
            Ticket.status.in_(active_statuses),
        ).limit(1)
    )

    t = Ticket(
        queue_id=queue_id,
        user_id=user.id,
        queue_sequence=seq,
        expires_at=None if earlier_active else now + timedelta(hours=2),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    ahead=await db.scalar(
        select(func.count()).select_from(Ticket).where(
            Ticket.queue_id==queue_id,
            Ticket.queue_sequence<seq,
            Ticket.status.in_(
                [s.value for s in [
                    TicketStatus.WAITING,
                    TicketStatus.CHECKED_IN,
                    TicketStatus.CALLED,
                    TicketStatus.IN_SERVICE]])))

    return TicketOut(id=t.id,queue_sequence=seq,status=t.status,people_ahead=ahead or 0,expires_at=t.expires_at)

@router.get("/tickets/{ticket_id}",response_model=TicketOut)
async def ticket(ticket_id:int,user=Depends(current_user),db:AsyncSession=Depends(get_db)):
    t=await db.scalar(
        select(Ticket).where(
            Ticket.id==ticket_id,
            Ticket.user_id==user.id
        )
    )
    if not t: raise HTTPException(404,"Ticket not found")
    ahead=await db.scalar(select(func.count()).select_from(Ticket).where(Ticket.queue_id==t.queue_id,Ticket.queue_sequence<t.queue_sequence,Ticket.status.in_([x.value for x in [TicketStatus.WAITING,TicketStatus.CHECKED_IN,TicketStatus.CALLED,TicketStatus.IN_SERVICE]])))
    return TicketOut(id=t.id,queue_sequence=t.queue_sequence,status=t.status,people_ahead=ahead or 0,expires_at=t.expires_at)

@router.post("/tickets/{ticket_id}/check-in", response_model=TicketOut)
async def check_in(
    ticket_id: int,
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):

    t = await db.scalar(
        select(Ticket)
        .where(Ticket.id == ticket_id, Ticket.user_id == user.id)
        .with_for_update()
    )

    if not t:
        raise HTTPException(404, "Ticket not found")

    if t.status != TicketStatus.WAITING.value:
        raise HTTPException(400, "Ticket cannot be checked in")

    now = datetime.now(timezone.utc)

    if t.expires_at and t.expires_at <= now:
        t.status = TicketStatus.EXPIRED.value
        t.resolved_at = now
        t.resolved_reason = (
            "QR_RESCAN_TTL" if t.call_attempts >= 2 else "ARRIVAL_TTL"
        )
        await db.commit()
        raise HTTPException(410, "Check-in deadline expired")

    t.status = TicketStatus.CHECKED_IN.value
    t.check_in_at = now
    t.expires_at = None

    await db.commit()
    await db.refresh(t)

    ahead = await db.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(
            Ticket.queue_id == t.queue_id,
            Ticket.queue_sequence < t.queue_sequence,
            Ticket.status.in_([
                TicketStatus.WAITING.value,
                TicketStatus.CHECKED_IN.value,
                TicketStatus.CALLED.value,
                TicketStatus.IN_SERVICE.value,
            ]),
        )
    )

    return TicketOut(
        id=t.id,
        queue_sequence=t.queue_sequence,
        status=t.status,
        people_ahead=ahead or 0,
        expires_at=t.expires_at,
    )


@router.post("/tickets/{ticket_id}/cancel")
async def cancel_ticket(
    ticket_id: int,
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    queue_id = await db.scalar(
        select(Ticket.queue_id).where(
            Ticket.id == ticket_id,
            Ticket.user_id == user.id,
        )
    )
    if queue_id is None:
        raise HTTPException(404, "Ticket not found")

    queue = await db.scalar(
        select(Queue)
        .where(Queue.id == queue_id)
        .with_for_update()
    )
    if not queue:
        raise HTTPException(404, "Queue not found")

    t = await db.scalar(
        select(Ticket)
        .where(
            Ticket.id == ticket_id,
            Ticket.user_id == user.id,
        )
        .with_for_update()
    )

    if not t:
        raise HTTPException(404, "Ticket not found")

    if t.status not in (
        TicketStatus.WAITING.value,
        TicketStatus.CHECKED_IN.value,
        TicketStatus.CALLED.value,
    ):
        raise HTTPException(400, "Ticket cannot be cancelled")

    #was_called = t.status == TicketStatus.CALLED.value
    now = datetime.now(timezone.utc)
    t.status = TicketStatus.CANCELLED.value
    t.resolved_at = now
    t.resolved_reason = "CANCELLED"
    t.expires_at = None

    earlier_active = await db.scalar(
        select(Ticket.id)
        .where(
            Ticket.queue_id == queue_id,
            Ticket.queue_sequence < t.queue_sequence,
            Ticket.status.in_([
                TicketStatus.WAITING.value,
                TicketStatus.CHECKED_IN.value,
                TicketStatus.CALLED.value,
                TicketStatus.IN_SERVICE.value,
            ]),
        )
        .limit(1)
    )

    if not earlier_active:
        next_ticket = await db.scalar(
            select(Ticket)
            .where(
                Ticket.queue_id == queue_id,
                Ticket.queue_sequence > t.queue_sequence,
                Ticket.status.in_([
                    TicketStatus.WAITING.value,
                    TicketStatus.CHECKED_IN.value,
                    TicketStatus.CALLED.value,
                    TicketStatus.IN_SERVICE.value,
                ]),
            )
            .order_by(Ticket.queue_sequence)
            .limit(1)
            .with_for_update()
        )

        if next_ticket:
            if (
                    next_ticket.status == TicketStatus.WAITING.value
                    and next_ticket.expires_at is None
            ):
                next_ticket.expires_at = now + timedelta(hours=2)

            elif next_ticket.status == TicketStatus.CHECKED_IN.value:
                next_ticket.status = TicketStatus.CALLED.value
                next_ticket.called_at = now
                next_ticket.call_attempts += 1
                next_ticket.expires_at = now + timedelta(minutes=5)



    await db.commit()

    return {
        "ticket_id": t.id,
        "status": t.status,
        "resolved_at": t.resolved_at,
    }


async def _owned_queue(queue_id:int,user,db):
    q=await db.scalar(select(Queue).join(Service,Queue.service_id==Service.id).join(Business,Business.id==Service.business_id).where(Queue.id==queue_id,Business.owner_id==user.id))
    if not q: raise HTTPException(404,"Queue not found")
    return q

@router.get("/admin/queues/{queue_id}")
async def admin_queue(queue_id:int,user=Depends(require_admin),db:AsyncSession=Depends(get_db)):
    q=await _owned_queue(queue_id,user,db)
    rows=(await db.scalars(select(Ticket).where(Ticket.queue_id==q.id).order_by(Ticket.queue_sequence))).all()
    return [{"id":t.id,"sequence":t.queue_sequence,"status":t.status,"expires_at":t.expires_at} for t in rows]

@router.post("/admin/queues/{queue_id}/call-next")
async def call_next(
    queue_id: int,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = await _owned_queue(queue_id, user, db)

    # Serialize calls within this queue.
    q = await db.scalar(
        select(Queue)
        .where(Queue.id == q.id)
        .with_for_update()
    )

    already_called = await db.scalar(
        select(Ticket.id)
        .where(
            Ticket.queue_id == q.id,
            Ticket.status == TicketStatus.CALLED.value,
        )
        .limit(1)
    )

    if already_called:
        raise HTTPException(409, "A ticket is already called")


    candidates = (
        await db.scalars(
            select(Ticket)
            .where(
                Ticket.queue_id == q.id,
                Ticket.status == TicketStatus.CHECKED_IN.value,
            )
            .order_by(Ticket.queue_sequence)
            .with_for_update()
        )
    ).all()

    if not candidates:
        raise HTTPException(409, "No checked-in tickets available")

    # Select the first customer not marked to be skipped.
    t = next(
        (item for item in candidates if not item.skip_once),
        None,
    )

    if t:
        # Clear the one-time skip for customers bypassed this time.
        # в чем смысл?
        for item in candidates:
            if item.queue_sequence >= t.queue_sequence:
                break
            if item.skip_once:
                item.skip_once = False
    else:
        # All candidates are marked: call the earliest to avoid
        # leaving the queue stuck.
        t = candidates[0]
        t.skip_once = False

    now = datetime.now(timezone.utc)

    t.status = TicketStatus.CALLED.value
    t.called_at = now
    t.call_attempts += 1
    t.expires_at = now + timedelta(minutes=5)

    await db.commit()

    return {
        "ticket_id": t.id,
        "sequence": t.queue_sequence,
        "status": t.status,
        "call_attempts": t.call_attempts,
        "expires_at": t.expires_at,
    }


@router.post("/admin/tickets/{ticket_id}/start")
async def start_ticket(ticket_id:int,user=Depends(require_admin),db:AsyncSession=Depends(get_db)):
    t=await db.scalar(
        select(Ticket).join(Queue,Ticket.queue_id==Queue.id)
        .join(Service,Queue.service_id==Service.id)
        .join(Business,Business.id==Service.business_id)
        .where(Ticket.id==ticket_id,Business.owner_id==user.id)
        .with_for_update())
    if not t or t.status != TicketStatus.CALLED.value:
        raise HTTPException(400,"Ticket cannot be started")
    t.status=TicketStatus.IN_SERVICE.value;
    t.service_started_at=datetime.now(timezone.utc);
    t.expires_at = None
    await db.commit();
    return {"ticket_id":t.id,"status":t.status}


@router.post("/admin/tickets/{ticket_id}/complete")
async def complete_ticket(
    ticket_id: int,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Получаем queue_id, чтобы сначала заблокировать очередь
    queue_id = await db.scalar(
        select(Ticket.queue_id).where(Ticket.id == ticket_id)
    )
    if queue_id is None:
        raise HTTPException(404, "Ticket not found")

    queue = await db.scalar(
        select(Queue)
        .where(Queue.id == queue_id)
        .with_for_update()
    )
    if not queue:
        raise HTTPException(404, "Queue not found")

    # Проверяем владельца и блокируем талон после блокировки очереди
    t = await db.scalar(
        select(Ticket)
        .join(Queue, Ticket.queue_id == Queue.id)
        .join(Service, Queue.service_id == Service.id)
        .join(Business, Business.id == Service.business_id)
        .where(
            Ticket.id == ticket_id,
            Business.owner_id == user.id,
        )
        .with_for_update()
    )

    if not t or t.status != TicketStatus.IN_SERVICE.value:
        raise HTTPException(400, "Ticket cannot be completed")

    now = datetime.now(timezone.utc)
    t.status = TicketStatus.COMPLETED.value
    t.completed_at = now
    t.resolved_at = now
    t.resolved_reason = "COMPLETED"

    # Находим следующего активного клиента в очереди
    next_ticket = await db.scalar(
        select(Ticket)
        .where(
            Ticket.queue_id == queue_id,
            Ticket.queue_sequence > t.queue_sequence,
            Ticket.status.in_([
                TicketStatus.WAITING.value,
                TicketStatus.CHECKED_IN.value,
                TicketStatus.CALLED.value,
                TicketStatus.IN_SERVICE.value,
            ]),
        )
        .order_by(Ticket.queue_sequence)
        .limit(1)
        .with_for_update()
    )

    # Если следующий клиент ещё не прошёл Check-in,
    # запускаем ему 2-часовой срок прибытия
    if (
        next_ticket
        and next_ticket.status == TicketStatus.WAITING.value
        and next_ticket.expires_at is None
    ):
        next_ticket.expires_at = now + timedelta(hours=2)

    await db.commit()

    return {
        "ticket_id": t.id,
        "status": t.status,
        "resolved_at": t.resolved_at,
    }
