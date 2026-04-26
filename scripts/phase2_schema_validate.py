#!/usr/bin/env python3
"""Validate JSON payloads against Phase-2 JSON schemas (stdlib-first)."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


SCHEMA_NAME = "phase2_schema_validate_v1"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to parse JSON from {path}: {exc}") from exc


def _type_ok(value: Any, type_name: str) -> bool:
    if type_name == "object":
        return isinstance(value, Mapping)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "null":
        return value is None
    return True


def _validate_minimal(
    data: Any,
    schema: Mapping[str, Any],
    *,
    strict: bool,
    path: str,
    errors: List[str],
) -> None:
    if len(errors) >= 200:
        return

    if "const" in schema and data != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
        return

    if "enum" in schema:
        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and data not in enum_values:
            errors.append(f"{path}: value {data!r} not in enum")
            return

    type_spec = schema.get("type")
    if isinstance(type_spec, str):
        if not _type_ok(data, type_spec):
            errors.append(f"{path}: expected type {type_spec}, got {type(data).__name__}")
            return
    elif isinstance(type_spec, list):
        if not any(isinstance(t, str) and _type_ok(data, t) for t in type_spec):
            errors.append(f"{path}: expected one of types {type_spec}, got {type(data).__name__}")
            return

    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and any_of:
        branch_ok = False
        branch_errors: List[str] = []
        for idx, sub in enumerate(any_of):
            if not isinstance(sub, Mapping):
                continue
            local_errors: List[str] = []
            _validate_minimal(data, sub, strict=strict, path=path, errors=local_errors)
            if not local_errors:
                branch_ok = True
                break
            branch_errors.append(f"branch {idx}: {local_errors[0]}")
        if not branch_ok:
            detail = "; ".join(branch_errors[:3]) or "no branch matched"
            errors.append(f"{path}: anyOf failed ({detail})")
            return

    one_of = schema.get("oneOf")
    if isinstance(one_of, list) and one_of:
        matches = 0
        for sub in one_of:
            if not isinstance(sub, Mapping):
                continue
            local_errors: List[str] = []
            _validate_minimal(data, sub, strict=strict, path=path, errors=local_errors)
            if not local_errors:
                matches += 1
        if matches != 1:
            errors.append(f"{path}: oneOf failed (matched {matches} branches)")
            return

    all_of = schema.get("allOf")
    if isinstance(all_of, list) and all_of:
        for sub in all_of:
            if not isinstance(sub, Mapping):
                continue
            _validate_minimal(data, sub, strict=strict, path=path, errors=errors)
            if len(errors) >= 200:
                return

    if isinstance(data, Mapping):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                key_str = str(key)
                if key_str not in data:
                    errors.append(f"{path}: missing required key '{key_str}'")
                    if len(errors) >= 200:
                        return

        properties = schema.get("properties")
        known_keys = set()
        if isinstance(properties, Mapping):
            for key in sorted(str(k) for k in properties.keys()):
                known_keys.add(key)
                if key not in data:
                    continue
                subschema = properties.get(key)
                if isinstance(subschema, Mapping):
                    _validate_minimal(
                        data.get(key),
                        subschema,
                        strict=strict,
                        path=f"{path}.{key}",
                        errors=errors,
                    )
                    if len(errors) >= 200:
                        return

        additional = schema.get("additionalProperties", True)
        strict_unknown = bool(strict)
        if strict_unknown and isinstance(properties, Mapping):
            for key in sorted(str(k) for k in data.keys()):
                if key in known_keys:
                    continue
                errors.append(f"{path}: unknown key '{key}'")
                if len(errors) >= 200:
                    return
        elif isinstance(properties, Mapping):
            for key in sorted(str(k) for k in data.keys()):
                if key in known_keys:
                    continue
                if additional is False:
                    errors.append(f"{path}: unknown key '{key}'")
                    if len(errors) >= 200:
                        return
                elif isinstance(additional, Mapping):
                    _validate_minimal(
                        data.get(key),
                        additional,
                        strict=strict,
                        path=f"{path}.{key}",
                        errors=errors,
                    )
                    if len(errors) >= 200:
                        return

    if isinstance(data, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for idx, item in enumerate(data):
                _validate_minimal(item, item_schema, strict=strict, path=f"{path}[{idx}]", errors=errors)
                if len(errors) >= 200:
                    return


def _tighten_additional_properties(schema: Any) -> Any:
    if isinstance(schema, Mapping):
        out: Dict[str, Any] = {}
        for key in sorted(str(k) for k in schema.keys()):
            out[key] = _tighten_additional_properties(schema[key])
        type_value = out.get("type")
        props = out.get("properties")
        if (type_value == "object" or (isinstance(type_value, list) and "object" in type_value)) and isinstance(props, Mapping):
            out["additionalProperties"] = False
        return out
    if isinstance(schema, list):
        return [_tighten_additional_properties(item) for item in schema]
    return schema


def _validate_with_jsonschema(data: Any, schema: Mapping[str, Any], *, strict: bool) -> List[str]:
    try:
        import jsonschema  # type: ignore
    except Exception:
        return ["JSONSCHEMA_IMPORT_FAILED"]

    use_schema: Mapping[str, Any] = schema
    if strict:
        use_schema = _tighten_additional_properties(copy.deepcopy(schema))

    validator = jsonschema.Draft7Validator(use_schema)
    out: List[str] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path_parts = [str(p) for p in list(err.path)]
        jpath = "$"
        for p in path_parts:
            if p.isdigit():
                jpath += f"[{p}]"
            else:
                jpath += f".{p}"
        out.append(f"{jpath}: {err.message}")
        if len(out) >= 200:
            break
    return out


def _schema_aliases(schema_path: Path, payload: Mapping[str, Any]) -> List[str]:
    aliases: set[str] = set()

    name = schema_path.name
    if name.endswith(".schema.json"):
        aliases.add(name[: -len(".schema.json")])
    aliases.add(schema_path.stem)

    sid = payload.get("$id")
    if isinstance(sid, str) and sid.strip():
        sid_text = sid.strip()
        aliases.add(sid_text)
        sid_name = Path(sid_text).name
        if sid_name.endswith(".schema.json"):
            aliases.add(sid_name[: -len(".schema.json")])
        aliases.add(Path(sid_name).stem)

    props = payload.get("properties")
    if isinstance(props, Mapping):
        schema_prop = props.get("schema")
        if isinstance(schema_prop, Mapping):
            const_val = schema_prop.get("const")
            if isinstance(const_val, str) and const_val.strip():
                aliases.add(const_val.strip())
            enum_val = schema_prop.get("enum")
            if isinstance(enum_val, list):
                for item in enum_val:
                    if isinstance(item, str) and item.strip():
                        aliases.add(item.strip())

    return sorted(x for x in aliases if x)


def _load_schema_index(schema_dir: Path) -> Tuple[Dict[str, Path], List[str]]:
    if not schema_dir.is_dir():
        raise ValueError(f"schema dir not found: {schema_dir}")

    schema_files = sorted(
        p for p in schema_dir.glob("*.schema.json") if p.is_file()
    )
    if not schema_files:
        raise ValueError(f"no *.schema.json files found under: {schema_dir}")

    alias_map: Dict[str, Path] = {}
    collisions: Dict[str, List[str]] = {}
    for path in schema_files:
        payload = _load_json(path)
        if not isinstance(payload, Mapping):
            raise ValueError(f"schema root must be object: {path}")
        aliases = _schema_aliases(path, payload)
        for alias in aliases:
            prev = alias_map.get(alias)
            if prev is None:
                alias_map[alias] = path
                continue
            if prev != path:
                collisions.setdefault(alias, sorted({str(prev), str(path)}))

    if collisions:
        keys = sorted(collisions.keys())
        detail = ", ".join(f"{k}=>{collisions[k]}" for k in keys[:5])
        raise ValueError(f"schema alias collisions in {schema_dir}: {detail}")

    return alias_map, sorted(str(p) for p in schema_files)


def _resolve_schema_path(
    *,
    explicit_schema: Optional[str],
    auto: bool,
    schema_dir: Path,
    data_payload: Any,
) -> Tuple[Path, str, List[str]]:
    if explicit_schema is not None and str(explicit_schema).strip():
        schema_path = Path(str(explicit_schema)).expanduser().resolve()
        if not schema_path.is_file():
            raise ValueError(f"--schema file not found: {schema_path}")
        return schema_path, "explicit", []

    if not auto:
        raise ValueError("--schema is required unless --auto is set")

    if not isinstance(data_payload, Mapping):
        raise ValueError("--auto requires JSON root object with top-level 'schema' string")

    schema_id = data_payload.get("schema")
    if not isinstance(schema_id, str) or not schema_id.strip():
        raise ValueError("--auto requires top-level 'schema' string in JSON payload")
    schema_key = schema_id.strip()

    alias_map, files = _load_schema_index(schema_dir)
    schema_path = alias_map.get(schema_key)
    if schema_path is None:
        available = sorted(alias_map.keys())
        shown = ", ".join(available[:50])
        more = "" if len(available) <= 50 else f" (+{len(available) - 50} more)"
        raise ValueError(
            "unknown schema id for --auto: "
            f"{schema_key}; available aliases: {shown}{more}; schema_files={files}"
        )
    return schema_path, f"auto:{schema_key}", files


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate a JSON file against a JSON schema (stdlib-first).")
    ap.add_argument("--schema", required=False, help="Path to schema JSON file")
    ap.add_argument("--schema-dir", default="v11.0.0/schemas", help="Schema directory for --auto mode")
    ap.add_argument("--auto", action="store_true", help="Auto-select schema from JSON top-level 'schema' value")
    ap.add_argument("--json", required=True, help="Path to JSON payload file")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--strict", action="store_true", help="Fail on unknown object keys")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    json_path = Path(str(args.json)).expanduser().resolve()

    if not json_path.is_file():
        print(f"ERROR: --json file not found: {json_path}")
        return 2

    try:
        data_payload = _load_json(json_path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    schema_dir = Path(str(args.schema_dir)).expanduser().resolve()
    try:
        schema_path, selected_by, available_files = _resolve_schema_path(
            explicit_schema=args.schema,
            auto=bool(args.auto),
            schema_dir=schema_dir,
            data_payload=data_payload,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    try:
        schema_payload = _load_json(schema_path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    if not isinstance(schema_payload, Mapping):
        print(f"ERROR: schema root must be a JSON object: {schema_path}")
        return 2

    jsonschema_errors = _validate_with_jsonschema(data_payload, schema_payload, strict=bool(args.strict))
    used_engine = "jsonschema"
    errors: List[str]
    if jsonschema_errors and jsonschema_errors[0] == "JSONSCHEMA_IMPORT_FAILED":
        used_engine = "minimal"
        errors = []
        _validate_minimal(data_payload, schema_payload, strict=bool(args.strict), path="$", errors=errors)
    else:
        errors = jsonschema_errors

    payload = {
        "tool": SCHEMA_NAME,
        "ok": len(errors) == 0,
        "schema": str(schema_path),
        "schema_dir": str(schema_dir),
        "schema_selected_by": selected_by,
        "available_schema_files": list(available_files),
        "json": str(json_path),
        "strict": bool(args.strict),
        "engine": used_engine,
        "n_errors": len(errors),
        "errors": list(errors),
    }

    if str(args.format) == "json":
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        print(f"tool={payload['tool']}")
        print(f"engine={payload['engine']}")
        print(f"schema={payload['schema']}")
        print(f"schema_selected_by={payload['schema_selected_by']}")
        print(f"json={payload['json']}")
        print(f"strict={payload['strict']}")
        print(f"ok={payload['ok']}")
        print(f"n_errors={payload['n_errors']}")
        for err in errors[:200]:
            print(f"error={err}")

    return 0 if len(errors) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
