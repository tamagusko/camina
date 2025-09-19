#!/usr/bin/env python3
"""
Quick Label Checker for CAMINA
Simple script to quickly check labels on your test images
"""

import argparse
import random
from pathlib import Path
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description="Quick check CAMINA auto-generated labels")
    parser.add_argument("dataset_path", help="Path to dataset (e.g., img/output_test)")
    parser.add_argument("--random", "-r", action="store_true", help="Show random images")
    parser.add_argument("--count", "-c", type=int, default=3, help="Number of images to show")
    parser.add_argument("--image", "-i", help="Specific image to check")
    parser.add_argument("--save", "-s", action="store_true", help="Save visualizations")

    args = parser.parse_args()

    dataset_path = Path(args.dataset_path)
    images_dir = dataset_path / "images"

    if not images_dir.exists():
        print(f"❌ Images directory not found: {images_dir}")
        return

    # Get available images
    image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))

    if not image_files:
        print("❌ No images found in dataset")
        return

    print(f"🖼️  Found {len(image_files)} images in dataset")

    # Prepare visualization command base
    viz_cmd = [sys.executable, "visualize_labels.py", str(dataset_path)]
    if args.save:
        viz_cmd.extend(["--save", "--output-dir", "img/visualizations"])

    # Check specific image
    if args.image:
        print(f"\n🔍 Checking specific image: {args.image}")
        cmd = viz_cmd + ["--image", args.image]
        subprocess.run(cmd)
        return

    # Show random images or first few
    if args.random:
        selected_images = random.sample(image_files, min(args.count, len(image_files)))
        print(f"\n🎲 Checking {len(selected_images)} random images:")
    else:
        selected_images = image_files[:args.count]
        print(f"\n🔍 Checking first {len(selected_images)} images:")

    for img_file in selected_images:
        print(f"\n📸 Checking: {img_file.name}")
        cmd = viz_cmd + ["--image", img_file.name]
        subprocess.run(cmd)

        # Wait for user input to continue (unless saving)
        if not args.save:
            input("Press Enter to continue to next image (Ctrl+C to exit)...")

if __name__ == "__main__":
    main()