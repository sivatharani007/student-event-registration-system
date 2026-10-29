"""Registration business rules (kept out of the routes so they are testable)."""
import threading
from datetime import datetime

from sqlalchemy.exc import IntegrityError

import constants as C
from models import Event, Registration, db

# SQLite allows only one writer at a time; this lock additionally makes the
# "check seats, then insert" step atomic inside one server process.
_registration_lock = threading.Lock()


def block_reason(event, user):
    """Return why `user` cannot register for `event`, or None if they can."""
    now = datetime.now()
    if event.status != "published":
        return "This event is not open for registration."
    if event.end_time < now:
        return "This event has already ended."
    if event.registration_deadline < now:
        return "The registration deadline for this event has passed."
    if not event.eligible_for(user.department):
        return f"This event is not open to {user.department} students."
    return None


def promote_waitlist(event):
    """Move waitlisted students into free seats, oldest first."""
    changed = 0
    while event.seats_left > 0:
        nxt = (Registration.query
               .filter_by(event_id=event.id, status=C.STATUS_WAITLISTED)
               .order_by(Registration.registered_at, Registration.id).first())
        if nxt is None:
            break
        nxt.status = C.STATUS_REGISTERED
        db.session.flush()
        changed += 1
    return changed


def register_user(user, event_id):
    """Register (or waitlist) a user. Returns (level, message, registration)."""
    with _registration_lock:
        event = db.session.get(Event, event_id)
        if event is None:
            return "danger", "That event does not exist.", None
        reason = block_reason(event, user)
        if reason:
            return "danger", reason, None

        reg = Registration.query.filter_by(user_id=user.id, event_id=event.id).first()
        if reg and reg.status in (C.STATUS_REGISTERED, C.STATUS_WAITLISTED):
            return "info", f"You are already {reg.status.lower()} for this event.", reg

        status = C.STATUS_REGISTERED if event.seats_left > 0 else C.STATUS_WAITLISTED
        if reg:  # re-registering after a cancellation
            reg.status = status
            reg.registered_at = datetime.now()
            reg.cancelled_at = None
        else:
            reg = Registration(user_id=user.id, event_id=event.id, status=status)
            db.session.add(reg)
        try:
            db.session.commit()
        except IntegrityError:  # duplicate slipped through
            db.session.rollback()
            return "info", "You are already registered for this event.", None

        if status == C.STATUS_REGISTERED:
            return "success", "You are registered for this event.", reg
        return ("warning",
                "This event is full, so you were added to the waitlist. "
                "You will be moved to Registered automatically if a seat opens.", reg)


def cancel_registration(user, registration_id):
    """Cancel a registration owned by `user`. Returns (level, message)."""
    with _registration_lock:
        reg = db.session.get(Registration, registration_id)
        if reg is None or reg.user_id != user.id:
            return "danger", "Registration not found."
        if reg.status == C.STATUS_CANCELLED:
            return "info", "This registration is already cancelled."
        event = reg.event
        if event.has_started:
            return "danger", "You can no longer cancel because the event has started."
        was_registered = reg.status == C.STATUS_REGISTERED
        reg.status = C.STATUS_CANCELLED
        reg.cancelled_at = datetime.now()
        db.session.flush()
        if was_registered:
            promote_waitlist(event)
        db.session.commit()
        return "success", "Your registration has been cancelled."
