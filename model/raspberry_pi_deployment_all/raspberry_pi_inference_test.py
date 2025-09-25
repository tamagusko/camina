#!/usr/bin/env python3
"""
CAMINA Raspberry Pi 5 Inference Test Script
Benchmark all NCNN models on Raspberry Pi and compare performance
"""

import time
import json
import numpy as np
import cv2
import statistics
import psutil
import platform
from pathlib import Path
from ultralytics import YOLO
import argparse
import sys

def get_system_info():
    """Get system information for the benchmark"""
    return {
        'platform': platform.platform(),
        'processor': platform.processor(),
        'architecture': platform.machine(),
        'python_version': platform.python_version(),
        'cpu_count': psutil.cpu_count(),
        'memory_total_gb': psutil.virtual_memory().total / (1024**3),
        'memory_available_gb': psutil.virtual_memory().available / (1024**3)
    }

def check_raspberry_pi():
    """Check if running on Raspberry Pi"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            content = f.read()
            return 'Raspberry Pi' in content or 'BCM' in content
    except:
        return False

def create_test_images(num_images=5, width=640, height=640):
    """Create multiple test images with different complexity levels"""
    images = []

    # Image 1: Simple geometric shapes
    img1 = np.random.randint(50, 200, (height, width, 3), dtype=np.uint8)
    cv2.rectangle(img1, (100, 100), (200, 200), (255, 0, 0), -1)
    cv2.circle(img1, (400, 300), 30, (0, 255, 0), -1)
    images.append(("simple_shapes", img1))

    # Image 2: Complex urban scene simulation
    img2 = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    # Simulate cars
    for i in range(3):
        x, y = np.random.randint(50, width-100), np.random.randint(50, height-80)
        cv2.rectangle(img2, (x, y), (x+80, y+40), (0, 0, 255), -1)
    # Simulate people
    for i in range(5):
        x, y = np.random.randint(50, width-20), np.random.randint(50, height-60)
        cv2.ellipse(img2, (x, y), (10, 30), 0, 0, 360, (255, 255, 0), -1)
    images.append(("complex_urban", img2))

    # Image 3: High contrast
    img3 = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.rectangle(img3, (150, 150), (250, 250), (255, 255, 255), -1)
    cv2.circle(img3, (400, 300), 50, (128, 128, 128), -1)
    images.append(("high_contrast", img3))

    # Image 4: Noisy image
    img4 = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    images.append(("noisy", img4))

    # Image 5: Real-world like (mixed complexity)
    img5 = np.random.randint(100, 200, (height, width, 3), dtype=np.uint8)
    # Add realistic objects
    cv2.rectangle(img5, (50, 300), (150, 400), (100, 50, 200), -1)  # Vehicle-like
    cv2.ellipse(img5, (300, 200), (15, 40), 0, 0, 360, (200, 200, 100), -1)  # Person-like
    cv2.rectangle(img5, (450, 250), (480, 320), (50, 200, 50), -1)  # Pole-like
    images.append(("realistic_mixed", img5))

    return images

def benchmark_model(model_path, test_images, num_runs_per_image=10, warmup_runs=3):
    """Benchmark a single model with multiple test images"""

    model_name = Path(model_path).name
    print(f"\n🎯 Benchmarking {model_name}")
    print("-" * 50)

    try:
        print(f"🔄 Loading model...")
        start_load = time.perf_counter()

        # Handle both directory and file paths
        if Path(model_path).is_dir():
            model = YOLO(model_path, task='detect')
        else:
            model = YOLO(model_path)

        load_time = (time.perf_counter() - start_load) * 1000
        print(f"✅ Model loaded in {load_time:.1f} ms")

        # Get model info
        try:
            model_size_mb = get_model_size(model_path)
            print(f"📊 Model size: {model_size_mb:.2f} MB")
        except:
            model_size_mb = 0

    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return None

    # Test each image type
    results = {
        'model_name': model_name,
        'model_path': str(model_path),
        'model_size_mb': model_size_mb,
        'load_time_ms': load_time,
        'image_results': {},
        'overall_stats': {}
    }

    all_times = []

    for img_name, test_img in test_images:
        print(f"📸 Testing with {img_name} image...")

        # Warmup runs
        for _ in range(warmup_runs):
            try:
                _ = model.predict(test_img, verbose=False, save=False, show=False)
            except Exception as e:
                print(f"⚠️ Warmup failed for {img_name}: {e}")
                continue

        # Benchmark runs
        img_times = []
        successful_runs = 0

        for run in range(num_runs_per_image):
            try:
                start_time = time.perf_counter()
                results_pred = model.predict(test_img, verbose=False, save=False, show=False)
                end_time = time.perf_counter()

                inference_time_ms = (end_time - start_time) * 1000
                img_times.append(inference_time_ms)
                all_times.append(inference_time_ms)
                successful_runs += 1

            except Exception as e:
                print(f"⚠️ Run {run+1} failed for {img_name}: {e}")

        if successful_runs > 0:
            img_stats = {
                'successful_runs': successful_runs,
                'mean_ms': statistics.mean(img_times),
                'median_ms': statistics.median(img_times),
                'min_ms': min(img_times),
                'max_ms': max(img_times),
                'std_ms': statistics.stdev(img_times) if len(img_times) > 1 else 0,
                'fps_mean': 1000 / statistics.mean(img_times),
                'fps_max': 1000 / min(img_times)
            }

            results['image_results'][img_name] = img_stats
            print(f"   Avg: {img_stats['mean_ms']:.1f} ms ({img_stats['fps_mean']:.1f} FPS)")
        else:
            print(f"   ❌ All runs failed for {img_name}")

    # Overall statistics
    if all_times:
        results['overall_stats'] = {
            'total_successful_runs': len(all_times),
            'mean_ms': statistics.mean(all_times),
            'median_ms': statistics.median(all_times),
            'min_ms': min(all_times),
            'max_ms': max(all_times),
            'std_ms': statistics.stdev(all_times) if len(all_times) > 1 else 0,
            'fps_mean': 1000 / statistics.mean(all_times),
            'fps_max': 1000 / min(all_times),
            'fps_min': 1000 / max(all_times)
        }

        print(f"📊 Overall Performance:")
        print(f"   Mean: {results['overall_stats']['mean_ms']:.1f} ± {results['overall_stats']['std_ms']:.1f} ms")
        print(f"   Range: {results['overall_stats']['min_ms']:.1f} - {results['overall_stats']['max_ms']:.1f} ms")
        print(f"   FPS: {results['overall_stats']['fps_mean']:.1f} (avg), {results['overall_stats']['fps_max']:.1f} (max)")

    return results

def get_model_size(model_path):
    """Get model size in MB"""
    path = Path(model_path)
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    elif path.is_dir():
        total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return total_size / (1024 * 1024)
    return 0

def generate_benchmark_report(system_info, all_results, output_file="benchmark_results.json"):
    """Generate comprehensive benchmark report"""

    # Sort results by performance
    valid_results = [r for r in all_results if r and 'overall_stats' in r and r['overall_stats']]
    valid_results.sort(key=lambda x: x['overall_stats']['mean_ms'])

    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'system_info': system_info,
        'is_raspberry_pi': check_raspberry_pi(),
        'benchmark_summary': {
            'total_models_tested': len(all_results),
            'successful_models': len(valid_results),
            'test_images': len(create_test_images()),
            'runs_per_image': 10
        },
        'model_results': all_results,
        'performance_ranking': []
    }

    # Create performance ranking
    for i, result in enumerate(valid_results):
        ranking_entry = {
            'rank': i + 1,
            'model_name': result['model_name'],
            'avg_inference_ms': result['overall_stats']['mean_ms'],
            'avg_fps': result['overall_stats']['fps_mean'],
            'model_size_mb': result['model_size_mb'],
            'fps_per_mb': result['overall_stats']['fps_mean'] / result['model_size_mb'] if result['model_size_mb'] > 0 else 0
        }
        report['performance_ranking'].append(ranking_entry)

    # Save report
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    return report

def print_summary_table(report):
    """Print a nice summary table"""

    print("\n" + "="*80)
    print("📊 CAMINA RASPBERRY PI INFERENCE BENCHMARK RESULTS")
    print("="*80)

    # System info
    sys_info = report['system_info']
    print(f"\n🖥️ System Information:")
    print(f"   Platform: {sys_info['platform']}")
    print(f"   Processor: {sys_info['processor']}")
    print(f"   CPU Cores: {sys_info['cpu_count']}")
    print(f"   Memory: {sys_info['memory_total_gb']:.1f} GB total, {sys_info['memory_available_gb']:.1f} GB available")
    print(f"   Raspberry Pi: {'✅ Yes' if report['is_raspberry_pi'] else '❌ No'}")

    # Performance table
    print(f"\n🏆 Model Performance Ranking:")
    print("Rank | Model      | Avg Time | Avg FPS | Size   | FPS/MB | Real-time")
    print("-" * 70)

    for entry in report['performance_ranking']:
        real_time = "✅" if entry['avg_fps'] >= 15 else "⚠️" if entry['avg_fps'] >= 5 else "❌"
        print(f" #{entry['rank']:<2} | {entry['model_name']:<10} | {entry['avg_inference_ms']:.1f} ms | {entry['avg_fps']:6.1f} | {entry['model_size_mb']:5.1f}MB | {entry['fps_per_mb']:5.1f} | {real_time}")

    # Recommendations
    print(f"\n🎯 Recommendations:")
    if report['performance_ranking']:
        best = report['performance_ranking'][0]
        most_efficient = max(report['performance_ranking'], key=lambda x: x['fps_per_mb'])

        print(f"   🏆 Fastest: {best['model_name']} ({best['avg_inference_ms']:.1f} ms)")
        print(f"   ⚡ Most Efficient: {most_efficient['model_name']} ({most_efficient['fps_per_mb']:.1f} FPS/MB)")

        if report['is_raspberry_pi']:
            print(f"   🍓 Raspberry Pi Optimized: All models tested on actual hardware")
        else:
            print(f"   🖥️ PC Benchmark: Results may be faster than actual Raspberry Pi performance")

    print("="*80)

def main():
    parser = argparse.ArgumentParser(description='CAMINA NCNN Models Inference Benchmark for Raspberry Pi')
    parser.add_argument('--models-dir', type=str,
                       default='/home/pi/camina_models',
                       help='Directory containing NCNN models (default: /home/pi/camina_models)')
    parser.add_argument('--output', type=str,
                       default='camina_benchmark_results.json',
                       help='Output file for results (default: camina_benchmark_results.json)')
    parser.add_argument('--runs', type=int, default=10,
                       help='Number of runs per image (default: 10)')
    parser.add_argument('--warmup', type=int, default=3,
                       help='Number of warmup runs (default: 3)')

    args = parser.parse_args()

    print("="*80)
    print("🍓 CAMINA Raspberry Pi 5 NCNN Models Benchmark")
    print("="*80)

    # Check system
    system_info = get_system_info()
    is_rpi = check_raspberry_pi()

    print(f"🖥️ Running on: {system_info['platform']}")
    print(f"🍓 Raspberry Pi: {'✅ Detected' if is_rpi else '❌ Not detected'}")
    print(f"💾 Memory: {system_info['memory_available_gb']:.1f} GB available")

    # Find models
    models_dir = Path(args.models_dir)
    if not models_dir.exists():
        # Try alternative locations
        alternative_paths = [
            Path('/home/tiago/repos/camina/model/raspberry_pi_deployment_all'),
            Path('./model/raspberry_pi_deployment_all'),
            Path('./models')
        ]

        for alt_path in alternative_paths:
            if alt_path.exists():
                models_dir = alt_path
                print(f"📁 Using models from: {models_dir}")
                break
        else:
            print(f"❌ Models directory not found: {args.models_dir}")
            print(f"   Tried: {args.models_dir}")
            for alt in alternative_paths:
                print(f"   Tried: {alt}")
            return 1

    # Find NCNN models
    model_paths = []
    for pattern in ['*_ncnn', '*ncnn*']:
        model_paths.extend(list(models_dir.glob(pattern)))

    if not model_paths:
        print(f"❌ No NCNN models found in {models_dir}")
        return 1

    print(f"📦 Found {len(model_paths)} NCNN models:")
    for model_path in model_paths:
        size = get_model_size(model_path)
        print(f"   • {model_path.name} ({size:.1f} MB)")

    # Create test images
    print(f"\n📸 Creating test images...")
    test_images = create_test_images()
    print(f"   Created {len(test_images)} test images with different complexity levels")

    # Benchmark all models
    all_results = []

    for i, model_path in enumerate(model_paths):
        print(f"\n[{i+1}/{len(model_paths)}] Testing {model_path.name}...")
        result = benchmark_model(model_path, test_images, args.runs, args.warmup)
        if result:
            all_results.append(result)

    # Generate report
    print(f"\n📊 Generating benchmark report...")
    report = generate_benchmark_report(system_info, all_results, args.output)

    # Print summary
    print_summary_table(report)

    print(f"\n💾 Detailed results saved to: {args.output}")
    print(f"📊 Benchmark completed successfully!")

    return 0

if __name__ == "__main__":
    sys.exit(main())