# EZSportsPicks


Web-based application that predicts MLB/NBA game outcomes using machine learning and publishes daily predictions

## Features
- Daily game predictions with win probabilities
- Historical comparisons & basic visualizations
- Reproducible ML pipeline (baseline Logistic Regression + advanced XGBoost)

## Tech Stack
- **Python**: pandas, numpy, scikit-learn, xgboost, matplotlib, seaborn
- **Web**: Flask or Django (choose one), HTML/CSS (Tailwind optional)
- **DB**: PostgreSQL or MySQL (for users + predictions)
- **Dev**: Jupyter/VS Code, GitHub

## Project Structure
```
mlb-predictor/
├── app.py                      # Flask web app (routes + HTML templates)
├── requirements.txt            # Python deps
├── README.md                   # project overview / setup
├── schedule_cli.py             # CLI to fetch MLB schedules (statsapi)
├── services/
│   ├── mlb_service.py          # MLB schedule + game page data (statsapi)
│   └── nba_service.py          # NBA schedule + game page data (BallDontLie API)
├── src/
│   ├── data.py                 # load/validate historical ML dataset
│   ├── features.py             # build ML features + target label
│   ├── models.py               # train LR + XGBoost + calibration + save/load
│   └── eval.py                 # evaluation plots (calibration curve, etc.)
├── static/
│   └── images/                 # backgrounds used by the UI (main.jpeg, wallpaper.jpeg, basketball.jpeg, etc.)
├── data/
├── artifacts/                  # saved models (.joblib) 
├── notebooks/                  # experiments
├── reports/                    # report docs / figures
└── docs/

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
