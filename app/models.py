from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime
import enum
Base = declarative_base()

        
class UserRole(str, enum.Enum):
    customer = "customer"
    admin = "admin"
    superadmin = "superadmin"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(200))
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    phone = Column(String(50), nullable=True)
    bio = Column(Text, nullable=True)
    is_superadmin = Column(Boolean, default=False)
    newsletter_subscribed = Column(Boolean, default=False)
    unsubscribe_token = Column(String(36), default=lambda: str(uuid.uuid4()))
    company_name = Column(String(100), nullable=True)
    company_link = Column(String(200), nullable=True)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    role = Column(Enum(UserRole), default=UserRole.customer, nullable=False)

    # Add OAuth fields
    google_id = Column(String(255), unique=True, index=True, nullable=True)
    apple_id = Column(String(255), unique=True, index=True, nullable=True)
    email_verified = Column(Boolean, default=False)
    
    # Track auth method
    auth_method = Column(String, default="email")
    
    # Relationships
    created_tours = relationship("Tour", back_populates="creator")
    bookings = relationship("Booking", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    
    sent_messages = relationship(
        "Message",
        foreign_keys='Message.sender_id',
        back_populates="sender",
        cascade="all, delete-orphan"
    )
    received_messages = relationship(
        "Message",
        foreign_keys='Message.receiver_id',
        back_populates="receiver",
        cascade="all, delete-orphan"
    )
    #property
    @property
    def role(self) -> str:
        if self.is_superadmin:
            return "superadmin"
        elif self.is_admin:
            return "admin"
        else:
            return "customer"
        


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, index=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class Tour(Base):
    __tablename__ = "tours"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), index=True)
    description = Column(String(500))
    price = Column(Float)
    duration = Column(String(50))
    locations = Column(String(100))
    image_url = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    tour_type = Column(String(50), default='safari')  # e.g., safari, cultural, adventure
    difficulty = Column(String(500), nullable=True, default='easy')  # e.g., easy, moderate, hard
    country = Column(String(100), nullable=False)
    max_participants = Column(Integer, default=20)
    included = Column(String(1000), nullable=False)
    not_included = Column(String(1000), nullable=False)
    cancellation_policy = Column(String(500), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    images = relationship("TourImage", back_populates="tour", cascade="all, delete-orphan")
    creator = relationship("User", back_populates="created_tours")
    bookings = relationship("Booking", back_populates="tour", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="tour", cascade="all, delete-orphan")

    def calculate_price(self, adults: int, kids: int, is_private: bool = False) -> float:
        base_price = (adults + kids) * self.price
        return base_price * 1.35 if is_private else base_price


class TourImage(Base):
    __tablename__ = "tour_images"
    id = Column(Integer, primary_key=True, index=True)
    tour_id = Column(Integer, ForeignKey("tours.id"))
    image_url = Column(String(200))
    is_primary = Column(Boolean, default=False)
    
    # Relationship
    tour = relationship("Tour", back_populates="images")


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tour_id = Column(Integer, ForeignKey("tours.id"))
    adults = Column(Integer)
    kids = Column(Integer)
    tour_date = Column(DateTime)
    total_price = Column(Float)
    is_private = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    payment_method = Column(String(20))
    payment_id = Column(String(50))
    payment_status = Column(String)
    status = Column(String(20), default='pending')
    deleted_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    donation = Column(Float, default=0.0)
    special_requirements = Column(String(500), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="bookings")
    tour = relationship("Tour", back_populates="bookings")
    
    messages = relationship(
        "Message",
        back_populates="booking",
        cascade="all, delete-orphan"
    )

    @property
    def participant_count(self):
        return self.adults + self.kids


class Country(Base):
    """
    Stores East African culture information for the Mmondo Adventures
    cultural bank page.
    """
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(50), unique=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=True)
    food = Column(String(1000), nullable=True)
    dress = Column(String(1000), nullable=True)
    traditions = Column(String(1500), nullable=True)
    tour_themes = Column(String(1000), nullable=True)
    video_url = Column(String(300), nullable=True)
    video_credit = Column(String(200), nullable=True)
    testimonial = Column(String(1500), nullable=True)
    badge_label = Column(String(50), nullable=True)
    badge_color = Column(String(50), nullable=True)
    
    # Relationship to culture images
    images = relationship(
        "CountryImage",
        back_populates="country",
        cascade="all, delete-orphan"
    )


class CountryImage(Base):
    """
    Image table for countries on the culture page.
    """
    __tablename__ = "country_images"
    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), index=True)
    image_url = Column(String(300), nullable=False)
    alt_text = Column(String(200), nullable=True)
    is_primary = Column(Boolean, default=False)
    filename = Column(String(200), nullable=True)
    filepath = Column(String(500), nullable=True)
    
    # Relationship
    country = relationship("Country", back_populates="images")


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    tour_id = Column(Integer, ForeignKey("tours.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tour = relationship("Tour", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
    
    
    
# Add this MessageStatus enum
class MessageStatus(enum.Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"

# Add this Message model
class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)  # Optional: link to specific booking
    parent_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)  # For threading
    subject = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    status = Column(Enum(MessageStatus), default=MessageStatus.UNREAD)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    booking = relationship("Booking", back_populates="messages")
    parent_message = relationship("Message", remote_side=[id], back_populates="replies")
    replies = relationship("Message", back_populates="parent_message")
    
    def mark_as_read(self):
        self.status = MessageStatus.READ
        return self

# Update User model to include messages (add to existing User model)
# In your existing User model, add:
# sent_messages = relationship("Message", foreign_keys=[Message.sender_id], back_populates="sender")
# received_messages = relationship("Message", foreign_keys=[Message.receiver_id], back_populates="receiver")

# Update Booking model to include messages (add to existing Booking model)
# In your existing Booking model, add:
# messages = relationship("Message", back_populates="booking")    

