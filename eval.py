"""
src/eval.py
Metrics & plotting helpers.
"""
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve

def plot_calibration(y_true, y_prob, title="Calibration"):
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10)
    plt.figure()
    plt.plot(mean_pred, frac_pos, "s-", label="Model")
    plt.plot([0,1],[0,1],"k--", label="Perfect")
    plt.xlabel("Mean Predicted Value")
    plt.ylabel("Fraction of Positives")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.show()
