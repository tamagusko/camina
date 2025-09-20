#!/bin/bash

# CAMINA YOLO Model Training and Evaluation Pipeline
# Academic-grade experimental methodology for paper submission

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  CAMINA YOLO Model Training & Evaluation${NC}"
echo -e "${BLUE}  Academic Paper Results Generation${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if we're in the right directory
if [ ! -f "train_evaluate_yolo_models.py" ]; then
    echo -e "${RED}Error: train_evaluate_yolo_models.py not found!${NC}"
    echo -e "${YELLOW}Please run this script from the CAMINA project root directory${NC}"
    exit 1
fi

# Check if dataset exists
if [ ! -d "data/dataset_v4i_yolov11" ]; then
    echo -e "${RED}Error: Dataset not found at data/dataset_v4i_yolov11${NC}"
    echo -e "${YELLOW}Please ensure the dataset is properly downloaded and extracted${NC}"
    exit 1
fi

# Check Python environment
echo -e "${YELLOW}Checking Python environment...${NC}"
if ! python3 -c "import torch, ultralytics" 2>/dev/null; then
    echo -e "${RED}Error: Required packages not installed${NC}"
    echo -e "${YELLOW}Please install requirements: pip install -r requirements.txt${NC}"
    exit 1
fi

# Check GPU availability
echo -e "${YELLOW}Checking GPU availability...${NC}"
GPU_INFO=$(python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU count: {torch.cuda.device_count()}'); print(f'GPU name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')" 2>/dev/null)
echo -e "${BLUE}$GPU_INFO${NC}"

# Create log directory
mkdir -p logs

# Get timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/yolo_comparison_${TIMESTAMP}.log"

echo -e "${GREEN}Starting YOLO model training and evaluation...${NC}"
echo -e "${YELLOW}This process will train 4 models: YOLOv5n, YOLOv8n, YOLOv10n, YOLO11n${NC}"
echo -e "${YELLOW}Expected duration: 2-8 hours depending on hardware${NC}"
echo -e "${YELLOW}Log file: ${LOG_FILE}${NC}"

# Ask for confirmation
read -p "Do you want to proceed? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Training cancelled by user${NC}"
    exit 0
fi

# Run the training and evaluation
echo -e "${GREEN}Starting training pipeline...${NC}"
python3 train_evaluate_yolo_models.py 2>&1 | tee "$LOG_FILE"

# Check if training completed successfully
if [ $? -eq 0 ]; then
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  Training and Evaluation Completed Successfully!${NC}"
    echo -e "${GREEN}================================================${NC}"

    # Show results location
    if [ -d "outputs/model_comparison" ]; then
        echo -e "${YELLOW}Results Location:${NC}"
        echo -e "${BLUE}📁 Models: outputs/model_comparison/models/${NC}"
        echo -e "${BLUE}📊 Tables: outputs/model_comparison/tables/${NC}"
        echo -e "${BLUE}📈 Plots: outputs/model_comparison/plots/${NC}"
        echo -e "${BLUE}📋 Reports: outputs/model_comparison/results/${NC}"
        echo -e "${BLUE}📝 Logs: ${LOG_FILE}${NC}"

        # Show quick summary if available
        if [ -f "outputs/model_comparison/tables/table3_model_comparison.csv" ]; then
            echo -e "\n${YELLOW}Quick Results Summary:${NC}"
            echo -e "${BLUE}$(head -1 outputs/model_comparison/tables/table3_model_comparison.csv)${NC}"
            tail -n +2 "outputs/model_comparison/tables/table3_model_comparison.csv" | while read line; do
                echo -e "${GREEN}$line${NC}"
            done
        fi
    fi

    echo -e "\n${GREEN}✅ Academic tables are ready for paper submission!${NC}"

else
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}  Training Failed!${NC}"
    echo -e "${RED}================================================${NC}"
    echo -e "${YELLOW}Check the log file for details: ${LOG_FILE}${NC}"
    exit 1
fi