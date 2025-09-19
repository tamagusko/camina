#!/usr/bin/env python3
"""
Standalone calibration script for CAMINA system.
Run this script when installing a new camera to automatically calibrate pixels_per_meter.
"""

import cv2
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.append(str(src_path))

from camina.utils.calibration import DepthCalibrator

def main():
    print("CAMINA Automatic Calibration")
    print("=" * 40)
    
    calibrator = DepthCalibrator()
    
    # Initialize camera
    camera_source = 0  # Use default camera
    cap = cv2.VideoCapture(camera_source)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        return
    
    print("Camera opened successfully")
    print("Press SPACE to capture image for calibration, ESC to exit")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        # Display frame
        cv2.imshow("Calibration - Press SPACE to calibrate", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        elif key == 32:  # SPACE
            print("Capturing frame for calibration...")
            success = calibrator.run_calibration(frame)
            if success:
                print("Calibration successful! You can now run the main application.")
                break
            else:
                print("Calibration failed. Please try again.")
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()