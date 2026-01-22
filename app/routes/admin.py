import uuid
import os
from fastapi import APIRouter, Request, Depends, HTTPException, Form, File, UploadFile, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta
from passlib.context import CryptContext

from app.models import User, Tour, TourImage, Booking, Review
from app.utils import get_current_admin, notify_subscribers
from app.database import get_db
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates", auto_reload=True)

# Password context for hashing and verification
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Helper functions for password handling
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

@router.get('/admin/dashboard', response_class=HTMLResponse)
async def admin_dashboard(
    request: Request, 
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_admin)
):
    """Admin dashboard with statistics and data visualization"""
    
    # Get tours (admins see their own, superadmins see all)
    if user.is_superadmin:
        tours = db.query(Tour).options(joinedload(Tour.images)).all()
        # For superadmins, show all bookings
        total_bookings = db.query(Booking).count()
        
        # Get total revenue from confirmed bookings
        total_revenue = db.query(func.sum(Booking.total_price)).filter(
            Booking.status == 'confirmed'
        ).scalar() or 0
        
        # Get total reviews
        total_reviews = db.query(Review).count()
        
        # Get recent bookings (last 10)
        recent_bookings = db.query(Booking).options(
            joinedload(Booking.tour),
            joinedload(Booking.user)
        ).order_by(Booking.created_at.desc()).limit(10).all()
        
        # Get reviews
        reviews = db.query(Review).options(
            joinedload(Review.tour),
            joinedload(Review.user)
        ).order_by(Review.created_at.desc()).limit(10).all()
        
        # Get pending bookings count
        pending_bookings = db.query(Booking).filter(
            Booking.status == 'pending'
        ).count()
        
        # Get recent activities (simplified version)
        recent_activities = []
        
    else:
        # Regular admin - only see their own tours
        tours = db.query(Tour).options(joinedload(Tour.images)).filter(Tour.creator_id == user.id).all()
        
        # Get bookings for this operator's tours
        total_bookings = db.query(Booking).join(Tour).filter(Tour.creator_id == user.id).count()
        
        # Calculate total revenue
        total_revenue = db.query(func.sum(Booking.total_price)).join(Tour).filter(
            Tour.creator_id == user.id,
            Booking.status == 'confirmed'
        ).scalar() or 0
        
        # Get reviews for this operator's tours
        total_reviews = db.query(Review).join(Tour).filter(Tour.creator_id == user.id).count()
        
        # Get recent bookings for this operator
        recent_bookings = db.query(Booking).join(Tour).filter(
            Tour.creator_id == user.id
        ).options(
            joinedload(Booking.tour),
            joinedload(Booking.user)
        ).order_by(Booking.created_at.desc()).limit(10).all()
        
        # Get reviews for this operator
        reviews = db.query(Review).join(Tour).filter(
            Tour.creator_id == user.id
        ).options(
            joinedload(Review.tour),
            joinedload(Review.user)
        ).order_by(Review.created_at.desc()).limit(10).all()
        
        # Get pending bookings count
        pending_bookings = db.query(Booking).join(Tour).filter(
            Tour.creator_id == user.id,
            Booking.status == 'pending'
        ).count()
        
        # Get recent activities (simplified version)
        recent_activities = []
    
    # Calculate statistics
    total_tours = len(tours)
    
    # Get top tours by revenue (simplified)
    top_tours_data = []
    if user.is_superadmin:
        tour_revenues = db.query(
            Tour,
            func.sum(Booking.total_price).label('revenue')
        ).outerjoin(Booking).filter(
            Booking.status == 'confirmed'
        ).group_by(Tour.id).order_by(desc('revenue')).limit(5).all()
        
        for tour, revenue in tour_revenues:
            top_tours_data.append({
                'title': tour.title,
                'revenue': revenue or 0,
                'image': tour.images[0].image_url if tour.images else None
            })
    else:
        tour_revenues = db.query(
            Tour,
            func.sum(Booking.total_price).label('revenue')
        ).outerjoin(Booking).filter(
            Tour.creator_id == user.id,
            Booking.status == 'confirmed'
        ).group_by(Tour.id).order_by(desc('revenue')).limit(5).all()
        
        for tour, revenue in tour_revenues:
            top_tours_data.append({
                'title': tour.title,
                'revenue': revenue or 0,
                'image': tour.images[0].image_url if tour.images else None
            })
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": user,
        "tours": tours,
        "total_tours": total_tours,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "total_reviews": total_reviews,
        "pending_bookings_count": pending_bookings,
        "bookings": recent_bookings,
        "reviews": reviews,
        "top_tours": top_tours_data,
        "recent_activities": recent_activities,
        "average_rating": 4.5,  # You can calculate this from reviews
        "rating_distribution": {5: 60, 4: 25, 3: 10, 2: 3, 1: 2},  # Example distribution
    })

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
    
    tour = db.query(Tour).options(joinedload(Tour.creator)).filter(Tour.id == tour_id).first()
    
    if not tour:
        return templates.TemplateResponse("admin/edit_tour.html", {
            "request": request,
            "error": "Tour not found",
            "tour_id": tour_id
        })
    
    if not user.is_superadmin and tour.creator_id != user.id:
        raise HTTPException(status_code=403, detail="You can only update tours you created")    
    
    # Update fields
    if title := form.get("title"):
        tour.title = title
    if description := form.get("description"):
        tour.description = description
    if price := form.get("price"):
        tour.price = float(price)
    if duration := form.get("duration"):
        tour.duration = duration
    if locations := form.get("locations"):
        tour.locations = locations
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

@router.post('/admin/bookings/{booking_id}/status')
async def update_booking_status(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Update booking status (confirm, decline, cancel)"""
    try:
        data = await request.json()
        new_status = data.get('status')
        
        if new_status not in ['pending', 'confirmed', 'declined', 'cancelled']:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Check if user has permission
        tour = db.query(Tour).filter(Tour.id == booking.tour_id).first()
        if not user.is_superadmin and tour.creator_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Update status and timestamps
        booking.status = new_status
        if new_status == 'cancelled':
            booking.cancelled_at = datetime.utcnow()
        elif new_status == 'confirmed':
            booking.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {"success": True, "message": f"Booking status updated to {new_status}"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating booking status: {str(e)}")

@router.post('/admin/profile/update', response_class=HTMLResponse)
async def update_profile(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Update admin profile information"""
    try:
        form = await request.form()
        
        # Update user fields
        if full_name := form.get('full_name'):
            user.full_name = full_name
        
        if email := form.get('email'):
            # Check if email is already taken by another user
            existing_user = db.query(User).filter(User.email == email, User.id != user.id).first()
            if existing_user:
                # Store error in session for display
                request.session['error'] = "Email already in use"
                return RedirectResponse(url="/admin/dashboard#profile", status_code=303)
            user.email = email
        
        if phone := form.get('phone'):
            user.phone = phone
        
        if company_name := form.get('company_name'):
            user.company_name = company_name
        
        if bio := form.get('bio'):
            user.bio = bio
        
        db.commit()
        
        # Set success message in session
        request.session['success'] = "Profile updated successfully"
        return RedirectResponse(url="/admin/dashboard#profile", status_code=303)
    
    except Exception as e:
        request.session['error'] = f"Error updating profile: {str(e)}"
        return RedirectResponse(url="/admin/dashboard#profile", status_code=303)

@router.post('/admin/profile/change-password', response_class=HTMLResponse)
async def change_password(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Change admin password"""
    try:
        form = await request.form()
        
        current_password = form.get('current_password')
        new_password = form.get('new_password')
        confirm_password = form.get('confirm_password')
        
        # Validate inputs
        if not current_password or not new_password or not confirm_password:
            request.session['error'] = "All password fields are required"
            return RedirectResponse(url="/admin/dashboard#profile", status_code=303)
        
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            request.session['error'] = "Current password is incorrect"
            return RedirectResponse(url="/admin/dashboard#profile", status_code=303)
        
        # Check password strength (optional)
        if len(new_password) < 8:
            request.session['error'] = "New password must be at least 8 characters long"
            return RedirectResponse(url="/admin/dashboard#profile", status_code=303)
        
        if new_password != confirm_password:
            request.session['error'] = "New passwords do not match"
            return RedirectResponse(url="/admin/dashboard#profile", status_code=303)
        
        # Update password
        user.hashed_password = hash_password(new_password)
        db.commit()
        
        # Set success message
        request.session['success'] = "Password changed successfully"
        return RedirectResponse(url="/admin/dashboard#profile", status_code=303)
    
    except Exception as e:
        request.session['error'] = f"Error changing password: {str(e)}"
        return RedirectResponse(url="/admin/dashboard#profile", status_code=303)

@router.post('/admin/reviews/{review_id}/verify')
async def verify_review(
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Verify a review"""
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        
        # Check permission
        tour = db.query(Tour).filter(Tour.id == review.tour_id).first()
        if not user.is_superadmin and tour.creator_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        review.is_verified = True
        db.commit()
        
        return {"success": True, "message": "Review verified successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying review: {str(e)}")

@router.delete('/admin/reviews/{review_id}')
async def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Delete a review"""
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        
        # Check permission
        tour = db.query(Tour).filter(Tour.id == review.tour_id).first()
        if not user.is_superadmin and tour.creator_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        db.delete(review)
        db.commit()
        
        return {"success": True, "message": "Review deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting review: {str(e)}")

@router.get('/admin/bookings')
async def get_all_bookings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Get all bookings with filtering"""
    try:
        if user.is_superadmin:
            bookings = db.query(Booking).options(
                joinedload(Booking.tour),
                joinedload(Booking.user)
            ).order_by(Booking.created_at.desc()).all()
        else:
            bookings = db.query(Booking).join(Tour).filter(
                Tour.creator_id == user.id
            ).options(
                joinedload(Booking.tour),
                joinedload(Booking.user)
            ).order_by(Booking.created_at.desc()).all()
        
        # Convert to serializable format
        bookings_data = []
        for booking in bookings:
            bookings_data.append({
                'id': booking.id,
                'tour_title': booking.tour.title if booking.tour else None,
                'tour_image': booking.tour.images[0].image_url if booking.tour and booking.tour.images else None,
                'customer_name': booking.user.full_name if booking.user else None,
                'customer_email': booking.user.email if booking.user else None,
                'tour_date': booking.tour_date.isoformat() if booking.tour_date else None,
                'adults': booking.adults,
                'kids': booking.kids,
                'total_price': booking.total_price,
                'tour_type': booking.tour_type if hasattr(booking, 'tour_type') else 'normal',
                'status': booking.status,
                'created_at': booking.created_at.isoformat() if booking.created_at else None,
            })
        
        return bookings_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching bookings: {str(e)}")

@router.get('/admin/revenue/analytics')
async def get_revenue_analytics(
    period: str = "monthly",  # monthly, quarterly, yearly
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Get revenue analytics data"""
    try:
        if user.is_superadmin:
            # Get all confirmed bookings
            confirmed_bookings = db.query(Booking).filter(
                Booking.status == 'confirmed'
            ).all()
        else:
            # Get only confirmed bookings for user's tours
            confirmed_bookings = db.query(Booking).join(Tour).filter(
                Tour.creator_id == user.id,
                Booking.status == 'confirmed'
            ).all()
        
        # Calculate revenue by period
        monthly_revenue = {}
        quarterly_revenue = {}
        yearly_revenue = {}
        
        for booking in confirmed_bookings:
            # Monthly
            month_key = booking.created_at.strftime("%Y-%m")
            monthly_revenue[month_key] = monthly_revenue.get(month_key, 0) + booking.total_price
            
            # Quarterly
            quarter = (booking.created_at.month - 1) // 3 + 1
            quarter_key = f"{booking.created_at.year}-Q{quarter}"
            quarterly_revenue[quarter_key] = quarterly_revenue.get(quarter_key, 0) + booking.total_price
            
            # Yearly
            year_key = booking.created_at.strftime("%Y")
            yearly_revenue[year_key] = yearly_revenue.get(year_key, 0) + booking.total_price
        
        # Sort by date
        monthly_revenue = dict(sorted(monthly_revenue.items()))
        quarterly_revenue = dict(sorted(quarterly_revenue.items()))
        yearly_revenue = dict(sorted(yearly_revenue.items()))
        
        # Get the last 12 months for chart
        last_12_months = {}
        for i in range(11, -1, -1):
            date = datetime.utcnow() - timedelta(days=30*i)
            month_key = date.strftime("%Y-%m")
            last_12_months[month_key] = monthly_revenue.get(month_key, 0)
        
        return {
            "period": period,
            "total_revenue": sum(monthly_revenue.values()),
            "monthly": monthly_revenue,
            "quarterly": quarterly_revenue,
            "yearly": yearly_revenue,
            "last_12_months": last_12_months,
            "total_bookings": len(confirmed_bookings),
            "average_booking_value": sum(monthly_revenue.values()) / len(confirmed_bookings) if confirmed_bookings else 0
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating revenue analytics: {str(e)}")

# Additional endpoints for enhanced dashboard functionality

@router.get('/admin/stats/overview')
async def get_stats_overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Get overview statistics for dashboard"""
    try:
        # Get counts
        if user.is_superadmin:
            total_tours = db.query(Tour).count()
            total_bookings = db.query(Booking).count()
            total_reviews = db.query(Review).count()
            pending_bookings = db.query(Booking).filter(Booking.status == 'pending').count()
            confirmed_bookings = db.query(Booking).filter(Booking.status == 'confirmed').count()
            total_revenue = db.query(func.sum(Booking.total_price)).filter(
                Booking.status == 'confirmed'
            ).scalar() or 0
        else:
            total_tours = db.query(Tour).filter(Tour.creator_id == user.id).count()
            total_bookings = db.query(Booking).join(Tour).filter(Tour.creator_id == user.id).count()
            total_reviews = db.query(Review).join(Tour).filter(Tour.creator_id == user.id).count()
            pending_bookings = db.query(Booking).join(Tour).filter(
                Tour.creator_id == user.id,
                Booking.status == 'pending'
            ).count()
            confirmed_bookings = db.query(Booking).join(Tour).filter(
                Tour.creator_id == user.id,
                Booking.status == 'confirmed'
            ).count()
            total_revenue = db.query(func.sum(Booking.total_price)).join(Tour).filter(
                Tour.creator_id == user.id,
                Booking.status == 'confirmed'
            ).scalar() or 0
        
        # Calculate month-over-month growth
        current_month = datetime.utcnow().strftime("%Y-%m")
        last_month = (datetime.utcnow().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        
        if user.is_superadmin:
            current_month_revenue = db.query(func.sum(Booking.total_price)).filter(
                Booking.status == 'confirmed',
                func.strftime("%Y-%m", Booking.created_at) == current_month
            ).scalar() or 0
            
            last_month_revenue = db.query(func.sum(Booking.total_price)).filter(
                Booking.status == 'confirmed',
                func.strftime("%Y-%m", Booking.created_at) == last_month
            ).scalar() or 0
        else:
            current_month_revenue = db.query(func.sum(Booking.total_price)).join(Tour).filter(
                Tour.creator_id == user.id,
                Booking.status == 'confirmed',
                func.strftime("%Y-%m", Booking.created_at) == current_month
            ).scalar() or 0
            
            last_month_revenue = db.query(func.sum(Booking.total_price)).join(Tour).filter(
                Tour.creator_id == user.id,
                Booking.status == 'confirmed',
                func.strftime("%Y-%m", Booking.created_at) == last_month
            ).scalar() or 0
        
        # Calculate growth percentage
        revenue_growth = ((current_month_revenue - last_month_revenue) / last_month_revenue * 100) if last_month_revenue > 0 else 0
        
        return {
            "total_tours": total_tours,
            "total_bookings": total_bookings,
            "total_reviews": total_reviews,
            "pending_bookings": pending_bookings,
            "confirmed_bookings": confirmed_bookings,
            "total_revenue": total_revenue,
            "current_month_revenue": current_month_revenue,
            "last_month_revenue": last_month_revenue,
            "revenue_growth": round(revenue_growth, 2),
            "average_booking_value": total_revenue / confirmed_bookings if confirmed_bookings > 0 else 0
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching statistics: {str(e)}")

@router.get('/admin/recent/activities')
async def get_recent_activities(
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Get recent activities for dashboard"""
    try:
        activities = []
        
        # Get recent bookings
        if user.is_superadmin:
            recent_bookings = db.query(Booking).options(
                joinedload(Booking.tour),
                joinedload(Booking.user)
            ).order_by(Booking.created_at.desc()).limit(limit).all()
        else:
            recent_bookings = db.query(Booking).join(Tour).filter(
                Tour.creator_id == user.id
            ).options(
                joinedload(Booking.tour),
                joinedload(Booking.user)
            ).order_by(Booking.created_at.desc()).limit(limit).all()
        
        for booking in recent_bookings:
            activities.append({
                'type': 'booking',
                'title': f'New Booking #{booking.id}',
                'description': f'{booking.user.full_name if booking.user else "Customer"} booked "{booking.tour.title if booking.tour else "Tour"}"',
                'time': booking.created_at,
                'icon': 'calendar-check'
            })
        
        # Get recent reviews
        if user.is_superadmin:
            recent_reviews = db.query(Review).options(
                joinedload(Review.tour),
                joinedload(Review.user)
            ).order_by(Review.created_at.desc()).limit(limit).all()
        else:
            recent_reviews = db.query(Review).join(Tour).filter(
                Tour.creator_id == user.id
            ).options(
                joinedload(Review.tour),
                joinedload(Review.user)
            ).order_by(Review.created_at.desc()).limit(limit).all()
        
        for review in recent_reviews:
            activities.append({
                'type': 'review',
                'title': f'New Review ({review.rating} stars)',
                'description': f'{review.user.full_name if review.user else "User"} reviewed "{review.tour.title if review.tour else "Tour"}"',
                'time': review.created_at,
                'icon': 'star'
            })
        
        # Sort by time and limit
        activities.sort(key=lambda x: x['time'], reverse=True)
        activities = activities[:limit]
        
        # Convert datetime to string
        for activity in activities:
            activity['time'] = activity['time'].strftime('%Y-%m-%d %H:%M') if activity['time'] else 'N/A'
        
        return activities
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching activities: {str(e)}")

@router.get('/admin/booking/{booking_id}/details')
async def get_booking_details(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin)
):
    """Get detailed booking information"""
    try:
        booking = db.query(Booking).options(
            joinedload(Booking.tour),
            joinedload(Booking.user)
        ).filter(Booking.id == booking_id).first()
        
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Check permission
        tour = db.query(Tour).filter(Tour.id == booking.tour_id).first()
        if not user.is_superadmin and tour.creator_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        booking_details = {
            'id': booking.id,
            'tour': {
                'id': booking.tour.id if booking.tour else None,
                'title': booking.tour.title if booking.tour else None,
                'price': booking.tour.price if booking.tour else None,
                'duration': booking.tour.duration if booking.tour else None,
                'country': booking.tour.country if booking.tour else None,
                'images': [img.image_url for img in booking.tour.images] if booking.tour else []
            },
            'customer': {
                'id': booking.user.id if booking.user else None,
                'name': booking.user.full_name if booking.user else None,
                'email': booking.user.email if booking.user else None,
                'phone': booking.user.phone if booking.user else None
            },
            'booking_details': {
                'adults': booking.adults,
                'kids': booking.kids,
                'tour_date': booking.tour_date.isoformat() if booking.tour_date else None,
                'total_price': booking.total_price,
                'status': booking.status,
                'payment_method': booking.payment_method,
                'payment_status': booking.payment_status,
                'donation': booking.donation,
                'special_requirements': booking.special_requirements,
                'created_at': booking.created_at.isoformat() if booking.created_at else None,
                'cancelled_at': booking.cancelled_at.isoformat() if booking.cancelled_at else None
            }
        }
        
        return booking_details
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching booking details: {str(e)}")