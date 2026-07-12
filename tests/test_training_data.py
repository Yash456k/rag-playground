from __future__ import annotations

import json
from pathlib import Path

from training.data import load_and_validate

PROJECT_ROOT = Path(__file__).parents[1]


def test_training_splits_cover_locked_current_corpus() -> None:
    bundle = load_and_validate(PROJECT_ROOT)

    assert len(bundle.chunks) == 17
    assert len(bundle.train) == 102
    assert len(bundle.dev) == 62
    assert len(bundle.locked_holdout) == 16
    assert {record["positive_chunk_id"] for record in bundle.train} == set(bundle.chunks)
    assert bundle.hashes["corpus_chunks_sha256"] == (
        "b8574d3306981fe2e39da36f43aa5b7443d7555101a49af23a0e9bbb3fbf8669"
    )


def test_training_recipes_pin_losses_revisions_prefixes_and_export_paths() -> None:
    raw = json.loads((PROJECT_ROOT / "training" / "recipes.json").read_text(encoding="utf-8"))
    recipes = {recipe["id"]: recipe for recipe in raw["models"]}

    e5 = recipes["e5-small-v2"]
    assert e5["base_revision"] == "ffb93f3bd4047442299a41ebb6fa998a38507c52"
    assert e5["loss"] == "MultipleNegativesRankingLoss"
    assert e5["batch_sampler"] == "no_duplicates"
    assert e5["include_hard_negatives"] is False
    assert (e5["query_prefix"], e5["document_prefix"]) == ("query: ", "passage: ")
    assert e5["output_directory"] == "portfolio-e5-small-v1"

    gte = recipes["gte-small"]
    assert gte["base_revision"] == "17e1f347d17fe144873b1201da91788898c639cd"
    assert gte["loss"] == "MultipleNegativesRankingLoss"
    assert gte["batch_sampler"] == "no_duplicates"
    assert gte["include_hard_negatives"] is True
    assert (gte["query_prefix"], gte["document_prefix"]) == ("", "")
    assert gte["output_directory"] == "portfolio-gte-small-v1"
