# Career Recommendation & Skill-Gap Roadmap

A Python and Streamlit prototype that recommends career paths for AI & Data Science students, identifies their skill gaps, and builds a week-by-week learning roadmap. It also includes metrics to evaluate whether the recommendations actually help.

## Features

- **Career recommendation:** ranks careers (Data Scientist, Data Analyst, ML Engineer) by how well the student's skills match.
- **Skill-gap analysis:** finds missing skills and ranks them by importance.
- **Roadmap generation:** orders skills by prerequisites (for example, statistics before ML) and assigns weeks.
- **Evaluation metrics:** relevance, skill-gap coverage, assessment improvement, and user satisfaction.
- **Editable data:** careers and prerequisites live in CSV files, so no code changes are needed to add roles.

## Project structure

```
career_project/
├── data/
│   ├── careers.csv     # career, skill, required level (0-5), importance weight
│   └── prereqs.csv     # skill, prerequisite skill
├── engine.py           # recommendation, gaps, roadmap, metrics
├── app.py              # Streamlit interface
└── requirements.txt
```

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

## How it works

| Step | Method |
|------|--------|
| Career fit | Weighted share of required skill levels the student already meets |
| Skill gap | `required level - current level`, priority = `gap x weight` |
| Roadmap | Prerequisite-aware ordering, then weeks assigned per level gained |

## Evaluation metrics

| Metric | Measure |
|--------|---------|
| Recommendation relevance | Hit@k: is the student's validated career in the top k? |
| Skill-gap coverage | Precision, recall and F1 against expert-labelled gaps |
| Assessment improvement | Raw gain and normalized gain `(post - pre) / (100 - pre)` |
| User satisfaction | Average 1-5 ratings for clarity, usefulness and topic order |

## Customize

Add a career by appending rows to `data/careers.csv`:

```
career,skill,level,weight
Data Engineer,sql,5,1.0
```

## Future work

- Build the career dataset from real job postings
- Save student results to SQLite for real evaluation data
- Recommend learning resources per skill

## Tech stack

Python, pandas, Streamlit
