"""
src/models.py
Train baseline (Logistic Regression) and advanced (XGBoost) models with calibration.
"""
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
from xgboost import XGBClassifier

NUM_COLS = ["home_last10_winrate","away_last10_winrate","home_run_diff_30","away_run_diff_30"]
CAT_COLS = ["home_team","away_team","park_id","month"]
TARGET = "target"

def fit_baseline(train_df: pd.DataFrame):
    pre = ColumnTransformer([
        ("num", StandardScaler(), NUM_COLS),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS),
    ])
    lr = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
    pipe = Pipeline([("pre", pre), ("lr", lr)])
    model = CalibratedClassifierCV(pipe, cv=5, method="isotonic")
    X, y = train_df[NUM_COLS + CAT_COLS], train_df[TARGET]
    model.fit(X, y)
    return model

def fit_xgb(train_df: pd.DataFrame):
    pre = ColumnTransformer([
        ("num", "passthrough", NUM_COLS),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS),
    ])
    xgb = XGBClassifier(
        n_estimators=600, learning_rate=0.05, max_depth=5,
        subsample=0.9, colsample_bytree=0.9,
        objective="binary:logistic", eval_metric="logloss", tree_method="hist",
        random_state=42
    )
    pipe = Pipeline([("pre", pre), ("xgb", xgb)])
    model = CalibratedClassifierCV(pipe, cv=5, method="isotonic")
    X, y = train_df[NUM_COLS + CAT_COLS], train_df[TARGET]
    model.fit(X, y)
    return model

def evaluate(model, test_df: pd.DataFrame):
    X, y = test_df[NUM_COLS + CAT_COLS], test_df[TARGET]
    probs = model.predict_proba(X)[:,1]
    preds = (probs >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y, preds)),
        "log_loss": float(log_loss(y, probs)),
        "brier": float(brier_score_loss(y, probs))
    }

def save_model(model, path: str):
    joblib.dump(model, path)

def load_model(path: str):
    return joblib.load(path)
