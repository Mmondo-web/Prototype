import uuid
import os
from fastapi import APIRouter, Request, Depends, HTTPException, Form, File, UploadFile, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.models import User, Tour, TourImage
from app.utils import get_current_admin, notify_subscribers
from app.database import get_db
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates", auto_reload=True)

@router.get('/admin/dashboard', response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    if not user.is_admin:
        return RedirectResponse(url="/", status_code=303)
    if user.is_superadmin:
        tours = db.query(Tour).options(joinedload(Tour.creator)).all()
    else:
        tours = db.query(Tour).options(joinedload(Tour.creator)).filter(Tour.creator_id == user.id).all()
    tours = db.query(Tour).all()
    return templates.TemplateResponse("admin/dashboard.html", {"request": request, "user": user, "tours": tours})

@router.post('/admin/tours/create', response_class=HTMLResponse)
async def create_tour(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    duration: str = Form(...),
    locations: str = Form(...),
    risk: str = Form(None),
    country: str = Form(...),
    tour_type: str = Form('normal'),
    max_participants: int = Form(20),
    included: str = Form(None),
    not_included: str = Form(None),
    cancellation_policy: str = Form(None),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    try:
        if not images:
            request.session['error'] = "At least one image is required"
            return RedirectResponse(url="/admin/tours/create", status_code=303)

        new_tour = Tour(
            title=title,
            description=description,
            price=price,
            duration=duration,
            locations=locations,
            risk=risk,
            tour_type=tour_type,
            country=country,
            max_participants=max_participants,
            included=included,
            not_included=not_included,
            cancellation_policy=cancellation_policy,
            # Set the creator of the tour
            creator_id=user.id
        )
        db.add(new_tour)
        db.flush()

        upload_dir = "static/uploads"
        os.makedirs(upload_dir, exist_ok=True)

        for idx, image in enumerate(images):
            if not image.content_type.startswith('image/'):
                continue

            file_ext = os.path.splitext(image.filename)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(upload_dir, filename)

            contents = await image.read()
            with open(file_path, "wb") as f:
                f.write(contents)

            db.add(TourImage(
                tour_id=new_tour.id,
                image_url=f"/static/uploads/{filename}",
                is_primary=(idx == 0)
            ))

        db.commit()
        background_tasks.add_task(notify_subscribers, db, new_tour.id)
        return RedirectResponse(url="/admin/dashboard", status_code=303)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating tour: {str(e)}"
        )

@router.get('/admin/tours/edit/{tour_id}', response_class=HTMLResponse)
async def edit_tour(request: Request, tour_id: int, 
                   db: Session = Depends(get_db), 
                   user: User = Depends(get_current_admin)):
    tour = db.query(Tour).options(joinedload(Tour.images), joinedload(Tour.creator)).filter(Tour.id == tour_id).first()
    
    if not tour:
        raise HTTPException(status_code=404, detail="Tour not found")
     # Check if user can edit this tour
    # Superadmins can edit any tour, regular admins can only edit their own
    if not user.is_superadmin and tour.creator_id != user.id:
        raise HTTPException(status_code=403, detail="You can only edit tours you created")
    
    return templates.TemplateResponse("admin/edit_tour.html", {
        "request": request,
        "tour": tour,
        "images": tour.images
    })

@router.post('/admin/tours/update/{tour_id}', response_class=HTMLResponse)
async def update_tour(request: Request, tour_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to access this page")
    
    form = await request.form()
    title = form.get("title")
    description = form.get("description")
    price = form.get("price")
    duration = form.get("duration")
    locations = form.get("locations")
    image_url = form.get("image_url")
    # Missing fields that you must extract:
    risk = form.get("risk")
    country = form.get("country")
    tour_type = form.get("tour_type")
    max_participants = form.get("max_participants")
    included = form.get("included")
    not_included = form.get("not_included")
    cancellation_policy = form.get("cancellation_policy")
    
    
    
    tour = db.query(Tour).options(joinedload(Tour.creator)).filter(Tour.id == tour_id).first()
    
    if not tour:
        return templates.TemplateResponse("admin/edit_tour.html", {
            "request": request,
            "error": "Tour not found",
            "tour_id": tour_id
        })
    # Check ownership - superadmins can edit any, regular admins only their own
    if not user.is_superadmin and tour.creator_id != user.id:
        raise HTTPException(status_code=403, detail="You can only update tours you created")    
    
    if title:
        tour.title = title
    if description:
        tour.description = description
    if price:
        tour.price = price
    if duration:
        tour.duration = duration
    if locations:
        tour.locations = locations
     # Update new fields
    if risk := form.get("risk"):
        tour.risk = risk
    if country := form.get("country"):
        tour.country = country
    if tour_type := form.get("tour_type"):
        tour.tour_type = tour_type    
    if max_participants := form.get("max_participants"):
        tour.max_participants = int(max_participants)
    if included := form.get("included"):
        tour.included = included
    if not_included := form.get("not_included"):
        tour.not_included = not_included
    if cancellation_policy := form.get("cancellation_policy"):
        tour.cancellation_policy = cancellation_policy
        
    
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@router.post('/admin/tours/delete/{tour_id}', response_class=HTMLResponse)
async def delete_tour(
    request: Request,
    tour_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to access this page")
    
    tour = db.query(Tour).filter(Tour.id == tour_id).first()
    if not tour:
        raise HTTPException(status_code=404, detail="Tour not found")
     # Check ownership - superadmins can delete any, regular admins only their own
    if not user.is_superadmin and tour.creator_id != user.id:
        raise HTTPException(status_code=403, detail="You can only delete tours you created")
    
    images = db.query(TourImage).filter(TourImage.tour_id == tour.id).all()
    for img in images:
        filename = img.image_url.split("/")[-1]
        image_path = os.path.join("static", "uploads", filename)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                print(f"Error deleting file {image_path}: {str(e)}")

    db.query(TourImage).filter(TourImage.tour_id == tour.id).delete()
    db.delete(tour)
    db.commit()

    return RedirectResponse(url="/admin/dashboard", status_code=303)