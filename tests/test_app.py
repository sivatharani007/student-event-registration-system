"""Integration tests for the Flask app (uses an in-memory SQLite database)."""
from datetime import datetime, timedelta

import pytest

import services
from app import create_app
from models import Event, Registration, User, db


@pytest.fixture()
def app():
    app = create_app("testing")
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def add_event(app, **kw):
    start = datetime.now() + timedelta(days=5)
    data = dict(name="Test Event", description="Description", category="Hackathon",
                event_type="Technical", kind="Competition", start_time=start,
                end_time=start + timedelta(hours=5), registration_deadline=start - timedelta(days=1),
                venue="Lab 1", mode="Offline", fee=0, capacity=2, skill_level="Any",
                eligible_departments="All", interests="Coding", goals="Learn something new",
                organizer="Club", status="published")
    data.update(kw)
    with app.app_context():
        event = Event(**data)
        db.session.add(event)
        db.session.commit()
        return event.id


def add_user(app, email="a@college.edu", password="Passw0rd!", role="student", department="Computer Science"):
    with app.app_context():
        user = User(full_name="Test Student", email=email, college="Test College",
                    department=department, year=2, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def login(client, email="a@college.edu", password="Passw0rd!"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Discover Events" in response.data


def test_student_registration_and_password_is_hashed(app, client):
    response = client.post("/register", data={
        "full_name": "Asha Rao", "email": "Asha@College.edu", "college": "ABC College",
        "department": "Computer Science", "year": "2", "password": "Secret123",
        "confirm_password": "Secret123"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="asha@college.edu").first()
        assert user is not None and user.role == "student"
        assert user.password_hash != "Secret123" and user.check_password("Secret123")


def test_registration_rejects_duplicate_email_and_weak_password(app, client):
    add_user(app)
    data = {"full_name": "Asha", "email": "a@college.edu", "college": "ABC", "department": "Other",
            "year": "1", "password": "Secret123", "confirm_password": "Secret123"}
    assert b"already exists" in client.post("/register", data=data).data
    data.update(email="new@college.edu", password="short", confirm_password="short")
    assert b"at least 8 characters" in client.post("/register", data=data).data


def test_login_and_logout(app, client):
    add_user(app)
    assert b"Welcome back" in login(client)
    assert client.get("/dashboard").status_code == 200
    client.post("/logout", follow_redirects=True)
    assert client.get("/dashboard").status_code == 302  # redirected to login


def test_wrong_password_is_rejected(app, client):
    add_user(app)
    assert b"Invalid email or password" in login(client, password="wrong")


def test_event_registration_and_duplicate_prevention(app, client):
    add_user(app)
    event_id = add_event(app, capacity=5)
    login(client)
    client.post(f"/events/{event_id}/register")
    client.post(f"/events/{event_id}/register")
    with app.app_context():
        assert Registration.query.filter_by(event_id=event_id).count() == 1
        assert db.session.get(Event, event_id).seats_left == 4


def test_capacity_restriction_waitlists_and_promotes(app):
    event_id = add_event(app, capacity=1)
    u1, u2 = add_user(app, "one@c.edu"), add_user(app, "two@c.edu")
    with app.app_context():
        first = db.session.get(User, u1)
        second = db.session.get(User, u2)
        _, _, r1 = services.register_user(first, event_id)
        level, _, r2 = services.register_user(second, event_id)
        assert r1.status == "Registered"
        assert r2.status == "Waitlisted" and level == "warning"
        assert db.session.get(Event, event_id).seats_taken == 1
        services.cancel_registration(first, r1.id)
        assert db.session.get(Registration, r2.id).status == "Registered"


def test_cannot_register_for_ended_event_or_after_deadline(app):
    past = datetime.now() - timedelta(days=2)
    ended_id = add_event(app, start_time=past, end_time=past + timedelta(hours=2),
                         registration_deadline=past - timedelta(days=1))
    closed_id = add_event(app, registration_deadline=datetime.now() - timedelta(hours=1))
    uid = add_user(app)
    with app.app_context():
        user = db.session.get(User, uid)
        assert services.register_user(user, ended_id)[0] == "danger"
        assert services.register_user(user, closed_id)[0] == "danger"
        assert Registration.query.count() == 0


def test_department_eligibility_enforced_on_server(app):
    event_id = add_event(app, eligible_departments="Civil Engineering")
    uid = add_user(app, department="Computer Science")
    with app.app_context():
        level, message, _ = services.register_user(db.session.get(User, uid), event_id)
        assert level == "danger" and "not open" in message


def test_admin_pages_require_admin_role(app, client):
    add_user(app, "student@c.edu")
    add_user(app, "admin@c.edu", role="admin")
    assert client.get("/admin").status_code == 302          # anonymous -> login
    login(client, "student@c.edu")
    assert client.get("/admin").status_code == 403           # student blocked
    assert client.get("/admin/events").status_code == 403
    assert client.get("/admin/registrations/export.csv").status_code == 403
    assert client.post("/admin/events/new", data={}).status_code == 403
    client.post("/logout")
    login(client, "admin@c.edu", "Passw0rd!")
    assert client.get("/admin").status_code == 200
    assert client.get("/admin/events").status_code == 200


def test_admin_can_create_event_and_export_csv(app, client):
    add_user(app, "admin@c.edu", role="admin")
    login(client, "admin@c.edu")
    start = datetime.now() + timedelta(days=10)
    fmt = "%Y-%m-%dT%H:%M"
    response = client.post("/admin/events/new", data={
        "name": "New Workshop", "description": "About it", "category": "Coding Workshop",
        "event_type": "Technical", "kind": "Workshop", "status": "published",
        "start_time": start.strftime(fmt), "end_time": (start + timedelta(hours=3)).strftime(fmt),
        "registration_deadline": (start - timedelta(days=1)).strftime(fmt), "venue": "Lab",
        "mode": "Offline", "fee": "0", "capacity": "30", "skill_level": "Beginner",
        "team_min": "1", "team_max": "1", "organizer": "Club", "eligible": ["All"],
        "interests": ["Coding"], "goals": ["Learn something new"]}, follow_redirects=True)
    assert b"Event created" in response.data
    with app.app_context():
        assert Event.query.filter_by(name="New Workshop").count() == 1
    csv_response = client.get("/admin/registrations/export.csv")
    assert csv_response.status_code == 200 and csv_response.mimetype == "text/csv"


def test_explore_filters_work(app, client):
    add_event(app, name="Free Python Class", fee=0, mode="Online")
    add_event(app, name="Paid Robotics Meet", fee=500, mode="Offline")
    assert b"Free Python Class" in client.get("/events?fee=free").data
    assert b"Paid Robotics Meet" not in client.get("/events?fee=free").data
    assert b"Paid Robotics Meet" in client.get("/events?q=robotics").data
    assert b"Free Python Class" not in client.get("/events?mode=Offline").data


def test_recommendation_page_flow(app, client):
    add_event(app, name="Coding Night", interests="Coding", fee=0)
    response = client.post("/find-my-event", data={
        "department": "Computer Science", "interests": ["Coding"], "event_type": "Any type",
        "skill_level": "Any level", "mode": "Any mode", "budget": "free", "date_range": "30",
        "duration": "any", "participation": "either", "goal": "Learn something new"})
    assert response.status_code == 200
    assert b"Coding Night" in response.data and b"preference-match score" in response.data
