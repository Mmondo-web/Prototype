# app/routes/culture.py
#
# Dynamic East Africa culture page for Mmondo Adventures.
# - Uses SQLite via SQLAlchemy (through get_db)
# - No static region data inside this file
# - Everything comes from the database and is passed into `culture.html`

from datetime import datetime

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload   # <-- joinedload added for images

from app.database import get_db
from app import models  # we assume you (or the original dev) defined these

router = APIRouter()
templates = Jinja2Templates(directory="app/templates", auto_reload=True)


@router.get("/cultures", response_class=HTMLResponse)
async def show_cultures(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Main East Africa culture page.

    This function:
      1. Loads all culture-related data from SQLite via SQLAlchemy models
      2. Converts them into simple dictionaries
      3. Passes them to `culture.html` for rendering

    Nothing here is hard-coded culture content.
    """

    # --------------------------------------------------------
    # 1. LOAD COUNTRIES / REGIONS
    # --------------------------------------------------------
    # Uses the Country model you added (by Bammez).
    # Now we also preload related CountryImage rows via joinedload.
    countries_db = (
        db.query(models.Country)
        .options(joinedload(models.Country.images))  # <-- Added for image relationship
        .order_by(models.Country.name)
        .all()
    )

    regions = []
    country_options = []

    for c in countries_db:
        # ===== Map CountryImage -> template format (Added by Bammez) =====
        images = []
        for img in getattr(c, "images", []):
            images.append(
                {
                    "url": img.image_url,          # /static/uploads/uganda1.jpg etc.
                    "alt": img.alt_text or c.name  # fallback alt text
                }
            )

        # Food can be a simple string (as stored in your model)
        food_value = c.food

        # If you later add a relation for interests, this list can be filled.
        interests = []
        if hasattr(c, "interests_rel"):
            for rel in c.interests_rel:
                if hasattr(rel, "interest") and hasattr(rel.interest, "slug"):
                    interests.append(rel.interest.slug)

        # Build region dict for the template
        region = {
            "slug": c.slug,                        # used as HTML id + scroll target
            "name": c.name,                        # visible title
            "country_slug": getattr(c, "slug", None),
            "country_name": getattr(c, "country_name", None) or c.name,

            "food": food_value,
            "dress": c.dress,
            "traditions": getattr(c, "traditions", None),
            "tour_themes": getattr(c, "tour_themes", None),

            "images": images,                      # now from CountryImage

            # YouTube: full link stored in DB, template converts to /embed/ form
            "video_url": getattr(c, "video_url", None),
            "video_credit": getattr(c, "video_credit", None),

            "testimonial": getattr(c, "testimonial", None),

            # For filters
            "interests": interests,

            # CTA links – you can adjust URLs to your real tour pages
            "tours_url": f"/tours?country={c.slug}",
            "itinerary_url": f"/plan-trip?country={c.slug}",
            "badge_label": getattr(c, "badge_label", None),
            "badge_color": getattr(c, "badge_color", None),
        }

        regions.append(region)

        # For country dropdown (filter)
        country_options.append(
            {
                "slug": c.slug,
                "name": c.name,
            }
        )

    # --------------------------------------------------------
    # 2. LOAD INTEREST TYPES (for the dropdown)
    # --------------------------------------------------------
    interests_db = []
    if hasattr(models, "InterestType"):
        interests_db = (
            db.query(models.InterestType)
            .order_by(models.InterestType.display_order, models.InterestType.label)
            .all()
        )

    interests = [
        {"slug": i.slug, "label": i.label}
        for i in interests_db
    ]

    # --------------------------------------------------------
    # 3. LOAD FESTIVALS
    # --------------------------------------------------------
    festivals_db = []
    if hasattr(models, "Festival"):
        festivals_db = db.query(models.Festival).all()

    festivals = [
        {
            "name": f.name,
            "date_label": getattr(f, "date_label", None),
            "location_label": getattr(f, "location_label", None),
            "description": f.description,
        }
        for f in festivals_db
    ]

    # --------------------------------------------------------
    # 4. LOAD STORIES / LEGENDS
    # --------------------------------------------------------
    stories_db = []
    if hasattr(models, "Story"):
        stories_db = (
            db.query(models.Story)
            .order_by(models.Story.sort_order)
            .all()
        )

    stories = [
        {
            "title": s.title,
            "region_label": getattr(s, "region_label", None),
            "summary": s.summary,
        }
        for s in stories_db
    ]

    # --------------------------------------------------------
    # 5. LOAD LOCAL HOSTS
    # --------------------------------------------------------
    locals_db = []
    if hasattr(models, "LocalHost"):
        locals_db = (
            db.query(models.LocalHost)
            .order_by(models.LocalHost.name)
            .all()
        )

    locals_list = [
        {
            "name": l.name,
            "location": getattr(l, "location", None),
            "quote": getattr(l, "quote", None),
        }
        for l in locals_db
    ]

    # --------------------------------------------------------
    # 6. LOAD DESTINATIONS FOR MAP MARKERS
    # --------------------------------------------------------
    destinations_db = []
    if hasattr(models, "Destination"):
        destinations_db = db.query(models.Destination).all()

    destinations = [
        {
            "slug": d.country_slug,
            "name": d.name,
            "country_name": getattr(d, "country_name", None),
            "lat": d.lat,
            "lng": d.lng,
            "tours_url": f"/tours?country={d.country_slug}",
        }
        for d in destinations_db
    ]

    # --------------------------------------------------------
    # 7. RENDER TEMPLATE
    # --------------------------------------------------------
    return templates.TemplateResponse(
        "culture.html",
        {
            "request": request,

            "page_title": "East Africa Cultures | Mmondo Adventures",
            "header_title": "East Africa Cultural Tour Bank",
            "header_subtitle": "Discover food, dance, dress and traditions across East Africa – curated by Mmondo Adventures.",

            "regions": regions,
            "country_options": country_options,
            "interests": interests,
            "festivals": festivals,
            "stories": stories,
            "locals": locals_list,
            "destinations": destinations,

            "current_year": datetime.utcnow().year,
        },
    )

