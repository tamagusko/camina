#!/usr/bin/env python3
"""
CAMINA NCNN Model Inference Speed Benchmark
Test inference times for the NCNN optimized model to estimate Raspberry Pi performance
"""

import time
import numpy as np
from pathlib import Path
from ultralytics import YOLO
import cv2
import statistics

def create_test_image(width=640, height=640):
    """Create a synthetic test image for benchmarking"""
    # Create a realistic test image with some patterns
    img = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)

    # Add some geometric shapes to make it more realistic
    cv2.rectangle(img, (100, 100), (200, 200), (255, 0, 0), -1)
    cv2.circle(img, (400, 300), 50, (0, 255, 0), -1)
    cv2.rectangle(img, (300, 400), (500, 500), (0, 0, 255), -1)

    return img

def benchmark_model(model_path, num_runs=50, warmup_runs=10):
    """Benchmark inference speed of a model"""

    print(f"🔄 Loading model: {model_path}")

    try:
        model = YOLO(model_path)
        print(f"✅ Model loaded successfully")
        print(f"📊 Model info:")
        print(f"   - Task: {model.task}")
        if hasattr(model, 'device'):
            print(f"   - Device: {model.device}")

    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return None

    # Create test image
    test_img = create_test_image()
    print(f"📸 Test image created: {test_img.shape}")

    # Warmup runs (don't count these)
    print(f"🔥 Warming up model with {warmup_runs} runs...")
    for i in range(warmup_runs):
        try:
            _ = model.predict(test_img, verbose=False, save=False, show=False)
            if (i + 1) % 5 == 0:
                print(f"   Warmup progress: {i + 1}/{warmup_runs}")
        except Exception as e:
            print(f"⚠️ Warmup run {i+1} failed: {e}")
            if i < 3:  # If first few runs fail, abort
                return None

    print(f"✅ Warmup complete")

    # Actual benchmark runs
    print(f"⏱️ Running {num_runs} benchmark iterations...")
    inference_times = []
    successful_runs = 0

    for i in range(num_runs):
        try:
            start_time = time.perf_counter()
            results = model.predict(test_img, verbose=False, save=False, show=False)
            end_time = time.perf_counter()

            inference_time_ms = (end_time - start_time) * 1000
            inference_times.append(inference_time_ms)
            successful_runs += 1

            if (i + 1) % 10 == 0:
                print(f"   Progress: {i + 1}/{num_runs} (avg: {np.mean(inference_times):.1f}ms)")

        except Exception as e:
            print(f"⚠️ Run {i+1} failed: {e}")

    if successful_runs == 0:
        print(f"❌ All benchmark runs failed")
        return None

    if successful_runs < num_runs:
        print(f"⚠️ Only {successful_runs}/{num_runs} runs succeeded")

    # Calculate statistics
    stats = {
        'successful_runs': successful_runs,
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

def estimate_raspberry_pi_performance(pc_stats, cpu_ratio=0.3):
    """
    Estimate Raspberry Pi performance based on PC benchmark

    Args:
        pc_stats: PC benchmark results
        cpu_ratio: Performance ratio (RPi5 / PC) - conservative estimate
    """
    if not pc_stats:
        return None

    estimated_stats = {
        'mean_ms': pc_stats['mean_ms'] / cpu_ratio,
        'median_ms': pc_stats['median_ms'] / cpu_ratio,
        'min_ms': pc_stats['min_ms'] / cpu_ratio,
        'max_ms': pc_stats['max_ms'] / cpu_ratio,
        'fps_mean': pc_stats['fps_mean'] * cpu_ratio,
        'fps_max': pc_stats['fps_max'] * cpu_ratio
    }

    return estimated_stats

def main():
    print("="*80)
    print("⏱️ CAMINA NCNN Inference Speed Benchmark")
    print("="*80)

    # Test both PyTorch and NCNN models
    models_to_test = {
        "PyTorch Original": "/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt",
        "NCNN Optimized": "/home/tiago/repos/camina/model/raspberry_pi_deployment/yolo11n_best_ncnn"
    }

    results = {}

    for model_name, model_path in models_to_test.items():
        print(f"\n🎯 Benchmarking {model_name}")
        print("-" * 50)

        if not Path(model_path).exists():
            print(f"❌ Model not found: {model_path}")
            continue

        stats = benchmark_model(model_path, num_runs=30, warmup_runs=5)
        results[model_name] = stats

        if stats:
            print(f"✅ Benchmark completed for {model_name}")
            print(f"📊 Results:")
            print(f"   • Mean inference: {stats['mean_ms']:.1f} ms")
            print(f"   • Median inference: {stats['median_ms']:.1f} ms")
            print(f"   • Min inference: {stats['min_ms']:.1f} ms")
            print(f"   • Max inference: {stats['max_ms']:.1f} ms")
            print(f"   • Std deviation: {stats['std_ms']:.1f} ms")
            print(f"   • Average FPS: {stats['fps_mean']:.1f}")
            print(f"   • Max FPS: {stats['fps_max']:.1f}")
        else:
            print(f"❌ Benchmark failed for {model_name}")

    # Summary and Raspberry Pi estimates
    print(f"\n" + "="*80)
    print("📊 BENCHMARK SUMMARY & RASPBERRY PI 5 ESTIMATES")
    print("="*80)

    for model_name, stats in results.items():
        if not stats:
            continue

        print(f"\n🖥️ {model_name} (Current PC):")
        print(f"   • Inference Time: {stats['mean_ms']:.1f} ± {stats['std_ms']:.1f} ms")
        print(f"   • FPS: {stats['fps_mean']:.1f}")

        # Estimate Raspberry Pi performance
        # RPi5 Cortex-A76 vs typical x86 - conservative estimate ~30% performance
        rpi_conservative = estimate_raspberry_pi_performance(stats, cpu_ratio=0.25)
        rpi_optimistic = estimate_raspberry_pi_performance(stats, cpu_ratio=0.40)

        print(f"🍓 Raspberry Pi 5 Estimates:")
        print(f"   • Conservative: {rpi_conservative['mean_ms']:.0f} ms ({rpi_conservative['fps_mean']:.1f} FPS)")
        print(f"   • Optimistic:   {rpi_optimistic['mean_ms']:.0f} ms ({rpi_optimistic['fps_mean']:.1f} FPS)")

    # Model comparison
    if len(results) > 1:
        pytorch_stats = results.get("PyTorch Original")
        ncnn_stats = results.get("NCNN Optimized")

        if pytorch_stats and ncnn_stats:
            speedup = pytorch_stats['mean_ms'] / ncnn_stats['mean_ms']
            print(f"\n🚀 NCNN vs PyTorch Performance:")
            print(f"   • NCNN Speedup: {speedup:.2f}x faster")
            print(f"   • PyTorch: {pytorch_stats['mean_ms']:.1f} ms")
            print(f"   • NCNN:    {ncnn_stats['mean_ms']:.1f} ms")

    # Raspberry Pi recommendations
    print(f"\n🎯 Raspberry Pi 5 Deployment Recommendations:")
    if "NCNN Optimized" in results and results["NCNN Optimized"]:
        ncnn_stats = results["NCNN Optimized"]
        rpi_estimate = estimate_raspberry_pi_performance(ncnn_stats, cpu_ratio=0.30)

        estimated_ms = rpi_estimate['mean_ms']
        estimated_fps = rpi_estimate['fps_mean']

        print(f"   • Expected inference: ~{estimated_ms:.0f} ms")
        print(f"   • Expected FPS: ~{estimated_fps:.1f}")

        if estimated_fps >= 15:
            print(f"   • ✅ Suitable for real-time applications")
        elif estimated_fps >= 5:
            print(f"   • ⚠️ Suitable for near real-time applications")
        else:
            print(f"   • ⚠️ Best for batch processing applications")

        if estimated_ms <= 100:
            print(f"   • ✅ Excellent edge device performance")
        elif estimated_ms <= 200:
            print(f"   • ✅ Good edge device performance")
        else:
            print(f"   • ⚠️ Moderate edge device performance")

    print("="*80)

if __name__ == "__main__":
    main()