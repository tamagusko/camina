### 🐞 Known Bugs & Issues

#### 1. Cyclist Misclassification ✅ RESOLVED

* **Description**: Cyclists were frequently misclassified as **motorcycles** instead of **bicycles** by base YOLO models.
* **Status**: **RESOLVED** with CAMINAv1 custom model
* **Solution**: Developed **CAMINAv1** model trained on COCO 2017 dataset with enhanced cyclist detection using synthetic cyclist class generation from person+bicycle overlaps.
* **Model**: `20250629_warmup_best.pt` (CAMINAv1)
* **Impact**: Significantly improved cyclist detection accuracy in modal share counting.

#### 2. Base YOLO11 Limitations

* **Description**: Base YOLO11 model lacks specific cyclist class, leading to detection inconsistencies.
* **Status**: **MITIGATED** with CAMINAv1
* **Workaround**: Use the custom CAMINAv1 model instead of base YOLO11.
* **Impact**: CAMINAv1 provides dedicated cyclist class with improved accuracy.
