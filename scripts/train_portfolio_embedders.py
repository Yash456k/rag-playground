from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.data import DatasetBundle, load_and_validate, sha256_file  # noqa: E402


@dataclass(frozen=True)
class Recipe:
    id: str
    base_model: str
    base_revision: str
    output_directory: str
    loss: str
    batch_sampler: str
    query_prefix: str
    document_prefix: str
    include_hard_negatives: bool
    epochs: int
    batch_size: int
    learning_rate: float
    weight_decay: float
    warmup_ratio: float
    max_grad_norm: float
    max_sequence_length: int
    acceptance_gates: dict[str, float]
    triplet_margin: float | None = None
    contrastive_margin: float | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Recipe:
        return cls(**value)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_recipes(repo_root: Path) -> tuple[int, list[Recipe], str]:
    path = repo_root / "training" / "recipes.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise ValueError("training/recipes.json has an unsupported schema version")
    seed = raw.get("seed")
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("training seed must be a non-negative integer")
    recipes = [Recipe.from_dict(value) for value in raw.get("models", [])]
    if {recipe.id for recipe in recipes} != {"e5-small-v2", "gte-small"}:
        raise ValueError("recipes must define exactly e5-small-v2 and gte-small")
    if any(len(recipe.base_revision) != 40 for recipe in recipes):
        raise ValueError("every base model must use a full 40-character revision")
    return seed, recipes, sha256_file(path)


def _set_determinism(seed: int) -> None:
    import numpy as np
    import torch
    from transformers import enable_full_determinism

    os.environ["PYTHONHASHSEED"] = str(seed)
    enable_full_determinism(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False


def _state_dict_sha256(model: Any) -> str:
    import torch

    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value = tensor.detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(json.dumps(list(value.shape), separators=(",", ":")).encode("ascii"))
        digest.update(value.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _evaluate_retrieval(
    model: Any,
    *,
    chunks: dict[str, str],
    dev: list[dict[str, Any]],
    query_prefix: str,
    document_prefix: str,
    batch_size: int,
) -> dict[str, Any]:
    import numpy as np

    chunk_ids = sorted(chunks)
    passages = [f"{document_prefix}{chunks[chunk_id]}" for chunk_id in chunk_ids]
    questions = [f"{query_prefix}{record['question']}" for record in dev]
    document_embeddings = model.encode(
        passages,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    query_embeddings = model.encode(
        questions,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    similarities = np.matmul(query_embeddings, document_embeddings.T)

    reciprocal_ranks: list[float] = []
    ranks: list[int] = []
    details: list[dict[str, Any]] = []
    for row_index, record in enumerate(dev):
        ordering = np.argsort(-similarities[row_index], kind="stable")
        relevant = set(record["relevant_chunk_ids"])
        rank = next(
            rank_index
            for rank_index, candidate_index in enumerate(ordering.tolist(), start=1)
            if chunk_ids[candidate_index] in relevant
        )
        ranks.append(rank)
        reciprocal_ranks.append(1.0 / rank)
        details.append(
            {
                "id": record["id"],
                "best_relevant_rank": rank,
                "top_5": [
                    {
                        "chunk_id": chunk_ids[candidate_index],
                        "score": round(float(similarities[row_index, candidate_index]), 8),
                    }
                    for candidate_index in ordering[:5]
                ],
            }
        )

    count = len(dev)
    return {
        "question_count": count,
        "recall_at_1": sum(rank <= 1 for rank in ranks) / count,
        "recall_at_3": sum(rank <= 3 for rank in ranks) / count,
        "recall_at_5": sum(rank <= 5 for rank in ranks) / count,
        "mrr": sum(reciprocal_ranks) / count,
        "mean_rank": sum(ranks) / count,
        "per_question": details,
    }


def _build_train_dataset(recipe: Recipe, bundle: DatasetBundle) -> Any:
    from datasets import Dataset

    if recipe.loss == "MultipleNegativesRankingLoss":
        rows = []
        for record in bundle.train:
            row = {
                "anchor": f"{recipe.query_prefix}{record['question']}",
                "positive": (
                    f"{recipe.document_prefix}{bundle.chunks[record['positive_chunk_id']]}"
                ),
            }
            if recipe.include_hard_negatives:
                row["negative"] = (
                    f"{recipe.document_prefix}"
                    f"{bundle.chunks[record['hard_negative_chunk_id']]}"
                )
            rows.append(row)
    elif recipe.loss == "BatchAllTripletLoss":
        chunk_labels = {chunk_id: index for index, chunk_id in enumerate(sorted(bundle.chunks))}
        rows = [
            {
                "sentence": f"{recipe.document_prefix}{content}",
                "label": chunk_labels[chunk_id],
            }
            for chunk_id, content in sorted(bundle.chunks.items())
        ]
        rows.extend(
            {
                "sentence": f"{recipe.query_prefix}{record['question']}",
                "label": chunk_labels[record["positive_chunk_id"]],
            }
            for record in bundle.train
        )
    elif recipe.loss == "ContrastiveLoss":
        rows = []
        for record in bundle.train:
            anchor = f"{recipe.query_prefix}{record['question']}"
            rows.extend(
                [
                    {
                        "sentence1": anchor,
                        "sentence2": (
                            f"{recipe.document_prefix}"
                            f"{bundle.chunks[record['positive_chunk_id']]}"
                        ),
                        "label": 1.0,
                    },
                    {
                        "sentence1": anchor,
                        "sentence2": (
                            f"{recipe.document_prefix}"
                            f"{bundle.chunks[record['hard_negative_chunk_id']]}"
                        ),
                        "label": 0.0,
                    },
                ]
            )
    elif recipe.loss == "TripletLoss":
        rows = [
            {
                "anchor": f"{recipe.query_prefix}{record['question']}",
                "positive": (
                    f"{recipe.document_prefix}{bundle.chunks[record['positive_chunk_id']]}"
                ),
                "negative": (
                    f"{recipe.document_prefix}{bundle.chunks[record['hard_negative_chunk_id']]}"
                ),
            }
            for record in bundle.train
        ]
    else:
        raise ValueError(f"unsupported training loss: {recipe.loss}")
    return Dataset.from_list(rows)


def _artifact_checksums(artifact_dir: Path) -> dict[str, Any]:
    files = {
        path.relative_to(artifact_dir).as_posix(): sha256_file(path)
        for path in sorted(artifact_dir.rglob("*"))
        if path.is_file() and path.name != "training-manifest.json"
    }
    safetensors = sorted(path for path in files if path.endswith(".safetensors"))
    legacy_bins = sorted(path for path in files if path.endswith((".bin", ".pt", ".pth")))
    if not safetensors:
        raise RuntimeError("export did not contain a safetensors weight file")
    if legacy_bins:
        raise RuntimeError(f"export unexpectedly contains legacy weight files: {legacy_bins}")
    return {
        "files": files,
        "tree_sha256": _canonical_hash(files),
        "safetensors_files": safetensors,
    }


def _acceptance_results(metrics: dict[str, Any], gates: dict[str, float]) -> dict[str, Any]:
    checks = {
        name: {
            "minimum": minimum,
            "actual": metrics[name],
            "passed": metrics[name] >= minimum,
        }
        for name, minimum in gates.items()
    }
    return {"passed": all(item["passed"] for item in checks.values()), "checks": checks}


def _promote_candidate(candidate: Path, destination: Path, *, overwrite: bool) -> None:
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"{destination} already exists; use --overwrite only after reviewing the prior manifest"
        )
    backup = destination.with_name(f".{destination.name}.previous")
    if backup.exists():
        shutil.rmtree(backup)
    if destination.exists():
        destination.rename(backup)
    try:
        candidate.rename(destination)
    except BaseException:
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _train_one(
    recipe: Recipe,
    *,
    seed: int,
    bundle: DatasetBundle,
    recipes_hash: str,
    output_root: Path,
    overwrite: bool,
) -> Path:
    import accelerate
    import datasets
    import safetensors
    import sentence_transformers
    import torch
    import transformers
    from sentence_transformers import (
        SentenceTransformer,
        SentenceTransformerTrainer,
        SentenceTransformerTrainingArguments,
    )
    from sentence_transformers.losses import (
        BatchAllTripletLoss,
        BatchHardTripletLossDistanceFunction,
        ContrastiveLoss,
        MultipleNegativesRankingLoss,
        TripletDistanceMetric,
        TripletLoss,
    )
    from sentence_transformers.training_args import BatchSamplers

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for portfolio embedder training")

    destination = output_root / recipe.output_directory
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"{destination} already exists; pass --overwrite to replace an accepted artifact"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    candidate_parent = Path(
        tempfile.mkdtemp(prefix=f".{recipe.output_directory}-", dir=output_root)
    )
    candidate = candidate_parent / "artifact"
    trainer_output = candidate_parent / "trainer"
    started_at = _utc_now()

    try:
        _set_determinism(seed)
        model = SentenceTransformer(
            recipe.base_model,
            revision=recipe.base_revision,
            device="cuda",
            trust_remote_code=False,
            model_kwargs={"use_safetensors": True},
        )
        model.max_seq_length = recipe.max_sequence_length
        base_state_sha256 = _state_dict_sha256(model)
        pre_metrics = _evaluate_retrieval(
            model,
            chunks=bundle.chunks,
            dev=bundle.dev,
            query_prefix=recipe.query_prefix,
            document_prefix=recipe.document_prefix,
            batch_size=recipe.batch_size,
        )
        train_dataset = _build_train_dataset(recipe, bundle)

        if recipe.loss == "MultipleNegativesRankingLoss":
            loss = MultipleNegativesRankingLoss(model)
            batch_sampler = BatchSamplers.NO_DUPLICATES
        elif recipe.loss == "BatchAllTripletLoss":
            loss = BatchAllTripletLoss(
                model,
                distance_metric=BatchHardTripletLossDistanceFunction.cosine_distance,
                margin=float(recipe.triplet_margin or 0.2),
            )
            batch_sampler = BatchSamplers.GROUP_BY_LABEL
        elif recipe.loss == "ContrastiveLoss":
            loss = ContrastiveLoss(
                model,
                margin=float(recipe.contrastive_margin or 0.5),
            )
            batch_sampler = BatchSamplers.BATCH_SAMPLER
        else:
            loss = TripletLoss(
                model,
                distance_metric=TripletDistanceMetric.COSINE,
                triplet_margin=float(recipe.triplet_margin),
            )
            batch_sampler = BatchSamplers.BATCH_SAMPLER

        arguments = SentenceTransformerTrainingArguments(
            output_dir=str(trainer_output),
            overwrite_output_dir=True,
            do_train=True,
            eval_strategy="no",
            save_strategy="no",
            logging_strategy="steps",
            logging_steps=1,
            report_to=[],
            disable_tqdm=False,
            seed=seed,
            data_seed=seed,
            full_determinism=True,
            per_device_train_batch_size=recipe.batch_size,
            num_train_epochs=recipe.epochs,
            learning_rate=recipe.learning_rate,
            weight_decay=recipe.weight_decay,
            warmup_ratio=recipe.warmup_ratio,
            max_grad_norm=recipe.max_grad_norm,
            lr_scheduler_type="linear",
            dataloader_num_workers=0,
            dataloader_drop_last=False,
            dataloader_pin_memory=True,
            fp16=False,
            bf16=False,
            tf32=False,
            batch_sampler=batch_sampler,
        )
        trainer = SentenceTransformerTrainer(
            model=model,
            args=arguments,
            train_dataset=train_dataset,
            loss=loss,
        )
        result = trainer.train()
        optimizer_steps = int(trainer.state.global_step)
        if optimizer_steps <= 0:
            raise RuntimeError("trainer completed without an optimizer step")

        trained_state_sha256 = _state_dict_sha256(model)
        if trained_state_sha256 == base_state_sha256:
            raise RuntimeError("trained state checksum equals the base state checksum")
        post_metrics = _evaluate_retrieval(
            model,
            chunks=bundle.chunks,
            dev=bundle.dev,
            query_prefix=recipe.query_prefix,
            document_prefix=recipe.document_prefix,
            batch_size=recipe.batch_size,
        )
        acceptance = _acceptance_results(post_metrics, recipe.acceptance_gates)
        metric_report = {
            "model_id": recipe.id,
            "base_revision": recipe.base_revision,
            "pre_training_dev": pre_metrics,
            "post_training_dev": post_metrics,
            "acceptance": acceptance,
            "optimizer_steps": optimizer_steps,
        }
        print(json.dumps(metric_report, indent=2, sort_keys=True))
        if not acceptance["passed"]:
            failure_dir = REPO_ROOT / "output" / "training-reports"
            failure_dir.mkdir(parents=True, exist_ok=True)
            (failure_dir / f"{recipe.id}-latest-failed.json").write_text(
                json.dumps(metric_report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            raise RuntimeError(f"{recipe.id} failed retrieval acceptance gates: {acceptance}")

        candidate.mkdir(parents=True)
        model.save_pretrained(str(candidate), safe_serialization=True)
        artifacts = _artifact_checksums(candidate)
        manifest = {
            "schema_version": 1,
            "model_id": recipe.id,
            "base_model": recipe.base_model,
            "base_revision": recipe.base_revision,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "training_device": "cuda",
            "cuda_device_name": torch.cuda.get_device_name(0),
            "seed": seed,
            "loss": recipe.loss,
            "optimizer_steps": optimizer_steps,
            "train_examples": len(bundle.train),
            "dev_examples": len(bundle.dev),
            "locked_holdout_examples": len(bundle.locked_holdout),
            "locked_holdout_used_for_training": False,
            "locked_holdout_used_for_evaluation": False,
            "hyperparameters": {
                "batch_sampler": recipe.batch_sampler,
                "epochs": recipe.epochs,
                "batch_size": recipe.batch_size,
                "learning_rate": recipe.learning_rate,
                "weight_decay": recipe.weight_decay,
                "warmup_ratio": recipe.warmup_ratio,
                "max_grad_norm": recipe.max_grad_norm,
                "max_sequence_length": recipe.max_sequence_length,
                "triplet_margin": recipe.triplet_margin,
                "contrastive_margin": recipe.contrastive_margin,
                "query_prefix": recipe.query_prefix,
                "document_prefix": recipe.document_prefix,
                "include_hard_negatives": recipe.include_hard_negatives,
            },
            "dataset_hashes": bundle.hashes,
            "recipes_file_sha256": recipes_hash,
            "base_state_dict_sha256": base_state_sha256,
            "trained_state_dict_sha256": trained_state_sha256,
            "state_dict_changed": True,
            "retrieval_metrics": {
                "pre_training_dev": pre_metrics,
                "post_training_dev": post_metrics,
            },
            "acceptance": acceptance,
            "train_runtime_metrics": result.metrics,
            "training_log_history": trainer.state.log_history,
            "software": {
                "python": platform.python_version(),
                "torch": torch.__version__,
                "sentence_transformers": sentence_transformers.__version__,
                "transformers": transformers.__version__,
                "datasets": datasets.__version__,
                "accelerate": accelerate.__version__,
                "safetensors": safetensors.__version__,
            },
            "artifacts": artifacts,
        }
        (candidate / "training-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _promote_candidate(candidate, destination, overwrite=overwrite)
        return destination
    finally:
        if candidate_parent.exists():
            shutil.rmtree(candidate_parent)
        for name in ("trainer", "model", "loss", "train_dataset"):
            if name in locals():
                del locals()[name]
        gc.collect()
        torch.cuda.empty_cache()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune and export the two portfolio retrieval embedders"
    )
    parser.add_argument(
        "--model",
        choices=("all", "e5-small-v2", "gte-small"),
        default="all",
        help="Train both models sequentially (default), or one named recipe.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "model-artifacts",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Atomically replace an existing accepted artifact after the new candidate passes gates."
        ),
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help=(
            "Validate recipes, exact corpus chunk coverage, split isolation, "
            "and hashes without CUDA."
        ),
    )
    args = parser.parse_args()

    seed, recipes, recipes_hash = _load_recipes(REPO_ROOT)
    bundle = load_and_validate(REPO_ROOT)
    print(
        json.dumps(
            {
                "status": "validated",
                "seed": seed,
                "corpus_chunks": len(bundle.chunks),
                "train_examples": len(bundle.train),
                "dev_examples": len(bundle.dev),
                "locked_holdout_examples": len(bundle.locked_holdout),
                "dataset_hashes": bundle.hashes,
                "recipes_file_sha256": recipes_hash,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate_only:
        return

    selected = recipes if args.model == "all" else [r for r in recipes if r.id == args.model]
    for index, recipe in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] training {recipe.id} from pinned {recipe.base_revision}")
        destination = _train_one(
            recipe,
            seed=seed,
            bundle=bundle,
            recipes_hash=recipes_hash,
            output_root=args.output_root.resolve(),
            overwrite=args.overwrite,
        )
        print(f"accepted artifact: {destination}")
        # The training frame has returned, so model tensors are no longer referenced.
        # Release allocator cache before loading the next model in this same process.
        import torch

        gc.collect()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
