# CAMINA Paper Figures

This directory contains publication-ready figures for the CAMINA research paper.

## Figure 1: Framework Overview

**Title:** "Summary of the Implemented Framework"

**Files:**
- `figure1_framework_overview.png` - High-resolution PNG (300 DPI, 12x10 inches)
- `figure1_framework_overview.pdf` - Vector PDF for publication
- `figure1_framework_overview.R` - Source R code for reproducibility

**Description:**
Comprehensive framework diagram showing the complete CAMINA methodology from input to output, including:

### Key Components Visualized:
1. **Input Layer**: Urban images dataset (2,295 images)
2. **Hybrid Detection Architecture**:
   - YOLO11n Branch (6 COCO classes)
   - YOLO-World Branch (3 emerging classes)
3. **Rule-Based Cyclist Detection Algorithm** (key innovation)
4. **Detection Fusion**: NMS and 9-class taxonomy mapping
5. **Edge Deployment**: Raspberry Pi 5 optimization
6. **Output Layer**: 9-class urban mobility detection

### Technical Specifications Highlighted:
- Hybrid architecture approach
- IoU thresholds (NMS: 0.5, Cyclist: ≥0.20)
- Real-time edge deployment focus
- Privacy-preserving citizen-led monitoring

### Design Features:
- Professional scientific style suitable for Q1 journals
- Color-coded components for clear differentiation
- Flow arrows showing data processing pipeline
- Technical specifications box
- Key innovations sidebar
- Publication-ready typography and layout

**Usage:** This figure serves as the primary architectural overview for the CAMINA paper, suitable for introduction or methodology sections.

## Generation Notes

All figures are generated using base R graphics for maximum compatibility and reproducibility. The code is structured to be easily maintainable and modifiable for future iterations.

**System Requirements:**
- R version 4.0+
- Base R graphics (no additional packages required)
- Standard fonts for cross-platform compatibility