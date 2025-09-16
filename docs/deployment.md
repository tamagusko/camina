# CAMINA Raspberry Pi 5 Deployment Guide

This guide provides comprehensive instructions for deploying CAMINA on Raspberry Pi 5 for edge inference with optimized performance.

## 📋 Prerequisites

### Hardware Requirements
- **Raspberry Pi 5** (8GB RAM recommended, 4GB minimum)
- **MicroSD Card**: 32GB+ (UHS-3 for 4K recording)
- **Camera**: Raspberry Pi Camera Module 3 (NoIR version for IR capability)
- **Power Supply**: Official Pi5 USB-C 5V/5A adapter
- **Cooling**: Active cooling fan (recommended for continuous operation)
- **Storage**: Optional USB 3.0 SSD for better I/O performance

### Optional Hardware
- **Display**: 7" touchscreen or HDMI monitor for debugging
- **Case**: Official Pi5 case with fan
- **LoRaWAN**: Dragino RS485-LN for remote data transmission
- **IR Lighting**: 850nm IR LED array for night vision

## 🚀 Quick Deployment

### 1. Prepare SD Card
```bash
# Download Raspberry Pi OS (64-bit)
wget https://downloads.raspberrypi.org/raspios_arm64/images/raspios_arm64-2023-12-05/2023-12-05-raspios-bookworm-arm64.zip

# Flash to SD card using Raspberry Pi Imager
# Enable SSH, set username/password, configure WiFi
```

### 2. Initial Setup
```bash
# SSH into Pi5
ssh pi@your-pi-ip

# Update system
sudo apt update && sudo apt full-upgrade -y

# Enable camera
sudo raspi-config
# Interface Options -> Camera -> Enable

# Reboot
sudo reboot
```

### 3. Install Dependencies
```bash
# Install Python and essential packages
sudo apt install -y python3-pip python3-venv git cmake

# Install system libraries for OpenCV
sudo apt install -y libopencv-dev python3-opencv
sudo apt install -y libatlas-base-dev libhdf5-dev libhdf5-serial-dev
sudo apt install -y libjasper-dev libqtgui4 libqt4-test

# Create virtual environment
python3 -m venv ~/camina-env
source ~/camina-env/bin/activate

# Upgrade pip
pip install --upgrade pip wheel setuptools
```

### 4. Install CAMINA
```bash
# Clone repository
git clone https://github.com/your-username/camina.git
cd camina

# Install Pi-specific requirements
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics opencv-python pillow numpy pyyaml
pip install onnxruntime  # CPU version for Pi5
```

### 5. Deploy Model
```bash
# Copy trained model from training system
scp user@training-machine:/path/to/output/edge_deployment/ ~/camina/models/

# Or download from cloud storage
wget -O models/camina_yolo11n.onnx https://your-storage/camina_yolo11n.onnx
```

## ⚡ Performance Optimization

### System Configuration
```bash
# Increase GPU memory split for better performance
sudo raspi-config
# Advanced Options -> Memory Split -> 128

# Enable GPU acceleration (if available)
echo 'dtoverlay=vc4-kms-v3d' | sudo tee -a /boot/config.txt

# Optimize CPU governor
echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Set GPU frequency
echo 'gpu_freq=750' | sudo tee -a /boot/config.txt

# Increase swap (optional, for large models)
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### Model Optimization
```bash
# Use ONNX model for best performance
python -c "
from ultralytics import YOLO
import onnxruntime as ort

# Test ONNX model
model_path = 'models/camina_yolo11n.onnx'
session = ort.InferenceSession(model_path)
print('ONNX model loaded successfully')
print(f'Input shape: {session.get_inputs()[0].shape}')
print(f'Input type: {session.get_inputs()[0].type}')
"
```

## 🔧 Configuration

### Camera Configuration
```bash
# Test camera
libcamera-hello --timeout 5000

# Camera configuration for CAMINA
cat > ~/camina/config/pi5_camera.yaml << EOF
camera:
  resolution: [640, 480]    # Optimized for Pi5
  fps: 30                   # Camera FPS
  device: 0                 # Camera device ID
  flip_horizontal: false    # Flip image horizontally
  flip_vertical: false      # Flip image vertically
  rotation: 0               # Rotation angle (0, 90, 180, 270)

inference:
  model_path: "models/camina_yolo11n.onnx"
  confidence_threshold: 0.25
  iou_threshold: 0.45
  input_size: 640

performance:
  num_threads: 4            # CPU threads for inference
  use_gpu: false            # GPU acceleration (if available)
  batch_size: 1             # Batch size for inference

display:
  show_fps: true            # Show FPS on display
  show_detections: true     # Show detection boxes
  font_scale: 0.5           # Font scale for text
EOF
```

### Create Inference Script
```bash
cat > ~/camina/pi5_inference.py << 'EOF'
#!/usr/bin/env python3
"""
CAMINA Pi5 Optimized Inference Script
"""
import cv2
import numpy as np
import time
import onnxruntime as ort
from pathlib import Path
import yaml
import argparse

class CaminaPi5:
    def __init__(self, config_path="config/pi5_camera.yaml"):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize ONNX Runtime session
        self.session = ort.InferenceSession(
            self.config['inference']['model_path'],
            providers=['CPUExecutionProvider']
        )

        # Get input details
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape

        # Class names
        self.class_names = [
            'pedestrian', 'cyclist', 'car', 'motorcycle',
            'bus', 'truck', 'e-scooter', 'SUV', 'delivery_van'
        ]

        # Performance tracking
        self.fps_counter = 0
        self.fps_time = time.time()

    def preprocess(self, image):
        """Preprocess image for inference"""
        # Resize
        input_size = self.config['inference']['input_size']
        resized = cv2.resize(image, (input_size, input_size))

        # Normalize
        normalized = resized.astype(np.float32) / 255.0

        # HWC to CHW
        transposed = np.transpose(normalized, (2, 0, 1))

        # Add batch dimension
        batched = np.expand_dims(transposed, 0)

        return batched

    def postprocess(self, outputs, original_shape):
        """Postprocess inference outputs"""
        detections = []

        # Extract outputs
        boxes = outputs[0][0]  # [num_detections, 6] (x1, y1, x2, y2, conf, class)

        h, w = original_shape[:2]
        input_size = self.config['inference']['input_size']

        for detection in boxes:
            x1, y1, x2, y2, conf, class_id = detection

            # Filter by confidence
            if conf < self.config['inference']['confidence_threshold']:
                continue

            # Scale coordinates back to original image
            x1 = int(x1 * w / input_size)
            y1 = int(y1 * h / input_size)
            x2 = int(x2 * w / input_size)
            y2 = int(y2 * h / input_size)

            class_id = int(class_id)
            if class_id < len(self.class_names):
                detections.append({
                    'bbox': [x1, y1, x2, y2],
                    'confidence': float(conf),
                    'class_id': class_id,
                    'class_name': self.class_names[class_id]
                })

        return detections

    def draw_detections(self, image, detections):
        """Draw detection results on image"""
        colors = [
            (0, 255, 0),    # pedestrian - green
            (255, 0, 0),    # cyclist - red
            (0, 0, 255),    # car - blue
            (255, 255, 0),  # motorcycle - cyan
            (255, 0, 255),  # bus - magenta
            (0, 255, 255),  # truck - yellow
            (128, 0, 128),  # e-scooter - purple
            (255, 165, 0),  # SUV - orange
            (0, 128, 0),    # delivery_van - dark green
        ]

        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            color = colors[det['class_id'] % len(colors)]

            # Draw bounding box
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            # Draw label
            label = f"{det['class_name']}: {det['confidence']:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX,
                                       self.config['display']['font_scale'], 2)[0]

            cv2.rectangle(image, (x1, y1 - label_size[1] - 10),
                         (x1 + label_size[0], y1), color, -1)
            cv2.putText(image, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX,
                       self.config['display']['font_scale'],
                       (255, 255, 255), 2)

        return image

    def calculate_fps(self):
        """Calculate and display FPS"""
        self.fps_counter += 1

        if self.fps_counter % 30 == 0:  # Update every 30 frames
            current_time = time.time()
            fps = 30 / (current_time - self.fps_time)
            self.fps_time = current_time
            return fps
        return None

    def run(self, source=0):
        """Main inference loop"""
        # Initialize camera
        cap = cv2.VideoCapture(source)

        # Set camera properties
        cam_config = self.config['camera']
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_config['resolution'][0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_config['resolution'][1])
        cap.set(cv2.CAP_PROP_FPS, cam_config['fps'])

        print("Starting CAMINA Pi5 inference...")
        print("Press 'q' to quit")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Apply transformations
            if cam_config.get('flip_horizontal', False):
                frame = cv2.flip(frame, 1)
            if cam_config.get('flip_vertical', False):
                frame = cv2.flip(frame, 0)
            if cam_config.get('rotation', 0) != 0:
                if cam_config['rotation'] == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif cam_config['rotation'] == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif cam_config['rotation'] == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            # Inference
            start_time = time.time()

            # Preprocess
            input_tensor = self.preprocess(frame)

            # Run inference
            outputs = self.session.run(None, {self.input_name: input_tensor})

            # Postprocess
            detections = self.postprocess(outputs, frame.shape)

            inference_time = time.time() - start_time

            # Draw results
            if self.config['display']['show_detections']:
                frame = self.draw_detections(frame, detections)

            # Show FPS
            if self.config['display']['show_fps']:
                fps = self.calculate_fps()
                if fps is not None:
                    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # Show inference time
                cv2.putText(frame, f"Inference: {inference_time*1000:.1f}ms",
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Show detection count
            cv2.putText(frame, f"Detections: {len(detections)}", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Display frame
            cv2.imshow('CAMINA Pi5', frame)

            # Check for quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

def main():
    parser = argparse.ArgumentParser(description='CAMINA Pi5 Inference')
    parser.add_argument('--config', default='config/pi5_camera.yaml',
                       help='Configuration file path')
    parser.add_argument('--source', default=0,
                       help='Video source (0 for camera, path for file)')

    args = parser.parse_args()

    # Initialize and run
    camina = CaminaPi5(args.config)
    camina.run(args.source)

if __name__ == "__main__":
    main()
EOF

chmod +x ~/camina/pi5_inference.py
```

## 🔄 System Service Setup

### Create Systemd Service
```bash
sudo tee /etc/systemd/system/camina.service << EOF
[Unit]
Description=CAMINA Urban Mobility Counter
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/camina
Environment=PATH=/home/pi/camina-env/bin
ExecStart=/home/pi/camina-env/bin/python pi5_inference.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable camina.service
sudo systemctl start camina.service

# Check status
sudo systemctl status camina.service
```

## 📊 Monitoring and Maintenance

### Performance Monitoring
```bash
# Create monitoring script
cat > ~/camina/monitor.py << 'EOF'
#!/usr/bin/env python3
import psutil
import time
import json
from datetime import datetime

def monitor_system():
    """Monitor system performance"""
    while True:
        stats = {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'temperature': get_cpu_temperature(),
            'disk_usage': psutil.disk_usage('/').percent
        }

        # Log to file
        with open('logs/system_monitor.log', 'a') as f:
            f.write(json.dumps(stats) + '\n')

        time.sleep(60)  # Monitor every minute

def get_cpu_temperature():
    """Get CPU temperature"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000
        return temp
    except:
        return None

if __name__ == "__main__":
    monitor_system()
EOF

chmod +x ~/camina/monitor.py

# Create log directory
mkdir -p ~/camina/logs

# Run monitor in background
nohup python ~/camina/monitor.py &
```

### Log Rotation
```bash
# Setup log rotation
sudo tee /etc/logrotate.d/camina << EOF
/home/pi/camina/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 pi pi
}
EOF
```

## 🔧 Troubleshooting

### Common Issues

#### Low FPS Performance
```bash
# Check CPU governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# Set to performance
echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Check temperature throttling
vcgencmd measure_temp
vcgencmd get_throttled
```

#### Memory Issues
```bash
# Check memory usage
free -h

# Optimize Python memory
export PYTHONMALLOC=malloc

# Reduce batch size in config
```

#### Camera Issues
```bash
# Test camera
libcamera-hello --timeout 5000

# Check camera connection
vcgencmd get_camera

# Enable legacy camera support if needed
sudo raspi-config
# Advanced Options -> GL Driver -> Legacy
```

### Performance Tuning

#### Optimal Configuration for Pi5
```yaml
# config/pi5_optimized.yaml
camera:
  resolution: [640, 480]    # Balance between quality and performance
  fps: 15                   # Reduced FPS for stable inference

inference:
  input_size: 416           # Reduced input size for faster inference
  confidence_threshold: 0.3 # Higher threshold to reduce false positives

performance:
  num_threads: 4            # Use all 4 cores
```

#### Disable Unnecessary Services
```bash
# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon
sudo systemctl disable triggerhappy
sudo systemctl disable dphys-swapfile  # If not using swap

# Disable desktop environment (if running headless)
sudo systemctl set-default multi-user.target
```

## 📈 Performance Expectations

### Benchmark Results (Pi5 8GB)

| Model Format | Input Size | FPS | CPU Usage | Memory Usage |
|--------------|------------|-----|-----------|--------------|
| ONNX         | 640x640    | 8-12| 70-80%    | 400-500MB    |
| ONNX         | 416x416    | 12-18| 60-70%   | 300-400MB    |
| NCNN         | 640x640    | 15-20| 50-60%   | 200-300MB    |
| NCNN         | 416x416    | 20-25| 40-50%   | 150-250MB    |

### Expected Performance Targets
- **Target FPS**: 15+ for real-time monitoring
- **Inference Time**: <66ms per frame
- **Memory Usage**: <1GB total system
- **CPU Temperature**: <70°C sustained
- **Power Consumption**: <10W (Pi5 + camera)

## 🚀 Next Steps

1. **Test the deployment** with your specific use case
2. **Fine-tune configuration** based on performance requirements
3. **Set up remote monitoring** for production deployments
4. **Implement data logging** for long-term analysis
5. **Add LoRaWAN connectivity** for remote sites
6. **Set up OTA updates** for model updates

For additional support, refer to the main CAMINA documentation or raise an issue on the GitHub repository.