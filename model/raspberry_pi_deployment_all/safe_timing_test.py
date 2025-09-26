#!/usr/bin/env python3
"""
Safe NCNN timing test - isolates each model test to prevent crashes from affecting others
"""

import os
import time
import glob
import json
import platform
import subprocess
import sys

def test_single_model(model_dir, test_image_path, num_runs=20):
    """Test a single NCNN model in isolation"""
    script_content = f'''
import os
import time
import sys

def test_model():
    try:
        import ncnn
        import cv2
        import numpy as np
    except ImportError as e:
        print(f"IMPORT_ERROR: {{e}}")
        return None

    # Find model files
    param_file = None
    bin_file = None
    for file in os.listdir("{model_dir}"):
        if file.endswith('.param'):
            param_file = os.path.join("{model_dir}", file)
        elif file.endswith('.bin'):
            bin_file = os.path.join("{model_dir}", file)

    if not param_file or not bin_file:
        print("MODEL_FILES_ERROR: Files not found")
        return None

    print(f"PARAM_FILE: {{os.path.basename(param_file)}}")
    print(f"BIN_FILE: {{os.path.basename(bin_file)}}")

    # Load model
    try:
        net = ncnn.Net()
        net.load_param(param_file)
        net.load_model(bin_file)
    except Exception as e:
        print(f"MODEL_LOAD_ERROR: {{e}}")
        return None

    # Load image
    img = cv2.imread("{test_image_path}")
    if img is None:
        print("IMAGE_LOAD_ERROR: Could not load image")
        return None

    # Preprocess
    img_resized = cv2.resize(img, (640, 640))
    mat = ncnn.Mat.from_pixels(img_resized, ncnn.Mat.PixelType.PIXEL_BGR, 640, 640)
    mean_vals = [0.0, 0.0, 0.0]
    norm_vals = [1/255.0, 1/255.0, 1/255.0]
    mat.substract_mean_normalize(mean_vals, norm_vals)

    # Warmup
    print("WARMUP_START")
    for _ in range(3):
        try:
            ex = net.create_extractor()
            ex.input("in0", mat)
            _, _ = ex.extract("out0")
        except Exception as e:
            print(f"WARMUP_ERROR: {{e}}")

    print("BENCHMARK_START")
    times = []

    for i in range({num_runs}):
        start_time = time.perf_counter()

        try:
            ex = net.create_extractor()
            ex.input("in0", mat)
            _, _ = ex.extract("out0")
        except Exception as e:
            print(f"INFERENCE_ERROR: {{e}}")

        end_time = time.perf_counter()
        inference_time_ms = (end_time - start_time) * 1000
        times.append(inference_time_ms)

        if (i + 1) % 5 == 0:
            print(f"PROGRESS: {{i+1}}/{num_runs}")

    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        fps = 1000 / avg_time

        print(f"RESULT: {{avg_time:.2f}},{{min_time:.2f}},{{max_time:.2f}},{{fps:.1f}},{{len(times)}}")
    else:
        print("NO_RESULTS")

if __name__ == "__main__":
    test_model()
'''

    # Write temporary script
    temp_script = f"/tmp/test_model_{os.path.basename(model_dir)}.py"
    with open(temp_script, 'w') as f:
        f.write(script_content)

    # Run the test in subprocess with timeout
    try:
        result = subprocess.run(
            [sys.executable, temp_script],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )

        # Clean up temp file
        try:
            os.remove(temp_script)
        except:
            pass

        return result
    except subprocess.TimeoutExpired:
        # Clean up temp file
        try:
            os.remove(temp_script)
        except:
            pass
        print("❌ Test timed out")
        return None
    except Exception as e:
        # Clean up temp file
        try:
            os.remove(temp_script)
        except:
            pass
        print(f"❌ Subprocess error: {e}")
        return None

def parse_result(result):
    """Parse the result from subprocess"""
    if result is None or result.returncode != 0:
        return None

    lines = result.stdout.strip().split('\n')
    parsed_result = {}

    for line in lines:
        if line.startswith('PARAM_FILE:'):
            parsed_result['param_file'] = line.split(':', 1)[1].strip()
        elif line.startswith('BIN_FILE:'):
            parsed_result['bin_file'] = line.split(':', 1)[1].strip()
        elif line.startswith('RESULT:'):
            # Parse: avg_time,min_time,max_time,fps,runs
            parts = line.split(':', 1)[1].strip().split(',')
            if len(parts) == 5:
                parsed_result.update({
                    'avg_time_ms': float(parts[0]),
                    'min_time_ms': float(parts[1]),
                    'max_time_ms': float(parts[2]),
                    'fps': float(parts[3]),
                    'successful_runs': int(parts[4])
                })
        elif 'ERROR:' in line:
            parsed_result['error'] = line

    return parsed_result if 'avg_time_ms' in parsed_result else None

def get_model_size(model_dir):
    """Get model size in MB"""
    total_size = 0
    for file in os.listdir(model_dir):
        if file.endswith(('.param', '.bin')):
            total_size += os.path.getsize(os.path.join(model_dir, file))
    return total_size / (1024 * 1024)

def main():
    print("🛡️ CAMINA Safe NCNN Timing Test - Raspberry Pi 5")
    print("=" * 55)

    # System info
    print(f"🖥️ Platform: {platform.platform()}")
    print(f"🔧 Python: {platform.python_version()}")
    print()

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # All models - test them all safely
    models = [
        'yolov5n_ncnn',
        'yolov8n_ncnn',
        'yolov10n_ncnn',
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

        # Run safe test
        print("🛡️ Running in isolated subprocess...")
        result = test_single_model(model_dir, test_image, num_runs=20)

        if result is not None:
            parsed = parse_result(result)

            if parsed:
                print(f"✅ Avg time: {parsed['avg_time_ms']:.2f} ms")
                print(f"🚀 Avg FPS: {parsed['fps']:.1f}")
                print(f"📈 Range: {parsed['min_time_ms']:.2f} - {parsed['max_time_ms']:.2f} ms")
                print(f"✔️ Success rate: {parsed['successful_runs']}/20")

                results[model_name] = {
                    'model_size_mb': size_mb,
                    **parsed
                }
            else:
                print("❌ Test failed - no valid results")
                if result and result.stderr:
                    print(f"🔍 Error details: {result.stderr[:200]}...")
        else:
            print("❌ Test failed - subprocess error")

        print("-" * 55)

    # Summary
    if results:
        print("\n🏆 SAFE TIMING RESULTS SUMMARY")
        print("=" * 55)
        print(f"{'Model':<10} {'Size(MB)':<9} {'Time(ms)':<10} {'FPS':<8} {'FPS/MB':<8}")
        print("-" * 55)

        sorted_results = sorted(results.items(), key=lambda x: x[1]['avg_time_ms'])

        for model_name, data in sorted_results:
            name = model_name.replace('_ncnn', '').upper()
            efficiency = data['fps'] / data['model_size_mb']
            print(f"{name:<10} {data['model_size_mb']:<9.2f} {data['avg_time_ms']:<10.2f} {data['fps']:<8.1f} {efficiency:<8.1f}")

        # Save results
        with open('safe_timing_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: safe_timing_results.json")

    print("\n🛡️ Safe timing test completed!")

if __name__ == "__main__":
    main()