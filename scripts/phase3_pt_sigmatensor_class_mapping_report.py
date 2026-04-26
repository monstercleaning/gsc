#!/usr/bin/env python3
"""Deterministic diagnostic report for SigmaTensor -> CLASS w0wa mapping quality."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


TOOL = "phase3_pt_sigmatensor_class_mapping_report"
SCHEMA = "phase3_sigmatensor_class_mapping_report_v1"
FAIL_MARKER = "PHASE3_CLASS_MAPPING_FAILED"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
CSV_FMT = "{:.12e}"


class UsageError(Exception):
    """Usage/configuration error (exit 1)."""


class GateError(Exception):
    """Deterministic validation gate failure (exit 2)."""


def _normalize_created_utc(raw: str) -> str:
    text = str(raw or "").strip()
    if not CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise UsageError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise UsageError(f"{name} must be a finite float")
    return float(out)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _fmt(value: float) -> str:
    return CSV_FMT.format(float(value))


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GateError(f"failed to parse JSON: {path.name}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise GateError(f"JSON root must be object: {path.name}")
    return payload


def _parse_ini(path: Path) -> Dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: Dict[str, str] = {}
    for raw in lines:
        line = str(raw).strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        k = str(key).strip().lower()
        v = str(value).strip()
        if not k:
            continue
        out[k] = v
    return out


def _extract_float(payload: Mapping[str, Any], paths: Sequence[Sequence[str]]) -> Optional[float]:
    for path in paths:
        cur: Any = payload
        ok = True
        for key in path:
            if not isinstance(cur, Mapping) or key not in cur:
                ok = False
                break
            cur = cur.get(key)
        if not ok:
            continue
        try:
            out = float(cur)
        except Exception:
            continue
        if math.isfinite(out):
            return float(out)
    return None


def _load_grid(path: Path) -> Dict[str, List[float]]:
    required = ("z", "H_over_H0", "w_phi", "Omega_phi")
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise GateError("SIGMATENSOR_DIAGNOSTIC_GRID.csv has no header")
            fieldnames = [str(x).strip() for x in reader.fieldnames]
            missing = [name for name in required if name not in fieldnames]
            if missing:
                raise GateError(f"SIGMATENSOR_DIAGNOSTIC_GRID.csv missing required columns: {','.join(missing)}")
            rows = list(reader)
    except GateError:
        raise
    except Exception as exc:
        raise GateError(f"failed to read SIGMATENSOR_DIAGNOSTIC_GRID.csv: {exc}") from exc

    if not rows:
        raise GateError("SIGMATENSOR_DIAGNOSTIC_GRID.csv has no data rows")

    z_grid: List[float] = []
    e_sigma: List[float] = []
    w_sigma: List[float] = []
    om_sigma: List[float] = []
    for idx, row in enumerate(rows):
        try:
            z = float(str(row.get("z", "")).strip())
            e = float(str(row.get("H_over_H0", "")).strip())
            w = float(str(row.get("w_phi", "")).strip())
            om = float(str(row.get("Omega_phi", "")).strip())
        except Exception as exc:
            raise GateError(f"grid parse failed at row {idx + 2}") from exc
        if not (math.isfinite(z) and math.isfinite(e) and math.isfinite(w) and math.isfinite(om)):
            raise GateError(f"grid contains non-finite values at row {idx + 2}")
        z_grid.append(float(z))
        e_sigma.append(float(e))
        w_sigma.append(float(w))
        om_sigma.append(float(om))

    return {
        "z": z_grid,
        "E_sigma": e_sigma,
        "w_sigma": w_sigma,
        "Omega_phi_sigma": om_sigma,
    }


def _rms(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    acc = 0.0
    for value in values:
        acc += float(value) * float(value)
    return math.sqrt(acc / float(len(values)))


def _build_markdown(payload: Mapping[str, Any]) -> str:
    residuals = payload.get("residuals") if isinstance(payload.get("residuals"), Mapping) else {}
    res_w = residuals.get("w") if isinstance(residuals, Mapping) and isinstance(residuals.get("w"), Mapping) else {}
    res_e = residuals.get("E") if isinstance(residuals, Mapping) and isinstance(residuals.get("E"), Mapping) else {}
    res_om = (
        residuals.get("Omega_phi")
        if isinstance(residuals, Mapping) and isinstance(residuals.get("Omega_phi"), Mapping)
        else {}
    )
    w0wa = payload.get("w0wa") if isinstance(payload.get("w0wa"), Mapping) else {}
    grid = payload.get("grid") if isinstance(payload.get("grid"), Mapping) else {}
    gates = payload.get("gates") if isinstance(payload.get("gates"), Mapping) else {}
    required = gates.get("required") if isinstance(gates, Mapping) and isinstance(gates.get("required"), Mapping) else {}

    lines: List[str] = []
    lines.append("# CLASS mapping validation report (diagnostic)")
    lines.append("")
    lines.append("This report compares the SigmaTensor diagnostic grid against the")
    lines.append("w0wa fluid approximation used in the CLASS template ini.")
    lines.append("Scope boundary: diagnostic mapping consistency only.")
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    lines.append(f"- created_utc: `{payload.get('created_utc')}`")
    lines.append(f"- export_pack: `{_extract_nested_str(payload, ('export_pack', 'basename'))}`")
    lines.append(f"- w0_fld: `{w0wa.get('w0_fld')}`")
    lines.append(f"- wa_fld: `{w0wa.get('wa_fld')}`")
    lines.append(f"- grid points: `{grid.get('n_points')}`")
    lines.append("")
    lines.append("## Residual summary")
    lines.append("")
    lines.append(f"- max_abs_rel_E: `{res_e.get('max_abs_rel')}`")
    lines.append(f"- rms_rel_E: `{res_e.get('rms_rel')}`")
    lines.append(f"- max_abs_dw: `{res_w.get('max_abs_dw')}`")
    lines.append(f"- rms_dw: `{res_w.get('rms_dw')}`")
    lines.append(f"- max_abs_dOmega_phi: `{res_om.get('max_abs')}`")
    lines.append(f"- rms_dOmega_phi: `{res_om.get('rms')}`")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append(f"- pass: `{gates.get('pass')}`")
    lines.append(f"- require_max_rel_E_le: `{required.get('max_rel_E_le')}`")
    lines.append(f"- require_rms_w_le: `{required.get('rms_w_le')}`")
    lines.append(f"- require_max_abs_omega_phi_le: `{required.get('max_abs_omega_phi_le')}`")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 v11.0.0/scripts/phase3_pt_sigmatensor_class_mapping_report.py \\")
    lines.append("  --export-pack <export_pack_dir> \\")
    lines.append("  --outdir <outdir> \\")
    lines.append("  --created-utc 2000-01-01T00:00:00Z \\")
    lines.append("  --format text")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _extract_nested_str(payload: Mapping[str, Any], path: Sequence[str]) -> str:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, Mapping):
            return ""
        cur = cur.get(key)
    return str(cur or "")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SigmaTensor->CLASS w0wa mapping diagnostic report.")
    ap.add_argument("--export-pack", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--require-max-rel-E-le", type=float, default=None)
    ap.add_argument("--require-rms-w-le", type=float, default=None)
    ap.add_argument("--require-max-abs-omega-phi-le", type=float, default=None)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        export_pack = Path(args.export_pack).expanduser().resolve()
        if not export_pack.is_dir():
            raise GateError(f"--export-pack must be an existing directory: {export_pack}")
        outdir = Path(args.outdir).expanduser().resolve()
        if outdir.exists() and not outdir.is_dir():
            raise UsageError(f"--outdir exists and is not a directory: {outdir}")
        outdir.mkdir(parents=True, exist_ok=True)

        grid_path = export_pack / "SIGMATENSOR_DIAGNOSTIC_GRID.csv"
        ini_path = export_pack / "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini"
        candidate_path = export_pack / "CANDIDATE_RECORD.json"
        summary_path = export_pack / "EXPORT_SUMMARY.json"
        for path in (grid_path, ini_path, candidate_path, summary_path):
            if not path.is_file():
                raise GateError(f"required file missing in export pack: {path.name}")

        grid = _load_grid(grid_path)
        ini = _parse_ini(ini_path)
        candidate_payload = _load_json(candidate_path)
        summary_payload = _load_json(summary_path)

        if "w0_fld" not in ini or "wa_fld" not in ini:
            raise GateError("CLASS ini missing w0_fld/wa_fld")
        w0_fld = _finite_float(ini.get("w0_fld"), name="w0_fld")
        wa_fld = _finite_float(ini.get("wa_fld"), name="wa_fld")

        omega_m0 = _extract_float(
            summary_payload,
            (
                ("params", "Omega_m0"),
                ("Omega_m0",),
                ("derived_today", "Omega_m0"),
            ),
        )
        if omega_m0 is None:
            omega_m0 = _extract_float(
                candidate_payload,
                (
                    ("record", "Omega_m0"),
                    ("Omega_m0",),
                    ("params", "Omega_m0"),
                    ("derived_today", "Omega_m0"),
                ),
            )
        if omega_m0 is None:
            raise GateError("missing Omega_m0 in export summary/candidate record")

        omega_r0 = _extract_float(
            summary_payload,
            (
                ("derived_today", "Omega_r0"),
                ("params", "Omega_r0"),
                ("Omega_r0",),
            ),
        )
        if omega_r0 is None:
            omega_r0 = _extract_float(
                candidate_payload,
                (
                    ("record", "Omega_r0"),
                    ("Omega_r0",),
                    ("derived_today", "Omega_r0"),
                    ("params", "Omega_r0"),
                ),
            )
        if omega_r0 is None:
            raise GateError("missing Omega_r0 in export summary/candidate record")

        Omega_m0 = float(omega_m0)
        Omega_r0 = float(omega_r0)
        Omega_phi0 = 1.0 - Omega_m0 - Omega_r0
        if not math.isfinite(Omega_phi0):
            raise GateError("non-finite Omega_phi0 derived from Omega_m0/Omega_r0")

        z_values = list(grid["z"])
        e_sigma = list(grid["E_sigma"])
        w_sigma = list(grid["w_sigma"])
        om_sigma = list(grid["Omega_phi_sigma"])

        e_w0wa: List[float] = []
        w_w0wa: List[float] = []
        om_w0wa: List[float] = []
        d_w: List[float] = []
        d_e_rel: List[float] = []
        d_om: List[float] = []
        digest_rows: List[str] = []

        for i, z in enumerate(z_values):
            zp1 = 1.0 + float(z)
            if zp1 <= 0.0:
                raise GateError(f"invalid z <= -1 at row {i + 2}")
            frac = float(z) / zp1
            w_model = float(w0_fld + wa_fld * frac)
            exp_pow = 3.0 * (1.0 + w0_fld + wa_fld)
            f_de = float((zp1 ** exp_pow) * math.exp(-3.0 * wa_fld * frac))
            e2_model = (
                Omega_r0 * (zp1 ** 4.0)
                + Omega_m0 * (zp1 ** 3.0)
                + Omega_phi0 * f_de
            )
            if not (math.isfinite(e2_model) and e2_model > 0.0):
                raise GateError(f"invalid E_w0wa^2 at row {i + 2}")
            e_model = math.sqrt(e2_model)
            om_model = float((Omega_phi0 * f_de) / e2_model)

            e_w0wa.append(float(e_model))
            w_w0wa.append(float(w_model))
            om_w0wa.append(float(om_model))

            de_rel = float((e_sigma[i] / e_model) - 1.0)
            dw = float(w_sigma[i] - w_model)
            dom = float(om_sigma[i] - om_model)
            d_e_rel.append(de_rel)
            d_w.append(dw)
            d_om.append(dom)
            digest_rows.append(
                ",".join(
                    [
                        _fmt(z_values[i]),
                        _fmt(e_sigma[i]),
                        _fmt(e_model),
                        _fmt(w_sigma[i]),
                        _fmt(w_model),
                        _fmt(om_sigma[i]),
                        _fmt(om_model),
                    ]
                )
                + "\n"
            )

        max_abs_rel_e = float(max(abs(x) for x in d_e_rel) if d_e_rel else 0.0)
        rms_rel_e = float(_rms(d_e_rel))
        max_abs_dom = float(max(abs(x) for x in d_om) if d_om else 0.0)
        rms_dom = float(_rms(d_om))
        residuals = {
            "w": {
                "max_abs_dw": float(max(abs(x) for x in d_w) if d_w else 0.0),
                "rms_dw": float(_rms(d_w)),
            },
            "E": {
                "max_abs_rel": max_abs_rel_e,
                "rms_rel": rms_rel_e,
                "max_abs_rel_E": max_abs_rel_e,
                "rms_rel_E": rms_rel_e,
            },
            "Omega_phi": {
                "max_abs": max_abs_dom,
                "rms": rms_dom,
                "max_abs_dOmega_phi": max_abs_dom,
                "rms_dOmega_phi": rms_dom,
            },
        }

        req_max_rel_e = None if args.require_max_rel_E_le is None else _finite_float(args.require_max_rel_E_le, name="--require-max-rel-E-le")
        req_rms_w = None if args.require_rms_w_le is None else _finite_float(args.require_rms_w_le, name="--require-rms-w-le")
        req_max_abs_om = None if args.require_max_abs_omega_phi_le is None else _finite_float(args.require_max_abs_omega_phi_le, name="--require-max-abs-omega-phi-le")
        if req_max_rel_e is not None and req_max_rel_e < 0.0:
            raise UsageError("--require-max-rel-E-le must be >= 0")
        if req_rms_w is not None and req_rms_w < 0.0:
            raise UsageError("--require-rms-w-le must be >= 0")
        if req_max_abs_om is not None and req_max_abs_om < 0.0:
            raise UsageError("--require-max-abs-omega-phi-le must be >= 0")

        gate_pass = True
        if req_max_rel_e is not None and residuals["E"]["max_abs_rel"] > float(req_max_rel_e):
            gate_pass = False
        if req_rms_w is not None and residuals["w"]["rms_dw"] > float(req_rms_w):
            gate_pass = False
        if req_max_abs_om is not None and residuals["Omega_phi"]["max_abs"] > float(req_max_abs_om):
            gate_pass = False

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "created_utc": created_utc,
            "export_pack": {
                "basename": str(export_pack.name),
                "digests": {
                    "grid_sha256": _sha256_path(grid_path),
                    "ini_sha256": _sha256_path(ini_path),
                    "candidate_sha256": _sha256_path(candidate_path),
                },
            },
            "w0wa": {
                "w0_fld": float(w0_fld),
                "wa_fld": float(wa_fld),
            },
            "cosmology_today": {
                "Omega_m0": float(Omega_m0),
                "Omega_r0": float(Omega_r0),
                "Omega_phi0": float(Omega_phi0),
            },
            "grid": {
                "z_min": float(min(z_values)),
                "z_max": float(max(z_values)),
                "n_points": int(len(z_values)),
            },
            "residuals": residuals,
            "gates": {
                "required": {
                    "max_rel_E_le": None if req_max_rel_e is None else float(req_max_rel_e),
                    "rms_w_le": None if req_rms_w is None else float(req_rms_w),
                    "max_abs_omega_phi_le": None if req_max_abs_om is None else float(req_max_abs_om),
                },
                "pass": bool(gate_pass),
            },
            "digests": {
                "table_sha256": _sha256_text("".join(digest_rows)),
            },
        }

        md_text = _build_markdown(payload)
        (outdir / "CLASS_MAPPING_REPORT.json").write_text(_json_pretty(payload), encoding="utf-8")
        (outdir / "CLASS_MAPPING_REPORT.md").write_text(md_text, encoding="utf-8")

        text_summary = (
            "class_mapping "
            f"n_points={int(len(z_values))} "
            f"max_rel_E={residuals['E']['max_abs_rel']:.12e} "
            f"rms_dw={residuals['w']['rms_dw']:.12e} "
            f"max_abs_dOm={residuals['Omega_phi']['max_abs']:.12e} "
            f"gates_pass={str(bool(gate_pass)).lower()}\n"
        )
        if str(args.format) == "json":
            sys.stdout.write(_json_pretty(payload))
        else:
            sys.stdout.write(text_summary)

        if not gate_pass:
            raise GateError("mapping quality gates failed")

    except GateError as exc:
        print(FAIL_MARKER, file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
