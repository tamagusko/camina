#!/usr/bin/env python3
"""
CAMINA Roboflow Upload Script

Uploads YOLO-World detection results to Roboflow in YOLOv11 format.
Handles both train and test datasets with YOLO format labels.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
import shutil
import json
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

try:
    from roboflow import Roboflow
except ImportError:
    logger.error("Roboflow library not installed. Install with: pip install roboflow")
    sys.exit(1)

@dataclass
class UploadConfig:
    """Configuration for Roboflow upload."""

    # Roboflow credentials
    api_key: str
    workspace: str
    project_name: str

    # Dataset paths - can be single dataset or train/test split
    dataset_type: str  # "single" for run.sh output, "split" for run_imagenet.sh output

    # For single dataset (run.sh output)
    images_dir: Optional[str] = None
    labels_dir: Optional[str] = None

    # For train/test split (run_imagenet.sh output)
    train_images_dir: Optional[str] = None
    train_labels_dir: Optional[str] = None
    test_images_dir: Optional[str] = None
    test_labels_dir: Optional[str] = None

    # Upload settings
    version_name: Optional[str] = None
    version_notes: Optional[str] = None

    # Class mapping (CAMINA classes)
    class_names: Dict[int, str] = None

    def __post_init__(self):
        if self.class_names is None:
            self.class_names = {
                0: "person",
                1: "cyclist",
                2: "car",
                3: "motorcycle",
                4: "bus",
                5: "truck",
                6: "e-scooter",      # YOLO-World detection
                7: "SUV",           # YOLO-World detection
                8: "delivery_van"   # YOLO-World detection
            }

        # Validate configuration based on dataset type
        if self.dataset_type == "single":
            if not self.images_dir or not self.labels_dir:
                raise ValueError("For single dataset, images_dir and labels_dir must be provided")
        elif self.dataset_type == "split":
            required_paths = [self.train_images_dir, self.train_labels_dir,
                            self.test_images_dir, self.test_labels_dir]
            if not all(required_paths):
                raise ValueError("For split dataset, all train/test paths must be provided")
        else:
            raise ValueError("dataset_type must be 'single' or 'split'")


class RoboflowUploader:
    """Handles uploading YOLO datasets to Roboflow."""

    def __init__(self, config: UploadConfig):
        self.config = config
        self.rf = None
        self.project = None

        # Validate paths
        self._validate_paths()

    def _validate_paths(self):
        """Validate that all required paths exist."""
        paths_to_check = []

        if self.config.dataset_type == "single":
            paths_to_check = [self.config.images_dir, self.config.labels_dir]
        elif self.config.dataset_type == "split":
            paths_to_check = [
                self.config.train_images_dir,
                self.config.train_labels_dir,
                self.config.test_images_dir,
                self.config.test_labels_dir
            ]

        for path in paths_to_check:
            if not Path(path).exists():
                raise FileNotFoundError(f"Path does not exist: {path}")

        logger.info("✅ All paths validated successfully")

    def connect_to_roboflow(self):
        """Connect to Roboflow and get project."""
        try:
            logger.info("🔌 Connecting to Roboflow...")
            self.rf = Roboflow(api_key=self.config.api_key)

            # Get workspace
            workspace = self.rf.workspace(self.config.workspace)
            logger.info(f"📁 Connected to workspace: {self.config.workspace}")

            # Get or create project
            try:
                self.project = workspace.project(self.config.project_name)
                logger.info(f"📂 Found existing project: {self.config.project_name}")
            except Exception:
                logger.info(f"📂 Creating new project: {self.config.project_name}")
                self.project = workspace.create_project(
                    project_name=self.config.project_name,
                    project_type="object-detection"
                )

        except Exception as e:
            logger.error(f"❌ Failed to connect to Roboflow: {e}")
            raise

    def create_dataset_yaml(self, output_dir: Path):
        """Create data.yaml file for YOLOv11 format."""
        yaml_content = {
            'path': str(output_dir),
            'train': 'images/train',
            'val': 'images/test',
            'test': 'images/test',
            'nc': len(self.config.class_names),
            'names': list(self.config.class_names.values())
        }

        yaml_path = output_dir / 'data.yaml'

        # Write YAML content
        with open(yaml_path, 'w') as f:
            f.write(f"path: {yaml_content['path']}\n")
            f.write(f"train: {yaml_content['train']}\n")
            f.write(f"val: {yaml_content['val']}\n")
            f.write(f"test: {yaml_content['test']}\n")
            f.write(f"\n")
            f.write(f"nc: {yaml_content['nc']}\n")
            f.write(f"names:\n")
            for name in yaml_content['names']:
                f.write(f"  - {name}\n")

        logger.info(f"📄 Created data.yaml: {yaml_path}")
        return yaml_path

    def prepare_yolo_dataset(self, output_dir: Path):
        """Prepare dataset in YOLOv11 format."""
        logger.info("📦 Preparing dataset in YOLOv11 format...")

        if self.config.dataset_type == "single":
            return self._prepare_single_dataset(output_dir)
        else:
            return self._prepare_split_dataset(output_dir)

    def _prepare_single_dataset(self, output_dir: Path):
        """Prepare single dataset (from run.sh) in YOLOv11 format."""
        # For single dataset, we'll split it 80/20 train/val
        logger.info("📁 Preparing single dataset with 80/20 train/val split...")

        # Create directory structure
        train_img_dir = output_dir / 'images' / 'train'
        val_img_dir = output_dir / 'images' / 'val'
        train_lbl_dir = output_dir / 'labels' / 'train'
        val_lbl_dir = output_dir / 'labels' / 'val'

        for dir_path in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Get all images and corresponding labels
        images_path = Path(self.config.images_dir)
        labels_path = Path(self.config.labels_dir)

        image_files = sorted(list(images_path.glob('*')))

        # Filter to only include images that have corresponding labels
        valid_pairs = []
        for img_file in image_files:
            label_file = labels_path / f"{img_file.stem}.txt"
            if label_file.exists():
                valid_pairs.append((img_file, label_file))

        # Split 80/20
        split_idx = int(len(valid_pairs) * 0.8)
        train_pairs = valid_pairs[:split_idx]
        val_pairs = valid_pairs[split_idx:]

        # Copy train files
        logger.info(f"📁 Copying {len(train_pairs)} train files...")
        for img_file, lbl_file in train_pairs:
            shutil.copy2(img_file, train_img_dir / img_file.name)
            shutil.copy2(lbl_file, train_lbl_dir / lbl_file.name)

        # Copy validation files
        logger.info(f"📁 Copying {len(val_pairs)} validation files...")
        for img_file, lbl_file in val_pairs:
            shutil.copy2(img_file, val_img_dir / img_file.name)
            shutil.copy2(lbl_file, val_lbl_dir / lbl_file.name)

        # Create data.yaml with val instead of test
        yaml_content = {
            'path': str(output_dir),
            'train': 'images/train',
            'val': 'images/val',
            'nc': len(self.config.class_names),
            'names': list(self.config.class_names.values())
        }

        yaml_path = output_dir / 'data.yaml'
        with open(yaml_path, 'w') as f:
            f.write(f"path: {yaml_content['path']}\n")
            f.write(f"train: {yaml_content['train']}\n")
            f.write(f"val: {yaml_content['val']}\n")
            f.write(f"\n")
            f.write(f"nc: {yaml_content['nc']}\n")
            f.write(f"names:\n")
            for name in yaml_content['names']:
                f.write(f"  - {name}\n")

        logger.info(f"📊 Single dataset prepared:")
        logger.info(f"   • Train: {len(train_pairs)} images")
        logger.info(f"   • Val: {len(val_pairs)} images")
        logger.info(f"   • Classes: {len(self.config.class_names)}")

        return output_dir

    def _prepare_split_dataset(self, output_dir: Path):
        """Prepare train/test split dataset (from run_imagenet.sh) in YOLOv11 format."""
        # Create directory structure
        train_img_dir = output_dir / 'images' / 'train'
        train_lbl_dir = output_dir / 'labels' / 'train'
        test_img_dir = output_dir / 'images' / 'test'
        test_lbl_dir = output_dir / 'labels' / 'test'

        for dir_path in [train_img_dir, train_lbl_dir, test_img_dir, test_lbl_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Copy train files
        logger.info("📁 Copying train files...")
        self._copy_files(self.config.train_images_dir, train_img_dir, "images")
        self._copy_files(self.config.train_labels_dir, train_lbl_dir, "labels")

        # Copy test files
        logger.info("📁 Copying test files...")
        self._copy_files(self.config.test_images_dir, test_img_dir, "images")
        self._copy_files(self.config.test_labels_dir, test_lbl_dir, "labels")

        # Create data.yaml
        yaml_path = self.create_dataset_yaml(output_dir)

        # Count files
        train_count = len(list(train_img_dir.glob('*')))
        test_count = len(list(test_img_dir.glob('*')))

        logger.info(f"📊 Split dataset prepared:")
        logger.info(f"   • Train: {train_count} images")
        logger.info(f"   • Test: {test_count} images")
        logger.info(f"   • Classes: {len(self.config.class_names)}")

        return output_dir

    def _copy_files(self, src_dir: str, dst_dir: Path, file_type: str):
        """Copy files from source to destination directory."""
        src_path = Path(src_dir)
        files = list(src_path.glob('*'))

        for file_path in files:
            if file_path.is_file():
                dst_file = dst_dir / file_path.name
                shutil.copy2(file_path, dst_file)

        logger.info(f"   • Copied {len(files)} {file_type} files")

    def upload_dataset(self, dataset_dir: Path):
        """Upload prepared dataset to Roboflow."""
        try:
            logger.info("🚀 Starting upload to Roboflow...")

            version_name = self.config.version_name or "yolo-world-detections"
            version_notes = self.config.version_notes or "CAMINA YOLO-World detections (e-scooter, SUV, delivery_van)"

            # Upload dataset
            version = self.project.upload(
                model_format="yolov11",
                model_path=str(dataset_dir),
                version_name=version_name,
                version_notes=version_notes
            )

            logger.info(f"✅ Upload completed successfully!")
            logger.info(f"🔗 Project URL: {self.project.url}")
            logger.info(f"📦 Version: {version_name}")

            return version

        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            raise

    def run_upload(self, temp_dir: str = "temp_roboflow_upload"):
        """Run complete upload process."""
        temp_path = Path(temp_dir)

        try:
            # Connect to Roboflow
            self.connect_to_roboflow()

            # Prepare dataset
            dataset_dir = self.prepare_yolo_dataset(temp_path)

            # Upload to Roboflow
            version = self.upload_dataset(dataset_dir)

            logger.info("🎉 Upload process completed successfully!")

            return version

        except Exception as e:
            logger.error(f"❌ Upload process failed: {e}")
            raise

        finally:
            # Cleanup temp directory
            if temp_path.exists():
                shutil.rmtree(temp_path)
                logger.info(f"🧹 Cleaned up temporary directory: {temp_path}")


def upload_run_sh_output():
    """Upload results from run.sh (complete pipeline on data/images)."""
    config = UploadConfig(
        # Roboflow credentials
        api_key="YOUR_ROBOFLOW_API_KEY",
        workspace="YOUR_WORKSPACE_NAME",
        project_name="camina-complete-pipeline",

        # Dataset type and paths (run.sh output)
        dataset_type="single",
        images_dir="outputs/mixed/dataset_viz/images",
        labels_dir="outputs/mixed/yolo",

        # Upload settings
        version_name="v1-complete-pipeline",
        version_notes="CAMINA complete pipeline: Stage A + Stage B + e-scooter spatial association + NMS prioritization"
    )

    print("🚀 Uploading run.sh results (Complete Pipeline)")
    print("=" * 60)
    print(f"📁 Images: {config.images_dir}")
    print(f"🏷️  Labels: {config.labels_dir}")
    print(f"📦 Features: All CAMINA pipeline features included")
    print()

    try:
        uploader = RoboflowUploader(config)
        version = uploader.run_upload()
        print("✅ SUCCESS! Complete pipeline dataset uploaded to Roboflow")
        print(f"🔗 Access your dataset at: {uploader.project.url}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False
    return True


def upload_run_imagenet_output():
    """Upload results from run_imagenet.sh (YOLO-World only on dataset_v4i_yolov11)."""
    config = UploadConfig(
        # Roboflow credentials
        api_key="YOUR_ROBOFLOW_API_KEY",
        workspace="YOUR_WORKSPACE_NAME",
        project_name="camina-yolo-world-detections",

        # Dataset type and paths (run_imagenet.sh output)
        dataset_type="split",
        train_images_dir="outputs/imagenet_train/dataset_viz/images",
        train_labels_dir="outputs/imagenet_train/yolo",
        test_images_dir="outputs/imagenet_test/dataset_viz/images",
        test_labels_dir="outputs/imagenet_test/yolo",

        # Upload settings
        version_name="v1-yolo-world-detections",
        version_notes="CAMINA YOLO-World detections for e-scooter, SUV, and delivery_van classes"
    )

    print("🚀 Uploading run_imagenet.sh results (YOLO-World Only)")
    print("=" * 60)
    print(f"📁 Train: {config.train_images_dir}")
    print(f"📁 Test: {config.test_images_dir}")
    print(f"🎯 Classes: e-scooter, SUV, delivery_van")
    print()

    try:
        uploader = RoboflowUploader(config)
        version = uploader.run_upload()
        print("✅ SUCCESS! YOLO-World dataset uploaded to Roboflow")
        print(f"🔗 Access your dataset at: {uploader.project.url}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False
    return True


def main():
    """Main function with upload options."""
    print("🚀 CAMINA Roboflow Upload Script")
    print("=" * 50)
    print()
    print("Choose which dataset to upload:")
    print("1. Complete Pipeline (run.sh output)")
    print("   • Source: outputs/mixed/")
    print("   • Features: Stage A + Stage B + e-scooter logic + NMS")
    print("   • Classes: All 9 CAMINA classes")
    print()
    print("2. YOLO-World Only (run_imagenet.sh output)")
    print("   • Source: outputs/imagenet_train/ + outputs/imagenet_test/")
    print("   • Features: YOLO-World detection only")
    print("   • Classes: e-scooter, SUV, delivery_van")
    print()
    print("3. Both datasets")
    print()

    while True:
        choice = input("Enter your choice (1/2/3): ").strip()

        if choice == "1":
            upload_run_sh_output()
            break
        elif choice == "2":
            upload_run_imagenet_output()
            break
        elif choice == "3":
            print("\n📤 Uploading Complete Pipeline dataset...")
            success1 = upload_run_sh_output()

            print("\n📤 Uploading YOLO-World dataset...")
            success2 = upload_run_imagenet_output()

            if success1 and success2:
                print("\n🎉 Both datasets uploaded successfully!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

    print("\n📝 Remember to:")
    print("   • Update your Roboflow API key and workspace name")
    print("   • Verify the file paths match your actual output locations")
    print("   • Check that both run.sh and run_imagenet.sh have completed successfully")


if __name__ == "__main__":
    main()