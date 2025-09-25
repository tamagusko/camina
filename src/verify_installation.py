#!/usr/bin/env python3
"""
CAMINA Installation Verification Script

Verifies that all components of the CAMINA pipeline are properly installed
and can be imported without errors.
"""

import sys
import logging
from pathlib import Path

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def verify_python_version():
    """Verify Python version compatibility."""
    logger.info("Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        logger.error(f"Python 3.8+ required, found {version.major}.{version.minor}")
        return False
    logger.info(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def verify_dependencies():
    """Verify required dependencies are installed."""
    logger.info("Checking dependencies...")

    required_packages = [
        ('torch', 'PyTorch'),
        ('torchvision', 'TorchVision'),
        ('ultralytics', 'Ultralytics YOLO'),
        ('cv2', 'OpenCV'),
        ('PIL', 'Pillow'),
        ('numpy', 'NumPy'),
        ('yaml', 'PyYAML'),
        ('psutil', 'psutil'),
        ('tqdm', 'tqdm')
    ]

    missing_packages = []

    for package, name in required_packages:
        try:
            __import__(package)
            logger.info(f"✅ {name}")
        except ImportError:
            logger.error(f"❌ {name} not found")
            missing_packages.append(name)

    if missing_packages:
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.error("Install with: pip install -r requirements.txt")
        return False

    return True

def verify_project_structure():
    """Verify project directory structure."""
    logger.info("Checking project structure...")

    required_dirs = [
        'src',
        'configs',
        'tests',
        'models',
        'archive/old'
    ]

    required_files = [
        'main.py',
        'configs/config.yaml',
        'src/__init__.py',
        'src/config.py',
        'src/detector_yolo11n.py',
        'src/detector_yolo_world.py',
        'src/cyclist_logic.py',
        'src/merger_nms.py',
        'src/io_utils.py',
        'src/utils.py'
    ]

    project_root = Path(__file__).parent

    # Check directories
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            logger.info(f"✅ Directory: {dir_path}")
        else:
            logger.error(f"❌ Missing directory: {dir_path}")
            return False

    # Check files
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            logger.info(f"✅ File: {file_path}")
        else:
            logger.error(f"❌ Missing file: {file_path}")
            return False

    return True

def verify_config_loading():
    """Verify configuration can be loaded."""
    logger.info("Testing configuration loading...")

    try:
        # Add src to path for imports
        sys.path.insert(0, str(Path(__file__).parent / 'src'))

        from src.config import load_config

        config_path = Path(__file__).parent / 'configs' / 'config.yaml'
        config = load_config(config_path)

        logger.info(f"✅ Configuration loaded successfully")
        logger.info(f"   Version: {config.metadata.version}")
        logger.info(f"   Stage A enabled: {config.stage_a.enabled}")
        logger.info(f"   Stage B enabled: {config.stage_b.enabled}")

        return True

    except Exception as e:
        logger.error(f"❌ Configuration loading failed: {e}")
        return False

def verify_imports():
    """Verify all CAMINA modules can be imported."""
    logger.info("Testing CAMINA module imports...")

    try:
        # Add src to path for imports
        sys.path.insert(0, str(Path(__file__).parent / 'src'))

        from src import (
            CAMINAConfig, load_config, YOLO11nDetector, YOLOWorldDetector,
            CyclistDetector, NMSConsolidator, ImageLoader, AnnotationWriter,
            DatasetValidator, MemoryManager, PerformanceMonitor, BatchProcessor
        )

        logger.info("✅ All CAMINA modules imported successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Module import failed: {e}")
        return False

def verify_cuda_availability():
    """Check CUDA availability for GPU acceleration."""
    logger.info("Checking CUDA availability...")

    try:
        import torch

        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            current_device = torch.cuda.current_device()
            device_name = torch.cuda.get_device_name(current_device)

            logger.info(f"✅ CUDA available")
            logger.info(f"   Devices: {device_count}")
            logger.info(f"   Current device: {current_device} ({device_name})")
        else:
            logger.warning("⚠️  CUDA not available - will use CPU")

        return True

    except Exception as e:
        logger.error(f"❌ CUDA check failed: {e}")
        return False

def main():
    """Run all verification checks."""
    logger.info("=== CAMINA Installation Verification ===")

    checks = [
        ("Python Version", verify_python_version),
        ("Dependencies", verify_dependencies),
        ("Project Structure", verify_project_structure),
        ("Configuration Loading", verify_config_loading),
        ("Module Imports", verify_imports),
        ("CUDA Availability", verify_cuda_availability)
    ]

    results = []

    for check_name, check_func in checks:
        logger.info(f"\n--- {check_name} ---")
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            logger.error(f"❌ {check_name} failed with exception: {e}")
            results.append((check_name, False))

    # Summary
    logger.info("\n=== Verification Summary ===")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {check_name}")

    logger.info(f"\nOverall: {passed}/{total} checks passed")

    if passed == total:
        logger.info("🎉 All checks passed! CAMINA is ready to use.")
        logger.info("\nNext steps:")
        logger.info("1. Place images in data/images/ directory")
        logger.info("2. Run: python main.py --images_dir data/images")
        logger.info("3. Check outputs/ directory for results")
        return True
    else:
        logger.error("❌ Some checks failed. Please resolve the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)