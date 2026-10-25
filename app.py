"""Career Roadmap: multi-user app (accounts, weekly plan, study log, skill checks, admin).
Run:  streamlit run app.py
"""
import hmac
import json
from collections import Counter
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import engine as E
from db import Store, current_week, streak_days

st.set_page_config(page_title="Career Roadmap", page_icon="🎯", layout="wide")

ACCENT, GREEN, RED, MUTED = "#6C5CE7", "#00B894", "#D63031", "#B2BEC3"

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1100px;}
.hero {background: linear-gradient(120deg, #6C5CE7 0%, #8E7CF3 55%, #00B894 130%);
       border-radius: 18px; padding: 24px 28px; color: #fff; margin-bottom: 16px;}
.hero h1 {color: #fff; margin: 0; font-size: 1.8rem;}
.hero p {color: rgba(255,255,255,.9); margin: 6px 0 0 0;}
.kpi {background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.22);
      border-radius: 16px; padding: 14px 16px; height: 100%;}
.kl {font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; opacity: .65;}
.kv {font-size: 1.6rem; font-weight: 700; line-height: 1.25;}
.ks {font-size: .78rem; opacity: .6;}
.tag {display: inline-block; font-size: .72rem; padding: 2px 9px; border-radius: 99px;
      margin-left: 8px; color: #fff; vertical-align: middle;}
div[data-testid="stTabs"] button {font-weight: 600;}
</style>
""", unsafe_allow_html=True)

LABELS = {"ml": "Machine Learning", "sql": "SQL", "mlops": "MLOps", "git": "Git / GitHub",
          "deep_learning": "Deep Learning", "model_evaluation": "Model Evaluation"}


def label(skill):
    return LABELS.get(skill, skill.replace("_", " ").title())


def secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return default


def style(fig, height=340):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def kpi(col, title, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="kl">{title}</div><div class="kv">{value}</div>'
                 f'<div class="ks">{sub}</div></div>', unsafe_allow_html=True)


def hero(title, text):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{text}</p></div>', unsafe_allow_html=True)


# ------------------------------------------------------------------- data
careers, prereqs = E.load_careers(), E.load_prereqs()
skills = E.all_skills(careers)
QUIZ = pd.read_csv(E.DATA / "quiz.csv")
RES = pd.read_csv(E.DATA / "resources.csv").set_index("skill")


@st.cache_resource
def get_store():
    return Store(secret("DATABASE_URL"))


store = get_store()


def get_plan(profile):
    gaps = E.find_gaps(profile["start"], profile["goal"], careers)
    return E.build_roadmap(gaps, profile["start"], prereqs)


# ------------------------------------------------------------------- auth
def auth_screen():
    hero("🎯 Career Roadmap", "Pick a career, see your skill gaps, and follow a weekly plan you can track every day.")
    t1, t2 = st.tabs(["Log in", "Create account"])
    with t1:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            go_login = st.form_submit_button("Log in")
        if go_login:
            user, msg = store.login(u, p)
            if user:
                st.session_state.user = user
                st.rerun()
            st.error(msg)
    with t2:
        with st.form("register"):
            u = st.text_input("Choose a username", help="3-30 letters, numbers or underscores")
            p = st.text_input("Choose a password", type="password", help="At least 6 characters")
            go_reg = st.form_submit_button("Create account")
        if go_reg:
            user, msg = store.create_user(u, p)
            if user:
                st.session_state.user = user
                st.rerun()
            st.error(msg)
        st.caption("No email needed. Only your username, a hashed password and your study data are stored.")


def onboarding(uid):
    hero("👋 Welcome", "Set up your plan in a minute. You can change it later.")
    names = list(careers)
    with st.form("setup"):
        goal = st.selectbox("Which career are you aiming for?", names,
                            index=names.index("Data Scientist") if "Data Scientist" in names else 0)
        st.caption("Rate your current level in each skill: 0 = none, 5 = expert")
        cols = st.columns(2)
        levels = {s: cols[i % 2].slider(label(s), 0, 5, 0, key=f"setup_{s}") for i, s in enumerate(skills)}
        create = st.form_submit_button("Create my roadmap")
    if create:
        store.save_profile(uid, goal, levels)
        st.rerun()


# ------------------------------------------------------------------ pages
def page_today(uid, profile):
    goal, week = profile["goal"], current_week(profile["start_date"])
    plan, done = get_plan(profile), store.steps_done(uid)
    logs = store.study_log(uid)
    cutoff = (date.today() - timedelta(days=6)).isoformat()
    streak = streak_days(logs["day"].tolist()) if len(logs) else 0
    week_min = int(logs[logs["day"] >= cutoff]["minutes"].sum()) if len(logs) else 0
    finished = len([p for p in plan if p["skill"] in done])
    pct = round(100 * finished / len(plan)) if plan else 100
    total_weeks = plan[-1]["end_week"] if plan else 0

    hero(f"Hi {st.session_state.user['username']} 👋", f"Your goal: {goal}")
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "Study streak", f"{streak} 🔥", "days in a row")
    kpi(k2, "Last 7 days", f"{week_min} min", "study time")
    kpi(k3, "Plan progress", f"{pct}%", f"{finished} of {len(plan)} steps")
    kpi(k4, "Current week", f"{week}", f"of about {total_weeks}")
    st.write("")

    todo = [p for p in plan if p["skill"] not in done]
    focus = [p for p in todo if p["start_week"] <= week]
    upcoming = [p for p in todo if p["start_week"] > week][:1]

    st.subheader("Focus now")
    if not plan or not todo:
        st.success("Every step is complete. Take the post-test in Skill check to measure your progress. 🎉")
    elif not focus:
        st.info("Nothing is due yet. Your next step starts soon.")
    for p in focus:
        s = p["skill"]
        late = p["end_week"] < week
        with st.container(border=True):
            tag = f'<span class="tag" style="background:{RED if late else ACCENT}">{"Behind" if late else "This week"}</span>'
            st.markdown(f"**{label(s)}**{tag}", unsafe_allow_html=True)
            st.caption(f"Weeks {p['start_week']} to {p['end_week']}  ·  gain {p['levels_to_gain']} levels")
            if s in RES.index:
                r = RES.loc[s]
                st.markdown(f"📚 [{r['title']}]({r['url']})  ·  about {r['hours']} h")
            if st.button("Mark step complete", key=f"done_{s}"):
                store.mark_step(uid, s)
                store.set_skill_level(uid, s, careers[goal][s][0])
                st.rerun()
    for p in upcoming:
        st.caption(f"Next up: {label(p['skill'])} (starts week {p['start_week']})")

    st.subheader("Log today's study")
    topics = {label(p["skill"]): p["skill"] for p in plan} or {"Other": "other"}
    with st.form("log", clear_on_submit=True):
        c1, c2 = st.columns(2)
        minutes = c1.number_input("Minutes studied", 5, 600, 30, step=5)
        topic = c2.selectbox("Topic", list(topics))
        note = st.text_input("What did you do? (optional)")
        save = st.form_submit_button("Save")
    if save:
        store.log_study(uid, minutes, topics[topic], note)
        st.success("Logged. Keep the streak going!")
        st.rerun()


def page_plan(uid, profile):
    goal, week = profile["goal"], current_week(profile["start_date"])
    plan, done = get_plan(profile), store.steps_done(uid)
    fit_start = E.fit_score(profile["start"], goal, careers)
    fit_now = E.fit_score(profile["now"], goal, careers)
    k1, k2, k3 = st.columns(3)
    kpi(k1, "Readiness at start", f"{fit_start}%", goal)
    kpi(k2, "Readiness now", f"{fit_now}%", f"{round(fit_now - fit_start, 1)} points gained")
    kpi(k3, "Steps left", len([p for p in plan if p["skill"] not in done]), f"of {len(plan)}")
    st.write("")
    if plan:
        colors = [GREEN if p["skill"] in done else RED if p["end_week"] < week
                  else ACCENT if p["start_week"] <= week else MUTED for p in plan]
        fig = go.Figure(go.Bar(
            y=[label(p["skill"]) for p in plan], x=[p["end_week"] - p["start_week"] + 1 for p in plan],
            base=[p["start_week"] - 1 for p in plan], orientation="h", marker_color=colors,
            text=[f"Wk {p['start_week']}-{p['end_week']}" for p in plan], textposition="inside"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title="Week")
        st.plotly_chart(style(fig, 90 + 42 * len(plan)))
        st.caption("Green = done, purple = this week, red = behind, grey = upcoming")
        st.download_button("⬇️ Download plan (CSV)", pd.DataFrame(plan).to_csv(index=False),
                           file_name="roadmap.csv", mime="text/csv")
    req = careers[goal]
    cats = [label(s) for s in req]
    need = [req[s][0] for s in req]
    now = [min(profile["now"].get(s, 0), req[s][0]) for s in req]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=need + need[:1], theta=cats + cats[:1], name="Required",
                                  line_color=MUTED, fill="toself", opacity=0.35))
    fig.add_trace(go.Scatterpolar(r=now + now[:1], theta=cats + cats[:1], name="You now",
                                  line_color=ACCENT, fill="toself", opacity=0.65))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 5], dtick=1)), legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(style(fig, 380))


def page_check(uid, profile):
    goal = profile["goal"]
    st.subheader("Skill check")
    st.caption("Take the pre-test once for your baseline, then the post-test after studying. "
               "They use different questions on the same skills.")
    asm = store.assessments(uid)
    pre, post = asm[asm["kind"] == "pre"], asm[asm["kind"] == "post"]
    choice = st.radio("Test", ["Pre-test (baseline)", "Post-test (after studying)"], horizontal=True)
    kind = "pre" if choice.startswith("Pre") else "post"
    if kind == "pre" and len(pre):
        st.info(f"Baseline recorded: {int(pre.iloc[0]['score'])}%. Next, take the post-test after you've studied.")
        return
    if kind == "post" and not len(pre):
        st.warning("Take the pre-test first so improvement can be measured.")
    qs = QUIZ[(QUIZ["form"] == ("A" if kind == "pre" else "B")) & QUIZ["skill"].isin(list(careers[goal]))]
    qs = qs.reset_index(drop=True)
    if qs.empty:
        st.info("There are no quiz questions for this career's skills yet.")
        return
    with st.form(f"quiz_{kind}"):
        answers = []
        for i, r in qs.iterrows():
            opts = [f"{L}. {r[c]}" for L, c in zip("ABCD", "abcd")]
            answers.append(st.radio(f"{i + 1}. {r['question']}", opts, index=None, key=f"q_{kind}_{i}"))
        submit = st.form_submit_button("Submit answers")
    if not submit:
        return
    if any(a is None for a in answers):
        st.warning("Answer every question before submitting.")
        return
    detail, right = {}, 0
    for (i, r), a in zip(qs.iterrows(), answers):
        ok = a[0] == r["answer"]
        right += ok
        c = detail.setdefault(r["skill"], [0, 0])
        c[0] += int(ok)
        c[1] += 1
    score = round(100 * right / len(qs))
    store.add_assessment(uid, kind, score, detail)
    st.success(f"Score: {score}% ({right} of {len(qs)} correct)")
    for s, (c, n) in detail.items():
        st.write(f"{label(s)}: {c} of {n}")
    if kind == "post" and len(pre):
        res = E.assessment_improvement(int(pre.iloc[0]["score"]), score)
        st.metric("Normalized learning gain", res["normalized_gain"], f"{res['raw_gain']} points")


def page_progress(uid, profile):
    goal = profile["goal"]
    logs, asm, done = store.study_log(uid), store.assessments(uid), store.steps_done(uid)
    pre, post = asm[asm["kind"] == "pre"], asm[asm["kind"] == "post"]
    gain = "n/a"
    if len(pre) and len(post):
        gain = E.assessment_improvement(int(pre.iloc[0]["score"]), int(post.iloc[-1]["score"]))["normalized_gain"]
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "Total study", f"{round(logs['minutes'].sum() / 60, 1) if len(logs) else 0} h")
    kpi(k2, "Days studied", logs["day"].nunique() if len(logs) else 0)
    kpi(k3, "Steps done", len(done))
    kpi(k4, "Learning gain", gain, "normalized")
    st.write("")
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    by_day = logs.groupby("day")["minutes"].sum().to_dict() if len(logs) else {}
    fig = go.Figure(go.Bar(x=[d[5:] for d in days], y=[by_day.get(d, 0) for d in days], marker_color=ACCENT))
    fig.update_yaxes(title="Minutes")
    st.subheader("Last 14 days")
    st.plotly_chart(style(fig, 260))
    req = careers[goal]
    names = [label(s) for s in req]
    fig = go.Figure()
    fig.add_bar(name="Start", x=names, y=[profile["start"].get(s, 0) for s in req], marker_color=MUTED)
    fig.add_bar(name="Now", x=names, y=[profile["now"].get(s, 0) for s in req], marker_color=ACCENT)
    fig.add_bar(name="Required", x=names, y=[req[s][0] for s in req], marker_color=GREEN)
    fig.update_layout(barmode="group", legend=dict(orientation="h", y=1.15))
    st.subheader("Skill levels")
    st.plotly_chart(style(fig, 320))
    if len(asm):
        st.subheader("Skill checks")
        st.dataframe(asm[["kind", "score", "taken_at"]], hide_index=True)
    with st.expander("Change target career or start over"):
        st.warning("This clears your plan and completed steps. Your study log and test scores are kept.")
        if st.checkbox("I understand") and st.button("Reset my plan"):
            store.reset_profile(uid)
            st.rerun()


def page_feedback(uid):
    st.subheader("How is the plan working for you?")
    with st.form("fb", clear_on_submit=True):
        clarity = st.slider("Was the plan clear?", 1, 5, 4)
        useful = st.slider("Was it useful?", 1, 5, 4)
        order = st.slider("Did the order of topics make sense?", 1, 5, 4)
        comment = st.text_area("Anything we should improve? (optional)")
        send = st.form_submit_button("Send feedback")
    if send:
        store.add_feedback(uid, clarity, useful, order, comment)
        st.success("Thanks. Your feedback helps improve the recommendations.")


def page_admin():
    pw = secret("ADMIN_PASSWORD")
    if not st.session_state.get("admin_ok"):
        entered = st.text_input("Admin password", type="password")
        if st.button("Unlock") and hmac.compare_digest(str(entered), str(pw)):
            st.session_state.admin_ok = True
            st.rerun()
        return
    T = store.admin_tables()
    users, prof, logs, asm, fb = T["users"], T["profiles"], T["study_log"], T["assessments"], T["feedback"]
    cutoff = (date.today() - timedelta(days=6)).isoformat()
    active = logs[logs["day"] >= cutoff]["user_id"].nunique() if len(logs) else 0
    gain, raw = "n/a", "n/a"
    if len(asm):
        first_pre = asm[asm["kind"] == "pre"].groupby("user_id")["score"].first().rename("pre")
        last_post = asm[asm["kind"] == "post"].groupby("user_id")["score"].last().rename("post")
        both = pd.concat([first_pre, last_post], axis=1).dropna()
        if len(both):
            both["ng"] = (both["post"] - both["pre"]) / (100 - both["pre"]).replace(0, float("nan"))
            gain, raw = round(both["ng"].mean(), 2), round((both["post"] - both["pre"]).mean(), 1)
    sat = round(fb[["clarity", "usefulness", "topic_order"]].mean().mean(), 2) if len(fb) else "n/a"
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "Users", len(users))
    kpi(k2, "Active (7 days)", active)
    kpi(k3, "Avg learning gain", gain, f"raw {raw} pts")
    kpi(k4, "Satisfaction", sat, "out of 5")
    st.write("")
    if len(prof):
        st.subheader("Chosen careers")
        vc = prof["goal"].value_counts()
        st.plotly_chart(style(go.Figure(go.Bar(x=vc.index.tolist(), y=vc.values.tolist(), marker_color=ACCENT)), 260))
        counter = Counter()
        for _, r in prof.iterrows():
            if r["goal"] in careers:
                counter.update(g["skill"] for g in E.find_gaps(json.loads(r["skills_start"]), r["goal"], careers))
        if counter:
            st.subheader("Most common skill gaps")
            top = counter.most_common(8)
            st.plotly_chart(style(go.Figure(go.Bar(x=[label(s) for s, _ in top], y=[n for _, n in top],
                                                   marker_color=GREEN)), 260))
    st.subheader("Export data")
    for name in ["profiles", "study_log", "assessments", "feedback"]:
        if len(T[name]):
            st.download_button(f"⬇️ {name}.csv", T[name].to_csv(index=False), file_name=f"{name}.csv", key=f"dl_{name}")


# ------------------------------------------------------------------- main
user = st.session_state.get("user")
if not user:
    auth_screen()
    st.stop()

uid = user["id"]
profile = store.get_profile(uid)
if not profile or profile["goal"] not in careers:
    onboarding(uid)
    st.stop()

pages = ["Today", "My plan", "Skill check", "Progress", "Feedback"]
if secret("ADMIN_PASSWORD"):
    pages.append("Admin")
with st.sidebar:
    st.markdown(f"**{user['username']}**")
    page = st.radio("Menu", pages, label_visibility="collapsed")
    if st.button("Log out"):
        st.session_state.pop("user", None)
        st.session_state.pop("admin_ok", None)
        st.rerun()

if page == "Today":
    page_today(uid, profile)
elif page == "My plan":
    page_plan(uid, profile)
elif page == "Skill check":
    page_check(uid, profile)
elif page == "Progress":
    page_progress(uid, profile)
elif page == "Feedback":
    page_feedback(uid)
else:
    page_admin()
