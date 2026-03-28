"""Basic walk-forward and purged splits."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class WFConfig:
    train_days: int = 252
    test_days: int = 20
    step_days: int = 20
    purge_days: int = 5


def make_walk_forward_splits(dates: list[pd.Timestamp], cfg: WFConfig) -> list[tuple[list[pd.Timestamp], list[pd.Timestamp]]]:
    uniq = sorted(set(dates))
    splits = []
    start = 0
    while start + cfg.train_days + cfg.purge_days + cfg.test_days <= len(uniq):
        train = uniq[start : start + cfg.train_days]
        test_start = start + cfg.train_days + cfg.purge_days
        test = uniq[test_start : test_start + cfg.test_days]
        splits.append((train, test))
        start += cfg.step_days
    return splits
