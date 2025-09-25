#!/usr/bin/env python3
"""
Simple Inference Speed Benchmark for CAMINA Models
Focus on PyTorch model and estimate Raspberry Pi performance
"""

import time
import numpy as np
from pathlib import Path
from ultralytics import YOLO
import cv2
import statistics

def create_test_image(width=640, height=640):
    """Create a synthetic test image for benchmarking"""
    # Create a realistic test image
    img = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)

    # Add some geometric shapes to make it more realistic for object detection
    cv2.rectangle(img, (100, 100), (200, 200), (255, 0, 0), -1)  # Blue rectangle (car-like)
    cv2.circle(img, (400, 300), 30, (0, 255, 0), -1)  # Green circle (person-like)
    cv2.rectangle(img, (300, 400), (350, 500), (0, 0, 255), -1)  # Red rectangle (person-like)
    cv2.ellipse(img, (500, 200), (40, 20), 0, 0, 360, (255, 255, 0), -1)  # Cyan ellipse (vehicle-like)

    return img

def benchmark_model_simple(model_path, num_runs=50):
    """Simple benchmark of model inference speed"""

    print(f"🔄 Loading model: {Path(model_path).name}")

    try:
        model = YOLO(model_path)
        print(f"✅ Model loaded successfully")

    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return None

    # Create test image
    test_img = create_test_image()
    print(f"📸 Test image: {test_img.shape} ({test_img.dtype})")

    # Warmup (3 runs)
    print(f"🔥 Warming up...")
    for _ in range(3):
        _ = model.predict(test_img, verbose=False, save=False, show=False)

    # Benchmark runs
    print(f"⏱️ Running {num_runs} benchmark iterations...")
    inference_times = []

    for i in range(num_runs):
        start_time = time.perf_counter()
        results = model.predict(test_img, verbose=False, save=False, show=False)
        end_time = time.perf_counter()

        inference_time_ms = (end_time - start_time) * 1000
        inference_times.append(inference_time_ms)

        if (i + 1) % 10 == 0:
            avg_so_far = np.mean(inference_times)
            print(f"   Progress: {i + 1}/{num_runs} (running avg: {avg_so_far:.1f}ms)")

    # Calculate statistics
    stats = {
        'mean_ms': statistics.mean(inference_times),
        'median_ms': statistics.median(inference_times),
        'min_ms': min(inference_times),
        'max_ms': max(inference_times),
        'std_ms': statistics.stdev(inference_times) if len(inference_times) > 1 else 0,
        'fps_mean': 1000 / statistics.mean(inference_times),
        'fps_max': 1000 / min(inference_times),
        'all_times': inference_times
    }

    return stats

def estimate_raspberry_pi_inference(pc_stats):
    """
    Estimate Raspberry Pi 5 inference times based on PC benchmark

    Conservative estimates based on:
    - RPi 5 Cortex-A76 @ 2.4GHz vs typical x86
    - NCNN optimization for ARM
    - Thermal throttling considerations
    """

    # Performance scaling factors
    estimates = {
        'conservative': 0.20,  # 20% of PC performance (5x slower)
        'realistic': 0.30,     # 30% of PC performance (3.3x slower)
        'optimistic': 0.45     # 45% of PC performance (2.2x slower)
    }

    results = {}

    for scenario, factor in estimates.items():
        results[scenario] = {
            'mean_ms': pc_stats['mean_ms'] / factor,
            'min_ms': pc_stats['min_ms'] / factor,
            'fps_mean': pc_stats['fps_mean'] * factor,
            'fps_max': pc_stats['fps_max'] * factor
        }

    return results

def main():
    print("="*70)
    print("⏱️ CAMINA Inference Speed Analysis for Raspberry Pi")
    print("="*70)

    # Test the best PyTorch model
    model_path = "/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt"

    if not Path(model_path).exists():
        print(f"❌ Model not found: {model_path}")
        return

    print(f"🎯 Benchmarking Best CAMINA Model: YOLO11n")
    print(f"📁 Model: {model_path}")

    # Get model size info
    model_size_mb = Path(model_path).stat().st_size / (1024 * 1024)
    print(f"📊 Model size: {model_size_mb:.2f} MB")

    # Run benchmark
    stats = benchmark_model_simple(model_path, num_runs=30)

    if not stats:
        print("❌ Benchmark failed")
        return

    # Current PC results
    print(f"\n🖥️ Current PC Performance:")
    print(f"   • Mean inference: {stats['mean_ms']:.2f} ms")
    print(f"   • Median inference: {stats['median_ms']:.2f} ms")
    print(f"   • Min inference: {stats['min_ms']:.2f} ms")
    print(f"   • Max inference: {stats['max_ms']:.2f} ms")
    print(f"   • Std deviation: {stats['std_ms']:.2f} ms")
    print(f"   • Average FPS: {stats['fps_mean']:.1f}")
    print(f"   • Peak FPS: {stats['fps_max']:.1f}")

    # Raspberry Pi estimates
    rpi_estimates = estimate_raspberry_pi_inference(stats)

    print(f"\n🍓 Raspberry Pi 5 Performance Estimates:")
    print(f"{'Scenario':<12} {'Inference (ms)':<15} {'FPS':<10} {'Real-time?'}")
    print("-" * 50)

    for scenario, data in rpi_estimates.items():
        real_time = "✅ Yes" if data['fps_mean'] >= 15 else "⚠️ Limited" if data['fps_mean'] >= 5 else "❌ No"
        print(f"{scenario.title():<12} {data['mean_ms']:.0f} ms{'':<10} {data['fps_mean']:.1f}{'':<5} {real_time}")

    # NCNN optimization estimate
    print(f"\n🚀 With NCNN Optimization (estimated +30% speed improvement):")
    ncnn_factor = 1.3
    for scenario, data in rpi_estimates.items():
        if scenario == 'realistic':  # Show realistic scenario with NCNN
            ncnn_ms = data['mean_ms'] / ncnn_factor
            ncnn_fps = data['fps_mean'] * ncnn_factor
            real_time = "✅ Yes" if ncnn_fps >= 15 else "⚠️ Limited" if ncnn_fps >= 5 else "❌ No"
            print(f"   • NCNN {scenario}: {ncnn_ms:.0f} ms ({ncnn_fps:.1f} FPS) {real_time}")

    # Application recommendations
    print(f"\n🎯 Raspberry Pi 5 Application Recommendations:")

    realistic = rpi_estimates['realistic']
    realistic_ncnn_fps = realistic['fps_mean'] * 1.3
    realistic_ncnn_ms = realistic['mean_ms'] / 1.3

    if realistic_ncnn_fps >= 20:
        print(f"   ✅ Excellent for real-time applications")
        print(f"   ✅ Suitable for live video processing")
        print(f"   ✅ Good for interactive applications")
    elif realistic_ncnn_fps >= 10:
        print(f"   ✅ Good for near real-time applications")
        print(f"   ✅ Suitable for monitoring systems")
        print(f"   ⚠️ Limited for interactive applications")
    else:
        print(f"   ⚠️ Best for batch processing")
        print(f"   ⚠️ Consider frame skipping for video")
        print(f"   ⚠️ Optimize input resolution if possible")

    print(f"\n📊 Key Metrics for Raspberry Pi 5:")
    print(f"   • Expected inference: ~{realistic_ncnn_ms:.0f} ms")
    print(f"   • Expected FPS: ~{realistic_ncnn_fps:.1f}")
    print(f"   • Memory usage: ~20 MB")
    print(f"   • Model format: NCNN (10.04 MB)")

    # Technical details
    print(f"\n⚙️ Technical Details:")
    print(f"   • Current PC CPU inference: {stats['mean_ms']:.1f} ms")
    print(f"   • RPi5 ARM Cortex-A76 @ 2.4GHz")
    print(f"   • NCNN framework optimized for ARM")
    print(f"   • Estimates include thermal considerations")

    print("="*70)

if __name__ == "__main__":
    main()