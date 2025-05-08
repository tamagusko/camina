import os
from ultralytics import YOLO

# Configuration
MODEL_PATH = "models/yolo11n.pt"
EXPORT_DIR = "models"


def export_to_onnx(model_path: str, export_dir: str, imgsz: int = 640) -> None:
    """Exports a YOLOv8 model to ONNX format and saves it to the export directory."""
    print(f"[INFO] Exporting model from {model_path} to ONNX format...")

    # Load YOLO model
    model = YOLO(model_path)

    # Export to ONNX
    model.export(
        format="onnx",
        imgsz=imgsz,
        simplify=True,
        dynamic=False,
        device="cpu"
    )

    # Move exported file to the export directory
    base_name = os.path.splitext(os.path.basename(model_path))[0]
    onnx_file = f"{base_name}.onnx"
    if os.path.exists(onnx_file):
        dest_path = os.path.join(export_dir, onnx_file)
        os.replace(onnx_file, dest_path)
        print(f"[INFO] ONNX model saved to {dest_path}")
    else:
        print("[ERROR] Export failed. ONNX file not found.")

    print("[✅] Export completed.")


if __name__ == "__main__":
    os.makedirs(EXPORT_DIR, exist_ok=True)
    export_to_onnx(MODEL_PATH, EXPORT_DIR)
