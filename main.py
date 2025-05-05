import cv2
import time
import subprocess
import logging
from datetime import datetime
from src.config import (
    LOW_LIGHT_CHECK_INTERVAL,
    LOW_LIGHT_THRESHOLD,
    CAMERA_ALIGNMENT_HOURS,
)
from src.motion_detector import detect_motion
from src.camera_position_check import check_camera_alignment

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# Convert interval from minutes to seconds
LOW_LIGHT_CHECK_SECONDS = LOW_LIGHT_CHECK_INTERVAL * 60


def is_low_light(frame, threshold=LOW_LIGHT_THRESHOLD):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return gray.mean() < threshold


def read_camera_frame():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    return ret, frame


def run_mode(script_name):
    return subprocess.Popen([
        "python", f"src/{script_name}"
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def should_check_alignment(now, last_check_time):
    return now.hour in CAMERA_ALIGNMENT_HOURS and (not last_check_time or now.date() != last_check_time.date())


def main():
    current_mode = None
    process = None
    last_switch = time.time() - LOW_LIGHT_CHECK_SECONDS
    last_alignment_check = None

    while True:
        now = datetime.now()

        # Run camera alignment check twice a day (e.g. 6h, 18h) only if no motion
        if should_check_alignment(now, last_alignment_check):
            cap = cv2.VideoCapture(0)
            if not detect_motion(cap):
                logging.info("Running camera alignment check.")
                check_camera_alignment()
                last_alignment_check = now
            else:
                logging.info("Skipping alignment check due to motion.")
            cap.release()

        # Switch between normal and lowlight mode if needed
        if time.time() - last_switch >= LOW_LIGHT_CHECK_SECONDS:
            ret, frame = read_camera_frame()
            if not ret:
                logging.error("Cannot read from camera.")
                time.sleep(60)
                continue

            low_light = is_low_light(frame)
            new_mode = "lowlight_counter.py" if low_light else "counter.py"

            if new_mode != current_mode:
                if process:
                    process.terminate()
                logging.info(f"Switching to {new_mode} mode.")
                process = run_mode(new_mode)
                current_mode = new_mode
                last_switch = time.time()

        time.sleep(60)


if __name__ == "__main__":
    main()
