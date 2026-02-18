from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.utils import get_current_user
from app.models import User, Booking, MessageStatus, UserRole
from app.crud.message import MessageCRUD
from app.schemas.message import MessageCreate, MessageUpdate, MessageWithUsers, Conversation
import logging
from datetime import datetime

router = APIRouter(prefix="/api/messages", tags=["messaging"])
logger = logging.getLogger(__name__)

# Dependency to get message CRUD
def get_message_crud(db: Session = Depends(get_db)):
    return MessageCRUD(db)

@router.post("/", response_model=MessageWithUsers)
async def send_message(
    message: MessageCreate,
    current_user: User = Depends(get_current_user),
    crud: MessageCRUD = Depends(get_message_crud)
):
    """
    Send a new message.
    Customers can only message superadmins about their bookings.
    Superadmins can message any admin.
    """
    # Validate receiver exists
    db = crud.db
    receiver = db.query(User).filter(User.id == message.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    
    # Validate booking if provided
    booking = None
    if message.booking_id:
        booking = db.query(Booking).filter(Booking.id == message.booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # For customers: ensure they own the booking and can only message superadmins
        if current_user.role == UserRole.customer:
            if booking.customer_id != current_user.id:
                raise HTTPException(status_code=403, detail="You don't have permission to message about this booking")
            if receiver.role != UserRole.superadmin:
                raise HTTPException(status_code=403, detail="Customers can only message superadmins")
        
        # For superadmins: can message any admin about any booking
        elif current_user.role == UserRole.superadmin:
            if receiver.role not in [UserRole.admin, UserRole.superadmin]:
                raise HTTPException(status_code=403, detail="Superadmins can only message admins or other superadmins")
        
        # For admins: can only message superadmins about their assigned bookings
        elif current_user.role == UserRole.admin:
            if receiver.role != UserRole.superadmin:
                raise HTTPException(status_code=403, detail="Admins can only message superadmins")
            # Optional: Check if admin is assigned to this booking/tour
    
    # Create the message
    db_message = crud.create(current_user.id, message)
    
    # Return with user details – FIX: use full_name instead of username
    return MessageWithUsers(
        **db_message.__dict__,
        sender_name=current_user.full_name or current_user.email,
        receiver_name=receiver.full_name or receiver.email,
        booking_reference=booking.booking_reference if message.booking_id else None
    )

@router.get("/", response_model=List[MessageWithUsers])
async def get_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    crud: MessageCRUD = Depends(get_message_crud)
):
    """Get all messages for current user"""
    messages = crud.get_user_messages(current_user.id, skip, limit)
    
    # Filter for unread only if requested
    if unread_only:
        messages = [msg for msg in messages if msg.status == MessageStatus.UNREAD and msg.receiver_id == current_user.id]
    
    result = []
    for msg in messages:
        sender = crud.db.query(User).filter(User.id == msg.sender_id).first()
        receiver = crud.db.query(User).filter(User.id == msg.receiver_id).first()
        
        # FIX: use full_name
        result.append(MessageWithUsers(
            **msg.__dict__,
            sender_name=sender.full_name or sender.email,
            receiver_name=receiver.full_name or receiver.email,
            booking_reference=msg.booking.booking_reference if msg.booking else None
        ))
    
    return result

@router.get("/conversations", response_model=List[Conversation])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    crud: MessageCRUD = Depends(get_message_crud)
):
    """Get all conversations for current user"""
    db = crud.db
    conversations = []
    
    # Get all users the current user has conversed with
    other_user_ids = crud.get_conversations(current_user.id)
    
    for other_id in other_user_ids:
        other_user = db.query(User).filter(User.id == other_id).first()
        if not other_user:
            continue
        
        # Get last message in conversation
        messages = crud.get_conversation(current_user.id, other_id)
        if not messages:
            continue
        
        last_msg = messages[-1]
        
        # Get unread count
        unread_count = sum(1 for msg in messages 
                          if msg.receiver_id == current_user.id and msg.status == MessageStatus.UNREAD)
        
        # Get common booking if exists
        common_booking = None
        booking_title = None
        for msg in messages:
            if msg.booking_id:
                booking = db.query(Booking).filter(Booking.id == msg.booking_id).first()
                if booking:
                    common_booking = msg.booking_id
                    booking_title = booking.tour.title if booking.tour else None
                    break
        
        # FIX: use full_name
        conversations.append(Conversation(
            booking_id=common_booking,
            other_user_id=other_id,
            other_user_name=other_user.full_name or other_user.email,
            other_user_role=other_user.role,
            other_user_company=other_user.company_name,
            last_message=last_msg.content[:100] + "..." if len(last_msg.content) > 100 else last_msg.content,
            last_message_time=last_msg.created_at,
            unread_count=unread_count,
            booking_title=booking_title
        ))
    
    # Sort by last message time (newest first)
    conversations.sort(key=lambda x: x.last_message_time or datetime.min, reverse=True)
    return conversations

@router.get("/conversation/{other_user_id}", response_model=List[MessageWithUsers])
async def get_conversation(
    other_user_id: int,
    booking_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    crud: MessageCRUD = Depends(get_message_crud)
):
    """Get conversation with specific user"""
    db = crud.db
    messages = crud.get_conversation(current_user.id, other_user_id, booking_id)
    
    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        receiver = db.query(User).filter(User.id == msg.receiver_id).first()
        
        # FIX: use full_name
        result.append(MessageWithUsers(
            **msg.__dict__,
            sender_name=sender.full_name or sender.email,
            receiver_name=receiver.full_name or receiver.email,
            booking_reference=msg.booking.booking_reference if msg.booking else None
        ))
    
    return result

@router.put("/{message_id}/read", response_model=MessageWithUsers)
async def mark_message_as_read(
    message_id: int,
    current_user: User = Depends(get_current_user),
    crud: MessageCRUD = Depends(get_message_crud)
):
    """Mark a message as read"""
    db = crud.db
    message = crud.mark_as_read(message_id, current_user.id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found or you don't have permission")
    
    sender = db.query(User).filter(User.id == message.sender_id).first()
    receiver = db.query(User).filter(User.id == message.receiver_id).first()
    
    # FIX: use full_name
    return MessageWithUsers(
        **message.__dict__,
        sender_name=sender.full_name or sender.email,
        receiver_name=receiver.full_name or receiver.email,
        booking_reference=message.booking.booking_reference if message.booking else None
    )

@router.get("/unread/count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    crud: MessageCRUD = Depends(get_message_crud)
):
    """Get count of unread messages"""
    count = crud.get_unread_count(current_user.id)
    return {"unread_count": count}

@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    crud: MessageCRUD = Depends(get_message_crud)
):
    """Delete a message (only if you're sender or receiver)"""
    success = crud.delete_message(message_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found or you don't have permission")
    return {"message": "Message deleted successfully"}