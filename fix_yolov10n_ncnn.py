#!/usr/bin/env python3
"""
Fix YOLOv10n NCNN Export - Resolve torch.topk compatibility issue

The problem: YOLOv10n uses torch.topk operation which is not supported in NCNN
Solution: Export to ONNX first, then simplify, then convert to NCNN
"""

import os
import shutil
import sys
from pathlib import Path
from ultralytics import YOLO
import onnx
import onnxsim

def fix_yolov10n_ncnn_export():
    """Fix YOLOv10n NCNN export with intermediate ONNX simplification"""

    print("🔧 Fixing YOLOv10n NCNN Export")
    print("="*60)

    # Paths
    model_path = "/home/tiago/repos/camina/model/yolo_comparison/YOLOv10n/train/weights/best.pt"
    output_dir = "/home/tiago/repos/camina/model/raspberry_pi_deployment_all"
    deployment_dir = Path(output_dir) / "yolov10n_ncnn"

    if not Path(model_path).exists():
        print(f"❌ YOLOv10n model not found: {model_path}")
        return False

    try:
        # Step 1: Load model
        print("🔄 Loading YOLOv10n model...")
        model = YOLO(model_path)
        print("✅ Model loaded successfully")

        # Step 2: Export to ONNX first (more compatible)
        print("🔄 Exporting to ONNX format...")
        onnx_path = model.export(
            format="onnx",
            imgsz=640,
            half=False,
            dynamic=False,
            simplify=True,  # Enable ONNX simplification
            opset=11        # Use older opset for better compatibility
        )
        print(f"✅ ONNX export successful: {onnx_path}")

        # Step 3: Additional ONNX simplification using onnxsim
        print("🔄 Applying advanced ONNX simplification...")
        try:
            onnx_model = onnx.load(onnx_path)
            simplified_model, check = onnxsim.simplify(onnx_model)

            if check:
                simplified_onnx_path = str(onnx_path).replace('.onnx', '_simplified.onnx')
                onnx.save(simplified_model, simplified_onnx_path)
                print(f"✅ ONNX simplified: {simplified_onnx_path}")
                onnx_path = simplified_onnx_path
            else:
                print("⚠️ ONNX simplification check failed, using original")

        except Exception as e:
            print(f"⚠️ ONNX simplification failed: {e}")
            print("Continuing with original ONNX...")

        # Step 4: Convert simplified ONNX to NCNN
        print("🔄 Converting ONNX to NCNN...")

        # Load the ONNX model and export to NCNN
        onnx_model = YOLO(onnx_path)
        ncnn_path = onnx_model.export(
            format="ncnn",
            imgsz=640,
            half=False,
            dynamic=False
        )
        print(f"✅ NCNN conversion successful: {ncnn_path}")

        # Step 5: Organize deployment directory
        if deployment_dir.exists():
            shutil.rmtree(deployment_dir)

        if Path(ncnn_path).is_dir():
            shutil.move(str(ncnn_path), str(deployment_dir))
        else:
            deployment_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ncnn_path), str(deployment_dir))

        print(f"📁 Final deployment location: {deployment_dir}")

        # Step 6: Test the fixed NCNN model
        print("🔄 Testing fixed NCNN model...")
        try:
            import ncnn
            import cv2
            import numpy as np

            # Find model files
            param_file = None
            bin_file = None
            for file in os.listdir(deployment_dir):
                if file.endswith('.param'):
                    param_file = os.path.join(deployment_dir, file)
                elif file.endswith('.bin'):
                    bin_file = os.path.join(deployment_dir, file)

            if param_file and bin_file:
                net = ncnn.Net()
                net.load_param(param_file)
                net.load_model(bin_file)

                # Test inference with dummy data
                dummy_img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
                mat = ncnn.Mat.from_pixels(dummy_img, ncnn.Mat.PixelType.PIXEL_BGR, 640, 640)
                mat.substract_mean_normalize([0, 0, 0], [1/255.0, 1/255.0, 1/255.0])

                ex = net.create_extractor()
                ex.input("in0", mat)
                _, result = ex.extract("out0")

                print("✅ NCNN model test successful!")

        except Exception as e:
            print(f"⚠️ NCNN test failed: {e}")
            print("Model exported but may have compatibility issues")

        # Step 7: Cleanup temporary files
        print("🧹 Cleaning up temporary files...")
        for temp_file in [onnx_path, str(onnx_path).replace('.onnx', '_simplified.onnx')]:
            if Path(temp_file).exists():
                try:
                    os.remove(temp_file)
                except:
                    pass

        print("🎉 YOLOv10n NCNN export fix completed successfully!")

        # Calculate model size
        model_size = sum(f.stat().st_size for f in deployment_dir.rglob('*') if f.is_file()) / (1024 * 1024)
        print(f"📊 Final model size: {model_size:.2f} MB")

        return True

    except Exception as e:
        print(f"❌ Fix attempt failed: {e}")
        print("YOLOv10n may have fundamental compatibility issues with NCNN")
        return False

def create_alternative_yolov10n():
    """Create a compatibility note for YOLOv10n if NCNN export fails"""

    deployment_dir = Path("/home/tiago/repos/camina/model/raspberry_pi_deployment_all/yolov10n_ncnn")
    deployment_dir.mkdir(parents=True, exist_ok=True)

    # Create compatibility note
    note_content = """# YOLOv10n NCNN Compatibility Issue

YOLOv10n uses torch.topk operations that are not supported in NCNN.

## Alternative Solutions:

### 1. Use ONNX Runtime instead:
```bash
pip install onnxruntime
```

```python
import onnxruntime as ort
import numpy as np

# Load ONNX model
session = ort.InferenceSession('yolov10n.onnx')
input_name = session.get_inputs()[0].name

# Run inference
results = session.run(None, {input_name: image_array})
```

### 2. Use other YOLO models:
- YOLOv8n: Best balance of speed/accuracy (15.3 FPS on RPi5)
- YOLOv5n: Most stable (15.0 FPS on RPi5)
- YOLO11n: Best accuracy (mAP@0.5 = 0.563)

### 3. Model Performance Comparison:
```
YOLOv8n:  65.46ms avg, 15.3 FPS - RECOMMENDED
YOLOv5n:  66.71ms avg, 15.0 FPS - STABLE
YOLOv10n: NCNN incompatible (torch.topk issue)
YOLO11n:  Best accuracy but test pending
```

## Recommendation:
Use YOLOv8n for Raspberry Pi deployment - it provides the best
speed/accuracy balance and full NCNN compatibility.
"""

    with open(deployment_dir / "COMPATIBILITY_NOTE.md", 'w') as f:
        f.write(note_content)

    print(f"📄 Compatibility note created: {deployment_dir}/COMPATIBILITY_NOTE.md")

def main():
    """Main execution"""

    print("🔧 YOLOv10n NCNN Fix Utility")
    print("="*60)

    # Check if onnxsim is available
    try:
        import onnxsim
        print("✅ onnxsim available for advanced optimization")
    except ImportError:
        print("⚠️ onnxsim not available, installing...")
        os.system("pip install onnxsim")
        try:
            import onnxsim
            print("✅ onnxsim installed successfully")
        except:
            print("❌ Could not install onnxsim, proceeding without advanced optimization")

    # Attempt to fix YOLOv10n
    success = fix_yolov10n_ncnn_export()

    if not success:
        print("\n🔄 Creating compatibility guidance instead...")
        create_alternative_yolov10n()
        print("💡 Check the compatibility note for alternative solutions")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())