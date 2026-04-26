"""Minimal late-time likelihood helpers (v11.0.0)."""

from __future__ import annotations

from typing import Dict, Iterable, Protocol

from .datasets.base import Chi2Result, HzModel


class Dataset(Protocol):
    name: str

    def chi2(self, model: HzModel) -> Chi2Result:  # pragma: no cover - Protocol signature only
        ...


def chi2_total(*, model: HzModel, datasets: Iterable[Dataset]) -> Chi2Result:
    chi2 = 0.0
    ndof = 0
    params: Dict[str, float] = {}

    for ds in datasets:
        r = ds.chi2(model)
        chi2 += float(r.chi2)
        ndof += int(r.ndof)
        for k, v in r.params.items():
            params[f"{ds.name}.{k}"] = float(v)

    return Chi2Result(chi2=float(chi2), ndof=int(ndof), params=params)
