#!/usr/bin/env python3
"""
CAMINA YOLO to NCNN Model Export Script
Production-ready YOLO model export to NCNN format optimized for Raspberry Pi 5.

Purpose: Export trained YOLO models to NCNN format with optimizations for edge deployment.
Target: Raspberry Pi 5 and similar ARM-based edge devices.
Output: Optimized NCNN models with INT8 quantization and static shapes.
"""

import os
import sys
import time
import logging
import warnings
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
import json

import torch
from ultralytics import YOLO
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.logging import RichHandler

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Initialize rich console for beautiful output
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("NCNN_OPTIMIZER")


@dataclass
class OptimizationConfig:
    """Configuration for NCNN optimization levels."""
    name: str
    int8: bool = True
    half: bool = False
    dynamic: bool = False
    simplify: bool = True
    optimize: bool = True
    imgsz: Union[int, Tuple[int, int]] = 640
    description: str = ""


@dataclass
class ExportResults:
    """Results from model export to NCNN."""
    model_name: str
    original_path: str
    ncnn_param_path: str
    ncnn_bin_path: str
    original_size_mb: float
    ncnn_size_mb: float
    compression_ratio: float
    export_time_seconds: float
    optimization_config: str
    success: bool
    error_message: Optional[str] = None


def setup_directories() -> Dict[str, Path]:
    """
    Create necessary directories for NCNN exports and outputs.

    Returns:
        Dictionary mapping directory names to Path objects
    """
    base_dir = Path("/home/tiago/repos/camina")
    directories = {
        "ncnn_exports": base_dir / "exports" / "ncnn",
        "logs": base_dir / "exports" / "ncnn" / "logs",
        "reports": base_dir / "exports" / "ncnn" / "reports"
    }

    for name, path in directories.items():
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {path}")

    return directories


def get_optimization_configs() -> Dict[str, OptimizationConfig]:
    """
    Define optimization configurations for different deployment scenarios.

    Returns:
        Dictionary of optimization configurations
    """
    configs = {
        "rpi5_production": OptimizationConfig(
            name="Raspberry Pi 5 Production",
            int8=True,
            half=False,
            dynamic=False,
            simplify=True,
            optimize=True,
            imgsz=640,
            description="Optimized for Raspberry Pi 5 with INT8 quantization"
        ),
        "rpi5_balanced": OptimizationConfig(
            name="Raspberry Pi 5 Balanced",
            int8=False,
            half=True,
            dynamic=False,
            simplify=True,
            optimize=True,
            imgsz=640,
            description="Balanced performance for Raspberry Pi 5 with FP16"
        ),
        "rpi5_quality": OptimizationConfig(
            name="Raspberry Pi 5 Quality",
            int8=False,
            half=False,
            dynamic=False,
            simplify=True,
            optimize=True,
            imgsz=640,
            description="Best quality for Raspberry Pi 5 with FP32"
        ),
        "edge_minimal": OptimizationConfig(
            name="Edge Minimal",
            int8=True,
            half=False,
            dynamic=False,
            simplify=True,
            optimize=True,
            imgsz=320,
            description="Minimal size for resource-constrained edge devices"
        )
    }

    return configs


def find_trained_models(base_path: Optional[Path] = None) -> List[Path]:
    """
    Find all trained YOLO models (best.pt files) in the project.

    Args:
        base_path: Base directory to search for models

    Returns:
        List of paths to trained model files
    """
    if base_path is None:
        base_path = Path("/home/tiago/repos/camina")

    logger.info("Searching for trained YOLO models...")

    # Search patterns for trained models
    search_patterns = [
        "models/yolo_comparison/*/train/weights/best.pt",
        "models/*/best.pt",
        "outputs/*/best.pt",
        "**/best.pt"
    ]

    model_files = []
    for pattern in search_patterns:
        found_files = list(base_path.glob(pattern))
        model_files.extend(found_files)

    # Remove duplicates and sort
    model_files = sorted(list(set(model_files)))

    if not model_files:
        logger.warning("No trained model files (best.pt) found")
        return []

    # Display found models
    table = Table(title="Found Trained YOLO Models")
    table.add_column("Index", style="cyan")
    table.add_column("Model Path", style="yellow")
    table.add_column("Size (MB)", style="magenta")
    table.add_column("Modified", style="green")

    for i, model_path in enumerate(model_files):
        size_mb = model_path.stat().st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(model_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i + 1), str(model_path), f"{size_mb:.1f}", modified)

    console.print(table)
    logger.info(f"Found {len(model_files)} trained models")

    return model_files


def validate_model(model_path: Path) -> bool:
    """
    Validate that a model file can be loaded and is compatible with NCNN export.

    Args:
        model_path: Path to the model file

    Returns:
        True if model is valid, False otherwise
    """
    try:
        logger.info(f"Validating model: {model_path}")
        model = YOLO(str(model_path))

        # Check if model has required attributes
        if not hasattr(model, 'export'):
            logger.error(f"Model does not support export: {model_path}")
            return False

        # Check model type
        if model.task not in ['detect']:
            logger.warning(f"Model task '{model.task}' may not be optimal for NCNN export")

        logger.info(f"Model validation successful: {model_path}")
        return True

    except Exception as e:
        logger.error(f"Model validation failed: {model_path} - {e}")
        return False


def export_to_ncnn(model_path: Path, config: OptimizationConfig,
                   output_dir: Path) -> ExportResults:
    """
    Export a YOLO model to NCNN format with specified optimizations.

    Args:
        model_path: Path to the trained YOLO model
        config: Optimization configuration
        output_dir: Directory to save exported models

    Returns:
        ExportResults object containing export metrics
    """
    logger.info(f"Exporting {model_path.name} to NCNN with {config.name} optimization")

    # Create model-specific output directory
    model_name = model_path.parent.parent.parent.name if "train" in str(model_path) else model_path.stem
    export_subdir = output_dir / f"{model_name}_{config.name.lower().replace(' ', '_')}"
    export_subdir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    original_size_mb = model_path.stat().st_size / (1024 * 1024)

    try:
        # Load model
        model = YOLO(str(model_path))

        # Export parameters
        export_params = {
            "format": "ncnn",
            "imgsz": config.imgsz,
            "half": config.half,
            "int8": config.int8,
            "dynamic": config.dynamic,
            "simplify": config.simplify,
            "optimize": config.optimize,
            "verbose": False
        }

        # Perform export
        with console.status(f"[bold green]Exporting {model_name} to NCNN..."):
            exported_path = model.export(**export_params)

        export_time = time.time() - start_time

        # Find generated NCNN files
        ncnn_files = list(Path(exported_path).parent.glob(f"{Path(exported_path).stem}*"))
        param_file = next((f for f in ncnn_files if f.suffix == '.param'), None)
        bin_file = next((f for f in ncnn_files if f.suffix == '.bin'), None)

        if not param_file or not bin_file:
            raise FileNotFoundError("NCNN parameter or binary file not found after export")

        # Move files to organized directory
        new_param_path = export_subdir / param_file.name
        new_bin_path = export_subdir / bin_file.name

        param_file.rename(new_param_path)
        bin_file.rename(new_bin_path)

        # Calculate NCNN model size
        ncnn_size_mb = (new_param_path.stat().st_size + new_bin_path.stat().st_size) / (1024 * 1024)
        compression_ratio = original_size_mb / ncnn_size_mb if ncnn_size_mb > 0 else 0

        results = ExportResults(
            model_name=model_name,
            original_path=str(model_path),
            ncnn_param_path=str(new_param_path),
            ncnn_bin_path=str(new_bin_path),
            original_size_mb=original_size_mb,
            ncnn_size_mb=ncnn_size_mb,
            compression_ratio=compression_ratio,
            export_time_seconds=export_time,
            optimization_config=config.name,
            success=True
        )

        logger.info(f"Export successful: {model_name}")
        logger.info(f"Original size: {original_size_mb:.2f} MB")
        logger.info(f"NCNN size: {ncnn_size_mb:.2f} MB")
        logger.info(f"Compression ratio: {compression_ratio:.2f}x")
        logger.info(f"Export time: {export_time:.2f} seconds")

        return results

    except Exception as e:
        export_time = time.time() - start_time
        error_msg = str(e)

        results = ExportResults(
            model_name=model_name,
            original_path=str(model_path),
            ncnn_param_path="",
            ncnn_bin_path="",
            original_size_mb=original_size_mb,
            ncnn_size_mb=0,
            compression_ratio=0,
            export_time_seconds=export_time,
            optimization_config=config.name,
            success=False,
            error_message=error_msg
        )

        logger.error(f"Export failed for {model_name}: {error_msg}")
        return results


def batch_export_models(model_paths: List[Path], config: OptimizationConfig,
                       output_dir: Path) -> List[ExportResults]:
    """
    Export multiple models to NCNN format in batch.

    Args:
        model_paths: List of model paths to export
        config: Optimization configuration
        output_dir: Output directory for exports

    Returns:
        List of ExportResults objects
    """
    logger.info(f"Starting batch export of {len(model_paths)} models with {config.name} optimization")

    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:

        main_task = progress.add_task(f"Exporting models to NCNN...", total=len(model_paths))

        for i, model_path in enumerate(model_paths):
            progress.update(main_task, description=f"Exporting {model_path.name}")

            try:
                # Validate model first
                if not validate_model(model_path):
                    logger.warning(f"Skipping invalid model: {model_path}")
                    continue

                # Export model
                export_result = export_to_ncnn(model_path, config, output_dir)
                results.append(export_result)

                progress.update(main_task, advance=1)

            except Exception as e:
                logger.error(f"Failed to export {model_path}: {e}")
                continue

    successful_exports = sum(1 for r in results if r.success)
    logger.info(f"Batch export completed: {successful_exports}/{len(results)} successful")

    return results


def generate_export_report(export_results: List[ExportResults],
                          output_dir: Path) -> None:
    """
    Generate comprehensive report of NCNN export results.

    Args:
        export_results: List of export results
        output_dir: Directory to save reports
    """
    logger.info("Generating NCNN export report...")

    # Separate successful and failed exports
    successful = [r for r in export_results if r.success]
    failed = [r for r in export_results if not r.success]

    # Generate summary table
    table = Table(title="NCNN Export Summary")
    table.add_column("Model", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Original Size (MB)", style="yellow")
    table.add_column("NCNN Size (MB)", style="yellow")
    table.add_column("Compression", style="magenta")
    table.add_column("Export Time (s)", style="blue")

    for result in export_results:
        status = "✅ Success" if result.success else "❌ Failed"
        compression = f"{result.compression_ratio:.2f}x" if result.success else "N/A"
        ncnn_size = f"{result.ncnn_size_mb:.2f}" if result.success else "N/A"

        table.add_row(
            result.model_name,
            status,
            f"{result.original_size_mb:.2f}",
            ncnn_size,
            compression,
            f"{result.export_time_seconds:.2f}"
        )

    console.print(table)

    # Generate detailed report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_content = f"""# CAMINA NCNN Export Report

**Generated:** {timestamp}
**Total Models:** {len(export_results)}
**Successful Exports:** {len(successful)}
**Failed Exports:** {len(failed)}

## Export Summary

### Successful Exports

| Model | Original Size (MB) | NCNN Size (MB) | Compression Ratio | Export Time (s) |
|-------|-------------------|----------------|-------------------|-----------------|"""

    for result in successful:
        report_content += f"\n| {result.model_name} | {result.original_size_mb:.2f} | {result.ncnn_size_mb:.2f} | {result.compression_ratio:.2f}x | {result.export_time_seconds:.2f} |"

    if failed:
        report_content += "\n\n### Failed Exports\n\n"
        for result in failed:
            report_content += f"- **{result.model_name}**: {result.error_message}\n"

    # Statistics
    if successful:
        avg_compression = sum(r.compression_ratio for r in successful) / len(successful)
        total_original_size = sum(r.original_size_mb for r in successful)
        total_ncnn_size = sum(r.ncnn_size_mb for r in successful)
        total_savings = total_original_size - total_ncnn_size

        report_content += f"""

## Statistics

- **Average Compression Ratio:** {avg_compression:.2f}x
- **Total Original Size:** {total_original_size:.2f} MB
- **Total NCNN Size:** {total_ncnn_size:.2f} MB
- **Total Size Savings:** {total_savings:.2f} MB ({(total_savings/total_original_size)*100:.1f}%)
- **Average Export Time:** {sum(r.export_time_seconds for r in successful) / len(successful):.2f} seconds

## Deployment Instructions

### Raspberry Pi 5 Setup

1. **Install NCNN:**
   ```bash
   sudo apt update
   sudo apt install cmake build-essential
   git clone https://github.com/Tencent/ncnn.git
   cd ncnn
   mkdir build && cd build
   cmake -DCMAKE_BUILD_TYPE=Release ..
   make -j4
   sudo make install
   ```

2. **Copy Models:**
   ```bash
   # Copy both .param and .bin files to your target device
   scp *.param *.bin pi@your-pi-ip:/path/to/models/
   ```

3. **Integration:**
   ```python
   import ncnn

   # Load NCNN model
   net = ncnn.Net()
   net.load_param("model.param")
   net.load_model("model.bin")

   # Inference
   ex = net.create_extractor()
   ex.input("images", ncnn_mat)
   ex.extract("output0", out)
   ```

### Performance Expectations

Based on optimization levels:
- **INT8 Quantization:** ~2-4x speed improvement, minimal accuracy loss
- **Static Shapes:** Optimized memory allocation and inference paths
- **Model Simplification:** Reduced computational graph complexity

### File Structure

Each exported model includes:
- `model.param`: Network structure definition
- `model.bin`: Model weights in optimized format

---

**Generated by CAMINA NCNN Optimization Pipeline**
**Repository:** https://github.com/tamagusko/camina
**Timestamp:** {timestamp}
"""

    # Save report
    report_path = output_dir / f"ncnn_export_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    # Save JSON report for programmatic access
    json_data = {
        "timestamp": timestamp,
        "total_models": len(export_results),
        "successful_exports": len(successful),
        "failed_exports": len(failed),
        "results": [
            {
                "model_name": r.model_name,
                "success": r.success,
                "original_size_mb": r.original_size_mb,
                "ncnn_size_mb": r.ncnn_size_mb,
                "compression_ratio": r.compression_ratio,
                "export_time_seconds": r.export_time_seconds,
                "optimization_config": r.optimization_config,
                "error_message": r.error_message
            }
            for r in export_results
        ]
    }

    json_path = output_dir / f"ncnn_export_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)

    logger.info(f"Export report saved to {report_path}")
    logger.info(f"Export data saved to {json_path}")


def interactive_model_selection(model_paths: List[Path]) -> List[Path]:
    """
    Allow user to interactively select models for export.

    Args:
        model_paths: List of available model paths

    Returns:
        List of selected model paths
    """
    console.print("\n[bold cyan]Model Selection[/bold cyan]")
    console.print("Available models:")

    table = Table()
    table.add_column("Index", style="cyan")
    table.add_column("Model Name", style="yellow")
    table.add_column("Path", style="dim")

    for i, model_path in enumerate(model_paths):
        model_name = model_path.parent.parent.parent.name if "train" in str(model_path) else model_path.stem
        table.add_row(str(i + 1), model_name, str(model_path))

    console.print(table)

    while True:
        try:
            console.print("\n[bold]Select models to export:[/bold]")
            console.print("- Enter model indices (e.g., '1,3,4' or '1-4' or 'all')")
            console.print("- Press Enter to select all models")

            selection = input("Selection: ").strip()

            if not selection or selection.lower() == 'all':
                return model_paths

            if ',' in selection:
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
            elif '-' in selection:
                start, end = map(int, selection.split('-'))
                indices = list(range(start - 1, end))
            else:
                indices = [int(selection) - 1]

            selected_models = [model_paths[i] for i in indices if 0 <= i < len(model_paths)]

            if selected_models:
                logger.info(f"Selected {len(selected_models)} models for export")
                return selected_models
            else:
                console.print("[red]Invalid selection. Please try again.[/red]")

        except (ValueError, IndexError):
            console.print("[red]Invalid input. Please enter valid indices.[/red]")


def main():
    """
    Main function to execute the NCNN export pipeline.
    """
    try:
        # Print header
        console.print("\n" + "="*100)
        console.print(Panel.fit(
            "[bold cyan]CAMINA YOLO to NCNN Export Pipeline[/bold cyan]\n"
            "[yellow]Production-ready model optimization for Raspberry Pi 5[/yellow]",
            border_style="bright_blue"
        ))
        console.print("="*100 + "\n")

        # Setup directories
        directories = setup_directories()

        # Get optimization configurations
        opt_configs = get_optimization_configs()

        # Display available optimization configs
        config_table = Table(title="Available Optimization Configurations")
        config_table.add_column("Key", style="cyan")
        config_table.add_column("Name", style="yellow")
        config_table.add_column("Description", style="green")

        for key, config in opt_configs.items():
            config_table.add_row(key, config.name, config.description)

        console.print(config_table)

        # Find trained models
        model_paths = find_trained_models()

        if not model_paths:
            logger.error("No trained models found. Please train models first.")
            return

        # Interactive model selection
        selected_models = interactive_model_selection(model_paths)

        # Interactive optimization config selection
        console.print("\n[bold cyan]Optimization Configuration Selection[/bold cyan]")
        config_keys = list(opt_configs.keys())

        while True:
            try:
                console.print("Select optimization configuration:")
                for i, key in enumerate(config_keys):
                    console.print(f"{i + 1}. {opt_configs[key].name}")

                config_choice = input("\nEnter configuration number (default: 1): ").strip()

                if not config_choice:
                    config_choice = "1"

                config_index = int(config_choice) - 1
                if 0 <= config_index < len(config_keys):
                    selected_config = opt_configs[config_keys[config_index]]
                    break
                else:
                    console.print("[red]Invalid selection. Please try again.[/red]")

            except ValueError:
                console.print("[red]Invalid input. Please enter a number.[/red]")

        logger.info(f"Selected configuration: {selected_config.name}")

        # Export models
        console.print(f"\n[bold green]Starting NCNN export process...[/bold green]")
        export_results = batch_export_models(selected_models, selected_config, directories["ncnn_exports"])

        # Generate report
        generate_export_report(export_results, directories["reports"])

        # Final summary
        successful_count = sum(1 for r in export_results if r.success)
        total_count = len(export_results)

        console.print("\n" + "="*100)

        if successful_count == total_count:
            panel_style = "bright_green"
            status_text = "[bold green]All exports completed successfully![/bold green]"
        elif successful_count > 0:
            panel_style = "bright_yellow"
            status_text = f"[bold yellow]{successful_count}/{total_count} exports completed successfully[/bold yellow]"
        else:
            panel_style = "bright_red"
            status_text = "[bold red]All exports failed![/bold red]"

        console.print(Panel.fit(
            f"{status_text}\n"
            f"[cyan]Exports saved to: {directories['ncnn_exports']}[/cyan]\n"
            f"[magenta]Reports saved to: {directories['reports']}[/magenta]\n"
            f"[yellow]Optimization: {selected_config.name}[/yellow]",
            border_style=panel_style
        ))
        console.print("="*100)

        # Display final statistics
        if successful_count > 0:
            successful_results = [r for r in export_results if r.success]
            avg_compression = sum(r.compression_ratio for r in successful_results) / len(successful_results)
            total_savings = sum(r.original_size_mb - r.ncnn_size_mb for r in successful_results)

            logger.info(f"Average compression ratio: {avg_compression:.2f}x")
            logger.info(f"Total size savings: {total_savings:.2f} MB")

    except KeyboardInterrupt:
        logger.warning("Export process interrupted by user")
    except Exception as e:
        logger.error(f"Export pipeline failed: {e}")
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()