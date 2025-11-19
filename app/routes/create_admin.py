import uuid
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.models import User
from app.utils import get_current_user, create_session, delete_session, verify_password, hash_password, send_email
from app.database import get_db
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates", auto_reload=True)

@router.get("/admin/register", response_class=HTMLResponse)
async def get_admin_register(request: Request):
    """Display admin registration form"""
    return templates.TemplateResponse("admin_register.html", {"request": request})

@router.post("/admin/register", response_class=HTMLResponse)
async def register_admin(
    request: Request,
    db: Session = Depends(get_db),
    company_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    company_link: str = Form(None)  # Optional field
):
    """Process admin registration"""
    try:
        # Check if user already exists
        if db.query(User).filter(User.email == email).first():
            return templates.TemplateResponse("admin_register.html", {
                "request": request,
                "error": "Email already exists"
            })
        
        # Validate password length
        if len(password) < 8:
            return templates.TemplateResponse("admin_register.html", {
                "request": request,
                "error": "Password must be at least 8 characters long"
            })
        
        # Create new admin user
        hashed_password = hash_password(password)
        new_admin = User(
            email=email,
            hashed_password=hashed_password,
            full_name=company_name,  # Using company name as full name
            company_name=company_name,
            company_link=company_link,
            is_admin=True
        )
        
        db.add(new_admin)
        db.commit()
        
        # Create session and log the admin in
        session_id = create_session(db, new_admin.id)
        response = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="auth_session_id", 
            value=session_id, 
            httponly=True, 
            max_age=1800,
            samesite="Lax",
            path="/"
        )
        
        return response
        
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("admin_register.html", {
            "request": request,
            "error": f"An error occurred during registration: {str(e)}"
        })