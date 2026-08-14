from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import load_pipeline
from app.ingest import chunk_document, discover_documents
from evaluation.eval_lib import load_split, regex_matches


def remap_cases_to_chunks(
    cases: list[dict[str, Any]], chunks: list[dict[str, Any]]
) -> int:
    """Resolve reviewed evidence regexes against one concrete chunking mode."""
    changed = 0
    for case in cases:
        for group in case["required_evidence"]:
            for option in group["any_of"]:
                patterns = option.get("content_any_of", [])
                if not patterns:
                    raise RuntimeError(
                        f"{case['id']}: cannot remap index-only evidence for {option['source']}"
                    )
                indexes = sorted(
                    chunk["chunkIndex"]
                    for chunk in chunks
                    if chunk["source"] == option["source"]
                    and any(regex_matches(pattern, chunk["content"]) for pattern in patterns)
                )
                if not indexes:
                    raise RuntimeError(
                        f"{case['id']}: no chunk matches reviewed evidence in {option['source']}"
                    )
                if option.get("chunk_indexes") != indexes:
                    option["chunk_indexes"] = indexes
                    changed += 1
    return changed


def remap_split(split: str, *, repo_root: Path) -> tuple[dict, int]:
    pipeline = load_pipeline(repo_root / "config" / "pipeline.yaml")
    chunks = [
        {
            "source": chunk.source,
            "chunkIndex": chunk.index,
            "content": chunk.content,
        }
        for document in discover_documents(repo_root / "corpus")
        for chunk in chunk_document(document, pipeline)
    ]
    payload = load_split(
        split,
        repo_root / "evaluation",
        verify_lock=split != "heldout",
    )
    changed = remap_cases_to_chunks(payload["cases"], chunks)
    for case in payload["cases"]:
        case.pop("split", None)
    return payload, changed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remap reviewed evidence regexes to current production chunk indexes."
    )
    parser.add_argument("--split", choices=("dev", "heldout"), required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args()

    root = args.repo_root.resolve()
    payload, changed = remap_split(args.split, repo_root=root)
    result = {"split": args.split, "cases": len(payload["cases"]), "optionsChanged": changed}
    if args.write:
        target = root / "evaluation" / f"{args.split}.json"
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        result["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        if args.split == "heldout":
            lock = root / "evaluation" / "heldout.sha256"
            lock.write_text(f"{result['sha256']}  heldout.json\n", encoding="ascii")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
