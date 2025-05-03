import cv2
import time
import subprocess
from src.config import LOW_LIGHT_CHECK_INTERVAL, LOW_LIGHT_THRESHOLD


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


def main():
    current_mode = None
    process = None
    last_switch = time.time() - LOW_LIGHT_CHECK_INTERVAL

    while True:
        if time.time() - last_switch >= LOW_LIGHT_CHECK_INTERVAL:
            ret, frame = read_camera_frame()
            if not ret:
                print("[ERROR] Cannot read from camera.")
                time.sleep(60)
                continue

            low_light = is_low_light(frame)
            new_mode = "lowlight_counter.py" if low_light else "counter.py"

            if new_mode != current_mode:
                if process:
                    process.terminate()
                print(f"[INFO] Switching to {new_mode} mode.")
                process = run_mode(new_mode)
                current_mode = new_mode
                last_switch = time.time()

        time.sleep(60)


if __name__ == "__main__":
    main()
