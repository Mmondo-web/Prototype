from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils import get_current_user
from app.models import User
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/users", tags=["users"])

class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    company_name: Optional[str] = None

    class Config:
        orm_mode = True

@router.get("/available", response_model=List[UserOut])
async def get_available_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns users that the current user can message.
    - Customers: only superadmins
    - Admins: only superadmins
    - Superadmins: all users except themselves
    """
    # Determine current user's role using boolean flags
    if current_user.is_superadmin:
        # Superadmin can see all other users
        users = db.query(User).filter(User.id != current_user.id).all()
    elif current_user.is_admin:
        # Admin can only see superadmins
        users = db.query(User).filter(User.is_superadmin == True).all()
    else:
        # Customer can only see superadmins
        users = db.query(User).filter(User.is_superadmin == True).all()

    # Build response list with computed role strings
    result = []
    for user in users:
        if user.is_superadmin:
            role = "superadmin"
        elif user.is_admin:
            role = "admin"
        else:
            role = "customer"
        result.append({
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": role,
            "company_name": user.company_name
        })
    return result