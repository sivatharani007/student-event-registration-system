"""Shared option lists used by forms, the database and the recommender."""

DEPARTMENTS = [
    "Computer Science",
    "Information Technology",
    "Artificial Intelligence and Data Science",
    "Electronics and Communication",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Other",
]

INTERESTS = [
    "Coding", "Artificial Intelligence", "Web Development", "Robotics",
    "Gaming", "Entrepreneurship", "Designing", "Photography",
    "Public Speaking", "Cultural Activities", "Sports", "Research",
]

GOALS = [
    "Improve technical skills", "Build my resume", "Win competitions",
    "Meet new people", "Explore career opportunities", "Have fun",
    "Learn something new",
]

CATEGORIES = [
    "Hackathon", "Technical Symposium", "Coding Competition", "Coding Workshop",
    "AI/ML Workshop", "Web Development Workshop", "Paper Presentation",
    "Project Exhibition", "Robotics Competition", "Gaming Tournament",
    "Cultural Festival", "Photography Competition", "Entrepreneurship",
    "Sports Competition", "Career Development",
]

EVENT_TYPES = ["Technical", "Non-technical", "Cultural", "Sports"]
KINDS = ["Workshop", "Competition", "Other"]

SKILL_LEVELS = ["Beginner", "Intermediate", "Advanced"]
EVENT_SKILL_LEVELS = SKILL_LEVELS + ["Any"]
SKILL_PREFS = SKILL_LEVELS + ["Any level"]

MODES = ["Online", "Offline", "Hybrid"]
MODE_PREFS = MODES + ["Any mode"]

TYPE_PREFS = ["Technical", "Non-technical", "Cultural", "Sports",
              "Workshop", "Competition", "Any type"]

# (value, label). Budget is a MAXIMUM the student is willing to pay.
BUDGETS = [
    ("free", "Free events only"),
    ("100", "Under ₹100"),
    ("500", "₹100–₹500"),
    ("1000", "₹500–₹1000"),
    ("any", "Any budget"),
]
BUDGET_LIMITS = {"free": 0, "100": 99, "500": 500, "1000": 1000, "any": None}

DATE_RANGES = [
    ("7", "Upcoming 7 days"),
    ("30", "Upcoming 30 days"),
    ("90", "Upcoming 3 months"),
    ("any", "Any upcoming date"),
]
DATE_LIMITS = {"7": 7, "30": 30, "90": 90, "any": None}

DURATIONS = [
    ("few_hours", "A few hours"),
    ("half_day", "Half a day"),
    ("full_day", "Full day"),
    ("multi_day", "Multiple days"),
    ("any", "Any duration"),
]

PARTICIPATION = [("individual", "Individual"), ("team", "Team"), ("either", "Either")]

YEARS = [1, 2, 3, 4, 5]

STATUS_REGISTERED = "Registered"
STATUS_WAITLISTED = "Waitlisted"
STATUS_CANCELLED = "Cancelled"
EVENT_STATUSES = ["published", "draft", "cancelled"]
