# app/routes/culture_admin.py
# Admin routes for managing culture countries and images

import os
import uuid
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Country, CountryImage, User
from app.utils import get_current_admin
from fastapi.templating import Jinja2Templates
from sqlalchemy import func

router = APIRouter()
templates = Jinja2Templates(directory="app/templates", auto_reload=True)

UPLOAD_DIR = "static/uploads/cultures"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/admin/cultures", response_class=HTMLResponse)
def admin_cultures(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    countries = db.query(Country).all()

    return templates.TemplateResponse(
        "admin/cultures.html",
        {
            "request": request,
            "countries": countries
        }
    )


@router.post("/admin/cultures/{country_id}/upload")
async def upload_country_image(
    country_id: int,
    image: UploadFile = File(...),
    is_primary: bool = Form(False),
    alt_text: str = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    country = db.query(Country).filter(Country.id == country_id).first()

    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_ext = os.path.splitext(image.filename)[1]
    filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    content = await image.read()
    with open(file_path, "wb") as f:
        f.write(content)

    if is_primary:
        db.query(CountryImage).filter(
            CountryImage.country_id == country.id
        ).update({"is_primary": False})

    new_img = CountryImage(
        country_id=country.id,
        image_url=f"/static/uploads/cultures/{filename}",
        alt_text=alt_text,
        is_primary=is_primary
    )

    db.add(new_img)
    db.commit()

    return RedirectResponse(
        url=f"/admin/cultures",
        status_code=303
    )


@router.post("/admin/cultures/image/delete/{image_id}")
def delete_country_image(
    image_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    image = db.query(CountryImage).filter(CountryImage.id == image_id).first()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = image.image_url.replace("/", "", 1)  # remove leading slash

    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(image)
    db.commit()

    return RedirectResponse("/admin/cultures", status_code=303)
