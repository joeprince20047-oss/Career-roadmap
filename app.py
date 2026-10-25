"""Career Roadmap dashboard.  Run:  streamlit run app.py"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import engine as E

st.set_page_config(page_title="Career Roadmap", page_icon="🎯", layout="wide")

ACCENT, ACCENT2, MUTED = "#6C5CE7", "#00B894", "#B2BEC3"

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1200px;}
.hero {background: linear-gradient(120deg, #6C5CE7 0%, #8E7CF3 55%, #00B894 130%);
       border-radius: 18px; padding: 26px 30px; color: #fff; margin-bottom: 18px;}
.hero h1 {color: #fff; margin: 0; font-size: 1.9rem;}
.hero p {color: rgba(255,255,255,.88); margin: 6px 0 0 0; font-size: 1rem;}
.kpi {background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.22);
      border-radius: 16px; padding: 16px 18px; height: 100%;}
.kl {font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; opacity: .65;}
.kv {font-size: 1.7rem; font-weight: 700; line-height: 1.25; margin-top: 2px;}
.ks {font-size: .8rem; opacity: .6; margin-top: 2px;}
.step {display: flex; gap: 14px; align-items: center; padding: 12px 14px; margin-bottom: 8px;
       background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.2); border-radius: 14px;}
.num {background: #6C5CE7; color: #fff; border-radius: 50%; min-width: 32px; height: 32px;
      display: flex; align-items: center; justify-content: center; font-weight: 700;}
.step small {opacity: .65;}
div[data-testid="stTabs"] button {font-weight: 600;}
</style>
""", unsafe_allow_html=True)

LABELS = {"ml": "Machine Learning", "sql": "SQL", "mlops": "MLOps", "git": "Git / GitHub",
          "deep_learning": "Deep Learning", "model_evaluation": "Model Evaluation"}


def label(skill):
    return LABELS.get(skill, skill.replace("_", " ").title())


def style(fig, height=380):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def kpi(col, title, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="kl">{title}</div><div class="kv">{value}</div>'
                 f'<div class="ks">{sub}</div></div>', unsafe_allow_html=True)


careers, prereqs = E.load_careers(), E.load_prereqs()
skills = E.all_skills(careers)
DEMO = {"python": 3, "sql": 2, "excel": 3, "ml": 1, "visualization": 1}


def load_demo():
    for s in skills:
        st.session_state[f"s_{s}"] = DEMO.get(s, 0)


def reset_all():
    for s in skills:
        st.session_state[f"s_{s}"] = 0


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Your profile")
    goal = st.selectbox("Target career", list(careers),
                        index=list(careers).index("Data Scientist") if "Data Scientist" in careers else 0)
    c1, c2 = st.columns(2)
    c1.button("Load demo", on_click=load_demo)
    c2.button("Reset", on_click=reset_all)
    st.caption("Rate each skill: 0 = none, 5 = expert")
    profile = {s: st.slider(label(s), 0, 5, 0, key=f"s_{s}") for s in skills}

# ------------------------------------------------------------- calculations
ranked = E.recommend(profile, careers)
gaps = E.find_gaps(profile, goal, careers)
plan = E.build_roadmap(gaps, profile, prereqs)
goal_fit = E.fit_score(profile, goal, careers)
total_weeks = plan[-1]["end_week"] if plan else 0

# -------------------------------------------------------------------- hero
st.markdown('<div class="hero"><h1>🎯 Career Roadmap Dashboard</h1>'
            '<p>Find your best-fit career, see your skill gaps, and follow a week-by-week plan.</p></div>',
            unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
kpi(k1, "Best match", ranked[0][0], f"{ranked[0][1]}% fit")
kpi(k2, f"Readiness: {goal}", f"{goal_fit}%", "skills already covered")
kpi(k3, "Skills to learn", len(gaps), "gaps for your target")
kpi(k4, "Estimated time", f"{total_weeks} wks", "to reach your target")
st.write("")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🧩 Skill gaps", "🗓️ Roadmap", "✅ Evaluate"])

# ---------------------------------------------------------------- overview
with tab1:
    left, right = st.columns(2)
    with left:
        st.subheader("Career fit")
        names, vals = [c for c, _ in ranked][::-1], [v for _, v in ranked][::-1]
        fig = go.Figure(go.Bar(x=vals, y=names, orientation="h",
                               marker_color=[ACCENT if n == goal else MUTED for n in names],
                               text=[f"{v}%" for v in vals], textposition="outside"))
        fig.update_xaxes(range=[0, 100], title="Fit (%)")
        st.plotly_chart(style(fig))
    with right:
        st.subheader(f"Skill profile vs {goal}")
        req = careers[goal]
        cats = [label(s) for s in req]
        have = [min(profile[s], req[s][0]) for s in req]
        need = [req[s][0] for s in req]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=need + need[:1], theta=cats + cats[:1], name="Required",
                                      line_color=MUTED, fill="toself", opacity=0.35))
        fig.add_trace(go.Scatterpolar(r=have + have[:1], theta=cats + cats[:1], name="You",
                                      line_color=ACCENT, fill="toself", opacity=0.65))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 5], dtick=1)),
                          legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(style(fig))

# ---------------------------------------------------------------- gap table
with tab2:
    if not gaps:
        st.success("You already meet every requirement for this role. 🎉")
    else:
        st.subheader("Where you stand")
        df = pd.DataFrame([{"Skill": label(g["skill"]), "Current": profile[g["skill"]],
                            "Required": careers[goal][g["skill"]][0], "Gap": g["gap"],
                            "Priority": g["priority"]} for g in gaps])
        fig = go.Figure()
        fig.add_bar(name="Current", x=df["Skill"], y=df["Current"], marker_color=ACCENT)
        fig.add_bar(name="Required", x=df["Skill"], y=df["Required"], marker_color=MUTED)
        fig.update_layout(barmode="group", legend=dict(orientation="h", y=1.12))
        fig.update_yaxes(range=[0, 5], title="Level")
        st.plotly_chart(style(fig, 340))
        st.dataframe(df, hide_index=True,
                     column_config={
                         "Current": st.column_config.ProgressColumn("Current", min_value=0, max_value=5, format="%d"),
                         "Required": st.column_config.ProgressColumn("Required", min_value=0, max_value=5, format="%d"),
                         "Priority": st.column_config.NumberColumn("Priority", format="%.2f")})

# ----------------------------------------------------------------- roadmap
with tab3:
    if not plan:
        st.success("Nothing to learn for this target. Pick a harder career in the sidebar.")
    else:
        st.subheader(f"Your {total_weeks}-week plan to become a {goal}")
        fig = go.Figure(go.Bar(
            y=[label(p["skill"]) for p in plan],
            x=[p["end_week"] - p["start_week"] + 1 for p in plan],
            base=[p["start_week"] - 1 for p in plan], orientation="h", marker_color=ACCENT,
            text=[f"Wk {p['start_week']}-{p['end_week']}" for p in plan], textposition="inside"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title="Week")
        st.plotly_chart(style(fig, 90 + 42 * len(plan)))
        for i, p in enumerate(plan, 1):
            st.markdown(f'<div class="step"><div class="num">{i}</div><div><b>{label(p["skill"])}</b><br>'
                        f'<small>Weeks {p["start_week"]} to {p["end_week"]} · gain {p["levels_to_gain"]} levels</small>'
                        f'</div></div>', unsafe_allow_html=True)
        st.download_button("⬇️ Download roadmap (CSV)", pd.DataFrame(plan).to_csv(index=False),
                           file_name="roadmap.csv", mime="text/csv")

# ---------------------------------------------------------------- evaluate
with tab4:
    e1, e2 = st.columns(2)
    with e1:
        st.subheader("Assessment improvement")
        pre = st.number_input("Pre-test score (%)", 0, 100, 45)
        post = st.number_input("Post-test score (%)", 0, 100, 72)
        res = E.assessment_improvement(pre, post)
        m1, m2 = st.columns(2)
        m1.metric("Raw gain", f"{res['raw_gain']} pts")
        m2.metric("Normalized gain", res["normalized_gain"])
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=max(res["normalized_gain"], 0) * 100,
            number={"suffix": "%"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": ACCENT2},
                   "steps": [{"range": [0, 30], "color": "rgba(214,48,49,.25)"},
                             {"range": [30, 70], "color": "rgba(253,203,110,.3)"},
                             {"range": [70, 100], "color": "rgba(0,184,148,.25)"}]}))
        st.plotly_chart(style(gauge, 240))
    with e2:
        st.subheader("User satisfaction")
        ratings = {q: st.slider(q, 1, 5, 4, key=f"r_{q}") for q in ["Clarity", "Usefulness", "Topic order"]}
        sat = E.satisfaction({q: [v] for q, v in ratings.items()})
        st.metric("Overall satisfaction", f"{sat['overall']} / 5")
        st.progress(sat["overall"] / 5)
        st.caption("Collect these from real students after they follow the plan.")
