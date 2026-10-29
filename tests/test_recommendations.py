"""Tests for the rule-based recommendation engine (no database needed)."""
from datetime import datetime, timedelta
from types import SimpleNamespace

from recommendations import Preferences, recommend, score_event

NOW = datetime(2026, 1, 1, 9, 0)


def make_event(event_id=1, **kw):
    data = dict(
        id=event_id, name=f"Event {event_id}", status="published",
        start_time=NOW + timedelta(days=5), end_time=NOW + timedelta(days=5, hours=5),
        registration_deadline=NOW + timedelta(days=3), fee=0, seats_left=10,
        skill_level="Beginner", mode="Offline", event_type="Technical", kind="Workshop",
        team_min=1, team_max=1, eligible_list=["All"],
        interests_list=["Coding", "Artificial Intelligence"],
        goals_list=["Learn something new"], skills_list=["Python"],
    )
    data.update(kw)
    if "start_time" in kw and "end_time" not in kw:
        data["end_time"] = data["start_time"] + timedelta(hours=5)
    ev = SimpleNamespace(**data)
    ev.duration_hours = (ev.end_time - ev.start_time).total_seconds() / 3600
    return ev


def prefs(**kw):
    base = dict(department="Computer Science", interests=["Coding", "Artificial Intelligence"],
                goal="Learn something new")
    base.update(kw)
    return Preferences.from_dict(base)


def test_score_is_between_0_and_100_and_explains_match():
    rec = score_event(make_event(), prefs(skill_level="Beginner", budget="free"))
    assert 0 <= rec.score <= 100
    assert rec.score == 100  # every criterion matches
    assert "Coding" in rec.explanation and "free" in rec.explanation
    assert rec.matched_interests == ["Coding", "Artificial Intelligence"]


def test_better_match_ranks_higher():
    good = make_event(1)
    weak = make_event(2, interests_list=["Sports"], goals_list=[], event_type="Sports", kind="Competition")
    out = recommend([weak, good], prefs(event_type="Technical"), now=NOW)
    assert out["results"][0].event.id == 1


def test_strict_budget_filter_excludes_expensive_events():
    cheap = make_event(1, fee=50)
    pricey = make_event(2, fee=800)
    out = recommend([cheap, pricey], prefs(budget="100"), now=NOW)
    ids = [r.event.id for r in out["results"]]
    assert ids == [1]
    assert any("budget" in reason for reason in out["excluded"])


def test_free_only_budget():
    out = recommend([make_event(1, fee=0), make_event(2, fee=1)], prefs(budget="free"), now=NOW)
    assert [r.event.id for r in out["results"]] == [1]


def test_date_window_filter():
    soon = make_event(1, start_time=NOW + timedelta(days=3))
    later = make_event(2, start_time=NOW + timedelta(days=20))
    out = recommend([soon, later], prefs(date_range="7"), now=NOW)
    assert [r.event.id for r in out["results"]] == [1]
    out = recommend([soon, later], prefs(date_range="30"), now=NOW)
    assert {r.event.id for r in out["results"]} == {1, 2}


def test_excludes_ended_full_closed_and_ineligible_events():
    ended = make_event(1, start_time=NOW - timedelta(days=3))
    full = make_event(2, seats_left=0)
    closed = make_event(3, registration_deadline=NOW - timedelta(hours=1))
    wrong_dept = make_event(4, eligible_list=["Civil Engineering"])
    draft = make_event(5, status="draft")
    ok = make_event(6)
    out = recommend([ended, full, closed, wrong_dept, draft, ok], prefs(), now=NOW)
    assert [r.event.id for r in out["results"]] == [6]


def test_strict_mode_filter_vs_flexible():
    online = make_event(1, mode="Online")
    offline = make_event(2, mode="Offline")
    flexible = recommend([online, offline], prefs(mode="Offline"), now=NOW)
    assert {r.event.id for r in flexible["results"]} == {1, 2}
    assert flexible["results"][0].event.id == 2  # matching mode scores higher
    strict = recommend([online, offline], prefs(mode="Offline", strict=["mode"]), now=NOW)
    assert [r.event.id for r in strict["results"]] == [2]


def test_hybrid_events_satisfy_online_or_offline_preference():
    hybrid = make_event(1, mode="Hybrid")
    out = recommend([hybrid], prefs(mode="Online", strict=["mode"]), now=NOW)
    assert len(out["results"]) == 1


def test_team_preference_strict():
    solo = make_event(1, team_min=1, team_max=1)
    team = make_event(2, team_min=2, team_max=4)
    out = recommend([solo, team], prefs(participation="team", strict=["participation"]), now=NOW)
    assert [r.event.id for r in out["results"]] == [2]


def test_no_match_gives_explanation_not_random_events():
    out = recommend([make_event(1, fee=900)], prefs(budget="free"), now=NOW)
    assert out["results"] == [] and out["alternatives"] == []
    assert "strict requirements" in out["message"]
    assert out["excluded"]


def test_low_scoring_events_become_alternatives_not_top_results():
    off_topic = make_event(1, interests_list=["Sports"], goals_list=[], event_type="Sports",
                           kind="Competition", skill_level="Advanced")
    out = recommend([off_topic], prefs(event_type="Technical", skill_level="Beginner",
                                       mode="Online", budget="any"), now=NOW)
    assert out["results"] == []
    assert len(out["alternatives"]) == 1
    assert out["message"]


def test_results_are_capped_at_six():
    events = [make_event(i) for i in range(1, 12)]
    out = recommend(events, prefs(), now=NOW)
    assert len(out["results"]) == 6


def test_invalid_form_values_fall_back_to_safe_defaults():
    p = Preferences.from_dict({"interests": ["Coding", "Hacking"], "budget": "bogus", "strict": ["mode", "x"]})
    assert p.interests == ["Coding"] and p.budget == "any" and p.strict == {"mode"}
