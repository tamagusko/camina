import os
import shutil
from ultralytics import YOLO

SOURCE_WEIGHTS = "models/20250629_warmup_best.pt"
DEST_DIR = "models/yolo11n_ncnn_model"

os.makedirs(DEST_DIR, exist_ok=True)

model = YOLO(SOURCE_WEIGHTS)
export_path = model.export(format="ncnn")

if os.path.abspath(export_path) != os.path.abspath(DEST_DIR):
    shutil.move(export_path, DEST_DIR)

print(f"✅ NCNN model exported to: {DEST_DIR}")
