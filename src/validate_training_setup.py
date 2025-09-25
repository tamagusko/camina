#!/usr/bin/env python3
"""
CAMINA Training Setup Validation Script
Validates that all components are properly configured for YOLO model training.
"""

import os
import sys
from pathlib import Path
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Try to import torch later to avoid immediate failure
torch = None

def check_python_packages():
    """Check if required Python packages are available."""
    required_packages = [
        ('torch', 'PyTorch'),
        ('ultralytics', 'Ultralytics YOLO'),
        ('numpy', 'NumPy'),
        ('pandas', 'Pandas'),
        ('matplotlib', 'Matplotlib'),
        ('seaborn', 'Seaborn'),
        ('yaml', 'PyYAML'),
        ('rich', 'Rich'),
        ('PIL', 'Pillow')
    ]

    console.print("\n[bold cyan]Checking Python Packages...[/bold cyan]")

    table = Table()
    table.add_column("Package", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Version", style="yellow")

    all_good = True
    global torch

    for package, name in required_packages:
        try:
            if package == 'torch':
                # Special handling for torch due to potential import issues
                import torch as torch_module
                torch = torch_module
            else:
                module = __import__(package)

            version = getattr(torch if package == 'torch' else module, '__version__', 'Unknown')
            table.add_row(name, "✅ Available", version)
        except ImportError as e:
            table.add_row(name, "❌ Missing", f"Import error: {str(e)}")
            all_good = False
        except Exception as e:
            table.add_row(name, "⚠️ Error", f"Error: {str(e)}")
            all_good = False

    console.print(table)
    return all_good

def check_dataset():
    """Check dataset structure and configuration."""
    console.print("\n[bold cyan]Checking Dataset...[/bold cyan]")

    dataset_path = Path("/home/tiago/repos/camina/data/dataset_v4i_yolov11")
    data_yaml_path = dataset_path / "data.yaml"

    table = Table()
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")

    all_good = True

    # Check if dataset directory exists
    if dataset_path.exists():
        table.add_row("Dataset Directory", "✅ Found", str(dataset_path))
    else:
        table.add_row("Dataset Directory", "❌ Missing", str(dataset_path))
        all_good = False

    # Check data.yaml
    if data_yaml_path.exists():
        try:
            with open(data_yaml_path, 'r') as f:
                data_config = yaml.safe_load(f)
            table.add_row("data.yaml", "✅ Valid", f"{data_config['nc']} classes")

            # Check class names
            class_names = data_config.get('names', [])
            table.add_row("Classes", "✅ Found", ", ".join(class_names))

        except Exception as e:
            table.add_row("data.yaml", "❌ Invalid", str(e))
            all_good = False
    else:
        table.add_row("data.yaml", "❌ Missing", "Configuration file not found")
        all_good = False

    # Check directories
    required_dirs = ["train/images", "train/labels", "test/images", "test/labels"]
    for dir_name in required_dirs:
        dir_path = dataset_path / dir_name
        if dir_path.exists():
            file_count = len(list(dir_path.iterdir()))
            table.add_row(f"{dir_name}", "✅ Found", f"{file_count} files")
        else:
            table.add_row(f"{dir_name}", "❌ Missing", "Directory not found")
            all_good = False

    console.print(table)
    return all_good

def check_gpu():
    """Check GPU availability and configuration."""
    console.print("\n[bold cyan]Checking GPU Configuration...[/bold cyan]")

    table = Table()
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")

    global torch

    if torch is None:
        table.add_row("PyTorch", "❌ Not Available", "Cannot check GPU without PyTorch")
        console.print(table)
        return False

    try:
        # Check CUDA availability
        if torch.cuda.is_available():
            table.add_row("CUDA", "✅ Available", f"Version {torch.version.cuda}")

            # GPU details
            gpu_count = torch.cuda.device_count()
            table.add_row("GPU Count", "✅ Found", str(gpu_count))

            for i in range(gpu_count):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                table.add_row(f"GPU {i}", "✅ Available", f"{gpu_name} ({gpu_memory:.1f} GB)")
        else:
            table.add_row("CUDA", "⚠️ Not Available", "CPU training only")

        console.print(table)
        return torch.cuda.is_available()

    except Exception as e:
        table.add_row("GPU Check", "❌ Error", str(e))
        console.print(table)
        return False

def check_output_directories():
    """Check if output directories can be created."""
    console.print("\n[bold cyan]Checking Output Directories...[/bold cyan]")

    base_dir = Path("/home/tiago/repos/camina")
    required_dirs = [
        "model/yolo_comparison",
        "outputs/model_comparison",
        "outputs/model_comparison/results",
        "outputs/model_comparison/plots",
        "outputs/model_comparison/tables",
        "outputs/model_comparison/logs"
    ]

    table = Table()
    table.add_column("Directory", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Path", style="yellow")

    all_good = True
    for dir_name in required_dirs:
        dir_path = base_dir / dir_name
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            table.add_row(dir_name, "✅ Ready", str(dir_path))
        except Exception as e:
            table.add_row(dir_name, "❌ Failed", str(e))
            all_good = False

    console.print(table)
    return all_good

def check_training_script():
    """Check if training script exists and is valid."""
    console.print("\n[bold cyan]Checking Training Script...[/bold cyan]")

    script_path = Path("/home/tiago/repos/camina/train_evaluate_yolo_models.py")
    exec_script_path = Path("/home/tiago/repos/camina/run_yolo_comparison.sh")

    table = Table()
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")

    all_good = True

    if script_path.exists():
        table.add_row("Training Script", "✅ Found", str(script_path))

        # Check if script is syntactically valid
        try:
            with open(script_path, 'r') as f:
                compile(f.read(), script_path, 'exec')
            table.add_row("Script Syntax", "✅ Valid", "No syntax errors")
        except SyntaxError as e:
            table.add_row("Script Syntax", "❌ Invalid", f"Line {e.lineno}: {e.msg}")
            all_good = False
    else:
        table.add_row("Training Script", "❌ Missing", str(script_path))
        all_good = False

    if exec_script_path.exists():
        is_executable = os.access(exec_script_path, os.X_OK)
        status = "✅ Executable" if is_executable else "⚠️ Not Executable"
        table.add_row("Execution Script", status, str(exec_script_path))
    else:
        table.add_row("Execution Script", "❌ Missing", str(exec_script_path))
        all_good = False

    console.print(table)
    return all_good

def main():
    """Run all validation checks."""
    console.print(Panel.fit(
        "[bold cyan]CAMINA Training Setup Validation[/bold cyan]\n"
        "[yellow]Checking all components for YOLO model training pipeline[/yellow]",
        border_style="bright_blue"
    ))

    checks = [
        ("Python Packages", check_python_packages),
        ("Dataset Structure", check_dataset),
        ("GPU Configuration", check_gpu),
        ("Output Directories", check_output_directories),
        ("Training Scripts", check_training_script)
    ]

    all_passed = True
    results = {}

    for check_name, check_function in checks:
        try:
            result = check_function()
            results[check_name] = result
            all_passed = all_passed and result
        except Exception as e:
            console.print(f"[red]Error in {check_name}: {e}[/red]")
            results[check_name] = False
            all_passed = False

    # Summary
    console.print("\n" + "="*80)
    console.print("[bold cyan]Validation Summary[/bold cyan]")
    console.print("="*80)

    summary_table = Table()
    summary_table.add_column("Check", style="cyan")
    summary_table.add_column("Result", style="green")

    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        summary_table.add_row(check_name, status)

    console.print(summary_table)

    if all_passed:
        console.print(Panel.fit(
            "[bold green]🎉 All Checks Passed![/bold green]\n"
            "[yellow]Your system is ready for YOLO model training.[/yellow]\n"
            "[cyan]Run: ./run_yolo_comparison.sh to start training[/cyan]",
            border_style="bright_green"
        ))
    else:
        console.print(Panel.fit(
            "[bold red]❌ Some Checks Failed![/bold red]\n"
            "[yellow]Please fix the issues above before starting training.[/yellow]\n"
            "[cyan]Refer to YOLO_TRAINING_README.md for troubleshooting[/cyan]",
            border_style="bright_red"
        ))

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)