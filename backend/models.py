from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    items = db.relationship("Item", back_populates="owner", cascade="all, delete-orphan")


class Item(db.Model):
    __tablename__ = "items"
    __table_args__ = (
        Index("ix_items_status_type", "status", "item_type"),
        Index("ix_items_location", "location"),
        Index("ix_items_created_at", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    item_type = db.Column(db.Enum("lost", "found", name="item_type"), nullable=False)
    location = db.Column(db.String(160), nullable=False)
    status = db.Column(
        db.Enum("open", "recovered", name="recovery_status"),
        nullable=False,
        default="open",
    )
    image_object_name = db.Column(db.String(512), nullable=True)
    image_url = db.Column(db.String(2048), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    owner = db.relationship("User", back_populates="items")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "item_type": self.item_type,
            "location": self.location,
            "status": self.status,
            "image_url": self.image_url,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
