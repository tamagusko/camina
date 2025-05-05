### 🐞 Known Bugs & Issues

#### 1. Cyclist Misclassification

* **Description**: Cyclists are frequently misclassified as **motorcycles** instead of **bicycles** by YOLOv8.
* **Status**: Open
* **Workaround**: Retrain/fine-tune YOLO with cyclist-labeled data.
* **Suggested Fix**: Consider fine-tuning YOLOv8 with a dataset that includes explicit **cyclist** class 
* **Impact**: Affects modal share accuracy.
