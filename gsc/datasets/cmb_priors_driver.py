"""Dataset adapter that wires CMB priors through the Phase 2 driver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..early_time.cmb_priors_driver import (
    CMBKeyAlias,
    CMBPriorsDriverConfig,
    CMBPriorsEvaluation,
    evaluate_cmb_priors_dataset,
)
from .base import Chi2Result, HzModel
from .cmb_priors import CMBPriorsDataset


@dataclass
class CMBPriorsLikelihood:
    """Likelihood-style adapter for compressed CMB priors."""

    priors: CMBPriorsDataset
    driver_config: CMBPriorsDriverConfig
    name: str = "cmb"
    key_aliases: Mapping[str, CMBKeyAlias] | None = None

    def evaluate(self, model: HzModel) -> CMBPriorsEvaluation:
        return evaluate_cmb_priors_dataset(
            dataset=self.priors,
            model=model,
            config=self.driver_config,
            key_aliases=self.key_aliases,
        )

    def chi2_from_evaluation(self, evaluation: CMBPriorsEvaluation) -> Chi2Result:
        base = evaluation.result
        meta = dict(base.meta)
        meta.setdefault("keys", list(self.priors.keys))
        meta["mode"] = str(self.driver_config.mode)
        meta["bridge_z"] = (
            None if self.driver_config.z_bridge is None else float(self.driver_config.z_bridge)
        )
        return Chi2Result(
            chi2=float(base.chi2),
            ndof=int(base.ndof),
            params=dict(base.params),
            meta=meta,
        )

    def chi2(self, model: HzModel) -> Chi2Result:
        return self.chi2_from_evaluation(self.evaluate(model))


__all__ = ["CMBPriorsLikelihood"]
