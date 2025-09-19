# Academic Reports Guide

The CAMINA data preparation script generates comprehensive reports suitable for research publications.

## Generated Report Files

### 1. DATASET_REPORT.md
**Purpose:** General summary and documentation
**Contents:**
- Dataset overview (images, instances, classes)
- Split information (train/val counts)
- Class distribution table with percentages
- Pipeline features summary
- Detection source breakdown

**Use Case:** Documentation, project reports, general reference

### 2. ACADEMIC_REPORT.md
**Purpose:** Research paper integration
**Contents:**
- Abstract-ready dataset description
- Quantitative analysis with statistics
- Methodology description
- Quality assurance metrics
- Citation format
- Technical specifications for reproducibility

**Use Case:** Academic papers, journal submissions, conference presentations

### 3. class_distribution.csv
**Purpose:** Data analysis and visualization
**Columns:**
- `class_id`: Numeric class identifier (0-8)
- `class_name`: Human-readable class name
- `count`: Total instances of this class
- `percentage`: Percentage of total instances
- `detection_method`: Source (YOLO11l, YOLO-World, Spatial_Logic)

**Use Case:** Statistical analysis, plotting, custom reports

### 4. split_statistics.csv
**Purpose:** Dataset split analysis
**Columns:**
- `split`: Dataset split (train/val/test)
- `num_images`: Total images in split
- `images_with_labels`: Images with valid annotations
- `total_instances`: Total object instances
- `avg_instances_per_image`: Instance density
- `annotation_coverage`: Percentage of annotated images

**Use Case:** Split validation, coverage analysis, quality assessment

## Academic Report Content

### Statistical Metrics Included

**Dataset Composition:**
- Total images and annotations
- Average instances per image
- Class distribution analysis
- Most/least represented classes

**Quality Metrics:**
- Annotation coverage percentage
- Instance density statistics
- Standard deviation calculations
- Split balance ratios

**Methodology Description:**
- Detection pipeline overview
- Quality assurance procedures
- Technical specifications
- Reproducibility details

### Citation Format

The academic report includes a ready-to-use citation:

```bibtex
@dataset{camina_dataset_[name],
  title={CAMINA Urban Mobility Detection Dataset},
  author={CAMINA Research Team},
  year={2025},
  description={Multi-stage urban mobility object detection dataset with [N] annotations across [C] classes},
  url={https://github.com/camina-research/dataset}
}
```

## Using Reports in Papers

### For Methodology Sections

Extract content from **ACADEMIC_REPORT.md:**
- Pipeline description under "Detection Pipeline"
- Quality assurance under "Quality Assurance"
- Technical specifications for reproducibility

### For Results Sections

Use data from **CSV files:**
- Class distribution statistics
- Dataset composition metrics
- Annotation quality measurements

### For Data Availability Statements

Reference the **citation format** and **technical specifications** from the academic report.

## Example Integration

### Paper Section Example

```markdown
## Dataset

We created a comprehensive urban mobility dataset using the CAMINA
(Computer-Aided Mobility Intelligence for Nonlinear Analytics) pipeline.
The dataset contains 2,013 images with 15,247 object instances across
9 urban mobility classes, achieving 98.5% annotation coverage.

The detection pipeline employs a hybrid approach combining YOLO11l for
traditional object detection and YOLO-World for specialized urban
mobility objects. Spatial association algorithms generate cyclist
instances from person-bicycle pairs and combine person-e-scooter
detections for improved e-scooter detection accuracy.

Class distribution analysis reveals balanced representation across
vehicle categories, with cars (32.1%), persons (24.7%), and trucks
(15.3%) comprising the majority of instances. The dataset maintains
an 80/20 train-validation split with consistent instance density
(7.6 objects per image) across splits.
```

## Report Quality Indicators

### Completeness Metrics
- ✅ **Annotation Coverage:** >95% (excellent), 85-95% (good), <85% (needs review)
- ✅ **Instance Density:** >5 per image (rich), 2-5 (adequate), <2 (sparse)
- ✅ **Class Balance:** <50% in top class (balanced), 50-70% (acceptable), >70% (imbalanced)

### Validation Checks
- All images have corresponding labels
- YOLO format validation passed
- No empty annotation files
- Consistent class mappings

## Customizing Reports

### Adding Custom Metrics

The script can be extended to include:
- Bounding box size distributions
- Image resolution statistics
- Temporal analysis (if applicable)
- Geographical distribution

### Modifying Citation Format

Edit the `_create_academic_report()` method in `prepared_data_roboflow.py`:
```python
# Update citation section with your details
report += f"""
@dataset{{your_dataset_name,
  title={{Your Dataset Title}},
  author={{Your Name and Team}},
  institution={{Your Institution}},
  year={{2025}},
  ...
}}
"""
```

## Report File Locations

After running the preparation script:

```
roboflow_datasets/[dataset-name]/
├── DATASET_REPORT.md         # 📋 General summary
├── ACADEMIC_REPORT.md        # 📄 Paper-ready content
├── class_distribution.csv    # 📊 Class statistics
├── split_statistics.csv      # 📈 Split analysis
└── ...
```

## Best Practices

1. **Review reports before publication** - Verify all statistics and descriptions
2. **Customize citations** - Update author names and institutions
3. **Include methodology details** - Reference pipeline features used
4. **Validate quality metrics** - Ensure annotation coverage meets standards
5. **Use CSV data for plots** - Create visualizations from raw statistics