# app/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import os

from app.routes import (
    auth,
    tours,
    admin,
    booking,
    payment,
    newsletter,
    culture,
    tour_details,
    create_admin,
    culture_admin,
    superadmin,
    superadmin_creation,
    messaging,
    messaging_views,
    users
)

from app.database import engine
from app.models import Base

app = FastAPI(debug=True)

# Static files & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.auto_reload = True

# Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key="your_secret_key",  # move to .env later
    session_cookie="session_id",
)

# Routes
app.include_router(auth.router)
app.include_router(tours.router)
app.include_router(culture.router)
app.include_router(admin.router)
app.include_router(booking.router)
app.include_router(payment.router)
app.include_router(newsletter.router)
app.include_router(tour_details.router)
app.include_router(create_admin.router)
app.include_router(culture_admin.router)
app.include_router(superadmin.router)
app.include_router(superadmin_creation.router)
app.include_router(messaging.router)
app.include_router(messaging_views.router)
app.include_router(users.router)


Base.metadata.create_all(bind=engine)  # Create tables if they don't exist
