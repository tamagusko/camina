# CAMINA system configuration

# main.py
CAMERA_ALIGNMENT_HOURS = [6, 14]  # runs at 06:00 and 14:00 daily

# counter.py
LOCATION = "dublin"        # Location identifier (e.g. city or site)
CAMERA_ID = "cam01"        # Unique camera ID
LOW_LIGHT_CHECK_INTERVAL = 600  # Time in seconds (e.g. 600 = 10 min)
LOG_INTERVAL_MINUTES = 5  # Interval for logging counts
LOGGING_ENABLED = True     # Enable or disable logging
LOW_LIGHT_THRESHOLD = 40

# camera settings
FRAME_WIDTH = 416
FRAME_HEIGHT = 416
CAMERA_INDEX = 0

# model settings
MODEL_PATH = "models/yolov8n.pt"
CONFIDENCE_THRESHOLD = 0.4
FRAME_SKIP = 5

# motion_detector.py
MOTION_CHECK_INTERVAL = 1       # Interval (in seconds) between frame checks
MOTION_THRESHOLD = 500000       # Sum of pixel differences to trigger motion
STILL_THRESHOLD = 5

# camera_position_check.py
CAMERA_CHECK_SIMILARITY_THRESHOLD = 0.85  # float between 0–1 for SSIM score threshold
CAMERA_REFERENCE_IMAGE = "data/camera_reference.jpg"  # where the reference frame is stored
