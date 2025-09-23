# MLB Outcome Prediction System

Web-based application that predicts MLB game outcomes using machine learning and publishes daily predictions to a secure website for logged-in users.

## Features
- User auth (view predictions after login)
- Daily game predictions with win probabilities
- Historical comparisons & basic visualizations
- Export predictions to CSV/PDF
- Reproducible ML pipeline (baseline Logistic Regression + advanced XGBoost)

## Tech Stack
- **Python**: pandas, numpy, scikit-learn, xgboost, matplotlib, seaborn
- **Web**: Flask or Django (choose one), HTML/CSS (Tailwind optional)
- **DB**: PostgreSQL or MySQL (for users + predictions)
- **Dev**: Jupyter/VS Code, GitHub

## Project Structure
```
mlb-predictor/
├── src/
│   ├── data.py            # load/validate data
│   ├── features.py        # rolling stats, matchup features
│   ├── models.py          # fit_baseline (LR), fit_xgb (XGB), calibration
│   └── eval.py            # metrics & plots
├── data/                  # raw & processed data (gitignored)
├── artifacts/             # saved models (gitignored)
├── notebooks/             # experiments
├── reports/               # SRS/SDD, figures
├── docs/uml/              # UML diagrams (png)
├── .github/workflows/     # CI
├── .gitignore
├── LICENSE
└── README.md
```

## Local Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Quickstart
```bash
python -m src.data          # validate/load data
python -m src.features      # build features
python -m src.models        # train models
python -m src.eval          # evaluate & plot
```

## Deploying the Web App
- Create a Flask/Django app with login (Flask-Login or Django auth).
- Route `/predictions` reads from DB and renders today's matchups with probabilities.
- Schedule a daily job to run the pipeline and insert new predictions.

## License
MIT
