from datetime import datetime
from enum import Enum
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase): pass
class Role(str, Enum): CUSTOMER="CUSTOMER"; ADMIN="ADMIN"
class TicketStatus(str, Enum): WAITING="WAITING"; CHECKED_IN="CHECKED_IN"; CALLED="CALLED"; IN_SERVICE="IN_SERVICE"; COMPLETED="COMPLETED"; EXPIRED="EXPIRED"; CANCELLED="CANCELLED"

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    phone: Mapped[str]=mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(Text())
    role: Mapped[str]=mapped_column(String(16), default=Role.CUSTOMER.value)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), server_default=func.now())

class Business(Base):
    __tablename__="businesses"
    id: Mapped[int]=mapped_column(primary_key=True)
    owner_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str]=mapped_column(String(160))
    address: Mapped[str|None]=mapped_column(String(300), nullable=True)
    latitude: Mapped[float|None]=mapped_column(nullable=True)
    longitude: Mapped[float|None]=mapped_column(nullable=True)
    is_open: Mapped[bool]=mapped_column(Boolean, default=True)

class Service(Base):
    __tablename__="services"
    id: Mapped[int]=mapped_column(primary_key=True)
    business_id: Mapped[int]=mapped_column(ForeignKey("businesses.id"), index=True)
    name: Mapped[str]=mapped_column(String(160))
    avg_duration_minutes: Mapped[int]=mapped_column(Integer, default=30)
    active: Mapped[bool]=mapped_column(Boolean, default=True)

class Queue(Base):
    __tablename__="queues"
    id: Mapped[int]=mapped_column(primary_key=True)
    service_id: Mapped[int]=mapped_column(ForeignKey("services.id"), index=True)
    name: Mapped[str]=mapped_column(String(160))
    is_open: Mapped[bool]=mapped_column(Boolean, default=True)
    next_sequence: Mapped[int]=mapped_column(Integer, default=1)

class Ticket(Base):
    __tablename__="queue_tickets"
    id: Mapped[int]=mapped_column(primary_key=True)
    queue_id: Mapped[int]=mapped_column(ForeignKey("queues.id"), index=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    queue_sequence: Mapped[int]=mapped_column(Integer)

    call_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    skip_once: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    status: Mapped[str]=mapped_column(String(20), default=TicketStatus.WAITING.value, index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), server_default=func.now())
    check_in_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    called_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    service_started_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    resolved_reason: Mapped[str|None]=mapped_column(String(32), nullable=True)
