# Student Event Registration System

A Flask web app where college students discover events, get **rule-based event
recommendations**, and register for them. It also includes an admin dashboard.
It runs fully on your own computer: **no paid services and no API keys**.

**Stack:** Python, Flask, SQLAlchemy, SQLite, Jinja2, Bootstrap 5, Chart.js.

> The pages load Bootstrap, icons, fonts and Chart.js from public CDNs, so you
> need an internet connection in the browser for the styling to appear.
> Everything else (database, recommendations, event posters) works offline.

---

## 1. Run it in VS Code on Windows (PowerShell)

1. **Extract** `student-event-registration-system.zip` (right-click, *Extract All*).
2. **Open the folder in VS Code:** *File, Open Folder*, choose the extracted
   `student-event-registration-system` folder (the one that contains `app.py`).
3. **Install the Python extension** if VS Code asks (publisher: Microsoft).
4. **Check that Python is installed.** Open the terminal with
   `` Ctrl+` `` (or *Terminal, New Terminal*) and run:

   ```powershell
   py --version
   ```

   You need Python 3.10 or newer. If the command is not found, install Python
   from <https://www.python.org/downloads/> and tick **"Add python.exe to PATH"**,
   then restart VS Code.
5. **Create a virtual environment** (a private folder for this project's packages):

   ```powershell
   py -m venv .venv
   ```

6. **Activate it:**

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   Your prompt should now start with `(.venv)`.
7. **If PowerShell says "running scripts is disabled"**, use one of these safe
   options (none changes system-wide settings):
   - Allow scripts **only for this terminal window**, then activate again:

     ```powershell
     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
     .\.venv\Scripts\Activate.ps1
     ```
   - Or switch the VS Code terminal to *Command Prompt* (the dropdown next to
     the **+** button) and run `.venv\Scripts\activate.bat`.
   - Or skip activation and call the venv's Python directly. Replace `python`
     with `.\.venv\Scripts\python.exe` in every command below.
8. **Install the dependencies:**

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

9. **Environment variables are optional for local use.** In development the app
   creates a random secret key for you in `instance\.secret_key`. If you want to
   change settings, copy `.env.example` to `.env` and edit it (see section 4).
10. **Start the app:**

    ```powershell
    python app.py
    ```

    The first start creates the SQLite database (`instance\events.db`) and adds
    19 sample events automatically.
11. **Open the website:** <http://127.0.0.1:5000> in your browser.
12. **Stop the server:** click the terminal and press `Ctrl+C`.

### Create an admin account

Admins are never created with a default password. Run this once (in a second
terminal with the venv activated, or after stopping the server) and answer the prompts:

```powershell
python -m flask --app app create-admin
```

Then log in at <http://127.0.0.1:5000/admin/login>. If the email already belongs
to a student account, that account is promoted to admin and its password is reset.

### Sample data commands

```powershell
python -m flask --app app seed-events   # add sample events if there are none
python -m flask --app app reset-db      # DELETE everything and start fresh (asks first)
```

Students register through the website (**Register** in the top bar). No sample
students or registrations are created.

### Run the automated tests

```powershell
python -m pytest
```

---

## 2. How recommendations work (`recommendations.py`)

Each eligible event gets a score out of 100:

| Criterion | Points | How it is scored |
|---|---|---|
| Interests | 30 | Full points when the event covers 2 of your interests (or your only one) |
| Event type | 20 | Technical / Non-technical / Cultural / Sports / Workshop / Competition |
| Skill level | 15 | Same level or "Any" = 15, one level apart = 8 |
| Budget | 15 | Fee within your maximum budget |
| Participation mode | 10 | Exact match 10, Hybrid event for an Online/Offline wish 7 |
| Goal | 10 | The event supports your primary goal |

Flexible duration and individual/team mismatches subtract 5 points each.

**Always strict (events are removed, not just scored lower):** the event has
ended, the registration deadline passed, no seats left, your department is not
eligible, the fee is above your budget, or the start date is outside your date window.
**Optional strict choices** (checkboxes on the form): event type, skill level,
mode, duration and individual/team.

The top 3 to 6 events with a score of 40 or more are shown, with a plain-English
reason, matching interests, skills you can gain and a score breakdown. If nothing
fits, the page explains which rules removed events and shows lower-scoring events
that still obey every strict rule. The percentage is a **preference-match score**,
not a guarantee that an event is objectively the best choice.

## 3. Registration rules

- A student can register once per event; duplicates are blocked in code and by a
  database constraint.
- Registration is blocked when the event ended, the deadline passed, the event is
  not published, or the student's department is not eligible.
- When an event is full the student can join the **waitlist**. If someone cancels
  (or an admin raises the capacity) the oldest waitlisted student is moved to
  **Registered** automatically.
- Students can cancel until the event starts.
- Fees are displayed only. **No payment is processed.**
- No verification email is sent, and the app does not claim to send one.

## 4. Configuration (environment variables)

| Variable | Needed for | Meaning |
|---|---|---|
| `APP_ENV` | optional | `development` (default), `production`, `testing` |
| `SECRET_KEY` | **production** | Signs login sessions. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | optional | Default is SQLite at `instance/events.db` |
| `HOST`, `PORT` | optional | Used by `python app.py` (defaults `127.0.0.1`, `5000`) |

Local development needs none of them.

## 5. Preparing for deployment (not deployed yet)

This project is **not** deployed anywhere. It is prepared for a Python host:

- Entry point: `wsgi.py` exposes `app`. Start command: `gunicorn wsgi:app`
  (gunicorn is installed on Linux/macOS hosts; it does not run on Windows).
- Set `APP_ENV=production` and a strong `SECRET_KEY` as host environment
  variables. The app refuses to start in production without a secret key.
- Production turns off debug mode and marks session cookies `Secure`, so it must
  be served over **HTTPS**.
- SQLite is fine for a small deployment, but the file must be on persistent
  storage (set `DATABASE_URL=sqlite:////absolute/path/events.db`). For several
  server processes or many users, use PostgreSQL (`DATABASE_URL=postgresql://...`
  plus `pip install psycopg2-binary`). The registration lock is per process, so
  use a database with row locking in that case.
- Create the first admin on the server with the `create-admin` command above.
- Never commit `.env`, `instance/` data or secrets (already in `.gitignore`).

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `py` is not recognised | Reinstall Python with "Add to PATH", restart VS Code. Try `python --version` instead. |
| Activation blocked by PowerShell | See step 7 above. |
| `No module named flask` | The venv is not active, or step 8 was skipped. Run `.\.venv\Scripts\Activate.ps1`, then `python -m pip install -r requirements.txt`. |
| `Address already in use` / port 5000 busy | Set another port: `$env:PORT=5001; python app.py`, then open `http://127.0.0.1:5001`. |
| `no such table` or `no such column` | Your database is from an older version. Stop the app, then run `python -m flask --app app reset-db`. |
| `database is locked` | Close other programs using `instance\events.db` and try again. |
| Page looks unstyled | The browser could not reach the CDN. Check your internet connection. |
| "Your form expired" message | Reload the page and submit again (security token timed out). |
| Forgot the admin password | Run `create-admin` again with the same email. |

## 7. Project structure

```
student-event-registration-system/
├── app.py              Flask app factory, routes, CLI commands
├── wsgi.py             Production entry point (gunicorn wsgi:app)
├── config.py           Development / production / testing settings
├── constants.py        Shared option lists
├── models.py           User, Event, Registration, Wishlist
├── services.py         Registration, waitlist and cancellation rules
├── recommendations.py  Rule-based recommendation engine
├── seed.py             Sample events (dates relative to today)
├── requirements.txt  .env.example  .gitignore
├── instance/           SQLite database is created here
├── templates/          Jinja2 pages (student + admin + error pages)
├── static/             css/style.css, js/main.js, images/posters/*.svg
└── tests/              test_recommendations.py, test_app.py
```

## 8. Security notes

Passwords are hashed with Werkzeug; forms use CSRF tokens (Flask-WTF); admin
routes check the user's role on the server (students get a 403 page); all
database access goes through SQLAlchemy with bound parameters; input is
validated on the server; redirects after login only go to local paths; CSV
exports neutralise spreadsheet formulas; repeated failed logins are temporarily
blocked per email and address (kept in memory, so it resets when the app restarts).
