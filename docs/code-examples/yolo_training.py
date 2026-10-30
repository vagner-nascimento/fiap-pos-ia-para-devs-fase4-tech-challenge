"""Prepare the local YOLO dataset and train a two-class object detector."""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT / "yolo_imagens_treinamento"
DATASET_ROOT = ROOT / "yolo_dataset"
DEFAULT_OUTPUT_ROOT = ROOT / "runs" / "yolo_training"
CLASS_NAMES = ("faixa_elastica", "halter")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def collect_examples() -> list[tuple[Path, Path, int]]:
    """Collect image/label pairs and assign the class from their source folder."""
    examples: list[tuple[Path, Path, int]] = []

    for class_id, class_name in enumerate(("FAIXA_ELASTICA", "HALTER")):
        class_root = SOURCE_ROOT / class_name
        if not class_root.is_dir():
            raise FileNotFoundError(f"Dataset directory not found: {class_root}")

        for image_path in sorted(class_root.iterdir()):
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            label_path = image_path.with_suffix(".txt")
            if not label_path.is_file():
                raise FileNotFoundError(
                    f"Missing YOLO label for image {image_path.name}: {label_path}"
                )
            examples.append((image_path, label_path, class_id))

    if not examples:
        raise ValueError(f"No images found in {SOURCE_ROOT}")
    return examples


def rewrite_labels(label_path: Path, destination: Path, class_id: int) -> None:
    """Copy a label file while replacing its source-local class with class_id."""
    lines = []
    for line_number, line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(
                f"Invalid YOLO label at {label_path}:{line_number}; expected 5 fields"
            )
        lines.append(" ".join([str(class_id), *fields[1:]]))
    destination.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def prepare_dataset(val_fraction: float, seed: int) -> Path:
    """Create a consolidated train/validation dataset with remapped class IDs."""
    examples = collect_examples()
    rng = random.Random(seed)
    by_class: dict[int, list[tuple[Path, Path, int]]] = {0: [], 1: []}
    for example in examples:
        by_class[example[2]].append(example)

    splits: dict[str, list[tuple[Path, Path, int]]] = {"train": [], "val": []}
    for class_examples in by_class.values():
        rng.shuffle(class_examples)
        val_count = max(1, round(len(class_examples) * val_fraction))
        splits["val"].extend(class_examples[:val_count])
        splits["train"].extend(class_examples[val_count:])

    if DATASET_ROOT.exists():
        shutil.rmtree(DATASET_ROOT)

    for split, split_examples in splits.items():
        image_dir = DATASET_ROOT / "images" / split
        label_dir = DATASET_ROOT / "labels" / split
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        for image_path, label_path, class_id in split_examples:
            destination_image = image_dir / image_path.name
            shutil.copy2(image_path, destination_image)
            rewrite_labels(label_path, label_dir / label_path.name, class_id)

    data_yaml = DATASET_ROOT / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {DATASET_ROOT.as_posix()}",
                "train: images/train",
                "val: images/val",
                "",
                f"names: {list(CLASS_NAMES)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return data_yaml


def train(
    model_name: str,
    epochs: int,
    image_size: int,
    batch_size: int,
    val_fraction: float,
    seed: int,
    output_root: Path,
) -> None:
    """Prepare the dataset and train the YOLO model."""
    data_yaml = prepare_dataset(val_fraction, seed)
    model = YOLO(model_name)
    model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=image_size,
        batch=batch_size,
        project=str(output_root),
        name="two_objects",
        seed=seed,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    if not 0 < args.val_fraction < 1:
        parser.error("--val-fraction must be between 0 and 1")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    train(
        model_name=arguments.model,
        epochs=arguments.epochs,
        image_size=arguments.imgsz,
        batch_size=arguments.batch,
        val_fraction=arguments.val_fraction,
        seed=arguments.seed,
        output_root=arguments.output,
    )