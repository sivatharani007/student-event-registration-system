"""Student Event Registration System - Flask application.

Run locally:      python app.py
Flask CLI:        flask --app app run
Production WSGI:  gunicorn wsgi:app
"""
import csv
import io
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import click
from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

import constants as C
import services
from config import config_by_name
from models import Event, Registration, User, Wishlist, db
from recommendations import STRICT_OPTIONS, Preferences, recommend
from seed import seed_events

csrf = CSRFProtect()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DT_FORMAT = "%Y-%m-%dT%H:%M"

CATEGORY_ICONS = {
    "Hackathon": "bi-lightning-charge", "Technical Symposium": "bi-building",
    "Coding Competition": "bi-trophy", "Coding Workshop": "bi-code-slash",
    "AI/ML Workshop": "bi-cpu", "Web Development Workshop": "bi-globe2",
    "Paper Presentation": "bi-file-earmark-text", "Project Exhibition": "bi-easel",
    "Robotics Competition": "bi-robot", "Gaming Tournament": "bi-controller",
    "Cultural Festival": "bi-music-note-beamed", "Photography Competition": "bi-camera",
    "Entrepreneurship": "bi-rocket-takeoff", "Sports Competition": "bi-dribbble",
    "Career Development": "bi-briefcase",
}


# ----------------------------------------------------------------- helpers
def _dev_secret_key(instance_path):
    """Create (once) and reuse a random development key stored outside Git."""
    path = Path(instance_path) / ".secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_hex(32)
    path.write_text(key)
    return key


def safe_next(target, fallback):
    """Only allow redirects to local paths (prevents open redirects)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return fallback


def like_escape(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in as an administrator.", "warning")
            return redirect(url_for("admin_login"))
        if not g.user.is_admin:
            abort(403)  # enforced on the server, not just hidden in the UI
        return view(*args, **kwargs)
    return wrapped


def password_problem(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def parse_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------ event form
SCALAR_FIELDS = ["name", "description", "category", "event_type", "kind", "start_time", "end_time",
                 "registration_deadline", "venue", "mode", "fee", "capacity", "skill_level",
                 "required_skills", "skills_gained", "benefits", "team_min", "team_max",
                 "organizer", "contact_email", "image_url", "status"]


def event_form_defaults():
    start = (datetime.now() + timedelta(days=14)).replace(hour=10, minute=0, second=0, microsecond=0)
    return {
        "name": "", "description": "", "category": C.CATEGORIES[0], "event_type": "Technical",
        "kind": "Other", "start_time": start.strftime(DT_FORMAT),
        "end_time": (start + timedelta(hours=6)).strftime(DT_FORMAT),
        "registration_deadline": (start - timedelta(days=2)).strftime(DT_FORMAT),
        "venue": "", "mode": "Offline", "fee": "0", "capacity": "50", "skill_level": "Any",
        "required_skills": "", "skills_gained": "", "benefits": "", "team_min": "1",
        "team_max": "1", "organizer": "", "contact_email": "", "image_url": "",
        "status": "published", "eligible": ["All"], "interests": [], "goals": [],
        "is_featured": False,
    }


def event_form_values(event):
    v = {k: getattr(event, k) for k in SCALAR_FIELDS}
    for k in ("start_time", "end_time", "registration_deadline"):
        v[k] = getattr(event, k).strftime(DT_FORMAT)
    v["skills_gained"] = ", ".join(event.skills_list)
    v["eligible"] = event.eligible_list or ["All"]
    v["interests"] = event.interests_list
    v["goals"] = event.goals_list
    v["is_featured"] = event.is_featured
    return v


def request_form_values():
    f = request.form
    v = {k: f.get(k, "").strip() for k in SCALAR_FIELDS}
    v["eligible"] = f.getlist("eligible")
    v["interests"] = f.getlist("interests")
    v["goals"] = f.getlist("goals")
    v["is_featured"] = f.get("is_featured") == "on"
    return v


def validate_event_form(v, existing=None):
    """Validate admin event form values. Returns (clean_dict, errors)."""
    errors, clean = [], {}

    def need_text(key, label, max_len):
        value = v[key]
        if not value:
            errors.append(f"{label} is required.")
        elif len(value) > max_len:
            errors.append(f"{label} must be at most {max_len} characters.")
        clean[key] = value

    need_text("name", "Event name", 160)
    need_text("description", "Description", 5000)
    need_text("venue", "Venue", 200)
    need_text("organizer", "Organizer", 160)
    clean["required_skills"] = v["required_skills"][:1000]
    clean["benefits"] = v["benefits"][:1000]

    for key, allowed, label in [("category", C.CATEGORIES, "Category"),
                                ("event_type", C.EVENT_TYPES, "Event type"),
                                ("kind", C.KINDS, "Kind"),
                                ("mode", C.MODES, "Mode"),
                                ("skill_level", C.EVENT_SKILL_LEVELS, "Skill level"),
                                ("status", C.EVENT_STATUSES, "Status")]:
        if v[key] not in allowed:
            errors.append(f"Please choose a valid {label.lower()}.")
        clean[key] = v[key]

    if v["contact_email"] and not EMAIL_RE.match(v["contact_email"]):
        errors.append("Contact email is not a valid email address.")
    clean["contact_email"] = v["contact_email"][:255]

    image = v["image_url"]
    if image and not (image.startswith(("http://", "https://")) or image.startswith("images/")):
        errors.append("Image must be a full http(s) URL or a path starting with 'images/'.")
        image = ""
    clean["image_url"] = image[:500]

    times = {}
    for key, label in [("start_time", "Start time"), ("end_time", "End time"),
                       ("registration_deadline", "Registration deadline")]:
        try:
            times[key] = datetime.strptime(v[key], DT_FORMAT)
        except ValueError:
            errors.append(f"{label} is not a valid date and time.")
    clean.update(times)
    if len(times) == 3:
        if times["end_time"] <= times["start_time"]:
            errors.append("End time must be after the start time.")
        if times["registration_deadline"] > times["end_time"]:
            errors.append("Registration deadline cannot be after the event ends.")

    fee = parse_int(v["fee"])
    if fee is None or not 0 <= fee <= 100000:
        errors.append("Fee must be a whole number of rupees between 0 and 100000.")
    clean["fee"] = fee or 0

    capacity = parse_int(v["capacity"])
    if capacity is None or not 1 <= capacity <= 100000:
        errors.append("Capacity must be a whole number between 1 and 100000.")
    elif existing is not None and capacity < existing.seats_taken:
        errors.append(f"Capacity cannot be below the {existing.seats_taken} students already registered.")
    clean["capacity"] = capacity or 1

    tmin, tmax = parse_int(v["team_min"]), parse_int(v["team_max"])
    if tmin is None or tmax is None or tmin < 1 or tmax < tmin or tmax > 50:
        errors.append("Team size must satisfy 1 <= minimum <= maximum <= 50 (use 1 and 1 for individual events).")
        tmin, tmax = 1, 1
    clean["team_min"], clean["team_max"] = tmin, tmax

    eligible = [d for d in v["eligible"] if d in C.DEPARTMENTS]
    clean["eligible_departments"] = "All" if (not eligible or "All" in v["eligible"]) else "|".join(eligible)
    clean["interests"] = "|".join(i for i in v["interests"] if i in C.INTERESTS)
    clean["goals"] = "|".join(g_ for g_ in v["goals"] if g_ in C.GOALS)

    skills = [s.strip()[:40] for s in v["skills_gained"].replace("|", ",").split(",") if s.strip()]
    clean["skills_gained"] = "|".join(skills[:8])
    clean["is_featured"] = bool(v["is_featured"])
    return clean, errors


# -------------------------------------------------------------- app factory
def create_app(config_name=None):
    env = config_name or os.environ.get("APP_ENV", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(env, config_by_name["development"]))
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    if not app.config.get("SECRET_KEY"):
        if env == "production":
            raise RuntimeError("SECRET_KEY must be set in production. See README.md.")
        app.config["SECRET_KEY"] = _dev_secret_key(app.instance_path)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        db_path = Path(app.instance_path) / "events.db"
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path.as_posix()

    db.init_app(app)
    csrf.init_app(app)
    app.extensions["login_failures"] = {}

    with app.app_context():
        db.create_all()
        if app.config.get("SEED_SAMPLE_EVENTS"):
            seed_events()

    register_hooks(app)
    register_routes(app)
    register_commands(app)
    return app


def register_hooks(app):
    @app.before_request
    def load_user():
        user_id = session.get("user_id")
        g.user = db.session.get(User, user_id) if user_id else None
        if user_id and g.user is None:
            session.clear()

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.context_processor
    def inject_globals():
        wishlist_ids = set()
        if g.get("user") is not None:
            wishlist_ids = {w.event_id for w in Wishlist.query.filter_by(user_id=g.user.id)}
        return dict(current_user=g.get("user"), C=C, wishlist_ids=wishlist_ids,
                    now=datetime.now(), cat_icon=lambda c: CATEGORY_ICONS.get(c, "bi-calendar-event"))

    @app.template_filter("dt")
    def fmt_dt(value):
        return value.strftime("%d %b %Y, %I:%M %p") if value else ""

    @app.template_filter("day")
    def fmt_day(value):
        return value.strftime("%d %b %Y") if value else ""

    @app.template_filter("inr")
    def fmt_inr(value):
        return "Free" if not value else f"₹{value:,}"

    @app.template_filter("poster")
    def poster(event):
        url = event.image_url or "images/posters/fallback.svg"
        return url if url.startswith("http") else url_for("static", filename=url)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_template("500.html"), 500

    @app.errorhandler(CSRFError)
    def csrf_error(_e):
        flash("Your form expired or was invalid. Please try again.", "danger")
        return redirect(url_for("index"))


def register_routes(app):
    # ============================================================== public
    @app.route("/")
    def index():
        now = datetime.now()
        upcoming = Event.query.filter(Event.status == "published", Event.end_time >= now)
        featured = upcoming.filter(Event.is_featured.is_(True)).order_by(Event.start_time).limit(3).all()
        soon = upcoming.order_by(Event.start_time).limit(6).all()
        cat_rows = (db.session.query(Event.category, func.count(Event.id))
                    .filter(Event.status == "published", Event.end_time >= now)
                    .group_by(Event.category).order_by(func.count(Event.id).desc()).limit(8).all())
        stats = {
            "events": upcoming.count(),
            "students": User.query.filter_by(role="student").count(),
            "registrations": Registration.query.filter(
                Registration.status != C.STATUS_CANCELLED).count(),
            "categories": len(cat_rows),
        }
        return render_template("index.html", featured=featured, soon=soon,
                               categories=cat_rows, stats=stats)

    # ============================================================== auth
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("student_dashboard"))
        values = {"year": "1"}
        if request.method == "POST":
            f = request.form
            values = {k: f.get(k, "").strip() for k in ("full_name", "email", "college", "department", "year")}
            values["email"] = values["email"].lower()
            errors = []
            if not 2 <= len(values["full_name"]) <= 120:
                errors.append("Please enter your full name (2-120 characters).")
            if not EMAIL_RE.match(values["email"]) or len(values["email"]) > 255:
                errors.append("Please enter a valid college email address.")
            if not 2 <= len(values["college"]) <= 160:
                errors.append("Please enter your college name.")
            if values["department"] not in C.DEPARTMENTS:
                errors.append("Please choose your department.")
            year = parse_int(values["year"])
            if year not in C.YEARS:
                errors.append("Please choose your year of study.")
            password, confirm = f.get("password", ""), f.get("confirm_password", "")
            problem = password_problem(password)
            if problem:
                errors.append(problem)
            elif password != confirm:
                errors.append("Passwords do not match.")
            if not errors and User.query.filter_by(email=values["email"]).first():
                errors.append("An account with this email already exists. Try logging in.")
            if not errors:
                user = User(full_name=values["full_name"], email=values["email"],
                            college=values["college"], department=values["department"],
                            year=year, role="student")
                user.set_password(password)
                db.session.add(user)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    errors.append("An account with this email already exists. Try logging in.")
                else:
                    flash("Account created. Please log in. (No verification email is sent in this version.)", "success")
                    return redirect(url_for("login"))
            for err in errors:
                flash(err, "danger")
        return render_template("register.html", values=values)

    def _too_many_failures(key):
        window = [t for t in app.extensions["login_failures"].get(key, []) if time.time() - t < 600]
        app.extensions["login_failures"][key] = window
        return len(window) >= 5

    def _do_login(admin_only):
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        key = f"{email}|{request.remote_addr}"
        if _too_many_failures(key):
            flash("Too many failed attempts. Please wait 10 minutes and try again.", "danger")
            return None
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password) or (admin_only and not user.is_admin):
            app.extensions["login_failures"].setdefault(key, []).append(time.time())
            flash("Invalid email or password.", "danger")
            return None
        session.clear()
        session["user_id"] = user.id
        flash(f"Welcome back, {user.full_name.split()[0]}!", "success")
        return user

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("student_dashboard"))
        if request.method == "POST":
            user = _do_login(admin_only=False)
            if user:
                default = url_for("admin_dashboard") if user.is_admin else url_for("student_dashboard")
                return redirect(safe_next(request.args.get("next"), default))
        return render_template("login.html", admin_mode=False)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if g.user and g.user.is_admin:
            return redirect(url_for("admin_dashboard"))
        if request.method == "POST":
            if _do_login(admin_only=True):
                return redirect(url_for("admin_dashboard"))
        return render_template("login.html", admin_mode=True)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    # ============================================================== events
    @app.route("/events")
    def explore_events():
        a = request.args
        q, category, date_f = a.get("q", "").strip(), a.get("category", ""), a.get("date", "")
        fee_f, mode_f, skill_f = a.get("fee", ""), a.get("mode", ""), a.get("skill", "")
        dept_f, sort = a.get("department", ""), a.get("sort", "date")
        now = datetime.now()

        query = Event.query.filter(Event.status == "published", Event.end_time >= now)
        if q:
            query = query.filter(Event.name.ilike(f"%{like_escape(q)}%", escape="\\"))
        if category in C.CATEGORIES:
            query = query.filter(Event.category == category)
        days = C.DATE_LIMITS.get(date_f)
        if days:
            query = query.filter(Event.start_time <= now + timedelta(days=days))
        limit = C.BUDGET_LIMITS.get(fee_f)
        if limit is not None:
            query = query.filter(Event.fee <= limit)
        if mode_f in C.MODES:
            query = query.filter(Event.mode == mode_f)
        if skill_f in C.SKILL_LEVELS:
            query = query.filter(or_(Event.skill_level == skill_f, Event.skill_level == "Any"))
        if dept_f in C.DEPARTMENTS:
            query = query.filter(or_(Event.eligible_departments == "All",
                                     Event.eligible_departments.like(f"%{dept_f}%")))
        scores = {int(k): v for k, v in session.get("rec_scores", {}).items()}
        if sort == "fee_asc":
            query = query.order_by(Event.fee, Event.start_time)
        elif sort == "fee_desc":
            query = query.order_by(Event.fee.desc(), Event.start_time)
        else:
            query = query.order_by(Event.start_time)
        events = query.all()
        if sort == "score" and scores:
            events.sort(key=lambda e: (-scores.get(e.id, -1), e.start_time))
        return render_template("explore_events.html", events=events, scores=scores,
                               filters=dict(q=q, category=category, date=date_f, fee=fee_f,
                                            mode=mode_f, skill=skill_f, department=dept_f, sort=sort),
                               filtered=any([q, category, date_f, fee_f, mode_f, skill_f, dept_f]))

    @app.route("/events/<int:event_id>")
    def event_details(event_id):
        event = db.session.get(Event, event_id)
        if event is None or (event.status != "published" and not (g.user and g.user.is_admin)):
            abort(404)
        registration, reason = None, None
        if g.user:
            registration = Registration.query.filter_by(user_id=g.user.id, event_id=event.id).first()
            reason = services.block_reason(event, g.user)
        return render_template("event_details.html", event=event, registration=registration,
                               block_reason=reason)

    @app.route("/events/<int:event_id>/register", methods=["POST"])
    @login_required
    def register_event(event_id):
        level, message, reg = services.register_user(g.user, event_id)
        flash(message, level)
        if reg is not None and level in ("success", "warning"):
            return redirect(url_for("registration_confirmation", registration_id=reg.id))
        return redirect(url_for("event_details", event_id=event_id))

    @app.route("/registrations/<int:registration_id>")
    @login_required
    def registration_confirmation(registration_id):
        reg = db.session.get(Registration, registration_id)
        if reg is None or reg.user_id != g.user.id:
            abort(404)
        return render_template("registration_confirmation.html", reg=reg)

    @app.route("/registrations/<int:registration_id>/cancel", methods=["POST"])
    @login_required
    def cancel_registration(registration_id):
        level, message = services.cancel_registration(g.user, registration_id)
        flash(message, level)
        return redirect(url_for("my_registrations"))

    @app.route("/events/<int:event_id>/wishlist", methods=["POST"])
    @login_required
    def toggle_wishlist(event_id):
        event = db.session.get(Event, event_id)
        if event is None:
            abort(404)
        item = Wishlist.query.filter_by(user_id=g.user.id, event_id=event_id).first()
        if item:
            db.session.delete(item)
            flash("Removed from your wishlist.", "info")
        else:
            db.session.add(Wishlist(user_id=g.user.id, event_id=event_id))
            flash("Saved to your wishlist.", "success")
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        return redirect(safe_next(request.form.get("next"), url_for("event_details", event_id=event_id)))

    # ============================================================== recommender
    @app.route("/find-my-event", methods=["GET", "POST"])
    def recommend_events():
        prefs = Preferences(department=g.user.department if g.user else "Other")
        outcome = None
        if request.method == "POST":
            f = request.form
            prefs = Preferences.from_dict({
                "department": f.get("department"), "interests": f.getlist("interests"),
                "event_type": f.get("event_type"), "skill_level": f.get("skill_level"),
                "mode": f.get("mode"), "budget": f.get("budget"),
                "date_range": f.get("date_range"), "duration": f.get("duration"),
                "participation": f.get("participation"), "goal": f.get("goal"),
                "strict": f.getlist("strict"),
            })
            if f.get("department") not in C.DEPARTMENTS:
                flash("Please choose your department.", "danger")
            elif not prefs.interests:
                flash("Please select at least one interest.", "danger")
            elif not prefs.goal:
                flash("Please choose your primary goal.", "danger")
            else:
                exclude = set()
                if g.user:
                    exclude = {r.event_id for r in Registration.query.filter(
                        Registration.user_id == g.user.id,
                        Registration.status != C.STATUS_CANCELLED)}
                outcome = recommend(Event.query.all(), prefs, exclude_ids=exclude)
                session["rec_scores"] = {str(k): v for k, v in outcome["scores"].items()}
        return render_template("recommendations.html", prefs=prefs, outcome=outcome,
                               strict_options=STRICT_OPTIONS)

    # ============================================================== student area
    @app.route("/dashboard")
    @login_required
    def student_dashboard():
        regs = (Registration.query.filter(Registration.user_id == g.user.id,
                                          Registration.status != C.STATUS_CANCELLED)
                .order_by(Registration.registered_at.desc()).all())
        now = datetime.now()
        confirmed = [r for r in regs if r.status == C.STATUS_REGISTERED]
        chart = {}
        for r in confirmed:
            chart[r.event.category] = chart.get(r.event.category, 0) + 1
        return render_template(
            "student_dashboard.html", recent=regs[:5],
            total=len(confirmed),
            upcoming=sum(1 for r in confirmed if r.event.end_time >= now),
            completed=sum(1 for r in confirmed if r.event.end_time < now),
            saved=Wishlist.query.filter_by(user_id=g.user.id).count(),
            chart_labels=list(chart.keys()), chart_values=list(chart.values()))

    @app.route("/my-registrations")
    @login_required
    def my_registrations():
        regs = (Registration.query.filter_by(user_id=g.user.id)
                .order_by(Registration.registered_at.desc()).all())
        return render_template("my_registrations.html", regs=regs)

    @app.route("/wishlist")
    @login_required
    def wishlist():
        items = (Wishlist.query.filter_by(user_id=g.user.id)
                 .order_by(Wishlist.created_at.desc()).all())
        return render_template("wishlist.html", events=[i.event for i in items])

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            f = request.form
            errors = []
            name, college = f.get("full_name", "").strip(), f.get("college", "").strip()
            dept, year = f.get("department", ""), parse_int(f.get("year"))
            if not 2 <= len(name) <= 120:
                errors.append("Please enter your full name (2-120 characters).")
            if not 2 <= len(college) <= 160:
                errors.append("Please enter your college name.")
            if dept not in C.DEPARTMENTS:
                errors.append("Please choose a valid department.")
            if year not in C.YEARS:
                errors.append("Please choose a valid year of study.")
            new_pw = f.get("new_password", "")
            if new_pw:
                if not g.user.check_password(f.get("current_password", "")):
                    errors.append("Your current password is incorrect.")
                elif password_problem(new_pw):
                    errors.append(password_problem(new_pw))
                elif new_pw != f.get("confirm_password", ""):
                    errors.append("New passwords do not match.")
            if errors:
                for err in errors:
                    flash(err, "danger")
            else:
                g.user.full_name, g.user.college = name, college
                g.user.department, g.user.year = dept, year
                if new_pw:
                    g.user.set_password(new_pw)
                db.session.commit()
                flash("Profile updated.", "success")
                return redirect(url_for("profile"))
        return render_template("profile.html")

    # ============================================================== admin
    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        now = datetime.now()
        active = Registration.status == C.STATUS_REGISTERED
        rows = (db.session.query(Event.category, func.count(Registration.id))
                .join(Registration, Registration.event_id == Event.id)
                .filter(active).group_by(Event.category).all())
        total_capacity = db.session.query(func.coalesce(func.sum(Event.capacity), 0)).filter(
            Event.status == "published", Event.end_time >= now).scalar()
        filled = (Registration.query.join(Event, Registration.event_id == Event.id)
                  .filter(active, Event.status == "published", Event.end_time >= now).count())
        stats = {
            "events": Event.query.count(),
            "upcoming": Event.query.filter(Event.status == "published", Event.end_time >= now).count(),
            "students": User.query.filter_by(role="student").count(),
            "registered": Registration.query.filter(active).count(),
            "waitlisted": Registration.query.filter_by(status=C.STATUS_WAITLISTED).count(),
            "fill_rate": round(100 * filled / total_capacity) if total_capacity else 0,
        }
        recent = Registration.query.order_by(Registration.registered_at.desc()).limit(8).all()
        return render_template("admin_dashboard.html", stats=stats, recent=recent,
                               chart_labels=[r[0] for r in rows], chart_values=[r[1] for r in rows])

    @app.route("/admin/events")
    @admin_required
    def admin_events():
        q = request.args.get("q", "").strip()
        query = Event.query
        if q:
            query = query.filter(Event.name.ilike(f"%{like_escape(q)}%", escape="\\"))
        return render_template("admin_events.html", events=query.order_by(Event.start_time.desc()).all(), q=q)

    @app.route("/admin/events/new", methods=["GET", "POST"])
    @admin_required
    def add_event():
        values = event_form_defaults()
        if request.method == "POST":
            values = request_form_values()
            clean, errors = validate_event_form(values)
            if errors:
                for err in errors:
                    flash(err, "danger")
            else:
                db.session.add(Event(**clean))
                db.session.commit()
                flash("Event created.", "success")
                return redirect(url_for("admin_events"))
        return render_template("add_event.html", v=values)

    @app.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
    @admin_required
    def edit_event(event_id):
        event = db.session.get(Event, event_id) or abort(404)
        values = event_form_values(event)
        if request.method == "POST":
            values = request_form_values()
            clean, errors = validate_event_form(values, existing=event)
            if errors:
                for err in errors:
                    flash(err, "danger")
            else:
                for key, value in clean.items():
                    setattr(event, key, value)
                db.session.flush()
                services.promote_waitlist(event)
                db.session.commit()
                flash("Event updated.", "success")
                return redirect(url_for("admin_events"))
        return render_template("edit_event.html", v=values, event=event)

    @app.route("/admin/events/<int:event_id>/delete", methods=["POST"])
    @admin_required
    def delete_event(event_id):
        event = db.session.get(Event, event_id) or abort(404)
        db.session.delete(event)
        db.session.commit()
        flash("Event and its registrations were deleted.", "info")
        return redirect(url_for("admin_events"))

    @app.route("/admin/events/<int:event_id>/capacity", methods=["POST"])
    @admin_required
    def update_capacity(event_id):
        event = db.session.get(Event, event_id) or abort(404)
        capacity = parse_int(request.form.get("capacity"))
        if capacity is None or not 1 <= capacity <= 100000:
            flash("Capacity must be between 1 and 100000.", "danger")
        elif capacity < event.seats_taken:
            flash(f"Capacity cannot be below the {event.seats_taken} students already registered.", "danger")
        else:
            event.capacity = capacity
            db.session.flush()
            moved = services.promote_waitlist(event)
            db.session.commit()
            flash("Capacity updated." + (f" {moved} waitlisted student(s) were registered." if moved else ""), "success")
        return redirect(url_for("admin_events"))

    def registration_query():
        q = request.args.get("q", "").strip()
        event_id = parse_int(request.args.get("event_id"))
        status = request.args.get("status", "")
        query = (Registration.query.join(User, Registration.user_id == User.id)
                 .join(Event, Registration.event_id == Event.id))
        if q:
            like = f"%{like_escape(q)}%"
            query = query.filter(or_(User.full_name.ilike(like, escape="\\"),
                                     User.email.ilike(like, escape="\\"),
                                     User.college.ilike(like, escape="\\")))
        if event_id:
            query = query.filter(Registration.event_id == event_id)
        if status in (C.STATUS_REGISTERED, C.STATUS_WAITLISTED, C.STATUS_CANCELLED):
            query = query.filter(Registration.status == status)
        return query.order_by(Registration.registered_at.desc()), q, event_id, status

    @app.route("/admin/registrations")
    @admin_required
    def admin_registrations():
        query, q, event_id, status = registration_query()
        return render_template("admin_registrations.html", regs=query.all(), q=q,
                               event_id=event_id, status=status,
                               events=Event.query.order_by(Event.name).all())

    @app.route("/admin/registrations/export.csv")
    @admin_required
    def export_registrations():
        query, *_ = registration_query()

        def safe(value):  # stop spreadsheet formula injection
            value = "" if value is None else str(value)
            return "'" + value if value[:1] in ("=", "+", "-", "@") else value

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Registration ID", "Event", "Student", "Email", "College", "Department",
                         "Year", "Status", "Registered at"])
        for r in query.all():
            writer.writerow([r.id, safe(r.event.name), safe(r.user.full_name), safe(r.user.email),
                             safe(r.user.college), safe(r.user.department), r.user.year, r.status,
                             r.registered_at.strftime("%Y-%m-%d %H:%M")])
        return Response(buffer.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=registrations.csv"})

    @app.route("/admin/registrations/<int:registration_id>")
    @admin_required
    def admin_registration_detail(registration_id):
        reg = db.session.get(Registration, registration_id) or abort(404)
        return render_template("admin_registration_detail.html", reg=reg)


def register_commands(app):
    @app.cli.command("create-admin")
    @click.option("--name", prompt="Full name")
    @click.option("--email", prompt="Admin email")
    @click.password_option(confirmation_prompt=True)
    def create_admin(name, email, password):
        """Create an admin account (or promote an existing email)."""
        email = email.strip().lower()
        if not EMAIL_RE.match(email):
            raise click.ClickException("That is not a valid email address.")
        problem = password_problem(password)
        if problem:
            raise click.ClickException(problem)
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(full_name=name.strip(), email=email, college="Administration",
                        department="Other", year=1)
            db.session.add(user)
        user.role = "admin"
        user.set_password(password)
        db.session.commit()
        click.echo(f"Admin account ready: {email}")

    @app.cli.command("seed-events")
    def seed_command():
        """Insert the sample events if the events table is empty."""
        click.echo(f"Inserted {seed_events()} sample events.")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="This deletes ALL data. Continue?")
    def reset_db():
        """Drop and recreate all tables, then add sample events."""
        db.drop_all()
        db.create_all()
        click.echo(f"Database reset. Inserted {seed_events()} sample events.")


if __name__ == "__main__":
    application = create_app()
    application.run(host=os.environ.get("HOST", "127.0.0.1"),
                    port=int(os.environ.get("PORT", "5000")),
                    debug=application.config.get("DEBUG", False))
