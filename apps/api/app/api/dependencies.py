from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.models import User

bearer=HTTPBearer()
async def current_user(creds: HTTPAuthorizationCredentials=Depends(bearer), db: AsyncSession=Depends(get_db)):
    try: payload=jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(status_code=401, detail="Invalid token")
    user=await db.scalar(select(User).where(User.id==int(payload["sub"])))
    if not user: raise HTTPException(status_code=401, detail="User not found")
    return user

def require_admin(user=Depends(current_user)):
    if user.role != "ADMIN": raise HTTPException(status_code=403, detail="Admin role required")
    return user
