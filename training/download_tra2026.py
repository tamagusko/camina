"""Download the TRA 2026 dataset (Roboflow, YOLO format) into ``data/tra2026/``.

The API key comes from the environment, never from the repo::

    ROBOFLOW_API_KEY=... .venv-train/bin/python -m training.download_tra2026

Needs ``pip install roboflow`` (not in training/requirements.txt: it pulls in its
own OpenCV; install it for the download, then remove it).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE = "tiago-tamagusko"
PROJECT = "sdl-urban-mobility-dataset-crcy8"
VERSION = 3
TARGET = Path("data/tra2026")


def main() -> None:
    """Download the dataset version into ``data/tra2026``."""
    from roboflow import Roboflow

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        raise SystemExit("Set ROBOFLOW_API_KEY")
    project = Roboflow(api_key=key).workspace(WORKSPACE).project(PROJECT)
    project.version(VERSION).download("yolo26", location=str(TARGET))
    logger.info("Downloaded %s v%d to %s", PROJECT, VERSION, TARGET)


if __name__ == "__main__":
    main()
