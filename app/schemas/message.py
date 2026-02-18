from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum as PyEnum

class MessageStatusEnum(str, PyEnum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"

class MessageBase(BaseModel):
    receiver_id: int
    booking_id: Optional[int] = None
    parent_message_id: Optional[int] = None
    subject: Optional[str] = Field(None, max_length=255)
    content: str

class MessageCreate(MessageBase):
    pass

class MessageUpdate(BaseModel):
    status: Optional[MessageStatusEnum] = None

class MessageInDB(MessageBase):
    id: int
    sender_id: int
    status: MessageStatusEnum
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class MessageWithUsers(MessageInDB):
    sender_name: str
    receiver_name: str
    booking_reference: Optional[str] = None

class Conversation(BaseModel):
    booking_id: Optional[int]
    other_user_id: int
    other_user_name: str
    other_user_role: str
    other_user_company: Optional[str] = None
    last_message: Optional[str]
    last_message_time: Optional[datetime]
    unread_count: int = 0
    booking_title: Optional[str] = None
    