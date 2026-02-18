from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.utils import get_current_user

router = APIRouter(tags=["messaging_views"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/messaging", response_class=HTMLResponse)
async def messaging_page(request: Request, current_user = Depends(get_current_user)):
    return templates.TemplateResponse("messaging.html", {
        "request": request,
        "current_user": current_user
    })