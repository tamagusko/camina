# camina_run.py - Smart launcher for CAMINA (auto-selects day or low-light mode and logs results)

import cv2
import subprocess
import datetime
import time
import os
from config import LOCATION, CAMERA_ID, LOW_LIGHT_CHECK_INTERVAL

LOG_DIR = "data"
os.makedirs(LOG_DIR, exist_ok=True)

def is_low_light(frame, threshold=40):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = gray.mean()
    return brightness < threshold

def log_status(log_file, counts, low_light):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status = "LOW_LIGHT" if low_light else "NORMAL_LIGHT"
    count_str = ", ".join(f"{k}:{v}" for k, v in counts.items())
    with open(log_file, "a") as f:
        f.write(f"{timestamp}, {status}, {count_str}\n")

def read_camera_frame():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    return ret, frame

def run_mode(script_name):
    process = subprocess.Popen(["python", f"src/{script_name}"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return process

def main():
    current_mode = None
    process = None
    last_switch = time.time() - LOW_LIGHT_CHECK_INTERVAL  # Force check at start

    while True:
        now = datetime.datetime.now()
        log_filename = f"{now.strftime('%Y%m%d')}-{LOCATION}-{CAMERA_ID}-modalshare.log"
        log_path = os.path.join(LOG_DIR, log_filename)

        # Re-evaluate every LOW_LIGHT_CHECK_INTERVAL seconds
        if time.time() - last_switch >= LOW_LIGHT_CHECK_INTERVAL:
            ret, frame = read_camera_frame()
            if not ret:
                print("[ERROR] Cannot read from camera.")
                time.sleep(60)
                continue

            low_light = is_low_light(frame)
            new_mode = "solar_lowlight_counter.py" if low_light else "solar_counter.py"

            if new_mode != current_mode:
                if process:
                    process.terminate()
                print(f"[INFO] Switching to {new_mode} mode.")
                process = run_mode(new_mode)
                current_mode = new_mode
                last_switch = time.time()

        # Log status every minute
        ret, frame = read_camera_frame()
        if ret:
            low_light = is_low_light(frame)
            dummy_counts = {  # Placeholder for real values from shared memory or IPC in future
                "person": 0,
                "bicycle": 0,
                "car": 0,
                "motorcycle": 0,
                "bus": 0,
                "truck": 0,
            }
            log_status(log_path, dummy_counts, low_light)

        time.sleep(60)

if __name__ == "__main__":
    main()
