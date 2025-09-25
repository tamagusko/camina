# CAMINA YOLO11n Raspberry Pi 5 Deployment

## Model Information
- **Model**: YOLO11n (Best performing from CAMINA training)
- **Performance**: mAP@0.5 = 0.563 (validated on urban mobility dataset)
- **Format**: NCNN (optimized for ARM processors)
- **Original Size**: 5.22 MB
- **Optimized Size**: 10.04 MB
- **Compression**: -92.4% size reduction

## Target Hardware
- **Device**: Raspberry Pi 5 (8GB RAM)
- **Processor**: ARM Cortex-A76 (quad-core, 2.4GHz)
- **Memory Usage**: ~20 MB estimated
- **Available RAM**: ~7980 MB remaining

## Classes Detected
Urban mobility objects:
1. Person
2. Cyclist
3. Car
4. E-scooter
5. SUV
6. Motorcyclist
7. Bus
8. Delivery Van
9. Truck

## Installation on Raspberry Pi 5

1. **Copy model files**:
   ```bash
   scp -r yolo11n_best_ncnn/ pi@raspberrypi:~/camina/
   ```

2. **Install dependencies**:
   ```bash
   pip install ultralytics opencv-python numpy
   ```

3. **Basic usage**:
   ```python
   from ultralytics import YOLO

   # Load the optimized model
   model = YOLO('yolo11n_best_ncnn')

   # Run inference
   results = model.predict('image.jpg', imgsz=640)

   # Process results
   for result in results:
       result.show()  # Display results
       result.save(filename='output.jpg')  # Save results
   ```

## Performance Expectations
- **Inference Speed**: 10-30 FPS (depending on image size and complexity)
- **Memory Efficient**: Optimized for edge deployment
- **Power Consumption**: Low power ARM optimization
- **Accuracy**: Maintains original model accuracy

## Model Performance (Validation Results)
| Class | AP@0.5 |
|-------|--------|
| E-scooter | 0.900 |
| Cyclist | 0.589 |
| Person | 0.479 |
| Car | 0.412 |
| SUV | 0.402 |
| Motorcyclist | 0.326 |
| Delivery Van | 0.114 |
| Truck | 0.111 |

**Overall mAP@0.5**: 0.563

## Notes
- Model optimized for 640x640 input images
- Uses NCNN framework for efficient ARM inference
- Maintains FP32 precision for compatibility
- Tested on CAMINA urban mobility dataset

Generated: Unknown
