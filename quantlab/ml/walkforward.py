"""Walk-forward training with purging.

For each test year Y the model is trained only on episodes whose outcome was
already known before Y started (``exit_date < Y-01-01``). Episodes still open
at the cutoff are purged — their labels would leak the future.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd


def walk_forward_predict(
    episodes: pd.DataFrame,
    features: list[str],
    make_model: Callable[[], Any],
    first_test_year: int,
    min_train: int = 200,
) -> pd.DataFrame:
    """Return test-set predictions: one row per episode from ``first_test_year`` on.

    Adds ``prob`` (predicted P(profitable)) and ``train_base_rate`` (share of
    profitable episodes in that fold's training set).
    """
    out = []
    years = sorted(episodes["entry_date"].dt.year.unique())
    for year in [y for y in years if y >= first_test_year]:
        cutoff = pd.Timestamp(f"{year}-01-01")
        train = episodes[episodes["exit_date"] < cutoff]
        test = episodes[episodes["entry_date"].dt.year == year]
        if len(train) < min_train or test.empty or train["label"].nunique() < 2:
            continue
        model = make_model()
        model.fit(train[features], train["label"])
        fold = test.copy()
        fold["prob"] = model.predict_proba(test[features])[:, 1]
        fold["train_base_rate"] = train["label"].mean()
        fold["fold"] = year
        out.append(fold)
    return pd.concat(out) if out else pd.DataFrame()
