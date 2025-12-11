# app/routes/superadmin_creation.py
from fastapi import APIRouter, Request, Depends, HTTPException, status, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
import re
from typing import Tuple

from app.database import get_db
from app.models import User
from app.utils import get_current_user, hash_password
from app.utils import get_current_superadmin

router = APIRouter(prefix="/superadmin", tags=["superadmin-creation"])
templates = Jinja2Templates(directory="app/templates")

def validate_password_strength(password: str):
    """Validate password meets security requirements and ALWAYS return a tuple"""
    if len(password) < 8:
        return (False, "Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        return (False, "Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        return (False, "Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        return (False, "Password must contain at least one number")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return (False, "Password must contain at least one special character")
    return (True, "")

def validate_email_format(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

# SuperAdmin Creation Page
@router.get("/create", response_class=HTMLResponse)
async def superadmin_creation_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if current user is superadmin or if no superadmins exist
    is_first_superadmin = False
    
    # Check if any superadmin exists
    superadmin_count = db.query(User).filter(User.is_superadmin == True).count()
    
    if superadmin_count == 0:
        # First superadmin creation - no authentication required
        is_first_superadmin = True
    else:
        # Existing superadmins exist - require superadmin privileges
        if not current_user or not current_user.is_superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Superadmin privileges required"
            )
    
    return templates.TemplateResponse(
        "superadmin/create_superadmin.html",
        {
            "request": request,
            "is_first_superadmin": is_first_superadmin,
            "current_user": current_user
        }
    )

# Create SuperAdmin (API Endpoint)
@router.post("/create", response_class=JSONResponse)
async def create_superadmin(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(...),
    company_name: str = Form(None),
    company_link: str = Form(None),
    db: Session = Depends(get_db)
):
    # Validation checks
    errors = {}
    
    # Check if any superadmin exists
    superadmin_count = db.query(User).filter(User.is_superadmin == True).count()
    
    if superadmin_count > 0:
        # Require superadmin authentication
        current_user = get_current_user(request, db)
        if not current_user or not current_user.is_superadmin:
            errors["general"] = "Superadmin privileges required to create new superadmins"
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"success": False, "errors": errors}
            )
    
    # Validate email format
    if not validate_email_format(email):
        errors["email"] = "Invalid email format"
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        errors["email"] = "Email already registered"
    
    # Validate password strength
    is_valid_password, password_error = validate_password_strength(password)
    if not is_valid_password:
        errors["password"] = password_error
    
    # Check password match
    if password != confirm_password:
        errors["confirm_password"] = "Passwords do not match"
    
    # Validate full name
    if not full_name.strip():
        errors["full_name"] = "Full name is required"
    elif len(full_name.strip()) < 2:
        errors["full_name"] = "Full name must be at least 2 characters"
    
    # If there are errors, return them
    if errors:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "errors": errors}
        )
    
    # Create the superadmin user
    try:
        new_superadmin = User(
            email=email.strip().lower(),
            hashed_password=hash_password(password),
            full_name=full_name.strip(),
            company_name=company_name.strip() if company_name else None,
            company_link=company_link.strip() if company_link else None,
            is_active=True,
            is_admin=True,
            is_superadmin=True,
            email_verified=True,
            newsletter_subscribed=False,
            auth_method="email"
        )
        
        db.add(new_superadmin)
        db.commit()
        db.refresh(new_superadmin)
        
        # Log the creation (you might want to add logging here)
        print(f"Superadmin created: {email} by {request.client.host if request.client else 'unknown'}")
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "message": "Superadmin created successfully",
                "user_id": new_superadmin.id,
                "email": new_superadmin.email
            }
        )
        
    except Exception as e:
        db.rollback()
        print(f"Error creating superadmin: {str(e)}")
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "errors": {"general": "An error occurred while creating superadmin"}
            }
        )

# List Existing SuperAdmins
@router.get("/list", response_class=HTMLResponse)
async def list_superadmins(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)  # Only superadmins can view this
):
    superadmins = db.query(User).filter(
        User.is_superadmin == True,
        User.is_active == True
    ).order_by(User.created_at.desc()).all()
    
    total_superadmins = len(superadmins)
    
    return templates.TemplateResponse(
        "superadmin/superadmin_list.html",
        {
            "request": request,
            "superadmins": superadmins,
            "total_superadmins": total_superadmins,
            "current_user": current_user
        }
    )

# Promote User to SuperAdmin
@router.post("/promote/{user_id}")
async def promote_to_superadmin(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    # Check if current user is superadmin
    if not current_user or not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required"
        )
    
    # Find the user to promote
    user_to_promote = db.query(User).filter(User.id == user_id).first()
    if not user_to_promote:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is already superadmin
    if user_to_promote.is_superadmin:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "User is already a superadmin"}
        )
    
    # Promote to superadmin
    user_to_promote.is_superadmin = True
    user_to_promote.is_admin = True  # Ensure they're also admin
    
    try:
        db.commit()
        
        # Log the promotion
        print(f"User {user_id} promoted to superadmin by {current_user.id}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": f"User {user_to_promote.email} promoted to superadmin",
                "user": {
                    "id": user_to_promote.id,
                    "email": user_to_promote.email,
                    "full_name": user_to_promote.full_name
                }
            }
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error promoting user: {str(e)}"
        )

# Demote SuperAdmin
@router.post("/demote/{user_id}")
async def demote_superadmin(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    # Check if current user is superadmin
    if not current_user or not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required"
        )
    
    # Prevent self-demotion
    if user_id == current_user.id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Cannot demote yourself"}
        )
    
    # Find the superadmin to demote
    user_to_demote = db.query(User).filter(
        User.id == user_id,
        User.is_superadmin == True
    ).first()
    
    if not user_to_demote:
        raise HTTPException(status_code=404, detail="Superadmin not found")
    
    # Count remaining superadmins
    remaining_superadmins = db.query(User).filter(
        User.is_superadmin == True,
        User.id != user_id,
        User.is_active == True
    ).count()
    
    # Ensure at least one superadmin remains
    if remaining_superadmins == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Cannot demote the last superadmin"}
        )
    
    # Demote to regular admin
    user_to_demote.is_superadmin = False
    # Keep as admin but remove superadmin privileges
    
    try:
        db.commit()
        
        # Log the demotion
        print(f"User {user_id} demoted from superadmin by {current_user.id}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": f"User {user_to_demote.email} demoted from superadmin",
                "user": {
                    "id": user_to_demote.id,
                    "email": user_to_demote.email,
                    "full_name": user_to_demote.full_name
                }
            }
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error demoting user: {str(e)}"
        )

# Check if any superadmin exists (for first-time setup)
@router.get("/check-first-setup", response_class=JSONResponse)
async def check_first_setup(db: Session = Depends(get_db)):
    superadmin_count = db.query(User).filter(User.is_superadmin == True).count()
    
    return JSONResponse(
        content={
            "first_setup_required": superadmin_count == 0,
            "superadmin_count": superadmin_count
        }
    )