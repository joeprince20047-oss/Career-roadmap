# Career Roadmap

A multi-user Streamlit app that recommends a career for AI and Data Science students, finds their skill gaps, and turns them into a weekly plan they can track day to day.

## Features

- **Accounts:** sign up with a username and password (passwords are salted and hashed).
- **Setup:** choose a target career and rate your skills once.
- **Today:** study streak, this week's focus steps with learning resources, one-tap step completion, daily study log.
- **My plan:** timeline with done / current / behind / upcoming steps, readiness score, skill radar.
- **Skill check:** pre-test and post-test (different questions, same skills) with normalized learning gain.
- **Progress:** study time, skill levels over time, test history.
- **Feedback:** clarity, usefulness and topic-order ratings.
- **Admin:** user counts, average learning gain, satisfaction, common skill gaps, CSV export.

## Project structure

```
app.py          Streamlit interface
engine.py       recommendation, skill gaps, roadmap, metrics
db.py           storage (SQLite locally, Postgres in production)
data/
  careers.csv   career, skill, level, weight
  prereqs.csv   skill, prerequisite
  quiz.csv      pre/post questions (form A and B)
  resources.csv learning link per skill
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Data is stored in `data/app.db` (SQLite).

## Deploy for many users

Streamlit Community Cloud resets local files when the app restarts, so use a free Postgres database (Neon or Supabase) for permanent storage.

In the app's **Settings > Secrets**, add:

```toml
DATABASE_URL = "postgresql://user:password@host:5432/dbname"
ADMIN_PASSWORD = "choose-a-strong-password"
```

Tables are created automatically on first run.

## Customize

Add careers, skills and quiz questions by editing the CSV files in `data/`. No code changes needed.
