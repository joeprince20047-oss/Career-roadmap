"""Streamlit UI.  Run:  streamlit run app.py"""
import pandas as pd
import streamlit as st
import engine as E

st.set_page_config(page_title="Career Roadmap", layout="centered")
st.title("Career Recommendation & Skill-Gap Roadmap")

careers, prereqs = E.load_careers(), E.load_prereqs()
skills = E.all_skills(careers)

# ---- 1. Profile input -------------------------------------------------
st.header("1. Your skills")
st.caption("Rate yourself: 0 = none, 5 = expert")
profile = {}
cols = st.columns(2)
for i, s in enumerate(skills):
    profile[s] = cols[i % 2].slider(s.replace("_", " ").title(), 0, 5, 0, key=s)

# ---- 2. Recommendations -----------------------------------------------
st.header("2. Career fit")
ranked = E.recommend(profile, careers)
st.bar_chart(pd.DataFrame(ranked, columns=["Career", "Fit %"]).set_index("Career"))

goal = st.selectbox("Choose your target career", [c for c, _ in ranked])

# ---- 3. Gaps + roadmap ------------------------------------------------
gaps = E.find_gaps(profile, goal, careers)
st.header("3. Skill gaps")
if gaps:
    st.dataframe(pd.DataFrame(gaps)[["skill", "gap", "priority"]], hide_index=True)
    plan = E.build_roadmap(gaps, profile, prereqs)
    st.header("4. Roadmap")
    st.dataframe(pd.DataFrame(plan), hide_index=True)
    st.metric("Total duration (weeks)", plan[-1]["end_week"])
else:
    st.success("You already meet every requirement for this role.")

# ---- 4. Evaluation (stored in session) --------------------------------
st.header("5. Evaluate the plan")
c1, c2 = st.columns(2)
pre = c1.number_input("Pre-test score (%)", 0, 100, 45)
post = c2.number_input("Post-test score (%)", 0, 100, 72)
st.write("Assessment improvement:", E.assessment_improvement(pre, post))

ratings = {q: st.slider(q, 1, 5, 4) for q in ["Clarity", "Usefulness", "Topic order"]}
st.write("Satisfaction:", E.satisfaction({q: [v] for q, v in ratings.items()}))
