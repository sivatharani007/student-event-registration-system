"""Rule-based event recommendation engine (no AI API, no paid service).

Scoring (out of 100)
    interests   30   selected interests that the event covers
    event type  20   Technical / Non-technical / Cultural / Sports / Workshop / Competition
    skill level 15   event level vs. the student's level
    budget      15   fee within the student's maximum budget
    mode        10   Online / Offline / Hybrid
    goal        10   the event supports the student's primary goal
Flexible mismatches for duration and team/individual preference subtract 5 each.

Hard filters (always applied): event has not ended, registration is open,
seats are available, the student's department is eligible, the fee is within
budget, and the start date is inside the chosen date window.
Optional strict filters (student chooses): event type, skill level, mode,
duration, participation.

The functions only need event objects with the attributes used below, so they
are easy to unit-test without a database.
"""
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import constants as C

WEIGHTS = {"interests": 30, "event_type": 20, "skill_level": 15,
           "budget": 15, "mode": 10, "goal": 10}
STRICT_OPTIONS = {
    "event_type": "event type",
    "skill_level": "skill level",
    "mode": "participation mode",
    "duration": "duration",
    "participation": "individual/team choice",
}
MAX_RESULTS = 6
MIN_GOOD_SCORE = 40
LEVEL_INDEX = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}


@dataclass
class Preferences:
    department: str = "Other"
    interests: list = field(default_factory=list)
    event_type: str = "Any type"
    skill_level: str = "Any level"
    mode: str = "Any mode"
    budget: str = "any"
    date_range: str = "any"
    duration: str = "any"
    participation: str = "either"
    goal: str = ""
    strict: set = field(default_factory=set)

    @classmethod
    def from_dict(cls, data):
        """Build validated preferences from raw form data (a dict of strings/lists)."""
        def pick(key, allowed, default):
            value = data.get(key, default)
            return value if value in allowed else default

        interests = [i for i in data.get("interests", []) if i in C.INTERESTS]
        return cls(
            department=pick("department", C.DEPARTMENTS, "Other"),
            interests=interests,
            event_type=pick("event_type", C.TYPE_PREFS, "Any type"),
            skill_level=pick("skill_level", C.SKILL_PREFS, "Any level"),
            mode=pick("mode", C.MODE_PREFS, "Any mode"),
            budget=pick("budget", [v for v, _ in C.BUDGETS], "any"),
            date_range=pick("date_range", [v for v, _ in C.DATE_RANGES], "any"),
            duration=pick("duration", [v for v, _ in C.DURATIONS], "any"),
            participation=pick("participation", [v for v, _ in C.PARTICIPATION], "either"),
            goal=pick("goal", C.GOALS, ""),
            strict={s for s in data.get("strict", []) if s in STRICT_OPTIONS},
        )


@dataclass
class Recommendation:
    event: object
    score: int
    matched_interests: list
    explanation: str
    breakdown: list  # (label, earned, maximum)
    skills: list
    seats_left: int


# ---------------------------------------------------------------- helpers
def duration_bucket(hours):
    if hours <= 4:
        return "few_hours"
    if hours <= 7:
        return "half_day"
    if hours <= 14:
        return "full_day"
    return "multi_day"


def within_budget(fee, budget):
    limit = C.BUDGET_LIMITS.get(budget)
    return limit is None or fee <= limit


def type_matches(pref, event):
    if pref == "Any type":
        return True
    if pref == "Non-technical":
        return event.event_type in ("Non-technical", "Cultural", "Sports")
    if pref in ("Workshop", "Competition"):
        return event.kind == pref
    return event.event_type == pref


def mode_compatible(pref, mode):
    if pref == "Any mode":
        return True
    if pref == "Hybrid":
        return mode == "Hybrid"
    return mode in (pref, "Hybrid")


def skill_compatible(pref, level):
    return pref == "Any level" or level == "Any" or pref == level


def participation_ok(pref, event):
    if pref == "individual":
        return event.team_min <= 1
    if pref == "team":
        return event.team_max > 1
    return True


def strict_checks(event, prefs):
    return {
        "event_type": type_matches(prefs.event_type, event),
        "skill_level": skill_compatible(prefs.skill_level, event.skill_level),
        "mode": mode_compatible(prefs.mode, event.mode),
        "duration": prefs.duration == "any"
                    or duration_bucket(event.duration_hours) == prefs.duration,
        "participation": participation_ok(prefs.participation, event),
    }


def is_eligible(event, department):
    eligible = event.eligible_list
    return (not eligible) or "All" in eligible or department in eligible


def hard_filter_reason(event, prefs, now, exclude_ids=()):
    """Return a short reason key if the event must be excluded, else None."""
    if event.id in exclude_ids:
        return "already_joined"
    if event.status != "published" or event.end_time < now:
        return "unavailable"
    if event.registration_deadline < now:
        return "deadline"
    if event.seats_left <= 0:
        return "full"
    if not is_eligible(event, prefs.department):
        return "not_eligible"
    if not within_budget(event.fee, prefs.budget):
        return "budget"
    days = C.DATE_LIMITS.get(prefs.date_range)
    if event.start_time < now or (days is not None and event.start_time > now + timedelta(days=days)):
        return "date"
    checks = strict_checks(event, prefs)
    for key in prefs.strict:
        if not checks[key]:
            return key
    return None


# ---------------------------------------------------------------- scoring
def _skill_points(pref, level):
    if pref == "Any level" or level == "Any" or pref == level:
        return WEIGHTS["skill_level"]
    gap = abs(LEVEL_INDEX[pref] - LEVEL_INDEX[level])
    return 8 if gap == 1 else 0


def _mode_points(pref, mode):
    if pref == "Any mode" or pref == mode:
        return WEIGHTS["mode"]
    if mode == "Hybrid":
        return 7
    return 3 if pref == "Hybrid" else 0


def _join(items, word="and"):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {word} " + items[-1]


def score_event(event, prefs):
    """Return a Recommendation for one event (assumes hard filters already passed)."""
    selected = {i.lower() for i in prefs.interests}
    matched = [i for i in event.interests_list if i.lower() in selected]
    if selected:
        interest_pts = WEIGHTS["interests"] * min(1.0, len(matched) / min(2, len(selected)))
    else:
        interest_pts = 0
    type_ok = type_matches(prefs.event_type, event)
    type_pts = WEIGHTS["event_type"] if type_ok else 0
    skill_pts = _skill_points(prefs.skill_level, event.skill_level)
    budget_pts = WEIGHTS["budget"] if within_budget(event.fee, prefs.budget) else 0
    mode_pts = _mode_points(prefs.mode, event.mode)
    goal_ok = bool(prefs.goal) and prefs.goal in event.goals_list
    goal_pts = WEIGHTS["goal"] if goal_ok else 0

    checks = strict_checks(event, prefs)
    penalty = 0
    if prefs.duration != "any" and not checks["duration"]:
        penalty += 5
    if prefs.participation != "either" and not checks["participation"]:
        penalty += 5

    total = interest_pts + type_pts + skill_pts + budget_pts + mode_pts + goal_pts - penalty
    score = int(max(0, min(100, round(total))))

    reasons = []
    if matched:
        reasons.append(f"you selected {_join(matched, '&')}")
    if prefs.event_type != "Any type" and type_ok:
        reasons.append(f"it is a {prefs.event_type.lower()} event, as you prefer")
    if prefs.skill_level != "Any level" and skill_pts == WEIGHTS["skill_level"]:
        if event.skill_level == "Any":
            reasons.append("it welcomes every skill level")
        else:
            reasons.append(f"it suits {prefs.skill_level.lower()} participants")
    if event.fee == 0:
        reasons.append("it is free to join")
    elif prefs.budget != "any":
        reasons.append(f"the fee (₹{event.fee}) is within your budget")
    if prefs.mode != "Any mode" and mode_pts >= 7:
        reasons.append(f"it can be attended {event.mode.lower()}")
    if goal_ok:
        reasons.append(f"it supports your goal to {prefs.goal[0].lower() + prefs.goal[1:]}")
    if prefs.duration != "any" and checks["duration"]:
        reasons.append("the duration fits your available time")
    if prefs.participation != "either" and checks["participation"]:
        reasons.append(f"it allows {prefs.participation} participation")

    if reasons:
        explanation = "This event is recommended because " + _join(reasons) + "."
    else:
        explanation = ("This event satisfies your strict requirements but matches "
                       "few of your other preferences.")

    breakdown = [
        ("Interests", round(interest_pts), WEIGHTS["interests"]),
        ("Event type", type_pts, WEIGHTS["event_type"]),
        ("Skill level", skill_pts, WEIGHTS["skill_level"]),
        ("Budget", budget_pts, WEIGHTS["budget"]),
        ("Mode", mode_pts, WEIGHTS["mode"]),
        ("Goal", goal_pts, WEIGHTS["goal"]),
    ]
    if penalty:
        breakdown.append(("Duration/team mismatch", -penalty, 0))

    return Recommendation(event=event, score=score, matched_interests=matched,
                          explanation=explanation, breakdown=breakdown,
                          skills=event.skills_list, seats_left=event.seats_left)


_REASON_TEXT = {
    "already_joined": "you have already registered for {n}",
    "unavailable": "{n} have ended or are not open",
    "deadline": "{n} have a closed registration deadline",
    "full": "{n} are fully booked",
    "not_eligible": "{n} are not open to your department",
    "budget": "{n} cost more than your maximum budget",
    "date": "{n} start outside your chosen date window",
    "event_type": "{n} do not match your strict event type",
    "skill_level": "{n} do not match your strict skill level",
    "mode": "{n} do not match your strict participation mode",
    "duration": "{n} do not match your strict duration",
    "participation": "{n} do not match your strict individual/team choice",
}


def recommend(events, prefs, now=None, exclude_ids=()):
    """Rank events for the given preferences.

    Returns a dict with: results (top 3-6 good matches), alternatives (lower
    scoring events that still pass every strict rule), excluded (human-readable
    reasons events were removed), scores ({event_id: score}) and message.
    """
    now = now or datetime.now()
    kept, removed = [], Counter()
    for event in events:
        reason = hard_filter_reason(event, prefs, now, exclude_ids)
        if reason:
            removed[reason] += 1
        else:
            kept.append(score_event(event, prefs))
    kept.sort(key=lambda r: (-r.score, r.event.start_time))

    good = [r for r in kept if r.score >= MIN_GOOD_SCORE]
    results = good[:MAX_RESULTS]
    alternatives = []
    if len(results) < 3:
        alternatives = [r for r in kept if r not in results][: 3 - len(results)]

    excluded = [_REASON_TEXT[k].format(n=f"{n} event{'s' if n != 1 else ''}")
                for k, n in removed.most_common() if k in _REASON_TEXT]

    if results:
        message = ""
    elif kept:
        message = ("No event is a strong match for your interests, but these events "
                   "still follow all of your strict requirements.")
    else:
        message = ("No events satisfy your strict requirements right now. "
                   "Try a larger budget or date window, or change strict options to flexible.")
    return {
        "results": results,
        "alternatives": alternatives,
        "excluded": excluded,
        "message": message,
        "scores": {r.event.id: r.score for r in kept},
        "considered": len(kept) + sum(removed.values()),
    }
