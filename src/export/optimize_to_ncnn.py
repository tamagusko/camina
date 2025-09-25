#!/usr/bin/env python3
"""
CAMINA YOLO Model NCNN Optimization
Convert trained YOLO models to NCNN format for mobile/edge deployment
"""

import os
import subprocess
import sys
from pathlib import Path
from ultralytics import YOLO

def check_ncnn_tools():
    """Check if NCNN tools are available"""
    try:
        result = subprocess.run(['onnx2ncnn', '--help'], capture_output=True, text=True)
        return True
    except FileNotFoundError:
        print("❌ NCNN tools not found. Please install NCNN:")
        print("   Ubuntu/Debian: sudo apt install ncnn-dev ncnn-tools")
        print("   Or compile from source: https://github.com/Tencent/ncnn")
        return False

def export_to_onnx(model_path, output_dir):
    """Export YOLO model to ONNX format"""
    print(f"🔄 Exporting {model_path} to ONNX...")

    try:
        model = YOLO(model_path)

        # Export to ONNX
        onnx_path = model.export(
            format="onnx",
            imgsz=640,
            optimize=True,
            half=False,  # Full precision for better compatibility
            dynamic=False,
            simplify=True
        )

        print(f"✅ ONNX export successful: {onnx_path}")
        return onnx_path

    except Exception as e:
        print(f"❌ ONNX export failed: {e}")
        return None

def convert_onnx_to_ncnn(onnx_path, output_dir):
    """Convert ONNX model to NCNN format"""
    onnx_path = Path(onnx_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # NCNN model files
    param_file = output_dir / f"{onnx_path.stem}.param"
    bin_file = output_dir / f"{onnx_path.stem}.bin"

    print(f"🔄 Converting ONNX to NCNN...")
    print(f"   Input: {onnx_path}")
    print(f"   Output: {param_file}, {bin_file}")

    try:
        # Convert ONNX to NCNN
        cmd = [
            'onnx2ncnn',
            str(onnx_path),
            str(param_file),
            str(bin_file)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print("✅ NCNN conversion successful!")
            return param_file, bin_file
        else:
            print(f"❌ NCNN conversion failed:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return None, None

    except subprocess.TimeoutExpired:
        print("❌ NCNN conversion timed out (5 minutes)")
        return None, None
    except Exception as e:
        print(f"❌ NCNN conversion error: {e}")
        return None, None

def optimize_ncnn_model(param_file, bin_file):
    """Optimize NCNN model using ncnnoptimize"""
    if not param_file or not bin_file:
        return None, None

    param_file = Path(param_file)
    bin_file = Path(bin_file)

    # Optimized model files
    opt_param = param_file.parent / f"{param_file.stem}_opt.param"
    opt_bin = param_file.parent / f"{param_file.stem}_opt.bin"

    print(f"🔄 Optimizing NCNN model...")

    try:
        cmd = [
            'ncnnoptimize',
            str(param_file),
            str(bin_file),
            str(opt_param),
            str(opt_bin),
            '0'  # optimization level
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print("✅ NCNN optimization successful!")
            return opt_param, opt_bin
        else:
            print("⚠️ NCNN optimization failed, using non-optimized version")
            print(f"   Error: {result.stderr}")
            return param_file, bin_file

    except subprocess.TimeoutExpired:
        print("⚠️ NCNN optimization timed out, using non-optimized version")
        return param_file, bin_file
    except FileNotFoundError:
        print("⚠️ ncnnoptimize not found, using non-optimized version")
        return param_file, bin_file
    except Exception as e:
        print(f"⚠️ NCNN optimization error: {e}, using non-optimized version")
        return param_file, bin_file

def get_file_size_mb(file_path):
    """Get file size in MB"""
    if not file_path or not Path(file_path).exists():
        return 0
    return Path(file_path).stat().st_size / (1024 * 1024)

def convert_model_to_ncnn(model_name, model_path, output_base_dir):
    """Complete conversion pipeline for a single model"""
    print("="*80)
    print(f"🎯 Converting {model_name} to NCNN")
    print("="*80)

    model_output_dir = Path(output_base_dir) / model_name
    model_output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Export to ONNX
    onnx_path = export_to_onnx(model_path, model_output_dir)
    if not onnx_path:
        return None

    # Step 2: Convert ONNX to NCNN
    param_file, bin_file = convert_onnx_to_ncnn(onnx_path, model_output_dir)
    if not param_file:
        return None

    # Step 3: Optimize NCNN model
    opt_param, opt_bin = optimize_ncnn_model(param_file, bin_file)

    # Calculate sizes
    original_size = get_file_size_mb(model_path)
    onnx_size = get_file_size_mb(onnx_path)
    ncnn_param_size = get_file_size_mb(opt_param)
    ncnn_bin_size = get_file_size_mb(opt_bin)
    ncnn_total_size = ncnn_param_size + ncnn_bin_size

    results = {
        'model_name': model_name,
        'original_path': model_path,
        'onnx_path': onnx_path,
        'ncnn_param': opt_param,
        'ncnn_bin': opt_bin,
        'sizes': {
            'original_mb': original_size,
            'onnx_mb': onnx_size,
            'ncnn_param_mb': ncnn_param_size,
            'ncnn_bin_mb': ncnn_bin_size,
            'ncnn_total_mb': ncnn_total_size
        }
    }

    print(f"📊 Size Comparison for {model_name}:")
    print(f"   Original PT:  {original_size:.2f} MB")
    print(f"   ONNX:         {onnx_size:.2f} MB")
    print(f"   NCNN Param:   {ncnn_param_size:.2f} MB")
    print(f"   NCNN Bin:     {ncnn_bin_size:.2f} MB")
    print(f"   NCNN Total:   {ncnn_total_size:.2f} MB")
    print(f"   Compression:  {((original_size - ncnn_total_size) / original_size * 100):.1f}%")

    return results

def main():
    print("="*80)
    print("🎯 CAMINA YOLO to NCNN Conversion Pipeline")
    print("="*80)

    # Check prerequisites
    if not check_ncnn_tools():
        sys.exit(1)

    # Best performing model (YOLO11n based on our results)
    models_to_convert = {
        "YOLO11n": "/home/tiago/repos/camina/model/yolo_comparison/YOLO11n/train/weights/best.pt"
    }

    # Output directory
    output_dir = "/home/tiago/repos/camina/model/ncnn_optimized"

    results = []

    for model_name, model_path in models_to_convert.items():
        if not Path(model_path).exists():
            print(f"❌ Model not found: {model_path}")
            continue

        result = convert_model_to_ncnn(model_name, model_path, output_dir)
        if result:
            results.append(result)

    # Summary
    print("\n" + "="*80)
    print("📊 NCNN CONVERSION SUMMARY")
    print("="*80)

    if results:
        for result in results:
            sizes = result['sizes']
            print(f"\n🏆 {result['model_name']}:")
            print(f"   📁 NCNN Files: {result['ncnn_param']}")
            print(f"                  {result['ncnn_bin']}")
            print(f"   📊 Original:   {sizes['original_mb']:.2f} MB")
            print(f"   📊 NCNN:       {sizes['ncnn_total_mb']:.2f} MB")
            print(f"   🗜️  Compression: {((sizes['original_mb'] - sizes['ncnn_total_mb']) / sizes['original_mb'] * 100):.1f}%")
    else:
        print("❌ No models were successfully converted")

    print("\n" + "="*80)
    print("✅ NCNN Conversion Complete")
    print("="*80)

if __name__ == "__main__":
    main()