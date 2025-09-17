#!/usr/bin/env python3
"""
CAMINA Installation Verification Script
Verifies that all components of the CAMINA pipeline are properly installed and working
"""

import sys
import importlib
import torch

def check_package(package_name, import_name=None):
    """Check if a package is installed and can be imported"""
    if import_name is None:
        import_name = package_name

    try:
        module = importlib.import_module(import_name)
        version = getattr(module, '__version__', 'Unknown')
        print(f"✅ {package_name}: {version}")
        return True
    except ImportError as e:
        print(f"❌ {package_name}: Not found ({e})")
        return False

def main():
    """Main verification function"""
    print("🔍 CAMINA Pipeline Installation Verification")
    print("=" * 50)

    # Core ML/AI packages
    print("\n📦 Core ML/AI Frameworks:")
    torch_ok = check_package("PyTorch", "torch")
    torchvision_ok = check_package("TorchVision", "torchvision")
    ultralytics_ok = check_package("Ultralytics", "ultralytics")
    transformers_ok = check_package("Transformers", "transformers")

    # Computer Vision packages
    print("\n🖼️  Computer Vision:")
    cv2_ok = check_package("OpenCV", "cv2")
    pillow_ok = check_package("Pillow", "PIL")
    timm_ok = check_package("TIMM", "timm")

    # Data Science packages
    print("\n📊 Data Science:")
    numpy_ok = check_package("NumPy", "numpy")
    pandas_ok = check_package("Pandas", "pandas")
    sklearn_ok = check_package("Scikit-learn", "sklearn")
    matplotlib_ok = check_package("Matplotlib", "matplotlib")
    seaborn_ok = check_package("Seaborn", "seaborn")

    # Workflow packages
    print("\n⚡ Workflow:")
    tqdm_ok = check_package("TQDM", "tqdm")
    rich_ok = check_package("Rich", "rich")
    yaml_ok = check_package("PyYAML", "yaml")
    roboflow_ok = check_package("Roboflow", "roboflow")

    # GPU and CUDA check
    print("\n🎮 GPU & CUDA:")
    if torch_ok:
        print(f"✅ CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"✅ CUDA Version: {torch.version.cuda}")
            print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
            print(f"✅ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        else:
            print("⚠️  CUDA not available - will use CPU")

    # CAMINA scripts check
    print("\n📄 CAMINA Scripts:")
    try:
        import subprocess

        # Test dataset creator
        result = subprocess.run([sys.executable, "camina_dataset_creator.py", "--help"],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ camina_dataset_creator.py: Ready")
        else:
            print("❌ camina_dataset_creator.py: Error")

        # Test trainer
        result = subprocess.run([sys.executable, "camina_yolo11n_trainer.py", "--help"],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ camina_yolo11n_trainer.py: Ready")
        else:
            print("❌ camina_yolo11n_trainer.py: Error")

    except Exception as e:
        print(f"⚠️  Script check failed: {e}")

    # Summary
    print("\n" + "=" * 50)
    critical_packages = [torch_ok, ultralytics_ok, cv2_ok, numpy_ok]

    if all(critical_packages):
        print("🎉 CAMINA Pipeline Installation: SUCCESSFUL")
        print("🚀 Ready to process urban mobility datasets!")
        print("\n📋 Next Steps:")
        print("1. Prepare your raw images directory")
        print("2. Run: python camina_dataset_creator.py /path/to/images /output/dataset")
        print("3. Use Roboflow for label correction (optional)")
        print("4. Run: python camina_yolo11n_trainer.py /dataset /output --edge-optimization")

        if torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            if gpu_memory >= 12:
                print(f"💪 RTX 3060 ({gpu_memory:.1f}GB) detected - fully optimized pipeline available")
            else:
                print(f"⚡ GPU ({gpu_memory:.1f}GB) detected - basic pipeline available")
    else:
        print("❌ CAMINA Pipeline Installation: FAILED")
        print("🔧 Please install missing packages and try again")

    return all(critical_packages)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)