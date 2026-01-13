import uuid
import os
import secrets
from urllib.parse import urlencode
import httpx
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc6749 import OAuth2Token
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.models import User
from app.utils import get_current_user, create_session, delete_session, verify_password, hash_password, send_email,is_superadmin
from app.database import get_db
from fastapi.templating import Jinja2Templates
from sqlalchemy import func


router = APIRouter()

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_CLIENT_SECRET = os.getenv("APPLE_CLIENT_SECRET")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

oauth = OAuth()

# Configure Google OAuth
'''oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'redirect_uri': f"{BASE_URL}/auth/google/callback"
    }
)'''

# Configure Apple OAuth
'''oauth.register(
    name='apple',
    client_id=APPLE_CLIENT_ID,
    client_secret=APPLE_CLIENT_SECRET,
    authorize_url='https://appleid.apple.com/auth/authorize',
    access_token_url='https://appleid.apple.com/auth/token',
    client_kwargs={
        'scope': 'name email',
        'redirect_uri': f'{BASE_URL}/auth/apple/callback'
    }
)'''

@router.get("/auth/test")
async def auth_test():
    return {"message": "Auth router is working!"}

@router.get("/auth/debug/config")
async def debug_config():
    """Check Google OAuth configuration"""
    return {
        "google_client_id_set": bool(GOOGLE_CLIENT_ID),
        "google_client_secret_set": bool(GOOGLE_CLIENT_SECRET),
        "base_url": BASE_URL,
        "redirect_uri": f"{BASE_URL}/auth/google/callback"
    }

@router.get("/auth/google")
async def google_login(request: Request):
    """Initiate Google OAuth flow"""
    try:
        # Check if configuration is set
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            return RedirectResponse("/login?error=Google+OAuth+not+configured")
        
        redirect_uri = f"{BASE_URL}/auth/google/callback"
        
        # Use manual OAuth flow instead of Authlib's automatic discovery
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "prompt": "select_account"
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return RedirectResponse(auth_url)
        
    except Exception as e:
        print(f"Google login error: {str(e)}")
        return RedirectResponse("/login?error=Google+OAuth+configuration+error")
    

@router.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    try:
        code = request.query_params.get("code")
        error = request.query_params.get("error")
        
        print(f"Google callback received - code: {bool(code)}, error: {error}")
        
        if error:
            return RedirectResponse(f"/login?error=Google+auth+failed:{error}")
        
        if not code:
            return RedirectResponse("/login?error=No+authorization+code+received")
        
        # Exchange code for tokens
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{BASE_URL}/auth/google/callback"
        }
        
        async with httpx.AsyncClient() as client:
            # Get access token
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            print(f"Token response status: {token_response.status_code}")
            
            if token_response.status_code != 200:
                error_msg = "Failed to exchange code for token"
                try:
                    error_data = token_response.json()
                    error_msg = error_data.get("error_description", error_msg)
                    print(f"Token error: {error_data}")
                except:
                    pass
                return RedirectResponse(f"/login?error={error_msg.replace(' ', '+')}")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            
            if not access_token:
                return RedirectResponse("/login?error=No+access+token+received")
            
            # Get user info
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            print(f"Userinfo response status: {userinfo_response.status_code}")
            
            if userinfo_response.status_code != 200:
                return RedirectResponse("/login?error=Failed+to+get+user+information")
            
            user_info = userinfo_response.json()
            print(f"User info: {user_info}")
        
        # Process user information
        email = user_info.get('email')
        google_id = user_info.get('sub')
        name = user_info.get('name', '')
        picture = user_info.get('picture')  # ✅ Get picture from Google
        email_verified = user_info.get('email_verified', False)
        
        if not email:
            return RedirectResponse("/login?error=No+email+provided+by+Google")
        
        print(f"Processing user: {email}, google_id: {google_id}")
        
        # ✅ CORRECTED: Find or create user FIRST, then update picture
        user = db.query(User).filter(
            (User.email == email) | (User.google_id == google_id)
        ).first()
        
        if user:
            # Update existing user
            print(f"Found existing user by email: {user.id}")
            if not user.google_id:
                user.google_id = google_id
            # ✅ Update picture if available
            if picture and hasattr(user, 'picture'):
                user.picture = picture
            db.commit()
        else:
            # Create new user
            random_password = secrets.token_urlsafe(32)
            hashed_password = hash_password(random_password)
            
            # ✅ Create user with picture if the field exists
            user_data = {
                "email": email,
                "hashed_password": hashed_password,
                "full_name": name or email.split('@')[0],
                "google_id": google_id,
                "email_verified": email_verified
            }
            
            # Only add picture if the column exists in User model
            if hasattr(User, 'picture'):
                user_data["picture"] = picture
            
            user = User(**user_data)
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created new user: {user.id}")
        
        # Create session
        session_id = create_session(db, user.id)
        response = RedirectResponse(url="/tours?just_logged_in=true", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="auth_session_id", 
            value=session_id, 
            httponly=True, 
            max_age=1800, 
            samesite="Lax", 
            path="/"
        )
        print("Google login successful!")
        return response
        
    except Exception as e:
        print(f"Google callback error: {str(e)}")
        import traceback
        traceback.print_exc()
        return RedirectResponse("/login?error=Google+authentication+failed")

@router.get("/auth/apple")
async def apple_login(request: Request):
    """Initiate Apple OAuth flow"""
    redirect_uri = f'{BASE_URL}/auth/apple/callback'
    return await oauth.apple.authorize_redirect(request, redirect_uri)

@router.get("/auth/apple/callback")
async def apple_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Apple OAuth callback"""
    try:
        token = await oauth.apple.authorize_access_token(request)
        
        # Apple returns user info differently - we need to decode the ID token
        id_token = token.get('id_token')
        if not id_token:
            raise HTTPException(status_code=400, detail="No ID token from Apple")
        
        # Decode Apple ID token to get user info
        # Note: You'll need to implement proper JWT verification for Apple
        user_info = await verify_apple_token(id_token)
        
        email = user_info.get('email')
        apple_id = user_info.get('sub')
        
        # Apple might not return name in subsequent logins
        name = user_info.get('name', {})
        full_name = f"{name.get('firstName', '')} {name.get('lastName', '')}".strip()
        if not full_name:
            full_name = email.split('@')[0]
        
        # Find or create user
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            user = User(
                email=email,
                full_name=full_name,
                apple_id=apple_id,
                email_verified=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        elif not user.apple_id:
            user.apple_id = apple_id
            db.commit()
        
        # Create session
        session_id = create_session(db, user.id)
        response = RedirectResponse(url="/tours", status_code=status.HTTP_302_FOUND)
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
        print(f"Apple OAuth error: {str(e)}")
        return RedirectResponse(url="/login?error=Apple+authentication+failed")

async def verify_apple_token(id_token: str) -> dict:
    """Verify Apple ID token and return user info"""
    # This is a simplified version - you should implement proper JWT verification
    # using Apple's public keys
    try:
        # For production, use proper JWT verification with Apple's public keys
        # You can use authlib or python-jose for this
        import jwt
        
        # Note: This is a basic implementation - you need to handle proper verification
        decoded = jwt.decode(id_token, options={"verify_signature": False})
        return decoded
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid Apple token")


templates = Jinja2Templates(directory="app/templates", auto_reload=True)
temporary_reset_tokens = {}
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

@router.get("/signup", response_class=HTMLResponse)
async def get_signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup", response_class=HTMLResponse)
async def signup(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    email = form.get("email")
    password = form.get("password")
    full_name = form.get("full_name")
    
    if not all([email, password, full_name]):
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Please fill in all fields"})
    
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Email already exists"})
    
    hashed_password = hash_password(password)
    new_user = User(email=email, hashed_password=hashed_password, full_name=full_name)
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    email = form.get("email")
    password = form.get("password")
    
    user = db.query(User).filter(User.email == email).first()
    
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid email or password"})
    
    session_id = create_session(db, user.id)
    if user.is_superadmin:
        redirect_url = "/superadmin/dashboard"
    elif user.is_admin:
        redirect_url = "/admin/dashboard"  # if you have one
    else:
        redirect_url = "/tours"

    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key="auth_session_id",
        value=session_id,
        httponly=True,
        max_age=1800,
        samesite="Lax",
        path="/"
    )
    return response
    
    #response = RedirectResponse(url="/tours", status_code=status.HTTP_302_FOUND)
    #response.set_cookie(key="auth_session_id", value=session_id, httponly=True, max_age=1800, samesite="Lax", path="/")
    #return response

@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("auth_session_id")
    if session_id:
        delete_session(db, session_id)
    
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="auth_session_id")
    return response

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_form(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@router.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return templates.TemplateResponse("forgot_password.html", {"request": request, "error": "Email not found."})
        
        reset_token = str(uuid.uuid4())
        temporary_reset_tokens[reset_token] = {
            "email": email,
            "expires": datetime.utcnow() + timedelta(hours=1)
        }

        reset_link = f"{BASE_URL.rstrip('/')}/reset-password?token={reset_token}"
        subject = "Password Reset Request"
        body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; background-color: #f9f9f9; padding: 20px;">
                <table width="100%" style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
                <tr style="background-color: #003366; color: #ffffff;">
                    <td style="padding: 20px; font-size: 18px;">
                    Password Reset Request
                    </td>
                </tr>
                <tr>
                    <td style="padding: 20px;">
                    <p>Dear {user.full_name},</p>
                    <p>We received a request to reset your password. Please click the link below to proceed:</p>
                    <p><a href="{reset_link}" style="background-color: #003366; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
                    <p>If you did not request this, please ignore this email or contact our support team.</p>
                    <p>Best regards,<br>Pearl Tours Support Team</p>
                    </td>
                </tr>
                <tr style="background-color: #f0f0f0; text-align: center;">
                    <td style="padding: 10px; font-size: 12px; color: #777;">
                    &copy; {datetime.now().year} Pearl Tours. All rights reserved.
                    </td>
                </tr>
                </table>
            </body>
            </html>
            """

        try:
            send_email(user.email, subject, body, is_html=True) 
        except Exception as e: 
            return templates.TemplateResponse("forgot_password.html", {"request": request, "error": f"Failed to send email: {str(e)}"})

        return templates.TemplateResponse("forgot_password.html", {"request": request, "message": "Reset link sent!"})
    
    except Exception as e:
        return templates.TemplateResponse("forgot_password.html", {"request": request, "error": "An unexpected error occurred."})

@router.get("/reset-password", response_class=HTMLResponse)
async def show_reset_password_form(request: Request, token: str = ""):
    if not token:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "error": "Missing reset token"
        })

    if token not in temporary_reset_tokens:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "error": "Invalid or expired token"
        })

    token_info = temporary_reset_tokens[token]
    if datetime.utcnow() > token_info["expires"]:
        del temporary_reset_tokens[token]
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "error": "Token has expired"
        })

    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token
    })

@router.post("/reset-password", response_class=HTMLResponse)
async def reset_password_post(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    error = None
    try:
        if not new_password or not confirm_password:
            error = "Please fill in all fields"
            raise ValueError
        
        if new_password != confirm_password:
            error = "Passwords do not match"
            raise ValueError
        
        if len(new_password) < 8:
            error = "Password must be at least 8 characters"
            raise ValueError

        if token not in temporary_reset_tokens:
            error = "Invalid or expired token"
            raise ValueError

        token_info = temporary_reset_tokens[token]
        if datetime.utcnow() > token_info["expires"]:
            del temporary_reset_tokens[token]
            error = "Token has expired"
            raise ValueError

        email = token_info["email"]
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            error = "User not found"
            raise ValueError

        hashed_password = hash_password(new_password)
        user.hashed_password = hashed_password
        db.commit()
        db.refresh(user)

        del temporary_reset_tokens[token]
        return RedirectResponse(url="/login", status_code=303)

    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "error": error or "An error occurred",
            "token": token
        })
    
@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """User profile page"""
    if not current_user:
        return RedirectResponse("/login")
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user
    })   
     # ✅ Redirect super admin
    if is_superadmin(current_user):
         return RedirectResponse(url="/superadmin/dashboard", status_code=HTTP_302_FOUND) 
    
# Add this debug endpoint to help troubleshoot
@router.get("/auth/debug/config")
async def debug_config():
    """Check Google OAuth configuration"""
    return {
        "google_client_id": GOOGLE_CLIENT_ID[:20] + "..." if GOOGLE_CLIENT_ID else None,
        "google_client_secret": "***" + GOOGLE_CLIENT_SECRET[-4:] if GOOGLE_CLIENT_SECRET else None,
        "base_url": BASE_URL,
        "redirect_uri": f"{BASE_URL}/auth/google/callback",
        "client_id_format": "Correct" if GOOGLE_CLIENT_ID and '.apps.googleusercontent.com' in GOOGLE_CLIENT_ID else "Incorrect"
    }