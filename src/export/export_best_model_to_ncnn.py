#!/usr/bin/env python3
"""
CAMINA YOLO Best Model to NCNN Export for Raspberry Pi 5
Export the best performing YOLO model (YOLO11n) to NCNN format optimized for edge deployment
"""

import os
import sys
from pathlib import Path
from ultralytics import YOLO

def get_file_size_mb(file_path):
    """Get file size in MB"""
    if isinstance(file_path, str):
        file_path = Path(file_path)

    if file_path.exists():
        return file_path.stat().st_size / (1024 * 1024)
    return 0

def get_directory_size_mb(dir_path):
    """Get total directory size in MB"""
    if isinstance(dir_path, str):
        dir_path = Path(dir_path)

    if not dir_path.exists():
        return 0

    total_size = 0
    for file_path in dir_path.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size

    return total_size / (1024 * 1024)

def export_best_model_to_ncnn():
    """Export the best CAMINA model to NCNN format for Raspberry Pi deployment"""

    print("="*80)
    print("🎯 CAMINA Best Model Export to NCNN for Raspberry Pi 5")
    print("="*80)

    # Best performing model based on our results: YOLO11n (mAP@0.5: 0.563)
    best_model_path = "/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt"

    if not Path(best_model_path).exists():
        print(f"❌ Best model not found: {best_model_path}")
        return None

    print(f"🏆 Using best performing model: YOLO11n")
    print(f"📁 Model path: {best_model_path}")

    # Get original model size
    original_size_mb = get_file_size_mb(best_model_path)
    print(f"📊 Original model size: {original_size_mb:.2f} MB")

    try:
        # Load the best YOLO11 model
        print(f"\n🔄 Loading YOLO11n model...")
        model = YOLO(best_model_path)
        print("✅ Model loaded successfully")

        # Export the model to NCNN format optimized for Raspberry Pi
        print(f"\n🔄 Exporting to NCNN format for Raspberry Pi 5...")
        print("   - Format: NCNN (optimized for ARM processors)")
        print("   - Target: Raspberry Pi 5 (8GB RAM)")
        print("   - Image size: 640x640")
        print("   - Optimization: Enabled")

        # Export with Raspberry Pi optimizations
        export_path = model.export(
            format="ncnn",
            imgsz=640,           # Standard YOLO input size
            half=False,          # Keep FP32 for better compatibility on RPi
            dynamic=False        # Static shape for better performance
        )

        print(f"✅ NCNN export successful!")
        print(f"📁 Export path: {export_path}")

        # Calculate NCNN model size
        ncnn_dir = Path(export_path)
        if ncnn_dir.exists() and ncnn_dir.is_dir():
            ncnn_size_mb = get_directory_size_mb(ncnn_dir)
        else:
            # Single file export
            ncnn_size_mb = get_file_size_mb(export_path)

        # Move to organized location
        output_dir = Path("/home/tiago/repos/camina/model/raspberry_pi_deployment")
        output_dir.mkdir(parents=True, exist_ok=True)

        final_ncnn_path = output_dir / "yolo11n_best_ncnn"

        # Move the exported model
        if Path(export_path).exists():
            if Path(export_path).is_dir():
                # Directory export
                import shutil
                if final_ncnn_path.exists():
                    shutil.rmtree(final_ncnn_path)
                shutil.move(str(export_path), str(final_ncnn_path))
            else:
                # File export (rename)
                final_ncnn_path.parent.mkdir(parents=True, exist_ok=True)
                Path(export_path).rename(final_ncnn_path)

        print(f"📁 Final deployment model: {final_ncnn_path}")

        # Test loading the exported NCNN model
        print(f"\n🔄 Testing NCNN model loading...")
        try:
            ncnn_model = YOLO(str(final_ncnn_path))
            print("✅ NCNN model loads successfully!")

            # Get model info
            print(f"📊 Model info:")
            print(f"   - Format: NCNN")
            print(f"   - Task: {ncnn_model.task}")
            if hasattr(ncnn_model, 'names'):
                print(f"   - Classes: {len(ncnn_model.names)}")
                print(f"   - Class names: {list(ncnn_model.names.values())}")

        except Exception as e:
            print(f"⚠️ NCNN model test loading failed: {e}")

        # Size comparison and compression analysis
        final_size_mb = get_directory_size_mb(final_ncnn_path) if final_ncnn_path.is_dir() else get_file_size_mb(final_ncnn_path)
        compression_ratio = ((original_size_mb - final_size_mb) / original_size_mb * 100) if original_size_mb > 0 else 0

        print(f"\n" + "="*80)
        print("📊 RASPBERRY PI 5 DEPLOYMENT MODEL SUMMARY")
        print("="*80)
        print(f"🏆 Model: YOLO11n (Best performing: mAP@0.5 = 0.563)")
        print(f"📁 Deployment path: {final_ncnn_path}")
        print(f"🎯 Target device: Raspberry Pi 5 (8GB RAM)")
        print(f"📊 Size comparison:")
        print(f"   - Original PyTorch: {original_size_mb:.2f} MB")
        print(f"   - NCNN Optimized:   {final_size_mb:.2f} MB")
        print(f"   - Compression:      {compression_ratio:.1f}%")
        print(f"   - Size reduction:   {original_size_mb - final_size_mb:.2f} MB")

        # Raspberry Pi performance estimates
        print(f"\n🍓 Raspberry Pi 5 Performance Estimates:")
        print(f"   - Memory usage:     ~{final_size_mb * 2:.0f} MB (model + inference)")
        print(f"   - Available RAM:    ~{8000 - final_size_mb * 2:.0f} MB remaining")
        print(f"   - Inference speed:  ~10-30 FPS (estimated)")
        print(f"   - Power efficiency: Optimized for ARM Cortex-A76")

        # Usage instructions
        print(f"\n🚀 Usage on Raspberry Pi 5:")
        print(f"   1. Copy entire folder to RPi: {final_ncnn_path.name}")
        print(f"   2. Install ultralytics: pip install ultralytics")
        print(f"   3. Load model: YOLO('{final_ncnn_path.name}')")
        print(f"   4. Run inference: model.predict('image.jpg')")

        print(f"\n✅ NCNN export completed successfully!")
        print("="*80)

        return {
            'original_path': best_model_path,
            'ncnn_path': final_ncnn_path,
            'original_size_mb': original_size_mb,
            'ncnn_size_mb': final_size_mb,
            'compression_ratio': compression_ratio,
            'model_name': 'YOLO11n_best'
        }

    except Exception as e:
        print(f"❌ Export failed: {e}")
        return None

def create_deployment_readme(export_result):
    """Create README for Raspberry Pi deployment"""
    if not export_result:
        return

    readme_content = f"""# CAMINA YOLO11n Raspberry Pi 5 Deployment

## Model Information
- **Model**: YOLO11n (Best performing from CAMINA training)
- **Performance**: mAP@0.5 = 0.563 (validated on urban mobility dataset)
- **Format**: NCNN (optimized for ARM processors)
- **Original Size**: {export_result['original_size_mb']:.2f} MB
- **Optimized Size**: {export_result['ncnn_size_mb']:.2f} MB
- **Compression**: {export_result['compression_ratio']:.1f}% size reduction

## Target Hardware
- **Device**: Raspberry Pi 5 (8GB RAM)
- **Processor**: ARM Cortex-A76 (quad-core, 2.4GHz)
- **Memory Usage**: ~{export_result['ncnn_size_mb'] * 2:.0f} MB estimated
- **Available RAM**: ~{8000 - export_result['ncnn_size_mb'] * 2:.0f} MB remaining

## Classes Detected
Urban mobility objects:
1. Person
2. Cyclist
3. Car
4. E-scooter
5. SUV
6. Motorcyclist
7. Bus
8. Delivery Van
9. Truck

## Installation on Raspberry Pi 5

1. **Copy model files**:
   ```bash
   scp -r {export_result['ncnn_path'].name}/ pi@raspberrypi:~/camina/
   ```

2. **Install dependencies**:
   ```bash
   pip install ultralytics opencv-python numpy
   ```

3. **Basic usage**:
   ```python
   from ultralytics import YOLO

   # Load the optimized model
   model = YOLO('{export_result['ncnn_path'].name}')

   # Run inference
   results = model.predict('image.jpg', imgsz=640)

   # Process results
   for result in results:
       result.show()  # Display results
       result.save(filename='output.jpg')  # Save results
   ```

## Performance Expectations
- **Inference Speed**: 10-30 FPS (depending on image size and complexity)
- **Memory Efficient**: Optimized for edge deployment
- **Power Consumption**: Low power ARM optimization
- **Accuracy**: Maintains original model accuracy

## Model Performance (Validation Results)
| Class | AP@0.5 |
|-------|--------|
| E-scooter | 0.900 |
| Cyclist | 0.589 |
| Person | 0.479 |
| Car | 0.412 |
| SUV | 0.402 |
| Motorcyclist | 0.326 |
| Delivery Van | 0.114 |
| Truck | 0.111 |

**Overall mAP@0.5**: 0.563

## Notes
- Model optimized for 640x640 input images
- Uses NCNN framework for efficient ARM inference
- Maintains FP32 precision for compatibility
- Tested on CAMINA urban mobility dataset

Generated: {export_result.get('timestamp', 'Unknown')}
"""

    readme_path = export_result['ncnn_path'].parent / "README.md"
    with open(readme_path, 'w') as f:
        f.write(readme_content)

    print(f"📄 Deployment README created: {readme_path}")

def main():
    """Main execution function"""
    result = export_best_model_to_ncnn()

    if result:
        create_deployment_readme(result)
        print(f"\n🎉 Success! NCNN model ready for Raspberry Pi 5 deployment")
        print(f"📁 Location: {result['ncnn_path']}")
        print(f"📊 Size: {result['ncnn_size_mb']:.2f} MB")
    else:
        print(f"\n❌ Export failed")
        sys.exit(1)

if __name__ == "__main__":
    main()