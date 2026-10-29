"""Sample events. Dates are generated relative to today so they are always upcoming."""
from datetime import datetime, timedelta

from models import Event, db

ALL = "All"
CS = "Computer Science"
IT = "Information Technology"
AI = "Artificial Intelligence and Data Science"
EC = "Electronics and Communication"
EE = "Electrical Engineering"
ME = "Mechanical Engineering"


def _e(name, category, event_type, kind, start, end, deadline_hours, venue, mode, fee, capacity,
       level, depts, interests, goals, skills, required, benefits, team, organizer, poster, desc,
       featured=False):
    return dict(
        name=name, category=category, event_type=event_type, kind=kind, start=start, end=end,
        deadline_hours=deadline_hours, venue=venue, mode=mode, fee=fee, capacity=capacity,
        skill_level=level, eligible="|".join(depts), interests="|".join(interests),
        goals="|".join(goals), skills="|".join(skills), required=required, benefits=benefits,
        team_min=team[0], team_max=team[1], organizer=organizer,
        image_url=f"images/posters/{poster}.svg", description=desc, featured=featured)


def _sample_data():
    imp, res, win, meet, car, fun, learn = (
        "Improve technical skills", "Build my resume", "Win competitions", "Meet new people",
        "Explore career opportunities", "Have fun", "Learn something new")
    return [
        _e("CodeSprint 24-Hour Hackathon", "Hackathon", "Technical", "Competition",
           (12, 9), (13, 9), 48, "Innovation Lab, Block C", "Offline", 300, 120, "Intermediate",
           [ALL], ["Coding", "Artificial Intelligence", "Web Development"], [win, res, meet],
           ["Rapid prototyping", "Teamwork", "Git collaboration", "Product pitching"],
           "Basic programming in any language and a laptop.",
           "Certificates for all, cash prizes for the top three teams, mentor feedback.",
           (2, 4), "Coding Club", "hackathon",
           "Build a working prototype in 24 hours around a surprise theme. Mentors from industry "
           "review every team, and finalists pitch live to a panel of judges.", True),
        _e("Python for Beginners Bootcamp", "Coding Workshop", "Technical", "Workshop",
           (5, 10), (5, 14), 24, "Computer Lab 2", "Offline", 0, 80, "Beginner",
           [ALL], ["Coding"], [learn, imp],
           ["Python basics", "Problem solving", "Writing small programs"],
           "No prior coding experience needed.",
           "Free study material, practice sheet and participation certificate.",
           (1, 1), "Coding Club", "coding",
           "A friendly, hands-on introduction to Python: variables, loops, functions and a "
           "mini project you will finish before you leave.", True),
        _e("Intro to Machine Learning with scikit-learn", "AI/ML Workshop", "Technical", "Workshop",
           (9, 10), (9, 16), 24, "Seminar Hall A and online stream", "Hybrid", 150, 60,
           "Beginner", [CS, IT, AI, EC],
           ["Artificial Intelligence", "Coding", "Research"], [learn, imp, car],
           ["Data preprocessing", "Model training", "Model evaluation"],
           "Basic Python. Bring a laptop with Python installed.",
           "Notebook templates, a certificate and a starter portfolio project.",
           (1, 1), "AI Club", "ai",
           "Train your first classifier, learn how to judge it honestly and avoid the most "
           "common beginner mistakes in machine learning."),
        _e("Deep Learning Masterclass", "AI/ML Workshop", "Technical", "Workshop",
           (20, 14), (20, 18), 48, "Online (link sent after registration)", "Online", 400, 100,
           "Advanced", [CS, IT, AI],
           ["Artificial Intelligence", "Research", "Coding"], [imp, car, res],
           ["Neural networks", "Model tuning", "Research reading"],
           "Comfortable with Python, NumPy and basic ML concepts.",
           "Recorded session, code repository and a certificate.",
           (1, 1), "AI Club", "ai",
           "A fast-paced, advanced session on training and tuning deep networks, with a live "
           "walkthrough of reading and reproducing a research paper."),
        _e("Frontend Forge: Responsive Web Workshop", "Web Development Workshop", "Technical",
           "Workshop", (3, 10), (3, 16), 6, "Computer Lab 1", "Offline", 0, 70, "Beginner",
           [ALL], ["Web Development", "Designing", "Coding"], [learn, imp, res],
           ["HTML and CSS", "Responsive layouts", "Basic JavaScript"],
           "Bring a laptop. No prior experience required.",
           "Deploy your first personal page and take home all the code.",
           (1, 1), "Web Dev Society", "web",
           "Go from a blank file to a responsive portfolio page in one day with step-by-step "
           "guidance from senior students."),
        _e("BuildIt Web Challenge", "Coding Competition", "Technical", "Competition",
           (17, 10), (17, 17), 24, "Computer Lab 3 and online", "Hybrid", 100, 90, "Intermediate",
           [CS, IT, AI], ["Web Development", "Coding", "Designing"], [win, res],
           ["UI design", "Full-stack basics", "Working under time limits"],
           "Experience with HTML, CSS and one backend language.",
           "Prizes, certificates and internship referrals for top performers.",
           (1, 2), "Web Dev Society", "web",
           "Solve a real-world web problem against the clock. Solo or pairs. Judged on design, "
           "functionality and code quality."),
        _e("RoboRumble Robotics Competition", "Robotics Competition", "Technical", "Competition",
           (26, 9), (26, 18), 72, "Mechatronics Arena", "Offline", 500, 40, "Intermediate",
           [EC, EE, ME, CS, AI], ["Robotics", "Coding"], [win, fun, meet],
           ["Sensor integration", "Control logic", "Mechanical design"],
           "Team with at least one member who can program a microcontroller.",
           "Trophies, certificates and a chance to showcase at the regional meet.",
           (3, 5), "Robotics Society", "robotics",
           "Design, build and program a line-following and obstacle-clearing robot, then race it "
           "head to head in knockout rounds.", True),
        _e("TechTalks Paper Presentation", "Paper Presentation", "Technical", "Competition",
           (34, 9), (34, 16), 72, "Auditorium", "Offline", 200, 50, "Advanced", [ALL],
           ["Research", "Public Speaking"], [res, car, imp],
           ["Technical writing", "Presenting research", "Handling Q&A"],
           "An abstract (max 250 words) on any engineering or technology topic.",
           "Best papers are recommended for publication in the college journal.",
           (1, 2), "Research Cell", "research",
           "Present original work or a survey in 8 minutes, followed by questions from faculty "
           "and industry judges."),
        _e("Innovate Expo Project Exhibition", "Project Exhibition", "Technical", "Other",
           (40, 10), (40, 18), 96, "Central Atrium", "Offline", 0, 150, "Any", [ALL],
           ["Research", "Robotics", "Entrepreneurship", "Designing"], [res, meet, car],
           ["Demoing a project", "Explaining technical ideas", "Networking"],
           "A working project, prototype or model of any size.",
           "Visitor feedback, faculty reviews and a chance to find collaborators.",
           (1, 4), "Innovation Cell", "expo",
           "Show your project to the whole campus and visiting industry guests. All years and "
           "all departments are welcome."),
        _e("PixelPit Gaming Tournament", "Gaming Tournament", "Non-technical", "Competition",
           (14, 11), (14, 19), 48, "Recreation Hall and online lobby", "Hybrid", 100, 128, "Any",
           [ALL], ["Gaming"], [fun, win, meet],
           ["Strategy", "Teamwork", "Quick decision making"],
           "Your own device for the online bracket.",
           "Prize pool, gaming merchandise and bragging rights.",
           (1, 4), "Gaming Club", "gaming",
           "Knockout brackets for popular PC and mobile titles. Play solo or bring a squad."),
        _e("Rhythm & Roots Cultural Fest", "Cultural Festival", "Cultural", "Other",
           (30, 10), (32, 21), 72, "Open Air Theatre", "Offline", 250, 400, "Any", [ALL],
           ["Cultural Activities", "Public Speaking", "Designing"], [fun, meet],
           ["Stage presence", "Event coordination", "Creative expression"],
           "None. Performers can register for music, dance, drama or art.",
           "Performance certificates, food stalls and three days of campus celebration.",
           (1, 10), "Cultural Committee", "cultural",
           "Three days of music, dance, drama and art. Perform, volunteer or just enjoy the "
           "festival with friends.", True),
        _e("Through the Lens Photography Contest", "Photography Competition", "Non-technical",
           "Competition", (8, 9), (10, 18), 48, "Online submission portal", "Online", 50, 200,
           "Beginner", [ALL], ["Photography", "Designing"], [fun, win, learn],
           ["Composition", "Storytelling with images", "Basic editing"],
           "A phone or camera. Theme: 'Campus in Motion'.",
           "Winning photos are exhibited on campus and printed in the annual magazine.",
           (1, 1), "Photography Club", "photo",
           "Capture the theme 'Campus in Motion' and submit up to three photos. Judged by "
           "professional photographers."),
        _e("Startup Spark Workshop", "Entrepreneurship", "Non-technical", "Workshop",
           (11, 14), (11, 17), 24, "Seminar Hall B and online stream", "Hybrid", 0, 100, "Beginner",
           [ALL], ["Entrepreneurship", "Public Speaking"], [learn, car, meet],
           ["Idea validation", "Business model basics", "Customer discovery"],
           "Curiosity. Bring a rough business idea if you have one.",
           "Mentor contacts, a business model canvas template and a certificate.",
           (1, 1), "E-Cell", "startup",
           "Founders walk you through validating an idea, finding first customers and building "
           "a simple business model."),
        _e("Pitch Perfect Startup Competition", "Entrepreneurship", "Non-technical", "Competition",
           (45, 9), (45, 17), 96, "Auditorium", "Offline", 750, 30, "Intermediate", [ALL],
           ["Entrepreneurship", "Public Speaking"], [win, res, car],
           ["Pitching", "Financial planning", "Market research"],
           "A startup idea with a one-page summary.",
           "Seed prize money, incubation support and investor feedback.",
           (2, 4), "E-Cell", "startup",
           "Pitch your startup to a panel of founders and investors in a 5-minute presentation "
           "followed by tough questions."),
        _e("Inter-College Cricket Cup", "Sports Competition", "Sports", "Competition",
           (21, 7), (21, 18), 96, "College Cricket Ground", "Offline", 600, 96, "Any", [ALL],
           ["Sports"], [win, fun, meet],
           ["Teamwork", "Fitness", "Leadership"],
           "Teams of 11 to 15 players. Medical fitness is your own responsibility.",
           "Trophies, medals and refreshments for all players.",
           (11, 15), "Sports Committee", "sports",
           "One-day knockout cricket tournament. Register as a team squad and play up to three "
           "matches."),
        _e("Campus Badminton Open", "Sports Competition", "Sports", "Competition",
           (6, 8), (6, 17), 12, "Indoor Stadium", "Offline", 100, 64, "Any", [ALL],
           ["Sports"], [fun, win],
           ["Fitness", "Strategy", "Sportsmanship"],
           "Bring your own racket. Singles or doubles.",
           "Medals for winners and runners-up.",
           (1, 2), "Sports Committee", "sports",
           "A relaxed but competitive singles and doubles tournament open to all skill levels."),
        _e("Resume & Interview Bootcamp", "Career Development", "Non-technical", "Workshop",
           (4, 10), (4, 13), 12, "Placement Cell Hall", "Offline", 0, 120, "Beginner", [ALL],
           ["Public Speaking", "Entrepreneurship"], [res, car, learn],
           ["Resume writing", "Interview skills", "LinkedIn basics"],
           "Bring a printed or digital copy of your current resume.",
           "Personal resume feedback and a mock interview slot.",
           (1, 1), "Placement Cell", "career",
           "Fix your resume, practise common interview questions and learn what recruiters "
           "look for in fresh graduates."),
        _e("Cloud Careers Live Talk", "Career Development", "Technical", "Other",
           (2, 18), (2, 20), 3, "Online (link sent after registration)", "Online", 0, 500, "Any",
           [CS, IT, AI, EC], ["Coding", "Artificial Intelligence"], [car, learn],
           ["Cloud roles overview", "Certification roadmap", "Interview expectations"],
           "None.",
           "Live Q&A with cloud engineers and a recording of the session.",
           (1, 1), "Placement Cell", "career",
           "Two engineers explain how they entered the cloud industry, which skills matter and "
           "how to prepare in your final years."),
        _e("ExcelTech Technical Symposium", "Technical Symposium", "Technical", "Other",
           (50, 9), (52, 17), 96, "Engineering Block", "Offline", 400, 300, "Any", [ALL],
           ["Coding", "Robotics", "Research", "Artificial Intelligence"], [meet, learn, res],
           ["Technical quizzes", "Project demos", "Networking"],
           "None. Choose from over a dozen events across departments.",
           "Access to all symposium events, certificates and networking with industry speakers.",
           (1, 4), "Engineering Departments", "symposium",
           "Our flagship three-day symposium with quizzes, circuit-design contests, coding rounds "
           "and guest lectures from industry experts.", True),
    ]


def seed_events():
    """Insert sample events if the table is empty. Returns the number inserted."""
    if Event.query.count() > 0:
        return 0
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    items = _sample_data()
    for d in items:
        start = today + timedelta(days=d["start"][0], hours=d["start"][1])
        end = today + timedelta(days=d["end"][0], hours=d["end"][1])
        db.session.add(Event(
            name=d["name"], description=d["description"], category=d["category"],
            event_type=d["event_type"], kind=d["kind"], start_time=start, end_time=end,
            registration_deadline=start - timedelta(hours=d["deadline_hours"]),
            venue=d["venue"], mode=d["mode"], fee=d["fee"], capacity=d["capacity"],
            required_skills=d["required"], skills_gained=d["skills"], benefits=d["benefits"],
            skill_level=d["skill_level"], eligible_departments=d["eligible"],
            interests=d["interests"], goals=d["goals"], team_min=d["team_min"],
            team_max=d["team_max"], organizer=d["organizer"],
            contact_email="events@college.example", image_url=d["image_url"],
            status="published", is_featured=d["featured"]))
    db.session.commit()
    return len(items)
