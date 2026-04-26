"""FRG flow-table ingestion scaffold (stdlib-only, diagnostic-only).

This module provides deterministic ingestion and summary helpers for external
RG/FRG flow tables. It does not provide a first-principles derivation of the
sigma sector; it is an operational bridge for reproducible diagnostics.
"""

from __future__ import annotations

from bisect import bisect_right
import csv
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def _finite_float(value: object, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise ValueError(f"{name} must be a finite float")
    return float(out)


def _normalize_header(value: object) -> str:
    return str(value).strip().lower()


def _line_is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    return (not stripped) or stripped.startswith("#")


@dataclass(frozen=True)
class RGFlowRow:
    """One parsed flow-table row."""

    k: float
    g: float
    lambda_value: Optional[float] = None
    G: Optional[float] = None
    Lambda: Optional[float] = None
    notes: Optional[str] = None


class RGFlowTable:
    """Deterministic container with interpolation and heuristic summaries."""

    def __init__(self, rows: Sequence[RGFlowRow]) -> None:
        if not rows:
            raise ValueError("flow table is empty")
        sorted_rows = sorted(rows, key=lambda row: (float(row.k), float(row.g)))
        ks = [float(row.k) for row in sorted_rows]
        for idx in range(1, len(ks)):
            if ks[idx] == ks[idx - 1]:
                raise ValueError(f"duplicate k value in flow table: k={ks[idx]}")
        self._rows: Tuple[RGFlowRow, ...] = tuple(sorted_rows)
        self._ks: Tuple[float, ...] = tuple(ks)
        self._gs: Tuple[float, ...] = tuple(float(row.g) for row in sorted_rows)
        self._lambda_vals: Tuple[Optional[float], ...] = tuple(row.lambda_value for row in sorted_rows)

    @property
    def rows(self) -> Tuple[RGFlowRow, ...]:
        return self._rows

    def g_of_k(self, k: float) -> float:
        """Linear interpolation for g(k), clamped outside the tabulated range."""
        kk = _finite_float(k, name="k")
        if kk <= self._ks[0]:
            return float(self._gs[0])
        if kk >= self._ks[-1]:
            return float(self._gs[-1])

        idx = bisect_right(self._ks, kk)
        hi = int(idx)
        lo = int(idx - 1)
        k_lo = float(self._ks[lo])
        k_hi = float(self._ks[hi])
        g_lo = float(self._gs[lo])
        g_hi = float(self._gs[hi])
        if k_hi <= k_lo:
            return float(g_lo)
        t = (kk - k_lo) / (k_hi - k_lo)
        return float(g_lo + t * (g_hi - g_lo))

    def estimate_k_star_by_g_threshold(self, threshold: float = 1.0) -> Dict[str, object]:
        """Heuristic threshold-crossing estimate for k* from g(k).

        Returns first crossing interval in ascending-k order. This is an
        operational diagnostic heuristic and not a physical definition.
        """

        thr = _finite_float(threshold, name="threshold")
        g_min = min(self._gs)
        g_max = max(self._gs)

        for idx in range(len(self._rows)):
            k_i = float(self._ks[idx])
            g_i = float(self._gs[idx])
            if g_i == thr:
                return {
                    "threshold": float(thr),
                    "k_star": float(k_i),
                    "reason": "exact_match",
                    "g_min": float(g_min),
                    "g_max": float(g_max),
                }
            if idx >= len(self._rows) - 1:
                continue
            k_j = float(self._ks[idx + 1])
            g_j = float(self._gs[idx + 1])
            crosses = (g_i - thr) * (g_j - thr) < 0.0
            if not crosses:
                continue
            if k_j <= k_i:
                continue
            frac = (thr - g_i) / (g_j - g_i)
            k_star = k_i + frac * (k_j - k_i)
            return {
                "threshold": float(thr),
                "k_star": float(k_star),
                "reason": "crossing",
                "g_min": float(g_min),
                "g_max": float(g_max),
            }

        return {
            "threshold": float(thr),
            "k_star": None,
            "reason": "no_crossing",
            "g_min": float(g_min),
            "g_max": float(g_max),
        }

    def summary_dict(self, *, k_star_threshold: float = 1.0) -> Dict[str, object]:
        lambda_values = [float(x) for x in self._lambda_vals if x is not None]
        has_lambda = bool(lambda_values)
        summary: Dict[str, object] = {
            "n_rows": int(len(self._rows)),
            "k_min": float(self._ks[0]),
            "k_max": float(self._ks[-1]),
            "g_min": float(min(self._gs)),
            "g_max": float(max(self._gs)),
            "has_lambda": bool(has_lambda),
            "lambda_min": float(min(lambda_values)) if has_lambda else None,
            "lambda_max": float(max(lambda_values)) if has_lambda else None,
            "k_star": self.estimate_k_star_by_g_threshold(float(k_star_threshold)),
        }
        return summary


def _collect_rows(reader: csv.DictReader) -> List[RGFlowRow]:
    raw_fieldnames = [str(name).strip() for name in (reader.fieldnames or []) if str(name).strip()]

    def _first_matching_lower(name: str) -> Optional[str]:
        target = str(name).strip().lower()
        for field in raw_fieldnames:
            if field.lower() == target:
                return field
        return None

    k_key = _first_matching_lower("k")
    g_key = _first_matching_lower("g")
    if k_key is None or g_key is None:
        raise ValueError("flow CSV must include header columns: k,g")

    lambda_col = "lambda" if "lambda" in raw_fieldnames else None
    notes_col = _first_matching_lower("notes")
    g_newton_col = "G" if "G" in raw_fieldnames else _first_matching_lower("g_newton")
    lambda_cosmo_col = "Lambda" if "Lambda" in raw_fieldnames else _first_matching_lower("lambda_cosmo")

    rows: List[RGFlowRow] = []
    for idx, record in enumerate(reader, start=2):
        if not isinstance(record, Mapping):
            continue
        try:
            k_raw = record.get(k_key)
            g_raw = record.get(g_key)
            k_val = _finite_float(k_raw, name=f"k (row {idx})")
            g_val = _finite_float(g_raw, name=f"g (row {idx})")
            if k_val <= 0.0:
                raise ValueError(f"k (row {idx}) must be > 0")

            lambda_val: Optional[float] = None
            if lambda_col is not None:
                lam_raw = record.get(lambda_col)
                if str(lam_raw).strip():
                    lambda_val = _finite_float(lam_raw, name=f"lambda (row {idx})")

            G_val: Optional[float] = None
            if g_newton_col is not None:
                raw = record.get(g_newton_col)
                if raw is not None and str(raw).strip():
                    G_val = _finite_float(raw, name=f"{g_newton_col} (row {idx})")

            Lambda_val: Optional[float] = None
            if lambda_cosmo_col is not None:
                raw = record.get(lambda_cosmo_col)
                if raw is not None and str(raw).strip():
                    Lambda_val = _finite_float(raw, name=f"{lambda_cosmo_col} (row {idx})")

            notes_val: Optional[str] = None
            if notes_col is not None:
                raw = record.get(notes_col)
                if raw is not None and str(raw).strip():
                    notes_val = str(raw).strip()

            rows.append(
                RGFlowRow(
                    k=float(k_val),
                    g=float(g_val),
                    lambda_value=lambda_val,
                    G=G_val,
                    Lambda=Lambda_val,
                    notes=notes_val,
                )
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
    if not rows:
        raise ValueError("flow CSV has no usable rows")
    return rows


def load_flow_table_csv(path: str) -> RGFlowTable:
    """Load and validate external FRG flow table CSV."""
    src = Path(str(path)).expanduser().resolve()
    try:
        raw_lines = src.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"failed to read flow CSV: {exc}") from exc

    filtered: List[str] = []
    for line in raw_lines:
        if _line_is_comment_or_blank(line):
            continue
        filtered.append(line)
    if not filtered:
        raise ValueError("flow CSV has no data rows")

    reader = csv.DictReader(filtered)
    rows = _collect_rows(reader)
    return RGFlowTable(rows)


__all__ = [
    "RGFlowRow",
    "RGFlowTable",
    "load_flow_table_csv",
]
