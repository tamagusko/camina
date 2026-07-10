import os
import cv2
import numpy as np
import logging
from datetime import datetime
from skimage.metrics import structural_similarity as ssim
from src.motion_detector import detect_motion
from src.config import (
    CAMERA_ID,
    LOCATION,
    CAMERA_CHECK_SIMILARITY_THRESHOLD,
    FRAME_WIDTH,
    FRAME_HEIGHT,
    CAMERA_REFERENCE_IMAGE,
)

# Setup log directory
LOG_DIR = "data"
os.makedirs(LOG_DIR, exist_ok=True)

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "system.log")),
        logging.StreamHandler()
    ]
)


def capture_frame() -> np.ndarray | None:
    """Capture a single frame from the camera."""
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def compute_similarity(img1: np.ndarray, img2: np.ndarray) -> float:
    """Compute SSIM similarity score between two images."""
    gray_a = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    score, _ = ssim(gray_a, gray_b, full=True)
    return score


def log_alignment(status: bool, score: float) -> None:
    """Log camera alignment status and similarity score."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_str = "OK" if status else "MOVED"
    message = "" if status else ", MISALIGNED_CAMERA"
    log_line = f"{now}, CAMERA_ALIGNMENT, status:{status_str}, similarity:{score:.3f}{message}"

    log_filename = f"{datetime.now().strftime('%Y%m%d')}-{LOCATION}-{CAMERA_ID}.log"
    log_path = os.path.join(LOG_DIR, log_filename)
    with open(log_path, "a") as f:
        f.write(log_line + "\n")

    logger.info(log_line)


def check_camera_alignment() -> None:
    """Compare current frame to reference to verify camera alignment."""
    logger.info("Waiting for still scene to check camera alignment...")
    cap = cv2.VideoCapture(0)

    if detect_motion(cap):
        logger.info("Movement detected. Skipping alignment check.")
        cap.release()
        return

    cap.release()
    logger.info("No movement detected. Capturing frame for alignment check...")
    current_frame = capture_frame()

    if current_frame is None:
        logger.error("Could not capture current frame.")
        return

    if not os.path.exists(CAMERA_REFERENCE_IMAGE):
        cv2.imwrite(CAMERA_REFERENCE_IMAGE, current_frame)
        logger.info(f"Reference image not found. Saved new reference to {CAMERA_REFERENCE_IMAGE}")
        log_alignment(True, 1.000)
        return

    reference = cv2.imread(CAMERA_REFERENCE_IMAGE)
    if reference is None:
        logger.error("Could not load reference image.")
        return

    similarity = compute_similarity(reference, current_frame)
    aligned = similarity >= CAMERA_CHECK_SIMILARITY_THRESHOLD
    log_alignment(aligned, similarity)


if __name__ == "__main__":
    check_camera_alignment()
