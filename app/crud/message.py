from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import Message, MessageStatus
from app.schemas.message import MessageCreate


class MessageCRUD:
    def __init__(self, db: Session):
        self.db = db

    def create(self, sender_id: int, message: MessageCreate) -> Message:
        db_message = Message(
            sender_id=sender_id,
            receiver_id=message.receiver_id,
            booking_id=message.booking_id,
            parent_message_id=message.parent_message_id,
            subject=message.subject,
            content=message.content,
            status=MessageStatus.UNREAD
        )
        self.db.add(db_message)
        self.db.commit()
        self.db.refresh(db_message)
        return db_message

    def get_message(self, message_id: int) -> Optional[Message]:
        return self.db.query(Message).filter(Message.id == message_id).first()

    def get_user_messages(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Message]:
        return (
            self.db.query(Message)
            .filter((Message.sender_id == user_id) | (Message.receiver_id == user_id))
            .order_by(Message.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_conversation(self, user1_id: int, user2_id: int, booking_id: Optional[int] = None) -> List[Message]:
        query = self.db.query(Message).filter(
            ((Message.sender_id == user1_id) & (Message.receiver_id == user2_id)) |
            ((Message.sender_id == user2_id) & (Message.receiver_id == user1_id))
        )

        if booking_id:
            query = query.filter(Message.booking_id == booking_id)

        return query.order_by(Message.created_at.asc()).all()

    def get_unread_count(self, user_id: int) -> int:
        return self.db.query(Message).filter(
            Message.receiver_id == user_id,
            Message.status == MessageStatus.UNREAD
        ).count()

    def mark_as_read(self, message_id: int, user_id: int) -> Optional[Message]:
        message = self.get_message(message_id)
        if message and message.receiver_id == user_id:
            message.status = MessageStatus.READ
            self.db.commit()
            self.db.refresh(message)
        return message

    def mark_conversation_as_read(self, user1_id: int, user2_id: int) -> int:
        updated = self.db.query(Message).filter(
            Message.receiver_id == user1_id,
            Message.sender_id == user2_id,
            Message.status == MessageStatus.UNREAD
        ).update({Message.status: MessageStatus.READ})
        self.db.commit()
        return updated

    # ✅ FIXED: Properly indented inside class
    def get_conversations(self, user_id: int) -> List[int]:
        sent = self.db.query(Message.receiver_id).filter(
            Message.sender_id == user_id
        )

        received = self.db.query(Message.sender_id).filter(
            Message.receiver_id == user_id
        )

        result = sent.union(received).distinct().all()

        return [r[0] for r in result]

    def delete_message(self, message_id: int, user_id: int) -> bool:
        message = self.get_message(message_id)
        if message and (message.sender_id == user_id or message.receiver_id == user_id):
            self.db.delete(message)
            self.db.commit()
            return True
        return False
