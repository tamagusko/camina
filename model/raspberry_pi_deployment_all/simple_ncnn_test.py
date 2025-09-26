#!/usr/bin/env python3
"""
Simple NCNN inference test for Raspberry Pi 5
Tests inference time for all 4 YOLO models converted to NCNN format
"""

import os
import time
import glob
from pathlib import Path
import json
import platform

def test_ncnn_model(model_dir, test_image_path, num_runs=10):
    """Test NCNN model inference time"""
    try:
        import ncnn
        import cv2
        import numpy as np
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Install with: pip install opencv-python numpy")
        return None

    # Find .param and .bin files
    param_file = None
    bin_file = None

    for file in os.listdir(model_dir):
        if file.endswith('.param'):
            param_file = os.path.join(model_dir, file)
        elif file.endswith('.bin'):
            bin_file = os.path.join(model_dir, file)

    if not param_file or not bin_file:
        print(f"❌ Could not find .param and .bin files in {model_dir}")
        return None

    print(f"📂 Using: {os.path.basename(param_file)}")

    # Initialize NCNN network
    net = ncnn.Net()
    net.load_param(param_file)
    net.load_model(bin_file)

    # Load and preprocess image
    img = cv2.imread(test_image_path)
    if img is None:
        print(f"❌ Could not load image: {test_image_path}")
        return None

    # Resize to 640x640 (standard YOLO input)
    img_resized = cv2.resize(img, (640, 640))

    # Convert to ncnn Mat
    mat = ncnn.Mat.from_pixels(img_resized, ncnn.Mat.PixelType.PIXEL_BGR, 640, 640)

    # Normalize (assuming standard YOLO normalization)
    mean_vals = [0.0, 0.0, 0.0]
    norm_vals = [1/255.0, 1/255.0, 1/255.0]
    mat.substract_mean_normalize(mean_vals, norm_vals)

    # Warmup runs
    print("🔥 Warming up...")
    for _ in range(3):
        try:
            ex = net.create_extractor()
            ex.input("images", mat)
            _, _ = ex.extract("output0")  # Assuming standard YOLO output name
        except:
            # Try different input/output names
            try:
                ex = net.create_extractor()
                ex.input("in0", mat)
                _, _ = ex.extract("out0")
            except:
                print("⚠️ Could not determine input/output layer names")
                break

    # Benchmark runs
    times = []
    print(f"⏱️ Running {num_runs} inference tests...")

    for i in range(num_runs):
        start_time = time.perf_counter()

        try:
            ex = net.create_extractor()
            ex.input("images", mat)
            _, result = ex.extract("output0")
        except:
            try:
                ex = net.create_extractor()
                ex.input("in0", mat)
                _, result = ex.extract("out0")
            except Exception as e:
                print(f"⚠️ Run {i+1} failed: {e}")
                continue

        end_time = time.perf_counter()
        inference_time_ms = (end_time - start_time) * 1000
        times.append(inference_time_ms)

        if (i + 1) % 3 == 0:
            print(f"   Completed {i+1}/{num_runs} runs...")

    if not times:
        return None

    # Calculate statistics
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    fps = 1000 / avg_time

    return {
        'avg_time_ms': avg_time,
        'min_time_ms': min_time,
        'max_time_ms': max_time,
        'fps': fps,
        'successful_runs': len(times),
        'total_runs': num_runs
    }

def get_model_size(model_dir):
    """Get total size of model files in MB"""
    total_size = 0
    for file in os.listdir(model_dir):
        if file.endswith(('.param', '.bin')):
            total_size += os.path.getsize(os.path.join(model_dir, file))
    return total_size / (1024 * 1024)  # Convert to MB

def main():
    print("🚀 CAMINA NCNN Inference Test on Raspberry Pi 5")
    print("=" * 60)

    # System info
    print(f"🖥️ Platform: {platform.platform()}")
    print(f"🔧 Python: {platform.python_version()}")

    # Find models
    model_dirs = [
        'yolov5n_ncnn',
        'yolov8n_ncnn',
        'yolov10n_ncnn',
        'yolo11n_ncnn'
    ]

    # Find test images (check both current dir and script dir)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_images_dir = os.path.join(script_dir, 'test_images')
    if not os.path.exists(test_images_dir):
        test_images_dir = 'test_images'
    if not os.path.exists(test_images_dir):
        print(f"❌ Test images directory not found: {test_images_dir}")
        print("Please add some test images to the test_images/ folder")
        return

    test_images = glob.glob(os.path.join(test_images_dir, '*.jpg'))
    if not test_images:
        print(f"❌ No test images found in {test_images_dir}")
        return

    test_image = test_images[0]  # Use first image
    print(f"📸 Using test image: {os.path.basename(test_image)}")
    print()

    results = {}

    for model_dir in model_dirs:
        # Check both current dir and script dir for models
        full_model_path = os.path.join(script_dir, model_dir) if not os.path.exists(model_dir) else model_dir
        if not os.path.exists(full_model_path):
            print(f"⚠️ Model directory not found: {model_dir}")
            continue
        model_dir = full_model_path

        print(f"🤖 Testing {model_dir}...")

        # Get model size
        model_size = get_model_size(model_dir)
        print(f"📊 Model size: {model_size:.2f} MB")

        # Run inference test
        result = test_ncnn_model(model_dir, test_image, num_runs=10)

        if result:
            print(f"✅ Average inference time: {result['avg_time_ms']:.1f} ms")
            print(f"🚀 Average FPS: {result['fps']:.1f}")
            print(f"📈 Range: {result['min_time_ms']:.1f} - {result['max_time_ms']:.1f} ms")
            print(f"✔️ Success rate: {result['successful_runs']}/{result['total_runs']}")

            results[model_dir] = {
                'model_size_mb': model_size,
                **result
            }
        else:
            print("❌ Test failed")

        print("-" * 60)

    # Summary
    if results:
        print("\n🏆 PERFORMANCE SUMMARY")
        print("=" * 60)
        print(f"{'Model':<15} {'Size (MB)':<10} {'Avg Time (ms)':<15} {'FPS':<8} {'Efficiency':<12}")
        print("-" * 60)

        # Sort by average time (fastest first)
        sorted_results = sorted(results.items(), key=lambda x: x[1]['avg_time_ms'])

        for model_dir, data in sorted_results:
            model_name = model_dir.replace('_ncnn', '').upper()
            efficiency = data['fps'] / data['model_size_mb']  # FPS per MB
            print(f"{model_name:<15} {data['model_size_mb']:<10.2f} {data['avg_time_ms']:<15.1f} {data['fps']:<8.1f} {efficiency:<12.1f}")

        # Save results
        with open('ncnn_benchmark_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: ncnn_benchmark_results.json")

    print("\n🎉 Benchmark completed!")

if __name__ == "__main__":
    main()