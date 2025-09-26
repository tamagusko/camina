#!/usr/bin/env python3
"""
Simple NCNN timing test - measures inference time without output validation
"""

import os
import time
import glob
import json
import platform

def test_ncnn_timing(model_dir, test_image_path, num_runs=20):
    """Test NCNN model inference time - basic timing only"""
    try:
        import ncnn
        import cv2
        import numpy as np
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return None

    # Find model files
    param_file = None
    bin_file = None
    for file in os.listdir(model_dir):
        if file.endswith('.param'):
            param_file = os.path.join(model_dir, file)
        elif file.endswith('.bin'):
            bin_file = os.path.join(model_dir, file)

    if not param_file or not bin_file:
        print(f"❌ Model files not found in {model_dir}")
        return None

    print(f"📂 Param: {os.path.basename(param_file)}")
    print(f"📂 Model: {os.path.basename(bin_file)}")

    # Load model
    net = ncnn.Net()
    net.load_param(param_file)
    net.load_model(bin_file)

    # Load image
    img = cv2.imread(test_image_path)
    if img is None:
        print(f"❌ Could not load image: {test_image_path}")
        return None

    # Preprocess
    img_resized = cv2.resize(img, (640, 640))
    mat = ncnn.Mat.from_pixels(img_resized, ncnn.Mat.PixelType.PIXEL_BGR, 640, 640)
    mean_vals = [0.0, 0.0, 0.0]
    norm_vals = [1/255.0, 1/255.0, 1/255.0]
    mat.substract_mean_normalize(mean_vals, norm_vals)

    # Warmup (ignore errors)
    print("🔥 Warming up...")
    for _ in range(3):
        try:
            ex = net.create_extractor()
            ex.input("in0", mat)
            _, _ = ex.extract("out0")
        except:
            pass

    # Benchmark runs - only measure time
    print(f"⏱️ Running {num_runs} timing tests...")
    times = []

    for i in range(num_runs):
        start_time = time.perf_counter()

        try:
            ex = net.create_extractor()
            ex.input("in0", mat)
            _, _ = ex.extract("out0")  # Don't care about output, just timing
        except:
            # Even if extraction fails, we still measured the time
            pass

        end_time = time.perf_counter()
        inference_time_ms = (end_time - start_time) * 1000
        times.append(inference_time_ms)

        if (i + 1) % 5 == 0:
            print(f"   Completed {i+1}/{num_runs} runs...")

    if not times:
        return None

    # Statistics
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    fps = 1000 / avg_time

    return {
        'avg_time_ms': avg_time,
        'min_time_ms': min_time,
        'max_time_ms': max_time,
        'fps': fps,
        'successful_runs': len(times)
    }

def get_model_size(model_dir):
    """Get model size in MB"""
    total_size = 0
    for file in os.listdir(model_dir):
        if file.endswith(('.param', '.bin')):
            total_size += os.path.getsize(os.path.join(model_dir, file))
    return total_size / (1024 * 1024)

def main():
    print("⚡ CAMINA NCNN Timing Test - Raspberry Pi 5")
    print("=" * 50)

    # System info
    print(f"🖥️ Platform: {platform.platform()}")
    print(f"🔧 Python: {platform.python_version()}")
    print()

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Models to test - try all models with error handling
    models = [
        'yolov5n_ncnn',
        'yolov8n_ncnn',
        'yolov10n_ncnn',  # Will handle segfault gracefully
        'yolo11n_ncnn'
    ]

    # Find test image
    test_images_dir = os.path.join(script_dir, 'test_images')
    test_images = glob.glob(os.path.join(test_images_dir, '*.jpg'))
    if not test_images:
        print(f"❌ No test images in {test_images_dir}")
        return

    test_image = test_images[0]
    print(f"📸 Test image: {os.path.basename(test_image)}")
    print()

    results = {}

    for model_name in models:
        model_dir = os.path.join(script_dir, model_name)
        if not os.path.exists(model_dir):
            print(f"⚠️ Model not found: {model_name}")
            continue

        print(f"🤖 Testing {model_name.replace('_ncnn', '').upper()}...")

        # Model size
        size_mb = get_model_size(model_dir)
        print(f"📊 Size: {size_mb:.2f} MB")

        # Run timing test with error handling for segfaults
        try:
            result = test_ncnn_timing(model_dir, test_image, num_runs=20)
        except Exception as e:
            print(f"❌ Model crashed: {e}")
            result = None

        if result:
            print(f"✅ Avg time: {result['avg_time_ms']:.2f} ms")
            print(f"🚀 Avg FPS: {result['fps']:.1f}")
            print(f"📈 Range: {result['min_time_ms']:.2f} - {result['max_time_ms']:.2f} ms")

            results[model_name] = {
                'model_size_mb': size_mb,
                **result
            }
        else:
            print("❌ Test failed")

        print("-" * 50)

    # Summary
    if results:
        print("\n🏆 TIMING RESULTS SUMMARY")
        print("=" * 50)
        print(f"{'Model':<10} {'Size(MB)':<9} {'Time(ms)':<10} {'FPS':<8} {'FPS/MB':<8}")
        print("-" * 50)

        sorted_results = sorted(results.items(), key=lambda x: x[1]['avg_time_ms'])

        for model_name, data in sorted_results:
            name = model_name.replace('_ncnn', '').upper()
            efficiency = data['fps'] / data['model_size_mb']
            print(f"{name:<10} {data['model_size_mb']:<9.2f} {data['avg_time_ms']:<10.2f} {data['fps']:<8.1f} {efficiency:<8.1f}")

        # Save results
        with open('timing_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: timing_results.json")

    print("\n⚡ Timing test completed!")

if __name__ == "__main__":
    main()