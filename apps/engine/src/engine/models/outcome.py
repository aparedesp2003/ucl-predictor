"""Maps a pre-match Elo difference to P(home), P(draw), P(away)."""

from collections.abc import Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression

from engine.models.elo import AWAY, DRAW, HOME

CLASSES = (HOME, DRAW, AWAY)


def _features(diffs: Sequence[float] | np.ndarray) -> np.ndarray:
    return np.asarray(diffs, dtype=float).reshape(-1, 1) / 400.0


class OutcomeModel:
    """Multinomial logistic regression on the single feature ``diff / 400``."""

    def __init__(self) -> None:
        self._clf = LogisticRegression(C=1.0, max_iter=1000)

    def fit(self, diffs: Sequence[float], outcomes: Sequence[int]) -> "OutcomeModel":
        y = np.asarray(outcomes, dtype=int)
        missing = set(CLASSES) - set(y.tolist())
        if missing:
            raise ValueError(f"training outcomes lack classes {sorted(missing)}")
        self._clf.fit(_features(diffs), y)
        return self

    def predict_proba(self, diffs: Sequence[float] | np.ndarray) -> np.ndarray:
        """(n, 3) array of probabilities in HOME, DRAW, AWAY order; rows sum to 1."""
        proba = self._clf.predict_proba(_features(diffs))
        order = [list(self._clf.classes_).index(c) for c in CLASSES]
        return proba[:, order]
