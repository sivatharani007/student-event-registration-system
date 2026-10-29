"""Database models: User, Event, Registration, Wishlist."""
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

import constants as C

db = SQLAlchemy()
SEP = "|"  # separator for list-like text columns


def _split(value):
    return [part.strip() for part in (value or "").split(SEP) if part.strip()]


def _now():
    return datetime.now()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    college = db.Column(db.String(160), nullable=False, default="")
    department = db.Column(db.String(80), nullable=False, default="Other")
    year = db.Column(db.Integer, nullable=False, default=1)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    registrations = db.relationship(
        "Registration", back_populates="user", cascade="all, delete-orphan")
    wishlist_items = db.relationship(
        "Wishlist", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


class Event(db.Model):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("fee >= 0", name="ck_event_fee"),
        CheckConstraint("capacity >= 1", name="ck_event_capacity"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(60), nullable=False, index=True)
    event_type = db.Column(db.String(30), nullable=False, default="Technical")
    kind = db.Column(db.String(20), nullable=False, default="Other")  # Workshop / Competition / Other
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False)
    registration_deadline = db.Column(db.DateTime, nullable=False)
    venue = db.Column(db.String(200), nullable=False)
    mode = db.Column(db.String(20), nullable=False, default="Offline")
    fee = db.Column(db.Integer, nullable=False, default=0)  # INR
    capacity = db.Column(db.Integer, nullable=False, default=50)
    required_skills = db.Column(db.Text, nullable=False, default="")
    skills_gained = db.Column(db.Text, nullable=False, default="")  # "a|b|c"
    benefits = db.Column(db.Text, nullable=False, default="")
    skill_level = db.Column(db.String(20), nullable=False, default="Any")
    eligible_departments = db.Column(db.Text, nullable=False, default="All")  # "All" or "a|b"
    interests = db.Column(db.Text, nullable=False, default="")  # "Coding|Robotics"
    goals = db.Column(db.Text, nullable=False, default="")
    team_min = db.Column(db.Integer, nullable=False, default=1)
    team_max = db.Column(db.Integer, nullable=False, default=1)
    organizer = db.Column(db.String(160), nullable=False, default="Student Council")
    contact_email = db.Column(db.String(255), nullable=False, default="")
    image_url = db.Column(db.String(500), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="published", index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    registrations = db.relationship(
        "Registration", back_populates="event", cascade="all, delete-orphan")
    wishlisted_by = db.relationship(
        "Wishlist", back_populates="event", cascade="all, delete-orphan")

    # ---- list-like helpers -------------------------------------------------
    @property
    def interests_list(self):
        return _split(self.interests)

    @property
    def goals_list(self):
        return _split(self.goals)

    @property
    def skills_list(self):
        return _split(self.skills_gained)

    @property
    def eligible_list(self):
        return _split(self.eligible_departments)

    # ---- derived values ----------------------------------------------------
    @property
    def duration_hours(self):
        return (self.end_time - self.start_time).total_seconds() / 3600

    @property
    def is_free(self):
        return self.fee == 0

    @property
    def is_team_event(self):
        return self.team_max > 1

    @property
    def team_label(self):
        if self.team_max <= 1:
            return "Individual"
        if self.team_min <= 1:
            return f"Individual or team (up to {self.team_max})"
        return f"Team of {self.team_min}–{self.team_max}"

    @property
    def seats_taken(self):
        return Registration.query.filter_by(
            event_id=self.id, status=C.STATUS_REGISTERED).count()

    @property
    def seats_left(self):
        return max(self.capacity - self.seats_taken, 0)

    @property
    def waitlist_count(self):
        return Registration.query.filter_by(
            event_id=self.id, status=C.STATUS_WAITLISTED).count()

    @property
    def is_full(self):
        return self.seats_left <= 0

    @property
    def has_ended(self):
        return self.end_time < datetime.now()

    @property
    def has_started(self):
        return self.start_time <= datetime.now()

    @property
    def deadline_passed(self):
        return self.registration_deadline < datetime.now()

    def eligible_for(self, department):
        eligible = self.eligible_list
        return (not eligible) or "All" in eligible or department in eligible


class Registration(db.Model):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_user_event"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=C.STATUS_REGISTERED, index=True)
    registered_at = db.Column(db.DateTime, nullable=False, default=_now)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="registrations")
    event = db.relationship("Event", back_populates="registrations")


class Wishlist(db.Model):
    __tablename__ = "wishlist"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_wishlist_user_event"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    user = db.relationship("User", back_populates="wishlist_items")
    event = db.relationship("Event", back_populates="wishlisted_by")
