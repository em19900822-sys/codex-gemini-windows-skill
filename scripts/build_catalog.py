"""Build a local catalog from this computer's GPT cache and live gateway metadata."""
import argparse
import copy
import json
import os
import tempfile
from pathlib import Path
from common import load_json, local_json, loopback_url

def merge_catalog(native, gateway, model):
    models = native.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("Native cache needs a nonempty models list.")
    native_ids = [m.get("slug") for m in models]
    if any(not isinstance(s, str) or not s for s in native_ids) or len(set(native_ids)) != len(native_ids):
        raise ValueError("Native model slugs must be nonempty and unique.")
    if model in native_ids:
        raise ValueError("Selected Gemini ID already exists in the native snapshot; inspect its provenance.")
    candidates = gateway.get("data", gateway.get("models", []))
    matches = [m for m in candidates if m.get("id", m.get("slug")) == model]
    if len(matches) != 1:
        raise ValueError("Selected model is missing or duplicated in the live gateway catalog.")
    extra = copy.deepcopy(matches[0])
    required = ("display_name", "supported_reasoning_levels", "default_reasoning_level", "shell_type")
    if any(key not in extra for key in required):
        raise ValueError("Gateway metadata is not a Codex model catalog; inspect the installed gateway version.")
    extra["slug"] = model
    extra["visibility"] = "list"
    # This recipe validates text only. Do not advertise untested multimodal capabilities.
    extra["input_modalities"] = ["text"]
    extra["use_responses_lite"] = False
    result = copy.deepcopy(models)
    for entry in result:
        entry["use_responses_lite"] = False
    result.append(extra)
    return {"models": result}

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
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--gateway", default="http://127.0.0.1:51122")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.native.resolve() == args.output.resolve():
        parser.error("Output must not replace the native snapshot.")
    gateway = local_json(loopback_url(args.gateway) + "/v1/models")
    result = merge_catalog(load_json(args.native), gateway, args.model)
    write_catalog(args.output, result, args.replace)
    print(json.dumps({"native_models_preserved": len(result["models"]) - 1,
                      "added_model": args.model, "output": str(args.output)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
