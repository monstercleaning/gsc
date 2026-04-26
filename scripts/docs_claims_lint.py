#!/usr/bin/env python3
"""Lint reviewer-facing docs for claim guardrails and banned legacy phrases."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


V101_DIR = Path(__file__).resolve().parents[1]

DEFAULT_REL_FILES: Tuple[str, ...] = (
    "GSC_Framework_v10_1_FINAL.md",
    "GSC_Framework_v10_1_FINAL.tex",
    "docs/project_status_and_roadmap.md",
    "docs/external_reviewer_feedback.md",
    "docs/measurement_model.md",
    "docs/reviewer_faq.md",
    "docs/early_time_e2_status.md",
    "docs/perturbations_and_dm_scope.md",
    "docs/sigma_field_origin_status.md",
    "docs/phase3_sigma_tensor_model_v1.md",
    "docs/REVIEW_START_HERE.md",
    "docs/VERIFICATION_MATRIX.md",
    "docs/FRAMES_UNITS_INVARIANTS.md",
    "docs/DATA_LICENSES_AND_SOURCES.md",
    "docs/DATASET_ONBOARDING_POLICY.md",
    "docs/AI_USAGE_AND_VALIDATION_POLICY.md",
    "docs/DM_DECISION_MEMO.md",
    "docs/EPSILON_FRAMEWORK_READINESS.md",
    "docs/LEGACY_VERSIONED_ARTIFACTS.md",
    "docs/PRIOR_ART_AND_NOVELTY_MAP.md",
    "docs/PRIOR_ART_MAP.md",
    "docs/GSC_Consolidated_Roadmap_v2.8.md",
    "docs/GSC_Consolidated_Roadmap_v2.8.1_patch.md",
    "docs/PAPER2_SUBMISSION.md",
    "docs/PAPER2_SUBMISSION_GUIDE.md",
    "docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md",
    "docs/ARXIV_METADATA.md",
    "docs/ARXIV_UPLOAD_CHECKLIST.md",
    "docs/ARXIV_SUBMISSION_CHECKLIST.md",
    "docs/JOSS_AUTHORS.md",
    "docs/JOSS_SUBMISSION_GUIDE.md",
    "docs/JOSS_SUBMISSION.md",
    "docs/JOSS_SUBMISSION_CHECKLIST.md",
    "docs/AFFILIATION_AND_BRANDING.md",
    "outreach/labs_site_copy/labs_transparency.md",
    "bridges/phase4_qcd_gravity_bridge_v0.1/report/QCD_Gravity_Bridge_v0.1.md",
    "docs/rg_scale_identification.md",
    "docs/rg_asymptotic_safety_bridge.md",
    "docs/structure_formation_status.md",
    "docs/provenance_and_schemas.md",
)


@dataclass(frozen=True)
class Rule:
    key: str
    pattern: str
    message: str


@dataclass(frozen=True)
class Finding:
    file: str
    key: str
    message: str


BANNED_RULES: Tuple[Rule, ...] = (
    Rule(
        key="ban_torsion_behaves_like_axion",
        pattern=r"\btorsion\s+behaves\s+like\s+axion\b",
        message="Banned claim: 'torsion behaves like axion'.",
    ),
    Rule(
        key="ban_torsion_equals_axion",
        pattern=r"\btorsion\s*=\s*axion\b",
        message="Banned claim: 'torsion = axion'.",
    ),
    Rule(
        key="ban_mvac_equals_axion",
        pattern=r"\bm[_\s-]*vac\s*=\s*(?:m[_\s-]*)?axion\b",
        message="Banned claim: 'm_vac = axion'.",
    ),
    Rule(
        key="ban_wrong_mond_dimension_formula",
        pattern=r"\ba_?0\s*~\s*(?:ħ|hbar)\s*/\s*\(\s*m[_\s-]*vac",
        message="Banned wrong-dimension MOND formula (a0 ~ hbar/(m_vac ...)).",
    ),
    Rule(
        key="ban_wrong_birefringence_scale_claim",
        pattern=r"for\s+(?:Ω₀|omega0|omega_0)\s*~\s*(?:H₀|h0)\s*,?\s*(?:β|beta)\s*~\s*0\.1\s*-\s*1",
        message="Banned birefringence magnitude claim (Omega0~H0 -> beta~0.1-1 deg).",
    ),
    Rule(
        key="ban_birefringence_omega_h0_degree_claim",
        pattern=r"(?:Ω₀|omega0|omega_0).*(?:H₀|h0).*(?:0\.1\s*[-–]\s*1)\s*(?:deg|°)",
        message="Banned birefringence claim linking Omega0~H0 to 0.1-1 degree rotation.",
    ),
    Rule(
        key="ban_drift_as_frame_discriminator",
        pattern=r"redshift drift\s+(?:distinguishes|discriminates)\s+(?:freeze[\s-]*frame|frames?)\s*(?:vs\.?|versus)?\s*(?:expansion|flrw)",
        message="Banned claim: redshift drift as frame-label discriminator.",
    ),
    Rule(
        key="ban_drift_resolves_conformal_frame_degeneracy",
        pattern=r"redshift drift\s+resolves\s+conformal\s+(?:frame\s+)?degenerac",
        message="Banned claim: redshift drift resolves conformal-frame degeneracy by itself.",
    ),
    Rule(
        key="ban_mvac_derives_from_torsion",
        pattern=r"m[_\s-]*vac\s+derives\s+from\s+torsion",
        message="Banned claim: m_vac derived from torsion.",
    ),
)

DEFERRED_IDEAS_BLACKLIST_RULES: Tuple[Rule, ...] = (
    Rule(
        key="deferred_mvac_equals_axion_mass",
        pattern=r"\bm[_\s-]*vac\s*(?:=|equals?)\s*(?:m[_\s-]*)?axion(?:\s+mass)?\b",
        message=(
            "Deferred-ideas blacklist: banned claim that m_vac equals axion mass "
            "(see DEFERRED_IDEAS_v10 critical errors)."
        ),
    ),
    Rule(
        key="deferred_wrong_mond_a0_hbar_over_mvac_lambda2",
        pattern=r"\ba_?0\s*~\s*(?:ħ|hbar)\s*/\s*\(\s*m[_\s-]*vac\s*(?:\*|\s*)\s*(?:λ|lambda)\s*\^?2\s*\)",
        message=(
            "Deferred-ideas blacklist: banned wrong-dimension MOND claim "
            "(a0 ~ hbar/(m_vac lambda^2))."
        ),
    ),
    Rule(
        key="deferred_wrong_omega0_h0_beta_point1",
        pattern=r"(?:Ω₀|omega\s*_?\s*0)\s*~\s*(?:H₀|h\s*_?\s*0)[^\n]{0,120}(?:β|beta)\s*~\s*0\.1\b",
        message=(
            "Deferred-ideas blacklist: banned birefringence magnitude claim "
            "(Omega0~H0 implies beta~0.1...)."
        ),
    ),
)

ALL_BANNED_RULES: Tuple[Rule, ...] = BANNED_RULES + DEFERRED_IDEAS_BLACKLIST_RULES

RG_SCALE_TRIGGER = re.compile(
    r"\b(?:asymptotic\s+safety|functional\s+renormali[sz]ation\s+group|frg|reuter|saueressig)\b|k\s*(?:\(\s*(?:\\sigma|sigma)\s*\)|(?:↔|<->|~|=)\s*1\s*/\s*(?:\\sigma|sigma))",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
RG_SCALE_QUALIFIERS = re.compile(
    r"\b(?:ansatz|working\s+identification|working\s+hypothesis|not\s+derived|open\s+problem|phenomenological|not\s+a\s+frg\s+derivation|deferred\s+derivation)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

AS_FRG_TRIGGER = re.compile(
    r"\b(?:asymptotic\s+safety|functional\s+rg|functional\s+renormali[sz]ation\s+group|frg|reuter|saueressig)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
AS_FRG_DISCLAIMER = re.compile(
    r"\b(?:conceptual|phenomenolog\w*|do\s+not\s+attempt|not\s+attempt|no\s+derivation|ansatz|not\s+derived|motivated|motivation|consistent\s+with|open\s+problem|deferred|out\s+of\s+scope|roadmap)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
AS_LANDAU_WINDOW = re.compile(
    r"\b(?:landau|pole(?:-like)?)\b|1\s*-\s*\(\s*k\s*/\s*k\*\s*\)\s*\^?\s*2|\(\s*k\s*/\s*k\*\s*\)\s*\^?\s*2",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
AS_STRONG_CLAIM_VERB = re.compile(
    r"\b(?:predict(?:s|ed|ion)?|deriv(?:e|es|ed|ation)|implies?|therefore|follows?\s+from)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
AS_NEGATION_NEAR_VERB = re.compile(
    r"\b(?:do|does|did)\s+not\b|\bnot\b|\bno\b|\bwithout\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
K_SIGMA_MAPPING_TRIGGER = re.compile(
    r"k\s*(?:↔|<->|~|=)\s*1\s*/\s*(?:\\sigma|sigma)|k\s*=\s*k\(\s*(?:\\sigma|sigma)\s*\)|k\(\s*(?:\\sigma|sigma)\s*\)|(?:identified|identification|mapping)[^\n]{0,80}(?:k|\\sigma|sigma)",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
K_SIGMA_MAPPING_DISCLAIMER = re.compile(
    r"\b(?:ansatz|working\s+identification|working\s+hypothesis|non-?trivial|not\s+derived|open\s+problem|phenomenological|assumption)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
CMB_OVERCLAIM_PATTERN = re.compile(
    r"\b(?:fits?\s+cmb|matches?\s+cmb|consistent\s+with\s+cmb|consistent\s+with\s+planck|planck[-\s]*consistent|solves?\s+cmb|explains?\s+acoustic\s+peaks?|reproduces?\s+peaks?|cmb\s+already\s+confirms?)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
CMB_DISCLAIMER_PATTERN = re.compile(
    r"\b(?:compressed\s+priors?|compressed[-\s]*prior(?:s)?|not\s+full\s+power\s+spectrum|not\s+peak[-\s]*level|diagnostic\s+only|deferred|future\s+work|late[-\s]*time\s+only|not\s+replace(?:s|d)?|does\s+not\s+claim)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
CMB_WORD_PATTERN = re.compile(r"\bcmb\b", flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
CMB_CONTEXT_KEYWORDS = re.compile(
    r"\b(?:fit(?:s|ted|ting)?|consistent|agreement)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
CMB_FULL_SPECTRA_TRIGGER_PATTERN = re.compile(
    r"\b(?:TT\s*[/,]\s*TE\s*[/,]\s*EE|anisotrop(?:y|ies)\s+(?:spectra?|spectrum)|acoustic\s+peaks?|power\s+spectrum\s*(?:c_?\\ell|c_ell|cℓ)?|boltzmann(?:\s+(?:solver|hierarchy))?|CLASS|CAMB)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
CMB_FULL_SPECTRA_CONTEXT_PATTERN = re.compile(
    r"\b(?:cmb|TT\s*[/,]\s*TE\s*[/,]\s*EE|anisotrop(?:y|ies)|acoustic\s+peaks?|power\s+spectrum\s*(?:c_?\\ell|c_ell|cℓ)?)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
CMB_BOLTZMANN_CLASS_PATTERN = re.compile(
    r"\b(?:boltzmann(?:\s+(?:solver|hierarchy))?|CLASS|CAMB)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
CMB_FULL_SPECTRA_DISCLAIMER_PATTERN = re.compile(
    r"\b(?:distance\s+priors?|compressed\s+priors?|compressed[-\s]*prior(?:s)?|not\s+(?:a\s+)?full\s+(?:spectra?|power\s+spectrum|peak(?:-|\s*)level)|diagnostic(?:\s+only)?|deferred|future\s+work|out\s+of\s+scope|approximation(?:-first)?|not\s+boltzmann|late[-\s]*time\s+only|not\s+replace(?:s|d)?|does\s+not\s+claim)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
DM_OVERCLAIM_PATTERN = re.compile(
    r"\b(?:no\s+dark\s+matter\s+needed|without\s+dark\s+matter|eliminates?\s+dark\s+matter|dark\s+matter\s+not\s+needed)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
DM_SOLVED_OVERCLAIM_PATTERN = re.compile(
    r"\b(?:solve(?:s|d|ing)?\s+dark\s+matter|dark\s+matter\s+solved|explains?\s+dark\s+matter\s+without)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
STRUCTURE_OVERCLAIM_PATTERN = re.compile(
    r"\b(?:solves?\s+structure\s+formation|explains?\s+galaxy\s+formation|matches?\s+lss|reproduces?\s+lss)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
KILL_LCDM_RHETORIC_PATTERN = re.compile(
    r"\b(?:kill(?:s|ed|ing)?\s+(?:ΛCDM|LCDM|LambdaCDM)|beat\s+einstein|defeat\s+einstein)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
JOURNAL_NAME_DROP_PATTERN = re.compile(
    r"\b(?:nature|science)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
JOURNAL_NAME_DROP_CONTEXT_PATTERN = re.compile(
    r"\b(?:accept(?:ed|ance)?|submission|submitted|publish(?:ed|ing)?|review(?:ed|er)?|target(?:ing)?|prestige)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
DEFERRED_CLAIM_MARKER_PATTERN = re.compile(
    r"\b(?:DEFERRED_DM_CLAIM|DEFERRED_STRUCTURE_CLAIM|DEFERRED_CLAIM)\b",
    flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

QUARANTINE_DOC_PATTERNS: Tuple[str, ...] = (
    "DEFERRED_IDEAS_v10.md",
    "deferred_ideas",
)

K_SIGMA_ANSATZ_EXEMPT_REL_FILES: Tuple[str, ...] = (
    "docs/GSC_Consolidated_Roadmap_v2.8.md",
)

VERBATIM_ROADMAP_CONTEXT_EXEMPT_REL_FILES: Tuple[str, ...] = (
    "docs/GSC_Consolidated_Roadmap_v2.8.md",
)


REQUIRED_RULES: Dict[str, Tuple[Rule, ...]] = {
    "docs/measurement_model.md": (
        Rule(
            key="require_history_not_frame_measurement_model",
            pattern=r"Frame equivalence vs history discriminant",
            message="measurement_model must include explicit frame-vs-history section title.",
        ),
        Rule(
            key="require_kinematic_sandage_loeb_measurement_model",
            pattern=r"Sandage[-–]Loeb.*kinematic",
            message="measurement_model must state Sandage-Loeb is kinematic.",
        ),
    ),
    "docs/reviewer_faq.md": (
        Rule(
            key="require_faq_drift_frame_question",
            pattern=r"Does redshift drift discriminate frames\?",
            message="reviewer_faq must include the drift-vs-frame reviewer question.",
        ),
        Rule(
            key="require_faq_falsifiable_question",
            pattern=r"What exactly is falsifiable\?",
            message="reviewer_faq must include explicit falsifiability question.",
        ),
    ),
    "GSC_Framework_v10_1_FINAL.md": (
        Rule(
            key="require_field_redefinition_disclaimer_md",
            pattern=r"field redefinition:\s*it does not,\s*by itself,\s*constitute new physics",
            message="framework MD must explicitly state frame-map is not new physics.",
        ),
        Rule(
            key="require_history_discriminant_md",
            pattern=r"This relation is kinematic\..*discriminates competing histories",
            message="framework MD must state drift discriminates histories, not frames.",
        ),
    ),
    "GSC_Framework_v10_1_FINAL.tex": (
        Rule(
            key="require_field_redefinition_disclaimer_tex",
            pattern=r"field redefinition:\s*it does not,\s*by itself,\s*constitute new physics",
            message="framework TeX must explicitly state frame-map is not new physics.",
        ),
        Rule(
            key="require_history_discriminant_tex",
            pattern=r"This relation is kinematic\..*discriminates competing histories",
            message="framework TeX must state drift discriminates histories, not frames.",
        ),
    ),
    "docs/rg_scale_identification.md": (
        Rule(
            key="require_rg_scale_ansatz_wording",
            pattern=r"\bansatz\b|\bworking\s+identification\b",
            message="rg_scale_identification doc must label k(sigma) mapping as ansatz/working identification.",
        ),
        Rule(
            key="require_rg_scale_open_problem_wording",
            pattern=r"\bopen\s+problem\b|\bnot\s+derived\b",
            message="rg_scale_identification doc must state derivation is open/not yet derived.",
        ),
    ),
}


def _relative_key(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return path.name


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _line_bounds(text: str, index: int) -> Tuple[int, int]:
    start = text.rfind("\n", 0, index)
    if start == -1:
        start = 0
    else:
        start += 1
    end = text.find("\n", index)
    if end == -1:
        end = len(text)
    return start, end


def _is_reference_like_context(text: str, index: int) -> bool:
    lower = text.lower()
    for marker in (
        "## references",
        "\\hypertarget{references",
        "\\section{references",
        "references-starter-list",
    ):
        if lower.rfind(marker, 0, index) != -1:
            return True
    line_start, line_end = _line_bounds(text, index)
    line = text[line_start:line_end].strip().lower()
    if re.match(r"^\d+\.\s", line):
        return True
    if line.startswith("\\item") and ("arxiv" in line or "doi" in line):
        return True
    if "arxiv" in line and ("asymptotic safety" in line or "reuter" in line or "saueressig" in line):
        return True
    return False


def _iter_paragraphs(text: str) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    start = 0
    for m in re.finditer(r"\n\s*\n+", text, flags=re.MULTILINE):
        end = m.start()
        paragraph = text[start:end]
        if paragraph.strip():
            out.append((start, paragraph))
        start = m.end()
    tail = text[start:]
    if tail.strip():
        out.append((start, tail))
    return out


def _has_unnegated_strong_claim_near_landau(context: str, *, max_distance: int = 120) -> bool:
    landau_positions = [m.start() for m in AS_LANDAU_WINDOW.finditer(context)]
    if not landau_positions:
        return False
    for m in AS_STRONG_CLAIM_VERB.finditer(context):
        left = context[max(0, m.start() - 48) : m.start()]
        if AS_NEGATION_NEAR_VERB.search(left):
            continue
        if any(abs(m.start() - lp) <= max_distance for lp in landau_positions):
            return True
    return False


def _is_quarantine_doc(rel_path: str) -> bool:
    rel_low = rel_path.lower()
    for token in QUARANTINE_DOC_PATTERNS:
        if token.lower() in rel_low:
            return True
    return False


def lint_files(*, repo_root: Path, files: Sequence[Path], enforce_required: bool = True) -> List[Finding]:
    repo_root = repo_root.expanduser().resolve()
    findings: List[Finding] = []
    for raw in files:
        path = raw.expanduser().resolve()
        rel = _relative_key(path, repo_root)
        if _is_quarantine_doc(rel):
            continue
        if not path.is_file():
            findings.append(Finding(file=rel, key="missing_file", message=f"File not found: {path}"))
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        is_verbatim_roadmap_context_exempt = rel in VERBATIM_ROADMAP_CONTEXT_EXEMPT_REL_FILES

        for rule in ALL_BANNED_RULES:
            m = re.search(rule.pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if m:
                line = _line_number(text, m.start())
                findings.append(
                    Finding(
                        file=rel,
                        key=rule.key,
                        message=f"{rule.message} (line {line})",
                    )
                )

        m_trigger = RG_SCALE_TRIGGER.search(text)
        if (not is_verbatim_roadmap_context_exempt) and m_trigger and RG_SCALE_QUALIFIERS.search(text) is None:
            line = _line_number(text, m_trigger.start())
            findings.append(
                Finding(
                    file=rel,
                    key="require_rg_scale_qualifier_if_triggered",
                    message=(
                        "RG/FRG scale-identification trigger found without qualifier wording "
                        "(expected one of: ansatz / working identification / not derived / open problem / phenomenological). "
                        f"(line {line})"
                    ),
                )
            )

        for m in AS_FRG_TRIGGER.finditer(text):
            if is_verbatim_roadmap_context_exempt:
                break
            if _is_reference_like_context(text, m.start()):
                continue
            lo = max(0, m.start() - 600)
            hi = min(len(text), m.end() + 600)
            context = text[lo:hi]
            if AS_FRG_DISCLAIMER.search(context) is None:
                line = _line_number(text, m.start())
                findings.append(
                    Finding(
                        file=rel,
                        key="AS_CONTEXT_DISCLAIMER_REQUIRED",
                        message=(
                            "AS/FRG mention requires local qualifier wording "
                            "(conceptual/phenomenological/ansatz/not derived). "
                            f"(line {line})"
                        ),
                    )
                )

        conflation_reported = False
        for m in AS_FRG_TRIGGER.finditer(text):
            if is_verbatim_roadmap_context_exempt:
                break
            if _is_reference_like_context(text, m.start()):
                continue
            lo = max(0, m.start() - 600)
            hi = min(len(text), m.end() + 600)
            context = text[lo:hi]
            if AS_LANDAU_WINDOW.search(context) and _has_unnegated_strong_claim_near_landau(context):
                line = _line_number(text, m.start())
                findings.append(
                    Finding(
                        file=rel,
                        key="AS_LANDAU_CONFLATION",
                        message=(
                            "AS/FRG language is conflated with Landau/pole-like form as a derived/predicted claim. "
                            f"(line {line})"
                        ),
                    )
                )
                conflation_reported = True
            if conflation_reported:
                break

        m_k_sigma = K_SIGMA_MAPPING_TRIGGER.search(text)
        if (
            m_k_sigma
            and K_SIGMA_MAPPING_DISCLAIMER.search(text) is None
            and rel not in K_SIGMA_ANSATZ_EXEMPT_REL_FILES
        ):
            line = _line_number(text, m_k_sigma.start())
            findings.append(
                Finding(
                    file=rel,
                    key="K_SIGMA_IDENTIFICATION_REQUIRES_ANSATZ",
                    message=(
                        "k-sigma mapping language requires explicit ansatz/non-trivial/open-problem wording. "
                        f"(line {line})"
                    ),
                )
            )

        for paragraph_start, paragraph in _iter_paragraphs(text):
            if _is_reference_like_context(text, paragraph_start):
                continue
            has_cmb_full_trigger = CMB_FULL_SPECTRA_TRIGGER_PATTERN.search(paragraph) is not None
            boltzmann_class_only = (
                CMB_BOLTZMANN_CLASS_PATTERN.search(paragraph) is not None
                and CMB_FULL_SPECTRA_CONTEXT_PATTERN.search(paragraph) is None
            )
            if (
                (not is_verbatim_roadmap_context_exempt)
                and has_cmb_full_trigger
                and (not boltzmann_class_only)
                and CMB_FULL_SPECTRA_DISCLAIMER_PATTERN.search(paragraph) is None
            ):
                line = _line_number(text, paragraph_start)
                findings.append(
                    Finding(
                        file=rel,
                        key="CMB_FULL_SPECTRA_OVERCLAIM",
                        message=(
                            "Mention of full CMB spectra/peaks terms requires local scope disclaimer "
                            "(distance/compressed priors only, not full spectra fit, diagnostic/future work). "
                            "See docs/project_status_and_roadmap.md. "
                            f"(line {line})"
                        ),
                    )
                )
            if (
                (not is_verbatim_roadmap_context_exempt)
                and CMB_OVERCLAIM_PATTERN.search(paragraph)
                and CMB_DISCLAIMER_PATTERN.search(paragraph) is None
            ):
                line = _line_number(text, paragraph_start)
                findings.append(
                    Finding(
                        file=rel,
                        key="CMB_OVERCLAIM_LANGUAGE",
                        message=(
                            "CMB/Planck overclaim wording requires local disclaimer "
                            "(compressed priors / diagnostic-only / not full power spectrum). "
                            f"(line {line})"
                        ),
                    )
                )
            if (
                (not is_verbatim_roadmap_context_exempt)
                and
                CMB_WORD_PATTERN.search(paragraph)
                and CMB_CONTEXT_KEYWORDS.search(paragraph)
                and CMB_DISCLAIMER_PATTERN.search(paragraph) is None
            ):
                line = _line_number(text, paragraph_start)
                findings.append(
                    Finding(
                        file=rel,
                        key="CMB_CONTEXT_REQUIRES_COMPRESSED_PRIORS_DISCLAIMER",
                        message=(
                            "CMB paragraph using fit/consistent/agreement language must include "
                            "compressed-priors/diagnostic-only disclaimer wording. "
                            f"(line {line})"
                        ),
                    )
                )
            if DM_OVERCLAIM_PATTERN.search(paragraph) and DEFERRED_CLAIM_MARKER_PATTERN.search(paragraph) is None:
                line = _line_number(text, paragraph_start)
                findings.append(
                    Finding(
                        file=rel,
                        key="DARK_MATTER_ELIMINATION_OVERCLAIM",
                        message=(
                            "Dark-matter elimination overclaim wording is not allowed in canonical docs "
                            "(use explicit deferred marker if this is a deferred idea). "
                            f"(line {line})"
                        ),
                    )
                )
            if DM_SOLVED_OVERCLAIM_PATTERN.search(paragraph):
                line = _line_number(text, paragraph_start)
                findings.append(
                    Finding(
                        file=rel,
                        key="DM_SOLVED_OVERCLAIM",
                        message=(
                            "Claims that dark matter is solved/eliminated are not allowed in canonical docs. "
                            f"(line {line})"
                        ),
                    )
                )
            if STRUCTURE_OVERCLAIM_PATTERN.search(paragraph) and DEFERRED_CLAIM_MARKER_PATTERN.search(paragraph) is None:
                line = _line_number(text, paragraph_start)
                findings.append(
                    Finding(
                        file=rel,
                        key="STRUCTURE_FORMATION_SOLVED_OVERCLAIM",
                        message=(
                            "Structure-formation solved/galaxy-formation overclaim wording is not allowed "
                            "(use explicit deferred marker if this is a deferred idea). "
                            f"(line {line})"
                        ),
                    )
                )
            if KILL_LCDM_RHETORIC_PATTERN.search(paragraph):
                line = _line_number(text, paragraph_start)
                findings.append(
                    Finding(
                        file=rel,
                        key="KILL_LCDM_RHETORIC",
                        message=(
                            "Rhetorical claims such as 'kill LCDM'/'beat Einstein' are not allowed in canonical docs. "
                            f"(line {line})"
                        ),
                    )
                )
            if (
                (not is_verbatim_roadmap_context_exempt)
                and JOURNAL_NAME_DROP_PATTERN.search(paragraph)
                and JOURNAL_NAME_DROP_CONTEXT_PATTERN.search(paragraph)
            ):
                line = _line_number(text, paragraph_start)
                findings.append(
                    Finding(
                        file=rel,
                        key="JOURNAL_NAME_DROP_OVERHYPE",
                        message=(
                            "Nature/Science acceptance hype is not allowed in canonical docs. "
                            f"(line {line})"
                        ),
                    )
                )

        if not enforce_required:
            continue
        for rule in REQUIRED_RULES.get(rel, ()):
            if re.search(rule.pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL) is None:
                findings.append(Finding(file=rel, key=rule.key, message=rule.message))
    return findings


def _default_files(repo_root: Path) -> List[Path]:
    return [(repo_root / rel).resolve() for rel in DEFAULT_REL_FILES]


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="docs_claims_lint",
        description="Lint canonical docs for claim-hardening guardrails and banned legacy claims.",
    )
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=V101_DIR,
        help="v11.0.0 root directory containing framework/docs files.",
    )
    ap.add_argument(
        "--file",
        "--files",
        dest="files",
        action="append",
        type=Path,
        default=None,
        help="Optional file(s) to lint. Defaults to canonical framework/docs set.",
    )
    ap.add_argument(
        "--skip-required-patterns",
        action="store_true",
        help="Only run banned-phrase checks (useful for focused negative tests).",
    )
    args = ap.parse_args(argv)

    repo_root = args.repo_root.expanduser().resolve()
    files = [p.expanduser().resolve() for p in (args.files or _default_files(repo_root))]
    findings = lint_files(
        repo_root=repo_root,
        files=files,
        enforce_required=(not args.skip_required_patterns),
    )

    print("docs claims lint:")
    print(f"  repo_root: {repo_root}")
    for path in files:
        print(f"  file: {path}")
    if findings:
        print(f"ERROR: {len(findings)} claim-lint violations")
        for row in findings:
            print(f"  - [{row.key}] {row.file}: {row.message}")
        return 2

    print("OK: docs claims lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
