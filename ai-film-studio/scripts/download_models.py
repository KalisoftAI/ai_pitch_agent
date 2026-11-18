"""Download the local Gemma 4 QAT GGUF model.

Usage:
    python scripts/download_models.py
"""

from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "google/gemma-4-12B-it-qat-q4_0-gguf"
FILES = [
    "gemma-4-12b-it-qat-q4_0.gguf",
    "mmproj-gemma-4-12b-it-qat-q4_0.gguf",
]

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "storage" / "models" / "gemma-4-12b-it-qat-q4_0"


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        print(f"Downloading {REPO_ID}/{filename} -> {TARGET}")
        hf_hub_download(
            repo_id=REPO_ID,
            filename=filename,
            local_dir=TARGET,
        )
        print(f"Done: {filename}")
    print(f"Model ready at {TARGET}")


if __name__ == "__main__":
    main()
