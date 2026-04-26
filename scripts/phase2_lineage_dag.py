#!/usr/bin/env python3
"""Build deterministic Phase-2 lineage DAG manifest from a bundle directory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


SCHEMA_NAME = "phase2_lineage_dag_v1"
MANIFEST_CANDIDATES: Tuple[str, ...] = (
    "manifest.json",
    "phase2_e2_manifest.json",
    "phase2_e2_manifest_v1.json",
)


class LineageError(Exception):
    """Lineage construction error."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_relpath(text: str) -> str:
    raw = str(text or "").strip().replace("\\", "/")
    if not raw:
        raise LineageError("empty path encountered while building lineage")
    path = str(PurePosixPath(raw))
    if path.startswith("/"):
        raise LineageError(f"absolute path not allowed in lineage references: {raw}")
    if path in {"", "."}:
        raise LineageError(f"invalid path in lineage references: {raw}")
    parts = PurePosixPath(path).parts
    if any(part == ".." for part in parts):
        raise LineageError(f"path traversal not allowed in lineage references: {raw}")
    return path


def _detect_manifest_relpath(bundle_dir: Path) -> str:
    for rel in MANIFEST_CANDIDATES:
        candidate = bundle_dir / rel
        if candidate.is_file():
            return rel
    wildcard = sorted(
        p.relative_to(bundle_dir).as_posix()
        for p in bundle_dir.glob("*manifest*.json")
        if p.is_file()
    )
    if wildcard:
        return wildcard[0]
    raise LineageError("bundle manifest not found (expected manifest.json or phase2_e2_manifest*.json)")


def _load_manifest(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LineageError(f"failed to parse manifest JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise LineageError("bundle manifest root must be an object")
    return payload


def _iter_manifest_refs(manifest: Mapping[str, Any], field_name: str) -> Iterable[str]:
    value = manifest.get(field_name)
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, Mapping):
                continue
            raw = item.get("path", item.get("relpath", item.get("file")))
            if raw is None:
                continue
            yield str(raw)
    elif isinstance(value, Mapping):
        for key in sorted(str(k) for k in value.keys()):
            yield str(key)


def _to_bundle_relpath(raw: str, *, bundle_dir: Path) -> Optional[str]:
    text = str(raw or "").strip().replace("\\", "/")
    if not text:
        return None
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        try:
            rel = candidate.resolve().relative_to(bundle_dir.resolve()).as_posix()
            return _normalize_relpath(rel)
        except Exception:
            return None
    rel = _normalize_relpath(text)
    if (bundle_dir / rel).is_file():
        return rel
    return None


def _classify_type(relpath: str) -> str:
    rel = _normalize_relpath(relpath)
    name = PurePosixPath(rel).name.lower()
    rel_low = rel.lower()

    if name in {"manifest.json", "phase2_e2_manifest.json", "phase2_e2_manifest_v1.json"}:
        return "bundle_manifest"
    if name == "lineage.json":
        return "lineage_manifest"
    if name == "bundle_meta.json":
        return "bundle_meta"
    if "scan_config" in name:
        return "scan_config"
    if name in {"plan.json", "refine_plan.json"} or (name.endswith(".json") and "plan" in name):
        if "reviewer" in name:
            return "reviewer_pack_plan"
        return "plan"
    if name == "paper_assets_manifest.json":
        return "paper_assets_manifest"
    if name.endswith(".jsonl") or name.endswith(".jsonl.gz"):
        if "merged" in name:
            return "merged_jsonl"
        if "shard" in name:
            return "shard_jsonl"
        return "jsonl"
    if rel_low.endswith(".json"):
        return "json"
    return "file"


def _build_nodes(bundle_dir: Path, relpaths: Iterable[str]) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for rel in sorted(set(_normalize_relpath(x) for x in relpaths)):
        if rel in seen:
            continue
        seen.add(rel)
        abs_path = (bundle_dir / rel).resolve()
        if not abs_path.is_file():
            raise LineageError(f"referenced file missing for lineage node: {rel}")
        nodes.append(
            {
                "id": rel,
                "type": _classify_type(rel),
                "path": rel,
                "sha256": _sha256_file(abs_path),
                "bytes": int(abs_path.stat().st_size),
            }
        )
    return nodes


def _add_edge(edges: Set[Tuple[str, str, str]], src: str, dst: str, relation: str, *, node_ids: Set[str]) -> None:
    if src in node_ids and dst in node_ids and src != dst:
        edges.add((src, dst, relation))


def _first_of_type(nodes: Sequence[Mapping[str, Any]], type_name: str) -> Optional[str]:
    candidates = sorted(str(n.get("id")) for n in nodes if str(n.get("type")) == type_name)
    return candidates[0] if candidates else None


def _all_of_type(nodes: Sequence[Mapping[str, Any]], type_name: str) -> List[str]:
    return sorted(str(n.get("id")) for n in nodes if str(n.get("type")) == type_name)


def _build_edges(
    *,
    nodes: Sequence[Mapping[str, Any]],
    manifest_relpath: str,
    manifest_inputs: Sequence[str],
    manifest_artifacts: Sequence[str],
) -> List[Dict[str, Any]]:
    node_ids: Set[str] = {str(n.get("id")) for n in nodes}
    edges_set: Set[Tuple[str, str, str]] = set()

    manifest_node = manifest_relpath

    for rel in sorted(set(_normalize_relpath(x) for x in manifest_inputs)):
        _add_edge(edges_set, rel, manifest_node, "input_to_manifest", node_ids=node_ids)
    for rel in sorted(set(_normalize_relpath(x) for x in manifest_artifacts)):
        _add_edge(edges_set, manifest_node, rel, "manifest_to_artifact", node_ids=node_ids)

    plan_nodes = _all_of_type(nodes, "plan")
    scan_cfg_nodes = _all_of_type(nodes, "scan_config")
    shard_nodes = _all_of_type(nodes, "shard_jsonl")
    merged_nodes = _all_of_type(nodes, "merged_jsonl")
    reviewer_plan_nodes = _all_of_type(nodes, "reviewer_pack_plan")
    paper_manifest_nodes = _all_of_type(nodes, "paper_assets_manifest")
    bundle_meta_nodes = _all_of_type(nodes, "bundle_meta")

    for scan_cfg in scan_cfg_nodes:
        if plan_nodes:
            _add_edge(edges_set, plan_nodes[0], scan_cfg, "plan_to_scan_config", node_ids=node_ids)

    if shard_nodes:
        if scan_cfg_nodes:
            for shard in shard_nodes:
                _add_edge(edges_set, scan_cfg_nodes[0], shard, "scan_config_to_shard", node_ids=node_ids)
        elif plan_nodes:
            for shard in shard_nodes:
                _add_edge(edges_set, plan_nodes[0], shard, "plan_to_shard", node_ids=node_ids)

    if merged_nodes and shard_nodes:
        for shard in shard_nodes:
            _add_edge(edges_set, shard, merged_nodes[0], "shard_to_merge", node_ids=node_ids)

    if merged_nodes:
        _add_edge(edges_set, merged_nodes[0], manifest_node, "merge_to_bundle_manifest", node_ids=node_ids)

    if bundle_meta_nodes:
        _add_edge(edges_set, manifest_node, bundle_meta_nodes[0], "bundle_manifest_to_meta", node_ids=node_ids)

    for rp in reviewer_plan_nodes:
        _add_edge(edges_set, manifest_node, rp, "bundle_to_reviewer_plan", node_ids=node_ids)

    for pm in paper_manifest_nodes:
        _add_edge(edges_set, manifest_node, pm, "bundle_to_paper_assets_manifest", node_ids=node_ids)

    edges_out: List[Dict[str, Any]] = []
    for idx, (src, dst, rel) in enumerate(sorted(edges_set, key=lambda t: (t[0], t[1], t[2])), start=1):
        edges_out.append(
            {
                "id": f"e{idx:04d}",
                "source": src,
                "target": dst,
                "relation": rel,
            }
        )
    return edges_out


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build deterministic LINEAGE.json DAG for Phase-2 bundles.")
    ap.add_argument("--bundle-dir", required=True, help="Bundle directory path")
    ap.add_argument("--out", default=None, help="Output LINEAGE.json path (default: <bundle-dir>/LINEAGE.json)")
    ap.add_argument("--created-utc", default=None, help="Optional deterministic timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    ap.add_argument(
        "--include-absolute-paths",
        action="store_true",
        help="Include absolute bundle directory path in payload (default: portable redacted mode).",
    )
    ap.add_argument("--format", choices=("json",), default="json")
    return ap.parse_args(argv)


def _normalize_created_utc(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not text.endswith("Z"):
        raise LineageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    return text


def _make_lineage(
    bundle_dir: Path,
    *,
    created_utc: Optional[str],
    include_absolute_paths: bool,
) -> Dict[str, Any]:
    if not bundle_dir.is_dir():
        raise LineageError(f"--bundle-dir must be a directory: {bundle_dir}")

    manifest_relpath = _detect_manifest_relpath(bundle_dir)
    manifest_path = bundle_dir / manifest_relpath
    manifest = _load_manifest(manifest_path)

    raw_input_refs = list(_iter_manifest_refs(manifest, "inputs"))
    raw_artifact_refs = list(_iter_manifest_refs(manifest, "artifacts"))
    input_relpaths = [
        rel for rel in (_to_bundle_relpath(x, bundle_dir=bundle_dir) for x in raw_input_refs) if rel is not None
    ]
    artifact_relpaths = [
        rel for rel in (_to_bundle_relpath(x, bundle_dir=bundle_dir) for x in raw_artifact_refs) if rel is not None
    ]
    if not artifact_relpaths and not input_relpaths:
        raw_file_refs = list(_iter_manifest_refs(manifest, "files"))
        artifact_relpaths = [
            rel for rel in (_to_bundle_relpath(x, bundle_dir=bundle_dir) for x in raw_file_refs) if rel is not None
        ]

    referenced: Set[str] = set()
    referenced.add(_normalize_relpath(manifest_relpath))
    for rel in input_relpaths:
        referenced.add(_normalize_relpath(rel))
    for rel in artifact_relpaths:
        referenced.add(_normalize_relpath(rel))

    for extra in ("bundle_meta.json", "paper_assets_manifest.json", "reviewer_pack_plan.json"):
        candidate = bundle_dir / extra
        if candidate.is_file():
            referenced.add(extra)
    paper_assets_manifest = bundle_dir / "paper_assets" / "paper_assets_manifest.json"
    if paper_assets_manifest.is_file():
        referenced.add("paper_assets/paper_assets_manifest.json")

    nodes = _build_nodes(bundle_dir, referenced)
    edges = _build_edges(
        nodes=nodes,
        manifest_relpath=_normalize_relpath(manifest_relpath),
        manifest_inputs=input_relpaths,
        manifest_artifacts=artifact_relpaths,
    )

    type_counts: Dict[str, int] = {}
    for node in nodes:
        kind = str(node.get("type", "unknown"))
        type_counts[kind] = type_counts.get(kind, 0) + 1

    payload: Dict[str, Any] = {
        "schema": SCHEMA_NAME,
        "bundle_dir": ".",
        "manifest_relpath": _normalize_relpath(manifest_relpath),
        "nodes": nodes,
        "edges": edges,
        "counts": {
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "node_types": {k: type_counts[k] for k in sorted(type_counts.keys())},
            "n_external_refs_skipped": int(
                max(0, len(raw_input_refs) - len(input_relpaths))
                + max(0, len(raw_artifact_refs) - len(artifact_relpaths))
            ),
        },
    }
    if bool(include_absolute_paths):
        payload["bundle_dir_abs"] = str(bundle_dir)
    if created_utc is not None:
        payload["created_utc"] = created_utc
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    bundle_dir = Path(str(args.bundle_dir)).expanduser().resolve()
    try:
        created_utc = _normalize_created_utc(args.created_utc)
        payload = _make_lineage(
            bundle_dir,
            created_utc=created_utc,
            include_absolute_paths=bool(args.include_absolute_paths),
        )
    except LineageError as exc:
        print(f"ERROR: {exc}")
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 1

    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"

    out_path = (
        Path(str(args.out)).expanduser().resolve()
        if args.out
        else (bundle_dir / "LINEAGE.json").resolve()
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")

    if str(args.format) == "json":
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
