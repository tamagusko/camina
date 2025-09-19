import cv2
import numpy as np
import time
from src.config import MOTION_CHECK_INTERVAL, MOTION_THRESHOLD, STILL_THRESHOLD


def detect_motion(cap):
    """
    Detect motion in the camera feed.

    Args:
        cap: OpenCV VideoCapture object.

    Returns:
        True if motion is detected, False otherwise.
    """
    _, prev_frame = cap.read()
    if not _:
        print("[WARNING] Failed to read initial frame for motion detection.")
        return False

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    no_motion_seconds = 0

    while True:
        time.sleep(MOTION_CHECK_INTERVAL)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)
        motion_score = np.sum(thresh)

        if motion_score > MOTION_THRESHOLD:
            print("[INFO] Motion detected.")
            return True
        else:
            no_motion_seconds += MOTION_CHECK_INTERVAL
            if no_motion_seconds >= STILL_THRESHOLD:
                print("[INFO] Scene still for {} seconds.".format(STILL_THRESHOLD))
                return False

        prev_gray = gray.copy()
