"""Create or extend a local model catalog using live gateway metadata."""
import argparse
import copy
import json
import os
import tempfile
from pathlib import Path
from common import load_json, local_json, loopback_url

def merge_catalog(base, gateway, requested_models, *, initialize_native=False, display_names=None):
    models = base.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("Base catalog needs a nonempty models list.")
    if any(not isinstance(m, dict) for m in models):
        raise ValueError("Each catalog model must be an object.")
    native_ids = [m.get("slug") for m in models]
    if any(not isinstance(s, str) or not s for s in native_ids) or len(set(native_ids)) != len(native_ids):
        raise ValueError("Base model slugs must be nonempty and unique.")
    requested = [requested_models] if isinstance(requested_models, str) else list(requested_models)
    if not requested or any(not isinstance(m, str) or not m.strip() for m in requested):
        raise ValueError("Supply at least one nonempty model ID.")
    requested = list(dict.fromkeys(requested))
    names = dict(display_names or {})
    if set(names) - set(requested) or any(not isinstance(n, str) or not n.strip() for n in names.values()):
        raise ValueError("Display names must be nonempty and refer to requested model IDs.")
    candidates = gateway.get("data", gateway.get("models", []))
    if not isinstance(candidates, list) or any(not isinstance(m, dict) for m in candidates):
        raise ValueError("Gateway metadata needs a model list.")
    result = copy.deepcopy(base)
    # Only a fresh setup adapts native transport flags. Extensions preserve every old field.
    if initialize_native:
        for entry in result["models"]:
            entry["use_responses_lite"] = False
    existing = set(native_ids)
    for model in requested:
        if model in existing:
            continue
        matches = [m for m in candidates if m.get("id", m.get("slug")) == model]
        if len(matches) != 1:
            raise ValueError("Selected model is missing or duplicated in the live gateway catalog.")
        extra = copy.deepcopy(matches[0])
        required = ("display_name", "supported_reasoning_levels", "default_reasoning_level", "shell_type")
        if any(key not in extra for key in required):
            raise ValueError("Gateway metadata is not a Codex model catalog; inspect the installed gateway version.")
        extra["slug"] = model
        extra["visibility"] = "list"
        # Presence in the catalog does not validate multimodal capabilities or generation.
        extra["input_modalities"] = ["text"]
        extra["use_responses_lite"] = False
        if model in names:
            extra["display_name"] = names[model]
            extra["description"] = names[model] + " via the configured local gateway."
        result["models"].append(extra)
        existing.add(model)
    return result

def write_catalog(path, catalog, replace=False):
    path = Path(path).resolve()
    if path.exists() and not replace:
        raise FileExistsError("Output exists. Back it up and pass --replace to intentionally update it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".catalog-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(catalog, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if not replace and path.exists():
            raise FileExistsError("Output appeared during generation; refusing to overwrite.")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--native", type=Path, help="Fresh setup: adapt a native GPT snapshot for this gateway.")
    source.add_argument("--base-catalog", type=Path, help="Extend an existing catalog, preserving every existing field.")
    parser.add_argument("--gateway", default="http://127.0.0.1:51122")
    parser.add_argument("--model", required=True, action="append", help="Repeat for each qualified model ID to add.")
    parser.add_argument("--display-name", action="append", default=[], metavar="MODEL_ID=NAME",
                        help="Optional friendly name for a new entry. Existing entries are left unchanged.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    source_path = args.native or args.base_catalog
    if source_path.resolve() == args.output.resolve():
        parser.error("Output must not replace the input catalog. Generate a separate candidate first.")
    names = {}
    for value in args.display_name:
        model, separator, name = value.partition("=")
        if not separator or model not in args.model or not name.strip() or model in names:
            parser.error("Each --display-name must uniquely name a requested model as MODEL_ID=NAME.")
        names[model] = name.strip()
    gateway = local_json(loopback_url(args.gateway) + "/v1/models")
    base = load_json(source_path)
    result = merge_catalog(base, gateway, args.model, initialize_native=args.native is not None, display_names=names)
    write_catalog(args.output, result, args.replace)
    existing = {m["slug"] for m in base["models"]}
    print(json.dumps({"base_model_count": len(base["models"]),
                      "existing_entries_unchanged": args.base_catalog is not None,
                      "added_models": [m["slug"] for m in result["models"] if m["slug"] not in existing],
                      "output": str(args.output)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
