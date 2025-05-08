import os
from ultralytics import YOLO

# Configuration
MODEL_PATH = "models/yolo11n.pt"
EXPORT_DIR = "models"


def export_to_ncnn(model_path: str, export_dir: str) -> None:
    """Export a YOLOv8 model to NCNN format and move it to the export directory."""
    print(f"[INFO] Exporting {model_path} to NCNN format...")

    # Load the YOLOv8 model
    model = YOLO(model_path)

    # Export to NCNN format
    model.export(format="ncnn", imgsz=640, device="cpu")

    # Move output files (.param and .bin) to export directory
    base_name = os.path.splitext(os.path.basename(model_path))[0]
    param_file = f"{base_name}.param"
    bin_file = f"{base_name}.bin"

    for filename in [param_file, bin_file]:
        if os.path.exists(filename):
            dest_path = os.path.join(export_dir, filename)
            os.replace(filename, dest_path)
            print(f"[INFO] Saved {filename} to {dest_path}")
        else:
            print(f"[ERROR] Export failed. File not found: {filename}")

    print("[✅] NCNN export complete.")


if __name__ == "__main__":
    os.makedirs(EXPORT_DIR, exist_ok=True)
    export_to_ncnn(MODEL_PATH, EXPORT_DIR)
