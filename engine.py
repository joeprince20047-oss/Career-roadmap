"""Core logic: CSV loading, recommendation, skill gaps, roadmap, metrics."""
import csv
from pathlib import Path

DATA = Path(__file__).parent / "data"
WEEKS_PER_LEVEL = {"default": 1, "projects": 2, "statistics": 1.5, "deep_learning": 2}


# ---------------------------------------------------------------- LOADING
def _read(path, needed):
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            if all(row.get(k) for k in needed):
                yield row


def load_careers(path=DATA / "careers.csv"):
    careers = {}
    for r in _read(path, ["career", "skill", "level", "weight"]):
        careers.setdefault(r["career"], {})[r["skill"]] = (int(r["level"]), float(r["weight"]))
    return careers


def load_prereqs(path=DATA / "prereqs.csv"):
    prereqs = {}
    for r in _read(path, ["skill", "prereq"]):
        prereqs.setdefault(r["skill"], []).append(r["prereq"])
    return prereqs


def all_skills(careers):
    return sorted({s for reqs in careers.values() for s in reqs})


# --------------------------------------------------------- RECOMMENDATION
def fit_score(profile, career, careers):
    reqs = careers[career]
    got = sum(min(profile.get(s, 0), lvl) * w for s, (lvl, w) in reqs.items())
    need = sum(lvl * w for lvl, w in reqs.values())
    return round(100 * got / need, 1)


def recommend(profile, careers):
    scores = {c: fit_score(profile, c, careers) for c in careers}
    return sorted(scores.items(), key=lambda x: -x[1])


# ------------------------------------------------------------- SKILL GAPS
def find_gaps(profile, career, careers):
    gaps = []
    for skill, (lvl, w) in careers[career].items():
        gap = lvl - profile.get(skill, 0)
        if gap > 0:
            gaps.append({"skill": skill, "gap": gap, "weight": w, "priority": round(gap * w, 2)})
    return sorted(gaps, key=lambda g: -g["priority"])


# ---------------------------------------------------------------- ROADMAP
def build_roadmap(gaps, profile, prereqs):
    remaining = {g["skill"]: g for g in gaps}
    done, order = set(profile) - set(remaining), []
    while remaining:
        ready = [g for s, g in remaining.items()
                 if all(p in done or p not in remaining for p in prereqs.get(s, []))]
        nxt = max(ready or remaining.values(), key=lambda g: g["priority"])
        order.append(nxt)
        done.add(nxt["skill"])
        del remaining[nxt["skill"]]

    week, plan = 1, []
    for g in order:
        dur = max(1, round(g["gap"] * WEEKS_PER_LEVEL.get(g["skill"], WEEKS_PER_LEVEL["default"])))
        plan.append({"skill": g["skill"], "start_week": week, "end_week": week + dur - 1,
                     "levels_to_gain": g["gap"]})
        week += dur
    return plan


# ---------------------------------------------------------------- METRICS
def relevance_hit_at_k(recommended, chosen_goal, k=2):
    return int(chosen_goal in [c for c, _ in recommended[:k]])


def skill_gap_coverage(predicted_gaps, expert_gaps):
    p, e = {g["skill"] for g in predicted_gaps}, set(expert_gaps)
    tp = len(p & e)
    prec = tp / len(p) if p else 0
    rec = tp / len(e) if e else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return {"precision": round(prec, 2), "recall": round(rec, 2), "f1": round(f1, 2)}


def assessment_improvement(pre, post):
    return {"raw_gain": post - pre,
            "normalized_gain": round((post - pre) / (100 - pre), 2) if pre < 100 else 0.0}


def satisfaction(ratings):
    avg = {q: round(sum(r) / len(r), 2) for q, r in ratings.items()}
    avg["overall"] = round(sum(avg.values()) / len(avg), 2)
    return avg
