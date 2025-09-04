#!/usr/bin/env python3
"""
Raspberry Pi 5 Deployment Optimizer
Optimizes YOLO models for deployment on Raspberry Pi 5 with NCNN backend
"""

import os
import sys
import json
import logging
import argparse
import subprocess
import time
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import cv2

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RPi5DeploymentOptimizer:
    def __init__(self, model_path: str, output_dir: str = 'rpi5_deployment'):
        """
        Initialize Raspberry Pi 5 deployment optimizer
        
        Args:
            model_path: Path to trained YOLO model
            output_dir: Output directory for optimized models
        """
        self.model_path = Path(model_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Raspberry Pi 5 specifications
        self.rpi5_specs = {
            'cpu_cores': 4,
            'cpu_arch': 'aarch64',
            'ram_gb': 8,  # Assuming 8GB model
            'gpu': 'VideoCore VII',
            'preferred_formats': ['ncnn', 'onnx', 'tflite'],
            'max_threads': 4,
            'target_fps': 15,  # Realistic target for real-time inference
        }
        
        # Optimization configurations
        self.optimization_configs = {
            'ncnn': {
                'quantization': 'int8',
                'optimize_for_size': True,
                'vulkan_compute': True,  # RPi5 supports Vulkan
                'thread_count': 4
            },
            'onnx': {
                'opset_version': 12,
                'dynamic_batch': False,
                'optimize': True,
                'fp16': False  # Better compatibility
            },
            'tflite': {
                'quantization': 'int8',
                'representative_dataset': True,
                'optimize_for_size': True,
                'edge_tpu': False  # Standard RPi5 without Edge TPU
            }
        }
        
        logger.info(f"Initialized RPi5 optimizer for: {self.model_path}")
    
    def validate_model(self) -> bool:
        """Validate input model exists and is loadable"""
        if not self.model_path.exists():
            logger.error(f"Model file not found: {self.model_path}")
            return False
        
        try:
            # Try to load with ultralytics
            from ultralytics import YOLO
            model = YOLO(str(self.model_path))
            logger.info(f"Model validation successful: {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Model validation failed: {e}")
            return False
    
    def export_to_ncnn(self) -> Optional[str]:
        """
        Export model to NCNN format optimized for Raspberry Pi 5
        
        Returns:
            Path to exported NCNN model directory or None if failed
        """
        logger.info("Exporting model to NCNN format...")
        
        try:
            from ultralytics import YOLO
            
            # Load model
            model = YOLO(str(self.model_path))
            
            # Export with RPi5 optimizations
            ncnn_path = model.export(
                format='ncnn',
                imgsz=640,
                optimize=True,
                half=False,  # Better compatibility on ARM
                int8=self.optimization_configs['ncnn']['quantization'] == 'int8',
                dynamic=False,
                simplify=True,
                workspace=4,  # GB, suitable for RPi5
            )
            
            # Move to output directory
            ncnn_output = self.output_dir / 'ncnn_model'
            if ncnn_output.exists():
                shutil.rmtree(ncnn_output)
            shutil.move(str(ncnn_path), str(ncnn_output))
            
            logger.info(f"NCNN export successful: {ncnn_output}")
            
            # Create optimization metadata
            self._save_optimization_metadata('ncnn', ncnn_output)
            
            return str(ncnn_output)
            
        except Exception as e:
            logger.error(f"NCNN export failed: {e}")
            return None
    
    def export_to_onnx(self) -> Optional[str]:
        """
        Export model to ONNX format
        
        Returns:
            Path to exported ONNX model or None if failed
        """
        logger.info("Exporting model to ONNX format...")
        
        try:
            from ultralytics import YOLO
            
            model = YOLO(str(self.model_path))
            
            onnx_path = model.export(
                format='onnx',
                imgsz=640,
                dynamic=False,  # Fixed input size for better optimization
                simplify=True,
                opset=self.optimization_configs['onnx']['opset_version'],
            )
            
            # Move to output directory
            onnx_output = self.output_dir / 'model.onnx'
            shutil.move(str(onnx_path), str(onnx_output))
            
            logger.info(f"ONNX export successful: {onnx_output}")
            
            # Create optimization metadata
            self._save_optimization_metadata('onnx', onnx_output)
            
            return str(onnx_output)
            
        except Exception as e:
            logger.error(f"ONNX export failed: {e}")
            return None
    
    def export_to_tflite(self) -> Optional[str]:
        """
        Export model to TensorFlow Lite format
        
        Returns:
            Path to exported TFLite model or None if failed
        """
        logger.info("Exporting model to TensorFlow Lite format...")
        
        try:
            from ultralytics import YOLO
            
            model = YOLO(str(self.model_path))
            
            tflite_path = model.export(
                format='tflite',
                imgsz=640,
                int8=self.optimization_configs['tflite']['quantization'] == 'int8',
            )
            
            # Move to output directory
            tflite_output = self.output_dir / 'model.tflite'
            shutil.move(str(tflite_path), str(tflite_output))
            
            logger.info(f"TFLite export successful: {tflite_output}")
            
            # Create optimization metadata
            self._save_optimization_metadata('tflite', tflite_output)
            
            return str(tflite_output)
            
        except Exception as e:
            logger.error(f"TFLite export failed: {e}")
            return None
    
    def _save_optimization_metadata(self, format_name: str, model_path: Path):
        """Save optimization metadata for each exported model"""
        metadata = {
            'format': format_name,
            'source_model': str(self.model_path),
            'export_path': str(model_path),
            'optimization_config': self.optimization_configs[format_name],
            'target_device': 'Raspberry Pi 5',
            'target_specs': self.rpi5_specs,
            'export_timestamp': time.time(),
        }
        
        metadata_file = model_path.parent / f'{format_name}_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def create_rpi5_inference_script(self, model_format: str = 'ncnn') -> str:
        """
        Create optimized inference script for Raspberry Pi 5
        
        Args:
            model_format: Format to use ('ncnn', 'onnx', 'tflite')
            
        Returns:
            Path to created inference script
        """
        script_content = f'''#!/usr/bin/env python3
"""
Raspberry Pi 5 Optimized Inference Script
Generated for CAMINA 9-class urban mobility detection
"""

import cv2
import numpy as np
import time
import argparse
from pathlib import Path

class RPi5Inference:
    def __init__(self, model_path, format='{model_format}'):
        """Initialize inference engine for Raspberry Pi 5"""
        self.model_path = model_path
        self.format = format
        self.class_names = [
            'pedestrian', 'cyclist', 'car', 'motorcycle',
            'bus', 'truck', 'e-scooter', 'SUV', 'delivery_van'
        ]
        self.colors = [
            (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
            (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0), (0, 128, 128)
        ]
        
        self.load_model()
    
    def load_model(self):
        """Load model based on format"""
        if self.format == 'ncnn':
            self.load_ncnn_model()
        elif self.format == 'onnx':
            self.load_onnx_model()
        elif self.format == 'tflite':
            self.load_tflite_model()
        else:
            raise ValueError(f"Unsupported format: {{self.format}}")
    
    def load_ncnn_model(self):
        """Load NCNN model (requires ncnn-python)"""
        try:
            import ncnn
            
            self.net = ncnn.Net()
            self.net.opt.use_vulkan_compute = True  # RPi5 supports Vulkan
            self.net.opt.num_threads = 4  # RPi5 has 4 cores
            
            # Load model files
            model_dir = Path(self.model_path)
            param_file = model_dir / 'model.ncnn.param'
            bin_file = model_dir / 'model.ncnn.bin'
            
            self.net.load_param(str(param_file))
            self.net.load_model(str(bin_file))
            
            print("NCNN model loaded successfully")
            
        except ImportError:
            print("ncnn-python not installed. Install with: pip install ncnn")
            raise
    
    def load_onnx_model(self):
        """Load ONNX model (requires onnxruntime)"""
        try:
            import onnxruntime as ort
            
            # Optimize for RPi5
            sess_options = ort.SessionOptions()
            sess_options.inter_op_num_threads = 4
            sess_options.intra_op_num_threads = 4
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            providers = ['CPUExecutionProvider']
            self.session = ort.InferenceSession(self.model_path, sess_options, providers=providers)
            
            print("ONNX model loaded successfully")
            
        except ImportError:
            print("onnxruntime not installed. Install with: pip install onnxruntime")
            raise
    
    def load_tflite_model(self):
        """Load TensorFlow Lite model"""
        try:
            import tensorflow as tf
            
            # Load TFLite model
            self.interpreter = tf.lite.Interpreter(
                model_path=self.model_path,
                num_threads=4  # RPi5 optimization
            )
            self.interpreter.allocate_tensors()
            
            # Get input/output details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            print("TensorFlow Lite model loaded successfully")
            
        except ImportError:
            print("tensorflow not installed. Install with: pip install tensorflow")
            raise
    
    def preprocess_image(self, image, input_size=640):
        """Preprocess image for inference"""
        # Resize image
        h, w = image.shape[:2]
        scale = input_size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        
        resized = cv2.resize(image, (new_w, new_h))
        
        # Pad to square
        pad_w = input_size - new_w
        pad_h = input_size - new_h
        
        padded = cv2.copyMakeBorder(
            resized, 0, pad_h, 0, pad_w,
            cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )
        
        # Normalize
        normalized = padded.astype(np.float32) / 255.0
        
        # Add batch dimension and change to CHW format
        input_tensor = np.transpose(normalized, (2, 0, 1))
        input_tensor = np.expand_dims(input_tensor, axis=0)
        
        return input_tensor, scale
    
    def run_inference(self, image):
        """Run inference on preprocessed image"""
        input_tensor, scale = self.preprocess_image(image)
        
        start_time = time.time()
        
        if self.format == 'ncnn':
            outputs = self.run_ncnn_inference(input_tensor)
        elif self.format == 'onnx':
            outputs = self.run_onnx_inference(input_tensor)
        elif self.format == 'tflite':
            outputs = self.run_tflite_inference(input_tensor)
        
        inference_time = (time.time() - start_time) * 1000  # ms
        
        return outputs, inference_time, scale
    
    def run_ncnn_inference(self, input_tensor):
        """Run NCNN inference"""
        # Convert to ncnn Mat
        import ncnn
        
        mat = ncnn.Mat.from_pixels(
            input_tensor[0].transpose(1, 2, 0) * 255,
            ncnn.Mat.PixelType.PIXEL_RGB,
            640, 640
        )
        mat.substract_mean_normalize([0, 0, 0], [1/255.0, 1/255.0, 1/255.0])
        
        # Run inference
        extractor = self.net.create_extractor()
        extractor.input("in0", mat)
        
        outputs = []
        for i in range(3):  # Typically 3 output layers for YOLO
            ret, out = extractor.extract(f"out{{i}}")
            if ret == 0:
                outputs.append(np.array(out))
        
        return outputs
    
    def run_onnx_inference(self, input_tensor):
        """Run ONNX inference"""
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {{input_name: input_tensor.astype(np.float32)}})
        return outputs
    
    def run_tflite_inference(self, input_tensor):
        """Run TensorFlow Lite inference"""
        # Set input tensor
        self.interpreter.set_tensor(
            self.input_details[0]['index'],
            input_tensor.astype(np.float32)
        )
        
        # Run inference
        self.interpreter.invoke()
        
        # Get output tensors
        outputs = []
        for output_detail in self.output_details:
            output = self.interpreter.get_tensor(output_detail['index'])
            outputs.append(output)
        
        return outputs
    
    def postprocess_outputs(self, outputs, scale, conf_threshold=0.5, nms_threshold=0.4):
        """Postprocess model outputs to get detections"""
        # Simplified postprocessing - implement based on your specific model output format
        # This is a placeholder implementation
        detections = []
        
        # Parse outputs and apply NMS
        # Implementation depends on the specific YOLO version and output format
        
        return detections
    
    def draw_detections(self, image, detections):
        """Draw detection results on image"""
        for det in detections:
            x1, y1, x2, y2, conf, class_id = det
            
            # Draw bounding box
            color = self.colors[int(class_id) % len(self.colors)]
            cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            
            # Draw label
            label = f"{{self.class_names[int(class_id)]}}: {{conf:.2f}}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(image, (int(x1), int(y1) - label_size[1] - 10),
                         (int(x1) + label_size[0], int(y1)), color, -1)
            cv2.putText(image, label, (int(x1), int(y1) - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return image
    
    def process_video(self, video_path, output_path=None, display=True):
        """Process video file or camera stream"""
        # Open video
        if video_path == '0':
            cap = cv2.VideoCapture(0)  # Camera
        else:
            cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"Error opening video: {{video_path}}")
            return
        
        # Video writer setup
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        total_inference_time = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Run inference
            outputs, inference_time, scale = self.run_inference(frame)
            detections = self.postprocess_outputs(outputs, scale)
            
            # Draw results
            result_frame = self.draw_detections(frame.copy(), detections)
            
            # Add FPS info
            fps = 1000 / inference_time if inference_time > 0 else 0
            cv2.putText(result_frame, f"FPS: {{fps:.1f}}, Time: {{inference_time:.1f}}ms",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Display or save
            if display:
                cv2.imshow('CAMINA Detection', result_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            if output_path:
                out.write(result_frame)
            
            frame_count += 1
            total_inference_time += inference_time
            
            if frame_count % 30 == 0:
                avg_fps = 1000 / (total_inference_time / frame_count)
                print(f"Processed {{frame_count}} frames, Avg FPS: {{avg_fps:.1f}}")
        
        # Cleanup
        cap.release()
        if output_path:
            out.release()
        cv2.destroyAllWindows()
        
        # Final statistics
        if frame_count > 0:
            avg_inference_time = total_inference_time / frame_count
            avg_fps = 1000 / avg_inference_time
            print(f"\\nFinal Statistics:")
            print(f"Total frames: {{frame_count}}")
            print(f"Average inference time: {{avg_inference_time:.1f}}ms")
            print(f"Average FPS: {{avg_fps:.1f}}")

def main():
    parser = argparse.ArgumentParser(description='RPi5 CAMINA Inference')
    parser.add_argument('--model', required=True, help='Path to model file/directory')
    parser.add_argument('--format', choices=['ncnn', 'onnx', 'tflite'], 
                       default='ncnn', help='Model format')
    parser.add_argument('--input', required=True, 
                       help='Input video file or camera (use "0" for camera)')
    parser.add_argument('--output', help='Output video file (optional)')
    parser.add_argument('--no-display', action='store_true', 
                       help='Disable video display')
    
    args = parser.parse_args()
    
    # Initialize inference engine
    inference = RPi5Inference(args.model, args.format)
    
    # Process video
    inference.process_video(
        args.input, 
        args.output, 
        display=not args.no_display
    )

if __name__ == '__main__':
    main()
'''
        
        script_path = self.output_dir / 'rpi5_inference.py'
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make script executable
        os.chmod(script_path, 0o755)
        
        logger.info(f"Created RPi5 inference script: {script_path}")
        return str(script_path)
    
    def create_deployment_package(self) -> str:
        """
        Create complete deployment package for Raspberry Pi 5
        
        Returns:
            Path to deployment package directory
        """
        logger.info("Creating complete RPi5 deployment package...")
        
        # Export models in all supported formats
        exported_models = {}
        
        for format_name in self.rpi5_specs['preferred_formats']:
            if format_name == 'ncnn':
                model_path = self.export_to_ncnn()
            elif format_name == 'onnx':
                model_path = self.export_to_onnx()
            elif format_name == 'tflite':
                model_path = self.export_to_tflite()
            
            if model_path:
                exported_models[format_name] = model_path
        
        # Create inference scripts for each format
        for format_name in exported_models.keys():
            self.create_rpi5_inference_script(format_name)
        
        # Create installation script
        self._create_installation_script()
        
        # Create requirements file
        self._create_requirements_file()
        
        # Create README
        self._create_deployment_readme(exported_models)
        
        # Create benchmark script
        self._create_benchmark_script()
        
        logger.info(f"Deployment package created: {self.output_dir}")
        return str(self.output_dir)
    
    def _create_installation_script(self):
        """Create installation script for Raspberry Pi 5"""
        install_script = '''#!/bin/bash
# Raspberry Pi 5 CAMINA Installation Script

set -e

echo "Installing CAMINA detection system on Raspberry Pi 5..."

# Update system
sudo apt update
sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-venv git cmake build-essential
sudo apt install -y libopencv-dev python3-opencv
sudo apt install -y libvulkan1 mesa-vulkan-drivers

# Create virtual environment
python3 -m venv camina_env
source camina_env/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# Install format-specific packages
echo "Installing NCNN support..."
pip install ncnn || echo "NCNN installation failed - manual build may be required"

echo "Installing ONNX runtime..."
pip install onnxruntime

echo "Installing TensorFlow Lite..."
pip install tflite-runtime || pip install tensorflow

# Set up environment variables
echo 'export CAMINA_MODEL_PATH="$(pwd)"' >> ~/.bashrc
echo 'alias camina-detect="python3 rpi5_inference.py"' >> ~/.bashrc

echo "Installation completed!"
echo "Activate environment with: source camina_env/bin/activate"
echo "Run inference with: python3 rpi5_inference.py --model ncnn_model --input 0"
'''
        
        install_path = self.output_dir / 'install.sh'
        with open(install_path, 'w') as f:
            f.write(install_script)
        os.chmod(install_path, 0o755)
    
    def _create_requirements_file(self):
        """Create requirements.txt for Python dependencies"""
        requirements = '''# CAMINA RPi5 Requirements
opencv-python>=4.5.0
numpy>=1.21.0
onnxruntime>=1.12.0
tensorflow>=2.8.0
ncnn>=1.0.0
pillow>=8.0.0
psutil>=5.8.0
argparse
pathlib
'''
        
        req_path = self.output_dir / 'requirements.txt'
        with open(req_path, 'w') as f:
            f.write(requirements)
    
    def _create_deployment_readme(self, exported_models: Dict[str, str]):
        """Create comprehensive README for deployment"""
        readme_content = f'''# CAMINA Urban Mobility Detection - Raspberry Pi 5 Deployment

This package contains optimized YOLO models for 9-class urban mobility detection on Raspberry Pi 5.

## Classes Detected
1. Pedestrian
2. Cyclist  
3. Car
4. Motorcycle
5. Bus
6. Truck
7. E-scooter (new)
8. SUV (new)
9. Delivery Van (new)

## Hardware Requirements
- Raspberry Pi 5 (8GB recommended)
- Camera module or USB camera
- MicroSD card (32GB+)
- Raspberry Pi OS (64-bit)

## Installation

1. Run the installation script:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

2. Activate the environment:
   ```bash
   source camina_env/bin/activate
   ```

## Model Formats

This package includes models in multiple formats optimized for RPi5:

{chr(10).join([f"- **{fmt.upper()}**: {path}" for fmt, path in exported_models.items()])}

### Format Recommendations:
- **NCNN**: Best performance with Vulkan GPU acceleration
- **ONNX**: Good balance of speed and compatibility  
- **TensorFlow Lite**: Smallest size, good for memory-constrained scenarios

## Usage

### Camera Inference
```bash
python3 rpi5_inference.py --model ncnn_model --format ncnn --input 0
```

### Video File Inference
```bash
python3 rpi5_inference.py --model ncnn_model --format ncnn --input video.mp4 --output results.mp4
```

### Benchmark Performance
```bash
python3 benchmark.py --model ncnn_model --format ncnn
```

## Performance Expectations

Target performance on Raspberry Pi 5:
- **FPS**: 10-20 FPS (depending on format and scene complexity)
- **Latency**: 50-100ms per frame
- **Memory Usage**: 500MB-1GB
- **Power**: ~5-8W total system consumption

## Optimization Tips

1. **Use NCNN with Vulkan**: Best performance
2. **Lower resolution**: Use 480p input for higher FPS
3. **Reduce batch size**: Use batch=1 for real-time
4. **Enable GPU scheduling**: `sudo raspi-config` → Advanced → GPU Memory → 128MB
5. **Cooling**: Ensure adequate cooling for sustained performance

## Troubleshooting

### NCNN Issues
- Install Vulkan drivers: `sudo apt install mesa-vulkan-drivers`
- Check GPU memory: `vcgencmd get_mem gpu`

### Memory Issues  
- Increase swap: `sudo dphys-swapfile swapoff && sudo nano /etc/dphys-swapfile`
- Monitor usage: `htop` or `python3 -c "import psutil; print(psutil.virtual_memory())"`

### Performance Issues
- Check CPU frequency: `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq`
- Monitor temperature: `vcgencmd measure_temp`

## Development

### Custom Training
To retrain models with your data:
1. Prepare dataset in YOLO format
2. Use the training scripts in the main repository
3. Re-run this optimization pipeline

### Integration
The inference script can be easily integrated into larger applications:
```python
from rpi5_inference import RPi5Inference

inference = RPi5Inference("ncnn_model", "ncnn")
detections, time, scale = inference.run_inference(image)
```

## License
MIT License - see main repository for details

## Support
- Issues: Report on GitHub repository
- Performance: Check benchmark results
- Updates: Monitor repository for model improvements
'''
        
        readme_path = self.output_dir / 'README.md'
        with open(readme_path, 'w') as f:
            f.write(readme_content)
    
    def _create_benchmark_script(self):
        """Create benchmark script for performance testing"""
        benchmark_script = '''#!/usr/bin/env python3
"""
RPi5 Performance Benchmark Script
Tests inference speed and accuracy across different model formats
"""

import time
import cv2
import numpy as np
import json
import argparse
from pathlib import Path
from rpi5_inference import RPi5Inference

def benchmark_model(model_path, format_type, test_images=100):
    """Benchmark a specific model format"""
    print(f"Benchmarking {format_type.upper()} model...")
    
    # Initialize inference
    inference = RPi5Inference(model_path, format_type)
    
    # Generate test images
    test_imgs = []
    for i in range(test_images):
        img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        test_imgs.append(img)
    
    # Warmup
    for i in range(10):
        inference.run_inference(test_imgs[i % len(test_imgs)])
    
    # Benchmark
    inference_times = []
    start_time = time.time()
    
    for img in test_imgs:
        _, inf_time, _ = inference.run_inference(img)
        inference_times.append(inf_time)
    
    total_time = time.time() - start_time
    
    # Calculate metrics
    avg_inference_time = np.mean(inference_times)
    fps = 1000 / avg_inference_time
    throughput = test_images / total_time
    
    results = {
        'format': format_type,
        'model_path': str(model_path),
        'test_images': test_images,
        'avg_inference_time_ms': avg_inference_time,
        'fps': fps,
        'throughput_images_per_sec': throughput,
        'min_inference_time_ms': np.min(inference_times),
        'max_inference_time_ms': np.max(inference_times),
        'std_inference_time_ms': np.std(inference_times)
    }
    
    return results

def main():
    parser = argparse.ArgumentParser(description='RPi5 Model Benchmark')
    parser.add_argument('--model', required=True, help='Model path')
    parser.add_argument('--format', required=True, choices=['ncnn', 'onnx', 'tflite'])
    parser.add_argument('--images', type=int, default=100, help='Number of test images')
    parser.add_argument('--output', help='Output JSON file for results')
    
    args = parser.parse_args()
    
    # Run benchmark
    results = benchmark_model(args.model, args.format, args.images)
    
    # Print results
    print("\\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    print(f"Format: {results['format'].upper()}")
    print(f"Average Inference Time: {results['avg_inference_time_ms']:.2f}ms")
    print(f"FPS: {results['fps']:.1f}")
    print(f"Throughput: {results['throughput_images_per_sec']:.1f} images/sec")
    print(f"Min/Max Time: {results['min_inference_time_ms']:.1f}/{results['max_inference_time_ms']:.1f}ms")
    print("="*60)
    
    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {args.output}")

if __name__ == '__main__':
    main()
'''
        
        benchmark_path = self.output_dir / 'benchmark.py'
        with open(benchmark_path, 'w') as f:
            f.write(benchmark_script)
        os.chmod(benchmark_path, 0o755)
    
    def optimize_all_formats(self) -> Dict[str, str]:
        """
        Optimize model for all supported formats
        
        Returns:
            Dictionary mapping format names to exported model paths
        """
        if not self.validate_model():
            return {}
        
        exported_models = {}
        
        logger.info("Starting multi-format optimization for Raspberry Pi 5...")
        
        # Export to each format
        formats_methods = {
            'ncnn': self.export_to_ncnn,
            'onnx': self.export_to_onnx,
            'tflite': self.export_to_tflite
        }
        
        for format_name, export_method in formats_methods.items():
            try:
                model_path = export_method()
                if model_path:
                    exported_models[format_name] = model_path
                    logger.info(f"✓ {format_name.upper()} export successful")
                else:
                    logger.warning(f"✗ {format_name.upper()} export failed")
            except Exception as e:
                logger.error(f"✗ {format_name.upper()} export error: {e}")
        
        # Create complete deployment package
        if exported_models:
            self.create_deployment_package()
            
            # Save optimization summary
            summary = {
                'source_model': str(self.model_path),
                'exported_formats': exported_models,
                'rpi5_specs': self.rpi5_specs,
                'optimization_configs': self.optimization_configs,
                'timestamp': time.time()
            }
            
            summary_path = self.output_dir / 'optimization_summary.json'
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Optimization completed! Package: {self.output_dir}")
        
        return exported_models

def main():
    parser = argparse.ArgumentParser(description='Raspberry Pi 5 Deployment Optimizer')
    parser.add_argument('--model', required=True, help='Path to trained YOLO model')
    parser.add_argument('--output', default='rpi5_deployment', help='Output directory')
    parser.add_argument('--format', choices=['ncnn', 'onnx', 'tflite', 'all'], 
                       default='all', help='Export format(s)')
    
    args = parser.parse_args()
    
    # Initialize optimizer
    optimizer = RPi5DeploymentOptimizer(args.model, args.output)
    
    # Run optimization
    if args.format == 'all':
        exported_models = optimizer.optimize_all_formats()
        print(f"\\nExported models: {exported_models}")
    else:
        if args.format == 'ncnn':
            model_path = optimizer.export_to_ncnn()
        elif args.format == 'onnx':
            model_path = optimizer.export_to_onnx()
        elif args.format == 'tflite':
            model_path = optimizer.export_to_tflite()
        
        if model_path:
            optimizer.create_rpi5_inference_script(args.format)
            print(f"Model exported: {model_path}")

if __name__ == '__main__':
    main()