"""
Automatic camera calibration system using Depth Anything V2 for pixel-to-meter conversion.
"""

import time
import os
import cv2
import numpy as np
import torch
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional, Any
import yaml
import hashlib

from .config import load_config, _get_project_root


class DepthCalibrator:
    """Automatic calibration using Depth Anything V2 for pixel-to-meter conversion."""
    
    def __init__(self):
        self.config = load_config()
        self.project_root = _get_project_root()
        self.calibration_data_path = self.project_root / "data" / "calibration"
        self.calibration_data_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize Depth Anything V2
        self.depth_model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._initialize_depth_model()
        
        # Reference frame for camera position detection
        self.reference_frame_path = self.calibration_data_path / "reference_frame.jpg"
        self.reference_hash_path = self.calibration_data_path / "reference_hash.txt"
        
    def _initialize_depth_model(self):
        """Initialize Depth Anything V2 model."""
        try:
            # Try importing Depth Anything V2
            from depth_anything_v2.dpt import DepthAnythingV2
            
            # Load the model (you may need to adjust model path/size)
            model_configs = {
                'vits': {'encoder': 'vits', 'features': 64, 'out_channels': [48, 96, 192, 384]},
                'vitb': {'encoder': 'vitb', 'features': 128, 'out_channels': [96, 192, 384, 768]},
                'vitl': {'encoder': 'vitl', 'features': 256, 'out_channels': [256, 512, 1024, 1024]}
            }
            
            # Use the small model for Raspberry Pi efficiency
            model_size = 'vits'
            self.depth_model = DepthAnythingV2(**model_configs[model_size])
            
            # Load pretrained weights (you'll need to download these)
            checkpoint_path = self.project_root / "models" / "depth_anything_v2_vits.pth"
            if checkpoint_path.exists():
                self.depth_model.load_state_dict(torch.load(checkpoint_path, map_location=self.device))
                self.depth_model.to(self.device).eval()
                print("Depth Anything V2 model loaded successfully")
            else:
                print(f"Warning: Depth model not found at {checkpoint_path}")
                print("Please download the model from: https://github.com/DepthAnything/Depth-Anything-V2")
                self.depth_model = None
                
        except ImportError:
            print("Warning: Depth Anything V2 not available. Install with:")
            print("pip install depth-anything-v2")
            self.depth_model = None
        except Exception as e:
            print(f"Error loading depth model: {e}")
            self.depth_model = None
    
    def estimate_depth(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Estimate depth map from image using Depth Anything V2."""
        if self.depth_model is None:
            return None
            
        try:
            # Preprocess image
            height, width = image.shape[:2]
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Resize to model input size
            input_size = 518  # Standard input size for Depth Anything V2
            image_resized = cv2.resize(image_rgb, (input_size, input_size))
            
            # Normalize
            image_tensor = torch.from_numpy(image_resized).float().div(255.0)
            image_tensor = image_tensor.permute(2, 0, 1).unsqueeze(0).to(self.device)
            
            # Generate depth map
            with torch.no_grad():
                depth = self.depth_model(image_tensor)
                depth = torch.nn.functional.interpolate(
                    depth.unsqueeze(1), 
                    size=(height, width), 
                    mode='bilinear', 
                    align_corners=False
                ).squeeze().cpu().numpy()
            
            return depth
            
        except Exception as e:
            print(f"Error estimating depth: {e}")
            return None
    
    def calibrate_pixels_per_meter(self, image: np.ndarray, known_objects: bool = True) -> Optional[float]:
        """
        Calibrate pixels per meter using depth estimation.
        
        Args:
            image: Input image from camera
            known_objects: Whether to use known object sizes for calibration
            
        Returns:
            Estimated pixels per meter value, or None if calibration failed
        """
        depth_map = self.estimate_depth(image)
        if depth_map is None:
            return None
            
        try:
            # Method 1: Use ground plane estimation
            pixels_per_meter = self._calibrate_from_ground_plane(image, depth_map)
            
            if pixels_per_meter is None and known_objects:
                # Method 2: Use known object sizes (cars, people)
                pixels_per_meter = self._calibrate_from_known_objects(image, depth_map)
            
            return pixels_per_meter
            
        except Exception as e:
            print(f"Error in calibration: {e}")
            return None
    
    def _calibrate_from_ground_plane(self, image: np.ndarray, depth_map: np.ndarray) -> Optional[float]:
        """Calibrate using ground plane estimation."""
        height, width = image.shape[:2]
        
        # Sample ground plane points (bottom third of image)
        ground_y_start = int(height * 0.7)
        ground_region = depth_map[ground_y_start:, :]
        
        # Find median depth of ground plane
        ground_depth = np.median(ground_region[ground_region > 0])
        
        if ground_depth <= 0:
            return None
        
        # Estimate camera height (typical window installation: 1.5-3 meters)
        estimated_camera_height = 2.0  # meters
        
        # Calculate pixels per meter based on perspective geometry
        # For a pixel distance at ground level
        pixel_distance = 100  # pixels
        real_distance = (pixel_distance * ground_depth) / (height - ground_y_start)
        
        # Adjust for camera height perspective
        real_distance = real_distance * (ground_depth / estimated_camera_height)
        
        if real_distance > 0:
            pixels_per_meter = pixel_distance / real_distance
            
            # Sanity check: typical values should be 5-50 pixels per meter
            if 5 <= pixels_per_meter <= 50:
                return pixels_per_meter
        
        return None
    
    def _calibrate_from_known_objects(self, image: np.ndarray, depth_map: np.ndarray) -> Optional[float]:
        """Calibrate using known object sizes (requires object detection)."""
        # This would require running YOLO detection and using known object sizes
        # For now, return None - can be enhanced later
        return None
    
    def save_reference_frame(self, image: np.ndarray) -> None:
        """Save reference frame for camera position detection."""
        cv2.imwrite(str(self.reference_frame_path), image)
        
        # Calculate and save image hash for comparison
        image_hash = self._calculate_image_hash(image)
        with open(self.reference_hash_path, 'w') as f:
            f.write(image_hash)
        
        print(f"Reference frame saved: {self.reference_frame_path}")
    
    def check_camera_position_changed(self, current_image: np.ndarray, threshold: float = 0.1) -> bool:
        """
        Check if camera position has changed significantly.
        
        Args:
            current_image: Current camera frame
            threshold: Similarity threshold (lower = more sensitive)
            
        Returns:
            True if camera position has changed significantly
        """
        if not self.reference_frame_path.exists():
            return True  # No reference frame, consider as changed
        
        try:
            # Load reference frame
            reference_image = cv2.imread(str(self.reference_frame_path))
            if reference_image is None:
                return True
            
            # Calculate similarity using structural similarity
            current_gray = cv2.cvtColor(current_image, cv2.COLOR_BGR2GRAY)
            reference_gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY)
            
            # Resize to same size if needed
            if current_gray.shape != reference_gray.shape:
                reference_gray = cv2.resize(reference_gray, 
                                          (current_gray.shape[1], current_gray.shape[0]))
            
            # Calculate structural similarity
            from skimage.metrics import structural_similarity as ssim
            similarity = ssim(current_gray, reference_gray)
            
            # Also check hash-based similarity for faster comparison
            current_hash = self._calculate_image_hash(current_image)
            if self.reference_hash_path.exists():
                with open(self.reference_hash_path, 'r') as f:
                    reference_hash = f.read().strip()
                    
                # Simple hash comparison
                hash_similarity = self._compare_hashes(current_hash, reference_hash)
                
                # Combine both metrics
                combined_similarity = (similarity + hash_similarity) / 2
            else:
                combined_similarity = similarity
            
            changed = combined_similarity < (1.0 - threshold)
            
            if changed:
                print(f"Camera position change detected! Similarity: {combined_similarity:.3f}")
            
            return changed
            
        except Exception as e:
            print(f"Error checking camera position: {e}")
            return True  # Assume changed if error occurs
    
    def _calculate_image_hash(self, image: np.ndarray) -> str:
        """Calculate perceptual hash of image for quick comparison."""
        # Resize to small size and convert to grayscale
        small = cv2.resize(image, (8, 8))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        
        # Calculate average
        avg = gray.mean()
        
        # Create hash
        hash_bits = []
        for pixel in gray.flat:
            hash_bits.append('1' if pixel > avg else '0')
        
        return ''.join(hash_bits)
    
    def _compare_hashes(self, hash1: str, hash2: str) -> float:
        """Compare two perceptual hashes and return similarity (0-1)."""
        if len(hash1) != len(hash2):
            return 0.0
        
        matches = sum(c1 == c2 for c1, c2 in zip(hash1, hash2))
        return matches / len(hash1)
    
    def update_config_calibration(self, pixels_per_meter: float) -> bool:
        """Update the pixels_per_meter value in the config file."""
        try:
            config_path = self.project_root / "configs" / "main_config.yaml"
            
            # Read current config
            with open(config_path, 'r') as f:
                config_content = f.read()
            
            # Update pixels_per_meter value
            lines = config_content.split('\n')
            updated_lines = []
            updated = False
            
            for line in lines:
                if line.startswith('pixels_per_meter:'):
                    updated_lines.append(f'pixels_per_meter: {pixels_per_meter:.2f} # Auto-calibrated on {datetime.now().strftime("%Y-%m-%d %H:%M")}')
                    updated = True
                else:
                    updated_lines.append(line)
            
            if not updated:
                # Add the line if it doesn't exist
                # Find the speed estimation section
                for i, line in enumerate(updated_lines):
                    if '# Speed estimation settings' in line:
                        updated_lines.insert(i + 1, f'pixels_per_meter: {pixels_per_meter:.2f} # Auto-calibrated on {datetime.now().strftime("%Y-%m-%d %H:%M")}')
                        break
            
            # Write updated config
            with open(config_path, 'w') as f:
                f.write('\n'.join(updated_lines))
            
            print(f"Config updated: pixels_per_meter = {pixels_per_meter:.2f}")
            return True
            
        except Exception as e:
            print(f"Error updating config: {e}")
            return False
    
    def run_calibration(self, image: np.ndarray) -> bool:
        """
        Run complete calibration process.
        
        Args:
            image: Camera image for calibration
            
        Returns:
            True if calibration was successful
        """
        print("Starting automatic calibration...")
        
        # Estimate pixels per meter
        pixels_per_meter = self.calibrate_pixels_per_meter(image)
        
        if pixels_per_meter is None:
            print("Calibration failed - could not estimate pixels per meter")
            return False
        
        print(f"Estimated pixels per meter: {pixels_per_meter:.2f}")
        
        # Update config file
        if self.update_config_calibration(pixels_per_meter):
            # Save current image as reference frame
            self.save_reference_frame(image)
            
            # Save calibration metadata
            calibration_info = {
                'pixels_per_meter': pixels_per_meter,
                'calibration_date': datetime.now().isoformat(),
                'calibration_method': 'depth_anything_v2'
            }
            
            calibration_info_path = self.calibration_data_path / "calibration_info.yaml"
            with open(calibration_info_path, 'w') as f:
                yaml.dump(calibration_info, f)
            
            print("Calibration completed successfully!")
            return True
        else:
            print("Calibration failed - could not update config")
            return False


def create_calibration_script():
    """Create standalone calibration script."""
    script_content = '''#!/usr/bin/env python3
"""
Standalone calibration script for CAMINA system.
Run this script when installing a new camera to automatically calibrate pixels_per_meter.
"""

import cv2
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.append(str(src_path))

from camina.utils.calibration import DepthCalibrator

def main():
    print("CAMINA Automatic Calibration")
    print("=" * 40)
    
    calibrator = DepthCalibrator()
    
    # Initialize camera
    camera_source = 0  # Use default camera
    cap = cv2.VideoCapture(camera_source)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        return
    
    print("Camera opened successfully")
    print("Press SPACE to capture image for calibration, ESC to exit")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        # Display frame
        cv2.imshow("Calibration - Press SPACE to calibrate", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        elif key == 32:  # SPACE
            print("Capturing frame for calibration...")
            success = calibrator.run_calibration(frame)
            if success:
                print("Calibration successful! You can now run the main application.")
                break
            else:
                print("Calibration failed. Please try again.")
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
'''
    
    script_path = Path("/Users/tamagusko/repos/camina/scripts/calibrate_camera.py")
    script_path.parent.mkdir(exist_ok=True)
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make script executable
    os.chmod(script_path, 0o755)
    
    print(f"Calibration script created: {script_path}")