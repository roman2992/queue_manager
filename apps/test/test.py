from app.api.v1 import register, AuthIn
from app.core.database import get_db
from pydantic import BaseModel, Field
from app.models import User, Business, Service, Queue, Ticket, TicketStatus, Role
from fastapi import APIRouter, Depends, HTTPException




if __name__ == "__main__":
    print("Начало")

    for i in range(5):
        phone = "+111"
        password = "111"
        role = Role.CUSTOMER
        data = AuthIn(phone, password, role)
        register(data, Depends(get_db))

        print("Пользователь добавлен")

