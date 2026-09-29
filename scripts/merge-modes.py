#!/usr/bin/env python3
"""Merge generated custom_modes.yaml into an existing destination file.

Usage: merge-modes.py <generated-modes> <dest>

Merge semantics (mirrors src/merge.ts mergeModesYaml):
  - dest missing → write generated content as-is
  - dest exists  → replace entries with matching slug, keep foreign entries,
                    append new generated slugs (order: existing file first, then new)
  - malformed dest YAML → exit non-zero, do not modify dest
"""

from __future__ import annotations

import os
import sys

import yaml


def _slugs(modes: list[dict]) -> list[str]:
    return [m["slug"] for m in modes if "slug" in m]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: merge-modes.py <generated-modes> <dest>", file=sys.stderr)
        return 2

    gen_path, dest_path = argv[1], argv[2]

    try:
        with open(gen_path, encoding="utf-8") as fh:
            gen_data = yaml.safe_load(fh)
    except (FileNotFoundError, OSError) as exc:
        print(f"ERROR: cannot read generated modes file {gen_path}: {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"ERROR: malformed YAML in generated file {gen_path}: {exc}", file=sys.stderr)
        return 1

    gen_modes: list[dict] = gen_data.get("customModes", []) if gen_data else []

    try:
        with open(dest_path, encoding="utf-8") as fh:
            dest_data = yaml.safe_load(fh)
    except FileNotFoundError:
        # dest missing — write generated content as-is
        dest_dir = os.path.dirname(dest_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        with open(gen_path, encoding="utf-8") as src:
            content = src.read()
        with open(dest_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        slugs = _slugs(gen_modes)
        print(f"replaced=[] kept=[] added={slugs}")
        return 0
    except yaml.YAMLError as exc:
        print(f"ERROR: malformed YAML in {dest_path}: {exc}", file=sys.stderr)
        return 1

    raw_dest_modes = dest_data.get("customModes", []) if dest_data else []
    if not isinstance(raw_dest_modes, list):
        print(
            f"WARNING: customModes in {dest_path} is not a sequence "
            f"({type(raw_dest_modes).__name__}); replacing with generated modes only",
            file=sys.stderr,
        )
        dest_modes: list[dict] = []
    else:
        dest_modes = raw_dest_modes

    gen_slugs = {m["slug"] for m in gen_modes if "slug" in m}

    # Keep foreign entries (not in generated) in file order, then append generated.
    kept: list[dict] = []
    replaced: list[str] = []
    for entry in dest_modes:
        slug = entry.get("slug")
        if slug in gen_slugs:
            replaced.append(slug)
        else:
            kept.append(entry)

    kept_slugs = [m.get("slug", "?") for m in kept]

    # Build merged list: kept foreign entries first, then generated entries.
    merged = kept + gen_modes

    # Deduplicate by slug (keep first occurrence) — makes the script idempotent
    # for any duplicates that might already exist in the destination file.
    seen: set[str] = set()
    deduped: list[dict] = []
    for entry in merged:
        slug = entry.get("slug")
        if slug in seen:
            continue
        seen.add(slug)
        deduped.append(entry)
    merged = deduped

    added = [m.get("slug", "?") for m in gen_modes if m.get("slug") not in {s for s in _slugs(dest_modes)}]

    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    out_data = dict(dest_data) if dest_data else {}
    out_data["customModes"] = merged

    with open(dest_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(out_data, fh, sort_keys=False, allow_unicode=True)

    print(f"replaced={replaced} kept={kept_slugs} added={added}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
