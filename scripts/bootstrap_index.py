"""One-shot embedder for sample documents.

This utility encodes all Markdown files in a directory using a
Sentence-Transformers model and persists two artifacts:
  1) embeddings.npy  — NumPy array of shape (N, D)
  2) ids.json        — List[str] of document identifiers ("doc_{i}")

Why:
  - Keeps an inspectable snapshot of vectors for debugging and QA.
  - Decouples embedding from runtime to speed up demos.

Usage:
  # Default paths (data/sample_docs)
  python scripts/bootstrap_index.py

  # Custom directory/model/output
  python scripts/bootstrap_index.py \
    --data-dir data/sample_docs \
    --model sentence-transformers/all-MiniLM-L6-v2 \
    --emb-file data/sample_docs/embeddings.npy \
    --ids-file data/sample_docs/ids.json \
    --normalize
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer


# -----------------------------------------------------------------------------
# CLI / Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap-embedder")


# -----------------------------------------------------------------------------
# Core helpers
# -----------------------------------------------------------------------------
def find_markdown_files(root: Path) -> List[Path]:
    """Discover Markdown files under a directory (non-recursive).

    Args:
      root: Directory containing `.md` files.

    Returns:
      Sorted list of absolute file paths.

    Raises:
      FileNotFoundError: If `root` does not exist or is not a directory.
    """
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")
    files = sorted(p for p in root.iterdir() if p.suffix.lower() == ".md")
    return files


def load_docs(files: List[Path]) -> Tuple[List[str], List[str]]:
    """Load documents from disk and generate stable IDs.

    Args:
      files: List of `.md` files (sorted externally).

    Returns:
      A tuple (docs, ids) where:
        - docs: List of file contents (UTF-8).
        - ids:  List of stable identifiers (e.g., "doc_0", "doc_1", ...).
    """
    docs: List[str] = []
    ids: List[str] = []
    for i, fp in enumerate(files):
        with fp.open("r", encoding="utf-8") as f:
            docs.append(f.read())
        ids.append(f"doc_{i}")
    return docs, ids


def embed_docs(
    docs: List[str],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    normalize: bool = False,
) -> np.ndarray:
    """Encode documents with a Sentence-Transformers model.

    Args:
      docs: List of raw document strings to embed.
      model_name: Hugging Face model identifier.
      normalize: If True, L2-normalize embeddings in-place.

    Returns:
      NumPy array of shape (N, D) with dtype float32.
    """
    model = SentenceTransformer(model_name)
    embs: np.ndarray = model.encode(docs, convert_to_numpy=True)
    if normalize:
        # Safe in-place normalization (avoid div by zero).
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        embs = embs / norms
    return embs.astype(np.float32, copy=False)


def save_artifacts(embs: np.ndarray, ids: List[str], emb_path: Path, ids_path: Path) -> None:
    """Persist embeddings and IDs to disk.

    Args:
      embs: Embedding matrix (N, D).
      ids:  Parallel list of string identifiers of length N.
      emb_path: Output path for `.npy` file.
      ids_path: Output path for `.json` file.

    Raises:
      ValueError: If `len(ids)` != `embs.shape[0]`.
    """
    if len(ids) != embs.shape[0]:
        raise ValueError("IDs length must match number of embeddings")
    emb_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.parent.mkdir(parents=True, exist_ok=True)

    np.save(emb_path, embs)
    with ids_path.open("w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=2)


# -----------------------------------------------------------------------------
# CLI entrypoint
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
      argparse.Namespace with parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Embed Markdown files into .npy + ids.json")
    parser.add_argument("--data-dir", type=Path, default=Path("data/sample_docs"),
                        help="Directory containing .md files (default: data/sample_docs)")
    parser.add_argument("--model", type=str, default="sentence-transformers/all-MiniLM-L6-v2",
                        help="Sentence-Transformers model name")
    parser.add_argument("--emb-file", type=Path, default=Path("data/sample_docs/embeddings.npy"),
                        help="Output path for embeddings (.npy)")
    parser.add_argument("--ids-file", type=Path, default=Path("data/sample_docs/ids.json"),
                        help="Output path for ids (.json)")
    parser.add_argument("--normalize", action="store_true",
                        help="L2-normalize embeddings (cosine-friendly)")

    return parser.parse_args()


def main() -> None:
    """CLI main: encode docs and save artifacts.

    Steps:
      1) Discover `.md` files in `--data-dir`.
      2) Load documents and create stable IDs.
      3) Encode with Sentence-Transformers.
      4) (Optional) L2-normalize embeddings.
      5) Save `.npy` and `.json` artifacts.

    Side Effects:
      Writes files to `--emb-file` and `--ids-file`; creates parent directories.

    Raises:
      Exceptions bubbling up are logged and will cause a non-zero exit code.
    """
    args = parse_args()

    files = find_markdown_files(args.data_dir)
    if not files:
        logger.warning("No .md files found in %s", args.data_dir)
        return

    docs, ids = load_docs(files)
    logger.info("Loaded %d docs from %s", len(docs), args.data_dir)

    embs = embed_docs(docs, model_name=args.model, normalize=args.normalize)
    logger.info("Embeddings shape: %s (normalized=%s)", embs.shape, args.normalize)

    save_artifacts(embs, ids, args.emb_file, args.ids_file)
    logger.info("Saved embeddings -> %s", args.emb_file)
    logger.info("Saved ids        -> %s", args.ids_file)
    print(f"Embedded {len(docs)} docs → {embs.shape}. Saved {args.emb_file} & {args.ids_file}.")


if __name__ == "__main__":
    main()

