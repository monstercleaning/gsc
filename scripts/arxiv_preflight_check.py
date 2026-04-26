#!/usr/bin/env python3
"""Preflight checks for submission bundle zip (arXiv/journal hygiene)."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import re
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Sequence


_BANNED_NAMES = {
    ".DS_Store",
}
_BANNED_SUFFIXES = {
    ".aux",
    ".log",
    ".out",
    ".toc",
    ".fls",
    ".fdb_latexmk",
    ".synctex.gz",
    ".nav",
    ".snm",
    ".vrb",
}
_ALLOWED_SUFFIXES = {
    ".tex",
    ".sty",
    ".cls",
    ".bst",
    ".bib",
    ".bbl",
    ".png",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".eps",
    ".csv",
    ".tsv",
    ".txt",
    ".md",
    ".json",
    ".dat",
}
_PREFERRED_GRAPHICS_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}


_FORBIDDEN_TEX_PATTERNS = (
    (r"\\write18\b", r"forbidden TeX primitive \\write18"),
    (r"\bshell-escape\b", "forbidden shell-escape hint in TeX source"),
    (r"\\immediate\s*\\write", r"forbidden immediate \\write in TeX source"),
)

_LOG_FAIL_PATTERNS = (
    r"!\s+LaTeX Error:",
    r"!\s+Emergency stop\.",
    r"Citation [`'].*?undefined",
    r"There were undefined references",
    r"Undefined references",
    r"Please \(re\)run Biber",
)

_LOG_WARN_PATTERNS = (
    r"Overfull \\hbox",
    r"Underfull \\hbox",
    r"Label\(s\) may have changed\. Rerun",
    r"Font Warning",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_abs_or_traversal(name: str) -> bool:
    p = PurePosixPath(name)
    if name.startswith(("/", "\\")):
        return True
    return any(part == ".." for part in p.parts)


def _is_macos_junk(name: str) -> bool:
    p = PurePosixPath(name)
    if not p.parts:
        return False
    if p.parts[0] == "__MACOSX":
        return True
    if p.name in _BANNED_NAMES:
        return True
    if p.name.startswith("._"):
        return True
    return False


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == 0o120000


def _suffix(path: PurePosixPath) -> str:
    name = path.name.lower()
    if name.endswith(".synctex.gz"):
        return ".synctex.gz"
    return path.suffix.lower()


def _expand_asset_macros(s: str) -> str:
    s = s.replace("\\GSCAssetsDir", "paper_assets")
    s = s.replace("\\GSCFiguresDir", "paper_assets/figures")
    s = s.replace("\\GSCTablesDir", "paper_assets/tables")
    return s


def _extract_required_assets_from_tex(tex: str) -> set[str]:
    req: set[str] = set()

    for m in re.finditer(r"\\GSCInputAsset\{([^}]*)\}", tex):
        raw = m.group(1).strip()
        if raw and "#" not in raw:
            req.add(_expand_asset_macros(raw))

    for m in re.finditer(r"\\GSCIncludeFigure(?:\[[^\]]*\])?\{([^}]*)\}", tex):
        raw = m.group(1).strip()
        if raw and "#" not in raw:
            req.add(_expand_asset_macros(raw))

    for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", tex):
        raw = m.group(1).strip()
        if raw and "#" not in raw:
            req.add(_expand_asset_macros(raw))

    out: set[str] = set()
    for p in req:
        p = p.strip().strip("\"'")
        if not p:
            continue
        out.add(PurePosixPath(p).as_posix())
    return out


def _has_biblatex(tex_text: str) -> bool:
    if re.search(r"\\usepackage(?:\[[^\]]*\])?\{biblatex\}", tex_text):
        return True
    return re.search(r"\\addbibresource\{", tex_text) is not None


def _has_bibliography(tex_text: str) -> bool:
    return re.search(r"\\bibliography\{", tex_text) is not None


def _parse_compile_log(log_text: str) -> Dict[str, List[str]]:
    fails: List[str] = []
    warns: List[str] = []
    for pattern in _LOG_FAIL_PATTERNS:
        if re.search(pattern, log_text, flags=re.IGNORECASE):
            fails.append(pattern)
    for pattern in _LOG_WARN_PATTERNS:
        if re.search(pattern, log_text, flags=re.IGNORECASE):
            warns.append(pattern)
    return {"fail_patterns": sorted(set(fails)), "warn_patterns": sorted(set(warns))}


def _run_command(name: str, cmd: Sequence[str], cwd: Path, timeout_sec: float) -> Dict[str, Any]:
    started = _now_utc()
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        rc = proc.returncode
        out = proc.stdout or ""
        err = proc.stderr or ""
    except FileNotFoundError:
        rc = 127
        out = ""
        err = f"missing tool: {cmd[0]}"
    except subprocess.TimeoutExpired as exc:
        rc = 124
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        err = (err + "\n" if err else "") + f"timeout after {timeout_sec:.1f}s"

    step = {
        "name": name,
        "cmd": list(cmd),
        "status": "PASS" if rc == 0 else "FAIL",
        "exit_code": rc,
        "started_utc": started,
        "finished_utc": _now_utc(),
        "duration_sec": round(time.monotonic() - t0, 6),
        "stdout_tail": out[-2000:],
        "stderr_tail": err[-2000:],
    }
    return step


def _emit_json(target: str | None, payload: Dict[str, Any]) -> None:
    if not target:
        return
    steps = payload.get("steps", [])
    if "summary" not in payload:
        payload["summary"] = {
            "step_count": len(steps),
            "pass_count": sum(1 for s in steps if s.get("status") == "PASS"),
            "fail_count": sum(1 for s in steps if s.get("status") != "PASS"),
            "duration_sec_total": round(sum(float(s.get("duration_sec", 0.0)) for s in steps), 6),
        }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if target == "-":
        print(text, end="")
        return
    out = Path(target).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def _collect_reproduce_cmds(zip_path: Path, bib_mode: str) -> List[str]:
    cmds = [
        f"TMP=\"$(mktemp -d)\"",
        f"unzip -q {zip_path} -d \"$TMP\"",
        "cd \"$TMP\"",
        "pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex",
    ]
    if bib_mode == "bibtex":
        cmds.append("bibtex GSC_Framework_v10_1_FINAL")
        cmds.append("pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex")
        cmds.append("pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex")
    elif bib_mode == "biblatex":
        cmds.append("# biblatex detected: if needed, run biber (often unavailable on arXiv)")
        cmds.append("pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex")
        cmds.append("pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex")
    else:
        cmds.append("pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex")
        cmds.append("pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex")
    return cmds


def _run_full_compile(
    *,
    zip_path: Path,
    tex_text: str,
    timeout_sec: float,
    errors: List[str],
    warns: List[str],
    steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    compile_report: Dict[str, Any] = {
        "enabled": True,
        "bib_mode": "none",
        "log_fail_patterns": [],
        "log_warn_patterns": [],
        "main_tex": "GSC_Framework_v10_1_FINAL.tex",
        "status": "PASS",
        "log_source": "final_pass_and_log_file",
        "compile_pdf": {
            "produced": False,
            "path": "",
            "sha256": "",
            "main_tex": "GSC_Framework_v10_1_FINAL.tex",
            "bib_mode": "none",
            "steps_run": [],
            "passes_run": 0,
            "timestamp_utc": "",
        },
    }
    tex_name = "GSC_Framework_v10_1_FINAL.tex"
    tex_base = Path(tex_name).stem
    steps_run: List[str] = []
    passes_run = 0
    uses_biblatex = _has_biblatex(tex_text)
    uses_bibliography = _has_bibliography(tex_text)
    if uses_biblatex:
        compile_report["bib_mode"] = "biblatex"
    compile_report["compile_pdf"]["bib_mode"] = compile_report["bib_mode"]

    with tempfile.TemporaryDirectory(prefix="gsc_arxiv_preflight_") as td:
        tdp = Path(td)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tdp)

        tex_path = tdp / tex_name
        if not tex_path.is_file():
            errors.append(f"full-compile: missing TeX file after extraction: {tex_name}")
            compile_report["extracted_dir"] = str(tdp)
            compile_report["reproduce_commands"] = _collect_reproduce_cmds(zip_path, compile_report["bib_mode"])
            compile_report["status"] = "FAIL"
            return compile_report

        pdflatex_cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_name]
        step1 = _run_command("pdflatex_pass1", pdflatex_cmd, tdp, timeout_sec)
        steps.append(step1)
        steps_run.append("pdflatex_pass1")
        passes_run += 1
        final_logs = (step1.get("stdout_tail") or "") + "\n" + (step1.get("stderr_tail") or "")

        aux_path = tdp / "GSC_Framework_v10_1_FINAL.aux"
        aux_text = aux_path.read_text(encoding="utf-8", errors="ignore") if aux_path.is_file() else ""
        uses_bibtex = ("\\bibdata" in aux_text) or uses_bibliography
        if uses_bibtex and not uses_biblatex:
            compile_report["bib_mode"] = "bibtex"

        if step1["exit_code"] != 0:
            errors.append("full-compile: pdflatex pass 1 failed")

        if compile_report["bib_mode"] == "bibtex" and step1["exit_code"] == 0:
            bibtex_step = _run_command(
                "bibtex",
                ["bibtex", tex_base],
                tdp,
                timeout_sec,
            )
            steps.append(bibtex_step)
            steps_run.append("bibtex")
            if bibtex_step["exit_code"] != 0:
                errors.append("full-compile: bibtex failed")

        if step1["exit_code"] == 0 and not any("full-compile" in e for e in errors):
            step2 = _run_command("pdflatex_pass2", pdflatex_cmd, tdp, timeout_sec)
            step3 = _run_command("pdflatex_pass3", pdflatex_cmd, tdp, timeout_sec)
            steps.extend([step2, step3])
            steps_run.extend(["pdflatex_pass2", "pdflatex_pass3"])
            passes_run += 2
            final_logs = (step3.get("stdout_tail") or "") + "\n" + (step3.get("stderr_tail") or "")
            if step2["exit_code"] != 0 or step3["exit_code"] != 0:
                errors.append("full-compile: pdflatex repeat pass failed")

        log_path = tdp / "GSC_Framework_v10_1_FINAL.log"
        if log_path.is_file():
            final_logs += "\n" + log_path.read_text(encoding="utf-8", errors="ignore")

        parsed = _parse_compile_log(final_logs)
        compile_report["log_fail_patterns"] = parsed["fail_patterns"]
        compile_report["log_warn_patterns"] = parsed["warn_patterns"]

        for pat in parsed["warn_patterns"]:
            warns.append(f"compile-log warning pattern detected: {pat}")

        if parsed["fail_patterns"]:
            for pat in parsed["fail_patterns"]:
                errors.append(f"compile-log failure pattern detected: {pat}")

        if compile_report["bib_mode"] == "biblatex":
            biblatex_hard = any("Citation" in p or "undefined" in p.lower() or "Biber" in p for p in parsed["fail_patterns"])
            if biblatex_hard:
                errors.append(
                    "biblatex/biber workflow detected and unresolved in full compile; arXiv often cannot run biber. "
                    "Switch to bibtex-compatible flow or include a stable .bbl."
                )
            elif not errors:
                warns.append(
                    "biblatex detected; compile passed without biber in this environment. "
                    "Verify journal/arXiv backend compatibility before upload."
                )

        produced_pdf = tdp / f"{tex_base}.pdf"
        compile_pdf = compile_report["compile_pdf"]
        compile_pdf["bib_mode"] = compile_report["bib_mode"]
        compile_pdf["steps_run"] = steps_run
        compile_pdf["passes_run"] = passes_run
        compile_pdf["timestamp_utc"] = _now_utc()
        compile_pdf["main_tex"] = tex_name
        if produced_pdf.is_file():
            with tempfile.NamedTemporaryFile(prefix="gsc_submission_compile_", suffix=".pdf", delete=False) as tf:
                out_pdf = Path(tf.name)
            shutil.copy2(produced_pdf, out_pdf)
            compile_pdf["produced"] = True
            compile_pdf["path"] = str(out_pdf)
            compile_pdf["sha256"] = _sha256_file(out_pdf)
        else:
            compile_pdf["produced"] = False
            compile_pdf["path"] = ""
            compile_pdf["sha256"] = ""
            if not any("full-compile" in e for e in errors):
                warns.append("full-compile finished but no PDF was produced")

        compile_report["reproduce_commands"] = _collect_reproduce_cmds(zip_path, compile_report["bib_mode"])
        compile_report["status"] = "FAIL" if errors else ("WARN" if warns else "PASS")

    return compile_report


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="arxiv_preflight_check",
        description="Submission bundle hygiene checks (static + optional full compile).",
    )
    ap.add_argument("zip_path", help="Path to submission bundle zip")
    ap.add_argument("--warn-size-mb", type=float, default=10.0, help="Warn threshold for zip size (MB)")
    ap.add_argument("--strong-warn-size-mb", type=float, default=20.0, help="Stronger warn threshold for zip size (MB)")
    ap.add_argument("--max-size-mb", type=float, default=50.0, help="Fail threshold for zip size (MB)")
    ap.add_argument("--max-file-size-mb", type=float, default=15.0, help="Warn threshold for single file size (MB)")
    ap.add_argument("--warn-uncompressed-size-mb", type=float, default=100.0, help="Warn threshold for total uncompressed size (MB)")
    ap.add_argument("--skip-full-compile", action="store_true", help="Skip pdflatex/bibtex full compile checks")
    ap.add_argument("--compile-timeout-sec", type=float, default=120.0)
    ap.add_argument(
        "--json",
        nargs="?",
        const="-",
        default=None,
        help="Write structured preflight report JSON to PATH, or stdout when used without value.",
    )
    args = ap.parse_args(argv)

    zip_path = Path(args.zip_path)
    if not zip_path.is_file():
        print(f"ERROR: zip not found: {zip_path}")
        payload = {
            "timestamp_utc": _now_utc(),
            "zip_path": str(zip_path),
            "result": "FAIL",
            "overall_status": "FAIL",
            "errors": [f"zip not found: {zip_path}"],
            "warnings": [],
            "steps": [],
        }
        _emit_json(args.json, payload)
        return 2

    errors: List[str] = []
    warns: List[str] = []
    steps: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    compile_report: Dict[str, Any] = {"enabled": not args.skip_full_compile}

    zip_size_bytes = zip_path.stat().st_size
    zip_size_mb = float(zip_size_bytes) / (1024.0 * 1024.0)
    metrics["zip_size_bytes"] = zip_size_bytes
    metrics["zip_size_mb"] = round(zip_size_mb, 4)

    if zip_size_mb > args.max_size_mb:
        errors.append(
            f"zip size {zip_size_mb:.2f} MB exceeds hard limit {args.max_size_mb:.2f} MB"
        )
    elif zip_size_mb > args.strong_warn_size_mb:
        warns.append(
            f"zip size {zip_size_mb:.2f} MB exceeds strong warning threshold {args.strong_warn_size_mb:.2f} MB"
        )
    elif zip_size_mb > args.warn_size_mb:
        warns.append(f"zip size {zip_size_mb:.2f} MB exceeds warning threshold {args.warn_size_mb:.2f} MB")

    tex_name = "GSC_Framework_v10_1_FINAL.tex"
    tex_text = ""

    static_started = _now_utc()
    static_t0 = time.monotonic()
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        infos = zf.infolist()
        metrics["file_count"] = sum(1 for zi in infos if zi.filename and not zi.filename.endswith("/"))
        total_uncompressed = sum(int(zi.file_size) for zi in infos)
        metrics["uncompressed_size_bytes"] = total_uncompressed
        metrics["uncompressed_size_mb"] = round(float(total_uncompressed) / (1024.0 * 1024.0), 4)

        if float(total_uncompressed) / (1024.0 * 1024.0) > args.warn_uncompressed_size_mb:
            warns.append(
                f"uncompressed size {float(total_uncompressed)/(1024.0*1024.0):.2f} MB exceeds warning threshold {args.warn_uncompressed_size_mb:.2f} MB"
            )

        root_tex = [n for n in names if n.endswith(".tex") and "/" not in n]
        if tex_name not in names:
            errors.append(f"missing canonical TeX at zip root: {tex_name}")
        elif len(root_tex) != 1:
            errors.append(f"expected exactly one root TeX file, found {len(root_tex)}: {root_tex!r}")

        if not any(n.startswith("paper_assets/figures/") and not n.endswith("/") for n in names):
            errors.append("missing paper_assets/figures content")
        if not any(n.startswith("paper_assets/tables/") and not n.endswith("/") for n in names):
            errors.append("missing paper_assets/tables content")

        seen: set[str] = set()
        for info in infos:
            name = info.filename
            if not name:
                continue
            p = PurePosixPath(name)
            if _is_abs_or_traversal(name):
                errors.append(f"unsafe zip path: {name!r}")
                continue
            if _is_macos_junk(name):
                errors.append(f"macOS junk entry found: {name!r}")
                continue
            if _is_symlink(info):
                errors.append(f"symlink entry found: {name!r}")
                continue
            if name in seen:
                warns.append(f"duplicate zip entry: {name!r}")
            seen.add(name)
            if name.endswith("/"):
                continue

            if " " in name:
                warns.append(f"filename contains spaces: {name!r}")
            if len(name) > 180:
                warns.append(f"very long path in bundle: {name!r}")

            try:
                name.encode("ascii")
            except UnicodeEncodeError:
                warns.append(f"non-ASCII filename: {name!r}")

            if ".zip" == _suffix(p):
                errors.append(f"nested zip not allowed in submission bundle: {name!r}")
            if "docs/popular/" in name:
                errors.append(f"docs/popular content must not be in submission bundle: {name!r}")
            if name.startswith("results/") or "diagnostic" in name:
                errors.append(f"diagnostic/result artifact must not be in submission bundle: {name!r}")

            suff = _suffix(p)
            if suff in _BANNED_SUFFIXES:
                errors.append(f"generated/intermediate file not allowed: {name!r}")
            elif not suff:
                warns.append(f"filename has no extension: {name!r}")
            elif suff not in _ALLOWED_SUFFIXES:
                warns.append(f"non-standard extension in bundle: {name!r}")

            if suff in {".eps", ".svg", ".tif", ".tiff", ".bmp", ".gif"}:
                warns.append(f"rare graphics extension (may fail on some journals): {name!r}")
            if name.startswith(("paper_assets/figures/", "paper_assets/tables/")) and suff not in _PREFERRED_GRAPHICS_SUFFIXES and suff in {".eps", ".svg", ".tif", ".tiff", ".bmp", ".gif"}:
                warns.append(f"graphics extension outside preferred set (.pdf/.png/.jpg): {name!r}")

            size_mb = float(info.file_size) / (1024.0 * 1024.0)
            if size_mb > args.max_file_size_mb:
                warns.append(
                    f"large file {name!r}: {size_mb:.2f} MB > {args.max_file_size_mb:.2f} MB"
                )

        if tex_name in names:
            try:
                tex_text = zf.read(tex_name).decode("utf-8")
            except UnicodeDecodeError as exc:
                errors.append(f"{tex_name} is not UTF-8 decodable: {exc}")
                tex_text = ""

            for pattern, desc in _FORBIDDEN_TEX_PATTERNS:
                if re.search(pattern, tex_text, flags=re.IGNORECASE):
                    errors.append(desc)

            if tex_text:
                names_set = set(names)
                missing_assets: list[str] = []
                for p in sorted(_extract_required_assets_from_tex(tex_text)):
                    if not p:
                        continue
                    if p in names_set:
                        continue
                    if "." not in PurePosixPath(p).name:
                        if any((p + ext) in names_set for ext in (".png", ".pdf", ".jpg", ".jpeg")):
                            continue
                    missing_assets.append(p)
                if missing_assets:
                    errors.append(
                        "TeX references missing assets: "
                        + ", ".join(missing_assets[:8])
                        + (" ..." if len(missing_assets) > 8 else "")
                    )

    steps.append(
        {
            "name": "static_bundle_checks",
            "cmd": ["zip-inspection"],
            "status": "PASS" if not errors else "FAIL",
            "exit_code": 0 if not errors else 2,
            "started_utc": static_started,
            "finished_utc": _now_utc(),
            "duration_sec": round(time.monotonic() - static_t0, 6),
        }
    )

    if not args.skip_full_compile and not errors:
        compile_report = _run_full_compile(
            zip_path=zip_path,
            tex_text=tex_text,
            timeout_sec=args.compile_timeout_sec,
            errors=errors,
            warns=warns,
            steps=steps,
        )
    elif args.skip_full_compile:
        compile_report = {
            "enabled": False,
            "skipped": True,
            "status": "SKIP",
            "compile_pdf": {
                "produced": False,
                "path": "",
                "sha256": "",
                "main_tex": tex_name,
                "bib_mode": "none",
                "steps_run": [],
                "passes_run": 0,
                "timestamp_utc": _now_utc(),
            },
        }
    else:
        compile_report = {
            "enabled": False,
            "skipped": True,
            "status": "SKIP",
            "skipped_reason": "static checks failed",
            "compile_pdf": {
                "produced": False,
                "path": "",
                "sha256": "",
                "main_tex": tex_name,
                "bib_mode": "none",
                "steps_run": [],
                "passes_run": 0,
                "timestamp_utc": _now_utc(),
            },
        }

    sha = _sha256_file(zip_path)
    result = "PASS"
    if errors:
        result = "FAIL"
    elif warns:
        result = "WARN"

    payload: Dict[str, Any] = {
        "timestamp_utc": _now_utc(),
        "zip_path": str(zip_path),
        "sha256": sha,
        "metrics": metrics,
        "steps": steps,
        "errors": errors,
        "warnings": warns,
        "result": result,
        "overall_status": result,
        "compile": compile_report,
        "compile_pdf": compile_report.get("compile_pdf", {"produced": False}),
    }

    for w in warns:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        print(f"FAIL: arXiv preflight found {len(errors)} error(s) and {len(warns)} warning(s)")
        if isinstance(compile_report, dict) and compile_report.get("reproduce_commands"):
            print("Reproduce full compile locally:")
            for cmd in compile_report["reproduce_commands"]:
                print(f"  {cmd}")
        _emit_json(args.json, payload)
        return 2

    print("OK: arXiv preflight passed")
    print(f"  zip: {zip_path}")
    print(f"  sha256: {sha}")
    if warns:
        print(f"  warnings: {len(warns)}")
    _emit_json(args.json, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
