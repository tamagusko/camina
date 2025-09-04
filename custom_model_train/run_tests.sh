#!/bin/bash
# CAMINA Pipeline Quick Test Runner
# Run this script to validate the pipeline setup and run basic tests

set -e

echo "=============================================="
echo "🧪 CAMINA PIPELINE QUICK TEST SUITE"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "INFO" ]; then
        echo -e "${BLUE}[INFO]${NC} $message"
    elif [ "$status" = "SUCCESS" ]; then
        echo -e "${GREEN}[SUCCESS]${NC} $message"
    elif [ "$status" = "WARNING" ]; then
        echo -e "${YELLOW}[WARNING]${NC} $message"
    elif [ "$status" = "ERROR" ]; then
        echo -e "${RED}[ERROR]${NC} $message"
    fi
}

# Function to run test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo ""
    print_status "INFO" "Running: $test_name"
    echo "----------------------------------------"
    
    if eval "$test_command"; then
        print_status "SUCCESS" "$test_name PASSED"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_status "ERROR" "$test_name FAILED"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_TEST_NAMES+=("$test_name")
    fi
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
}

# Initialize counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
FAILED_TEST_NAMES=()

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_status "ERROR" "Python 3 is required but not installed"
    exit 1
fi

print_status "INFO" "Python version: $(python3 --version)"

# Test 1: Check Python dependencies
run_test "Python Dependencies Check" "python3 -c '
import sys
required = [\"ultralytics\", \"opencv-python\", \"numpy\", \"pandas\", \"torch\", \"matplotlib\"]
missing = []
for package in required:
    try:
        __import__(package.replace(\"-\", \"_\"))
        print(f\"✓ {package}\")
    except ImportError:
        missing.append(package)
        print(f\"✗ {package} - MISSING\")

if missing:
    print(f\"Missing packages: {missing}\")
    install_cmd = \" \".join(missing)
    print(f\"Install with: pip install {install_cmd}\")
    sys.exit(1)
else:
    print(\"All required packages are installed!\")
'"

# Test 2: Check directory structure
run_test "Directory Structure Check" "python3 -c '
import os
from pathlib import Path

required_dirs = [
    \"scripts\",
    \"datasets\", 
    \"all_camina_classes\"  # This will be created by conversion
]

optional_dirs = [
    \"runs\",
    \"results\",
    \"logs\"
]

for dir_name in required_dirs:
    if dir_name == \"all_camina_classes\" and not Path(dir_name).exists():
        print(f\"⚠ {dir_name} - Will be created by pipeline\")
        continue
    if Path(dir_name).exists():
        print(f\"✓ {dir_name}/\")
    else:
        print(f\"✗ {dir_name}/ - MISSING\")
        if dir_name == \"datasets\":
            print(\"  Please ensure SDL dataset is in datasets/ directory\")

for dir_name in optional_dirs:
    if Path(dir_name).exists():
        print(f\"✓ {dir_name}/ (optional)\")
    else:
        print(f\"○ {dir_name}/ (will be created)\")
'"

# Test 3: Check script files exist
run_test "Script Files Check" "python3 -c '
import os
from pathlib import Path

required_scripts = [
    \"scripts/convert_sdl_to_yolo11.py\",
    \"scripts/train_yolo11n.py\",
    \"scripts/sam2_clip_auto_labeling.py\",
    \"scripts/model_comparison_framework.py\",
    \"scripts/rpi5_deployment_optimizer.py\",
    \"scripts/evaluation_logging_system.py\"
]

all_exist = True
for script in required_scripts:
    if Path(script).exists():
        print(f\"✓ {script}\")
    else:
        print(f\"✗ {script} - MISSING\")
        all_exist = False

if not all_exist:
    exit(1)
'"

# Test 4: Validate script syntax
run_test "Script Syntax Validation" "python3 -c '
import ast
from pathlib import Path

scripts_dir = Path(\"scripts\")
if not scripts_dir.exists():
    print(\"Scripts directory not found\")
    exit(1)

for script_file in scripts_dir.glob(\"*.py\"):
    try:
        with open(script_file, \"r\") as f:
            ast.parse(f.read())
        print(f\"✓ {script_file.name} - Syntax OK\")
    except SyntaxError as e:
        print(f\"✗ {script_file.name} - Syntax Error: {e}\")
        exit(1)
    except Exception as e:
        print(f\"✗ {script_file.name} - Error: {e}\")
        exit(1)
'"

# Test 5: Check SDL dataset
run_test "SDL Dataset Check" "python3 -c '
from pathlib import Path
import yaml

sdl_path = Path(\"datasets/SDL fine-tuned_v3-cyclist_cleaned\")
if not sdl_path.exists():
    print(\"✗ SDL dataset not found\")
    print(\"  Expected: datasets/SDL fine-tuned_v3-cyclist_cleaned/\")
    exit(1)

# Check dataset structure
required_subdirs = [\"images/train\", \"images/test\", \"labels\"]
for subdir in required_subdirs:
    subdir_path = sdl_path / subdir
    if subdir_path.exists():
        if subdir.startswith(\"images\"):
            img_count = len(list(subdir_path.glob(\"*.jpg\")))
            print(f\"✓ {subdir}/ ({img_count} images)\")
        else:
            print(f\"✓ {subdir}/\")
    else:
        print(f\"✗ {subdir}/ - MISSING\")
        exit(1)

# Check data.yaml
data_yaml = sdl_path / \"data.yaml\"
if data_yaml.exists():
    with open(data_yaml, \"r\") as f:
        config = yaml.safe_load(f)
    nc = config.get(\"nc\", \"unknown\")
    print(f\"✓ data.yaml (classes: {nc})\")
else:
    print(\"✗ data.yaml - MISSING\")
    exit(1)
'"

# Test 6: Quick pipeline runner test
run_test "Pipeline Runner Quick Test" "python3 -c '
# Test that the main pipeline runner can be imported and initialized
import sys
sys.path.append(\".\")

try:
    from run_camina_pipeline import CAMINAPipelineRunner
    
    # Initialize runner with test config
    runner = CAMINAPipelineRunner()
    
    # Test basic functionality
    if hasattr(runner, \"check_dependencies\"):
        print(\"✓ Pipeline runner initialized successfully\")
        print(f\"✓ Pipeline ID: {runner.pipeline_id}\")
        print(f\"✓ Configuration loaded\")
    else:
        print(\"✗ Pipeline runner missing required methods\")
        exit(1)
        
except ImportError as e:
    print(f\"✗ Failed to import pipeline runner: {e}\")
    exit(1)
except Exception as e:
    print(f\"✗ Pipeline runner initialization failed: {e}\")
    exit(1)
'"

# Test 7: Configuration file validation
run_test "Configuration File Check" "python3 -c '
from pathlib import Path
import yaml

config_files = [\"pipeline_config.yaml\"]

for config_file in config_files:
    if Path(config_file).exists():
        try:
            with open(config_file, \"r\") as f:
                config = yaml.safe_load(f)
            print(f\"✓ {config_file} - Valid YAML\")
            
            # Check required sections
            required_sections = [\"pipeline\", \"testing\", \"output\"]
            for section in required_sections:
                if section in config:
                    print(f\"  ✓ {section} section\")
                else:
                    print(f\"  ✗ {section} section - MISSING\")
                    exit(1)
        except yaml.YAMLError as e:
            print(f\"✗ {config_file} - Invalid YAML: {e}\")
            exit(1)
    else:
        print(f\"○ {config_file} - Optional, will use defaults\")
'"

# Summary
echo ""
echo "=============================================="
echo "📊 TEST SUMMARY"
echo "=============================================="

if [ $FAILED_TESTS -eq 0 ]; then
    print_status "SUCCESS" "All tests passed! ($PASSED_TESTS/$TOTAL_TESTS)"
    echo ""
    print_status "INFO" "🚀 Pipeline is ready to run!"
    echo ""
    echo "Next steps:"
    echo "1. Run full pipeline:    python3 run_camina_pipeline.py --mode full"
    echo "2. Run tests only:       python3 run_camina_pipeline.py --mode test"  
    echo "3. Quick test mode:      python3 run_camina_pipeline.py --quick"
    echo "4. With custom config:   python3 run_camina_pipeline.py --config pipeline_config.yaml"
    exit 0
else
    print_status "ERROR" "Some tests failed! ($FAILED_TESTS/$TOTAL_TESTS failed)"
    echo ""
    echo "Failed tests:"
    for test_name in "${FAILED_TEST_NAMES[@]}"; do
        echo "  ❌ $test_name"
    done
    echo ""
    print_status "WARNING" "Please fix the issues above before running the pipeline"
    exit 1
fi