#!/usr/bin/env python3
"""Deterministic harness for external CLASS/CAMB runs (stdlib-only).

This tool does not implement Boltzmann physics. It prepares a deterministic
run directory from an export pack, executes an external solver (native or
docker), and writes reproducible run metadata.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


TOOL_NAME = "phase2_pt_boltzmann_run_harness"
SCHEMA_NAME = "phase2_pt_boltzmann_run_metadata_v1"

REQUIRED_EXPORT_FILES: Tuple[str, ...] = (
    "EXPORT_SUMMARY.json",
    "CANDIDATE_RECORD.json",
)
TEMPLATE_BY_CODE: Mapping[str, str] = {
    "class": "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini",
    "camb": "BOLTZMANN_INPUT_TEMPLATE_CAMB.ini",
}
ENV_BIN_BY_CODE: Mapping[str, str] = {
    "class": "GSC_CLASS_BIN",
    "camb": "GSC_CAMB_BIN",
}
ENV_IMAGE_BY_CODE: Mapping[str, str] = {
    "class": "GSC_CLASS_DOCKER_IMAGE",
    "camb": "GSC_CAMB_DOCKER_IMAGE",
}
DEFAULT_IMAGE_BY_CODE: Mapping[str, str] = {
    "class": "ghcr.io/lesgourg/class_public:latest",
    "camb": "ghcr.io/cmbant/camb:latest",
}
MARKER_UNPINNED_DOCKER_IMAGE = "HARNESS_UNPINNED_DOCKER_IMAGE"


class HarnessError(Exception):
    """Base harness error."""


class HarnessUsageError(HarnessError):
    """Usage/IO error (exit 1)."""


class HarnessGateError(HarnessError):
    """Requirement gate error (exit 2)."""


def _image_ref_is_pinned(image_ref: str) -> bool:
    text = str(image_ref).strip()
    if not text:
        return False
    if "@sha256:" in text:
        return True
    last = text.rsplit("/", 1)[-1]
    if ":" not in last:
        return False
    tag = last.rsplit(":", 1)[-1].strip()
    if not tag:
        return False
    return tag.lower() != "latest"


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _normalize_created_utc(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise HarnessUsageError("--created-utc must be non-empty")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise HarnessUsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _assert_executable(path: Path) -> None:
    if not path.is_file():
        raise HarnessGateError(f"binary not found: {path}")
    mode = path.stat().st_mode
    if (mode & stat.S_IXUSR) == 0 and (mode & stat.S_IXGRP) == 0 and (mode & stat.S_IXOTH) == 0:
        raise HarnessGateError(f"binary is not executable: {path}")


def _looks_like_absolute_path(text: str) -> bool:
    token = str(text).strip()
    if not token:
        return False
    if Path(token).is_absolute():
        return True
    if re.match(r"^[A-Za-z]:[\\/]", token):
        return True
    return token.startswith("\\\\")


def _redact_absolute_path_token(text: str) -> str:
    token = str(text).strip()
    if not token:
        return token
    if _looks_like_absolute_path(token):
        name = Path(token).name
        return f"[abs]/{name}" if name else "[abs]"
    return token


def _resolve_native_binary(*, code: str, explicit_bin: Optional[str]) -> Tuple[str, Dict[str, str]]:
    env_key = str(ENV_BIN_BY_CODE[str(code)])
    env_value = str(os.environ.get(env_key, "")).strip()
    if explicit_bin is not None and str(explicit_bin).strip():
        raw = str(explicit_bin).strip()
        source_env = {"arg_bin": raw}
    elif env_value:
        raw = env_value
        source_env = {env_key: raw}
    else:
        raise HarnessGateError(f"{env_key} is required for native runner (or pass --bin)")

    candidate = Path(raw)
    if candidate.is_absolute() or str(raw).startswith(".") or "/" in str(raw):
        resolved = candidate.expanduser().resolve()
        _assert_executable(resolved)
        return str(resolved), source_env

    found = shutil.which(raw)
    if not found:
        raise HarnessGateError(f"native binary '{raw}' not found in PATH")
    _assert_executable(Path(found))
    return str(Path(found).resolve()), source_env


def _prepare_run_dir(path: Path, *, overwrite: bool) -> None:
    if path.exists():
        if not path.is_dir():
            raise HarnessUsageError(f"--run-dir exists and is not a directory: {path}")
        if any(path.iterdir()):
            if not overwrite:
                raise HarnessUsageError(f"--run-dir is not empty (use --overwrite): {path}")
            shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)
    else:
        path.mkdir(parents=True, exist_ok=True)


def _copy_inputs(
    *,
    export_pack: Path,
    run_dir: Path,
    code: str,
    include_absolute_paths: bool,
) -> Tuple[Path, List[Dict[str, Any]]]:
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []

    required = list(REQUIRED_EXPORT_FILES) + [str(TEMPLATE_BY_CODE[str(code)])]
    for name in required:
        src = export_pack / name
        if not src.is_file():
            raise HarnessGateError(f"required export-pack file missing: {src}")
        dst = inputs_dir / name
        shutil.copyfile(src, dst)
        rows.append(
            {
                "path": str(dst.relative_to(run_dir).as_posix()),
                "bytes": int(dst.stat().st_size),
                "sha256": _sha256_path(dst),
                "source": str(name),
            }
        )
        if include_absolute_paths:
            rows[-1]["source_abs"] = str(src.resolve())

    rows.sort(key=lambda row: str(row.get("path", "")))
    template_path = inputs_dir / str(TEMPLATE_BY_CODE[str(code)])
    return template_path, rows


def _build_command(
    *,
    code: str,
    runner: str,
    template_path: Path,
    run_dir: Path,
    explicit_bin: Optional[str],
) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    if str(runner) == "native":
        binary, env_subset = _resolve_native_binary(code=str(code), explicit_bin=explicit_bin)
        return [str(binary), str(template_path)], env_subset, {"native_bin": str(binary)}

    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise HarnessGateError("docker not found in PATH")

    image_key = str(ENV_IMAGE_BY_CODE[str(code)])
    image = str(os.environ.get(image_key, str(DEFAULT_IMAGE_BY_CODE[str(code)]))).strip()
    if not image:
        raise HarnessGateError(f"{image_key} is empty")
    mount = f"{str(run_dir)}:/work"
    template_in_container = str(PurePosixPath("/work/inputs") / str(template_path.name))
    cmd = [
        str(docker_bin),
        "run",
        "--rm",
        "-v",
        mount,
        "-w",
        "/work",
        str(image),
        template_in_container,
    ]
    return cmd, {image_key: str(image), "docker_bin": str(docker_bin)}, {
        "docker_bin": str(docker_bin),
        "docker_image_ref": str(image),
    }


def _run_external_command(cmd: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


def _render_run_log(
    *,
    created_utc: str,
    code: str,
    runner: str,
    paths_redacted: bool,
    command_argv: Sequence[str],
    returncode: int,
    stdout: str,
    stderr: str,
) -> str:
    lines: List[str] = []
    lines.append(f"tool={TOOL_NAME}")
    lines.append(f"schema={SCHEMA_NAME}")
    lines.append(f"created_utc={created_utc}")
    lines.append(f"code={code}")
    lines.append(f"runner={runner}")
    lines.append(f"paths_redacted={str(bool(paths_redacted)).lower()}")
    lines.append(f"returncode={int(returncode)}")
    lines.append("command_argv=" + json.dumps([str(x) for x in command_argv], ensure_ascii=True, separators=(",", ":")))
    lines.append("")
    lines.append("[stdout]")
    lines.append(str(stdout or "").rstrip("\n"))
    lines.append("")
    lines.append("[stderr]")
    lines.append(str(stderr or "").rstrip("\n"))
    lines.append("")
    return "\n".join(lines)


def _normalize_command_argv(
    *,
    command_argv: Sequence[str],
    run_dir: Path,
    include_absolute_paths: bool,
) -> List[str]:
    run_dir_resolved = run_dir.resolve()
    command_payload: List[str] = []
    for item in command_argv:
        token = str(item)
        if include_absolute_paths:
            command_payload.append(token)
            continue
        if _looks_like_absolute_path(token):
            try:
                rel = Path(token).resolve().relative_to(run_dir_resolved)
                command_payload.append(rel.as_posix())
                continue
            except Exception:
                command_payload.append(_redact_absolute_path_token(token))
                continue
        command_payload.append(token)
    return command_payload


def _sanitize_stream_for_portable(
    *,
    text: str,
    run_dir: Path,
    include_absolute_paths: bool,
) -> str:
    out = str(text or "")
    if include_absolute_paths:
        return out

    run_dir_resolved = run_dir.resolve()
    tokens: List[str] = []
    raw = str(run_dir_resolved)
    if raw:
        tokens.append(raw)
    posix = run_dir_resolved.as_posix()
    if posix and posix not in tokens:
        tokens.append(posix)
    winish = raw.replace("/", "\\")
    if winish and winish not in tokens:
        tokens.append(winish)

    for token in sorted(tokens, key=len, reverse=True):
        out = out.replace(token, ".")
    return out


def _run_probe_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_sec: float = 2.0,
) -> subprocess.CompletedProcess[str]:
    args = [str(x) for x in argv]
    try:
        return subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=float(timeout_sec),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(
            args=args,
            returncode=125,
            stdout="",
            stderr=str(exc),
        )


def _first_nonempty_line(text: str) -> Optional[str]:
    for line in str(text or "").splitlines():
        out = str(line).strip()
        if out:
            return out
    return None


def _sanitize_string_for_portable(
    *,
    text: str,
    run_dir: Path,
    include_absolute_paths: bool,
) -> str:
    out = _sanitize_stream_for_portable(
        text=str(text or ""),
        run_dir=run_dir,
        include_absolute_paths=include_absolute_paths,
    )
    if include_absolute_paths:
        return out
    chunks = out.split()
    if not chunks:
        return out
    return " ".join(_redact_absolute_path_token(chunk) for chunk in chunks)


def _safe_json_loads(value: str) -> Any:
    try:
        return json.loads(str(value).strip())
    except Exception:
        return None


def _redact_value_for_portable(*, value: Any, run_dir: Path, include_absolute_paths: bool) -> Any:
    if isinstance(value, Mapping):
        return {
            str(k): _redact_value_for_portable(
                value=value[k],
                run_dir=run_dir,
                include_absolute_paths=include_absolute_paths,
            )
            for k in sorted(value.keys(), key=lambda x: str(x))
        }
    if isinstance(value, list):
        return [
            _redact_value_for_portable(
                value=v,
                run_dir=run_dir,
                include_absolute_paths=include_absolute_paths,
            )
            for v in value
        ]
    if isinstance(value, tuple):
        return [
            _redact_value_for_portable(
                value=v,
                run_dir=run_dir,
                include_absolute_paths=include_absolute_paths,
            )
            for v in value
        ]
    if isinstance(value, str):
        return _sanitize_string_for_portable(
            text=value,
            run_dir=run_dir,
            include_absolute_paths=include_absolute_paths,
        )
    return value


def _capture_external_code_provenance(
    *,
    code: str,
    runner: str,
    run_dir: Path,
    include_absolute_paths: bool,
    runtime_info: Mapping[str, str],
    require_pinned_image: bool,
    capture_docker_provenance: bool,
    capture_native_provenance: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"runner": str(runner)}

    if str(runner) == "docker":
        image_ref = str(runtime_info.get("docker_image_ref", "")).strip()
        docker_bin = str(runtime_info.get("docker_bin", "")).strip()
        image_is_pinned = _image_ref_is_pinned(image_ref)
        if bool(require_pinned_image) and not bool(image_is_pinned):
            raise HarnessGateError(f"{MARKER_UNPINNED_DOCKER_IMAGE}: {image_ref}")

        docker_payload: Dict[str, Any] = {
            "image_ref": image_ref,
            "image_is_pinned": bool(image_is_pinned),
            "image_repo_digests": [],
            "image_id": "",
            "docker_bin": docker_bin if include_absolute_paths else _redact_absolute_path_token(docker_bin),
            "docker_version": "",
            "inspect_ok": False,
            "notes": None,
        }
        if include_absolute_paths and docker_bin:
            docker_payload["docker_bin_abs"] = str(Path(docker_bin).resolve())

        if bool(capture_docker_provenance):
            notes: List[str] = []
            inspect_ok = True

            if docker_bin:
                proc_repo = _run_probe_command(
                    [docker_bin, "image", "inspect", image_ref, "--format", "{{json .RepoDigests}}"],
                    cwd=run_dir,
                )
                if int(proc_repo.returncode) == 0:
                    parsed_repo = _safe_json_loads(proc_repo.stdout)
                    if isinstance(parsed_repo, list):
                        docker_payload["image_repo_digests"] = [str(x) for x in parsed_repo]
                    elif isinstance(parsed_repo, str) and parsed_repo.strip():
                        docker_payload["image_repo_digests"] = [str(parsed_repo).strip()]
                else:
                    inspect_ok = False
                    notes.append("image_inspect_repo_digests_failed")

                proc_id = _run_probe_command(
                    [docker_bin, "image", "inspect", image_ref, "--format", "{{json .Id}}"],
                    cwd=run_dir,
                )
                if int(proc_id.returncode) == 0:
                    parsed_id = _safe_json_loads(proc_id.stdout)
                    if isinstance(parsed_id, str):
                        docker_payload["image_id"] = str(parsed_id)
                    elif parsed_id is not None:
                        docker_payload["image_id"] = str(parsed_id)
                    else:
                        docker_payload["image_id"] = str(proc_id.stdout or "").strip()
                else:
                    inspect_ok = False
                    notes.append("image_inspect_id_failed")

                proc_version = _run_probe_command(
                    [docker_bin, "version", "--format", "{{json .}}"],
                    cwd=run_dir,
                )
                if int(proc_version.returncode) == 0:
                    parsed_version = _safe_json_loads(proc_version.stdout)
                    if isinstance(parsed_version, (Mapping, list)):
                        docker_payload["docker_version"] = parsed_version
                    else:
                        docker_payload["docker_version"] = str(proc_version.stdout or "").strip()
                else:
                    inspect_ok = False
                    notes.append("docker_version_failed")
            else:
                inspect_ok = False
                notes.append("docker_bin_missing")

            docker_payload["inspect_ok"] = bool(inspect_ok)
            if notes:
                docker_payload["notes"] = ",".join(sorted(set(str(n) for n in notes)))
            else:
                docker_payload["notes"] = "captured"
        else:
            docker_payload["notes"] = "capture_disabled"

        payload["docker"] = docker_payload
        return _redact_value_for_portable(
            value=payload,
            run_dir=run_dir,
            include_absolute_paths=include_absolute_paths,
        )

    # native provenance
    native_bin = str(runtime_info.get("native_bin", "")).strip()
    if not native_bin:
        raise HarnessGateError("native runner missing resolved binary identity")
    native_path = Path(native_bin).expanduser().resolve()
    native_payload: Dict[str, Any] = {
        "bin_name": native_path.name,
        "bin_sha256": _sha256_path(native_path),
        "version_ok": False,
        "version_first_line": None,
    }
    if include_absolute_paths:
        native_payload["bin_path_abs"] = str(native_path)

    if bool(capture_native_provenance):
        try:
            proc_version = _run_probe_command([str(native_path), "--version"], cwd=run_dir)
            line = _first_nonempty_line(proc_version.stdout) or _first_nonempty_line(proc_version.stderr)
            if int(proc_version.returncode) == 0 and line:
                native_payload["version_ok"] = True
                native_payload["version_first_line"] = _sanitize_string_for_portable(
                    text=str(line),
                    run_dir=run_dir,
                    include_absolute_paths=include_absolute_paths,
                )
            else:
                native_payload["version_ok"] = False
        except (OSError, subprocess.SubprocessError):
            native_payload["version_ok"] = False
    payload["native"] = native_payload
    return _redact_value_for_portable(
        value=payload,
        run_dir=run_dir,
        include_absolute_paths=include_absolute_paths,
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Deterministic harness for external CLASS/CAMB runs.",
    )
    ap.add_argument("--export-pack", required=True, help="Directory produced by phase2_pt_boltzmann_export_pack.py")
    ap.add_argument("--code", choices=("class", "camb"), required=True)
    ap.add_argument("--runner", choices=("native", "docker"), required=True)
    ap.add_argument("--run-dir", required=True, help="Run output directory (created if missing)")
    ap.add_argument("--created-utc", required=True, help="Deterministic UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--bin", default=None, help="Optional explicit solver binary path for native runner")
    ap.add_argument(
        "--require-pinned-image",
        action="store_true",
        help="For docker runner, fail with exit 2 unless image ref is pinned (digest or non-latest tag).",
    )
    ap.add_argument(
        "--capture-docker-provenance",
        dest="capture_docker_provenance",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Capture docker inspect/version provenance fields (default: enabled).",
    )
    ap.add_argument(
        "--capture-native-provenance",
        dest="capture_native_provenance",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Capture native binary sha/version provenance fields (default: enabled).",
    )
    ap.add_argument(
        "--include-absolute-paths",
        action="store_true",
        help="Include absolute paths in metadata (default: redacted portable metadata).",
    )
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def _build_payload(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    command_payload: Sequence[str],
    env_subset: Mapping[str, str],
    input_files: Sequence[Mapping[str, Any]],
    run_log_path: Path,
    returncode: int,
    include_absolute_paths: bool,
    external_code: Mapping[str, Any],
) -> Dict[str, Any]:
    env_payload: Dict[str, str] = {}
    for key in sorted(env_subset.keys()):
        value = str(env_subset[key])
        env_payload[str(key)] = value if include_absolute_paths else _redact_absolute_path_token(value)

    return {
        "tool": TOOL_NAME,
        "schema": SCHEMA_NAME,
        "created_utc": str(args.created_utc),
        "paths_redacted": not bool(include_absolute_paths),
        "code": str(args.code),
        "runner": str(args.runner),
        "command_argv": command_payload,
        "environment": env_payload,
        "platform": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
        },
        "run_dir": ".",
        "run_log": str(run_log_path.name),
        "returncode": int(returncode),
        "input_files": list(input_files),
        "external_code": dict(external_code),
    }


def _render_text(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"tool={payload.get('tool')}")
    lines.append(f"schema={payload.get('schema')}")
    lines.append(f"created_utc={payload.get('created_utc')}")
    lines.append(f"code={payload.get('code')}")
    lines.append(f"runner={payload.get('runner')}")
    lines.append(f"run_dir={payload.get('run_dir')}")
    lines.append(f"run_log={payload.get('run_log')}")
    lines.append(f"returncode={payload.get('returncode')}")
    lines.append("command_argv=" + json.dumps(payload.get("command_argv") or [], ensure_ascii=True, separators=(",", ":")))
    lines.append("input_files=" + str(len(payload.get("input_files") or [])))
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        args.created_utc = created_utc

        export_pack = Path(str(args.export_pack)).expanduser().resolve()
        run_dir = Path(str(args.run_dir)).expanduser().resolve()

        if not export_pack.is_dir():
            raise HarnessUsageError(f"--export-pack must be an existing directory: {export_pack}")

        _prepare_run_dir(run_dir, overwrite=bool(args.overwrite))
        template_path, input_files = _copy_inputs(
            export_pack=export_pack,
            run_dir=run_dir,
            code=str(args.code),
            include_absolute_paths=bool(args.include_absolute_paths),
        )
        command_argv, env_subset, runtime_info = _build_command(
            code=str(args.code),
            runner=str(args.runner),
            template_path=template_path,
            run_dir=run_dir,
            explicit_bin=args.bin,
        )
        external_code = _capture_external_code_provenance(
            code=str(args.code),
            runner=str(args.runner),
            run_dir=run_dir,
            include_absolute_paths=bool(args.include_absolute_paths),
            runtime_info=runtime_info,
            require_pinned_image=bool(args.require_pinned_image),
            capture_docker_provenance=bool(args.capture_docker_provenance),
            capture_native_provenance=bool(args.capture_native_provenance),
        )

        proc = _run_external_command(command_argv, cwd=run_dir)
        include_absolute_paths = bool(args.include_absolute_paths)
        command_payload = _normalize_command_argv(
            command_argv=command_argv,
            run_dir=run_dir,
            include_absolute_paths=include_absolute_paths,
        )
        stdout_for_log = _sanitize_stream_for_portable(
            text=str(proc.stdout or ""),
            run_dir=run_dir,
            include_absolute_paths=include_absolute_paths,
        )
        stderr_for_log = _sanitize_stream_for_portable(
            text=str(proc.stderr or ""),
            run_dir=run_dir,
            include_absolute_paths=include_absolute_paths,
        )
        run_log = run_dir / "run.log"
        _write_text(
            run_log,
            _render_run_log(
                created_utc=created_utc,
                code=str(args.code),
                runner=str(args.runner),
                paths_redacted=not include_absolute_paths,
                command_argv=command_payload,
                returncode=int(proc.returncode),
                stdout=stdout_for_log,
                stderr=stderr_for_log,
            ),
        )

        payload = _build_payload(
            args=args,
            run_dir=run_dir,
            command_payload=command_payload,
            env_subset=env_subset,
            input_files=input_files,
            run_log_path=run_log,
            returncode=int(proc.returncode),
            include_absolute_paths=include_absolute_paths,
            external_code=external_code,
        )
        if include_absolute_paths:
            payload["run_dir_abs"] = str(run_dir.resolve())
        _write_json(run_dir / "RUN_METADATA.json", payload)

    except HarnessGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except HarnessUsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if str(args.format) == "json":
        sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    else:
        sys.stdout.write(_render_text(payload))

    if int(payload.get("returncode", 1)) != 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
