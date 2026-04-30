"""
Traffic Detection Module using YOLO
Detects vehicles in traffic footage and analyzes traffic density.
"""

import threading
from datetime import datetime

import cv2
import numpy as np
from ultralytics import YOLO


class TrafficDetector:
    """
    Detects vehicles using YOLO and calculates traffic density metrics.
    """
    
    # Vehicle classes that we care about
    VEHICLE_CLASSES = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 
                      4: 'airplane', 5: 'bus', 6: 'train', 7: 'truck'}
    
    TRAFFIC_VEHICLES = {2, 3, 5, 6, 7}  # car, motorcycle, bus, train, truck
    
    def __init__(self, model_name='yolov8n.pt'):
        """Initialize YOLO model"""
        self.model = YOLO(model_name)
        self._model_lock = threading.Lock()
        self.vehicle_count = 0
        self.density_level = 'Low'
        self.confidence_threshold = 0.5

    def _prepare_image(self, image, max_dimension=960):
        """Resize large frames to keep inference latency predictable."""
        if image is None:
            return None

        height, width = image.shape[:2]
        longest_side = max(height, width)
        if longest_side <= max_dimension:
            return image

        scale = max_dimension / float(longest_side)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)

    def _run_inference(self, image, image_size=640):
        """Serialize access to the shared YOLO model for repeated live requests."""
        with self._model_lock:
            return self.model.predict(
                source=image,
                conf=self.confidence_threshold,
                imgsz=image_size,
                verbose=False,
            )

    def detect_vehicles(self, image_path, image_size=640, max_dimension=960):
        """
        Detect vehicles in an image.
        
        Args:
            image_path: Path to image file or numpy array
            
        Returns:
            dict with detection results
        """
        # Read image if path is provided
        if isinstance(image_path, str):
            image = cv2.imread(image_path)
        else:
            image = image_path
        
        if image is None:
            return {'error': 'Could not load image'}

        prepared_image = self._prepare_image(image, max_dimension=max_dimension)
        results = self._run_inference(prepared_image, image_size=image_size)
        
        # Count vehicles
        vehicle_count = 0
        detections = []
        
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    
                    # Only count traffic vehicles
                    if class_id in self.TRAFFIC_VEHICLES:
                        vehicle_count += 1
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        detections.append({
                            'class': self.VEHICLE_CLASSES.get(class_id, 'unknown'),
                            'confidence': confidence,
                            'bbox': [x1, y1, x2, y2],
                            'center': [(x1 + x2) // 2, (y1 + y2) // 2]
                        })
        
        # Determine traffic density
        self.vehicle_count = vehicle_count
        self.density_level = self._calculate_density_level(vehicle_count)
        
        return {
            'vehicle_count': vehicle_count,
            'density_level': self.density_level,
            'detections': detections,
            'timestamp': datetime.now().isoformat()
        }
    
    def detect_vehicles_in_video(self, video_path, max_frames=100, frame_stride=3, image_size=640, max_dimension=960):
        """
        Detect vehicles across video frames.
        
        Args:
            video_path: Path to video file
            max_frames: Maximum frames to process
            
        Returns:
            dict with aggregated statistics
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {'error': 'Could not open video'}
        
        frame_count = 0
        total_vehicles = 0
        max_vehicles = 0
        vehicle_history = []
        sampled_frames = 0
        frame_index = 0
        
        while sampled_frames < max_frames:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_stride > 1 and (frame_index % frame_stride) != 0:
                frame_index += 1
                continue

            prepared_frame = self._prepare_image(frame, max_dimension=max_dimension)
            results = self._run_inference(prepared_frame, image_size=image_size)
            
            vehicles_in_frame = 0
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        if class_id in self.TRAFFIC_VEHICLES:
                            vehicles_in_frame += 1
            
            vehicle_history.append(vehicles_in_frame)
            total_vehicles += vehicles_in_frame
            max_vehicles = max(max_vehicles, vehicles_in_frame)
            sampled_frames += 1
            frame_index += 1
        
        cap.release()
        
        avg_vehicles = total_vehicles / max(sampled_frames, 1)
        if vehicle_history:
            sorted_history = sorted(vehicle_history)
            percentile_index = min(len(sorted_history) - 1, max(0, int(round((len(sorted_history) - 1) * 0.75))))
            percentile_75 = sorted_history[percentile_index]
            peak_weighted = int(round((max_vehicles * 0.65) + (avg_vehicles * 0.35)))
            representative_count = max(int(round(avg_vehicles)), percentile_75, peak_weighted)
        else:
            percentile_75 = 0
            peak_weighted = 0
            representative_count = 0
        
        return {
            'frames_processed': sampled_frames,
            'frames_seen': frame_index,
            'total_vehicles_detected': total_vehicles,
            'avg_vehicles_per_frame': round(avg_vehicles, 2),
            'p75_vehicles_per_frame': int(percentile_75),
            'max_vehicles_in_frame': max_vehicles,
            'peak_weighted_vehicle_count': int(peak_weighted),
            'representative_vehicle_count': int(representative_count),
            'vehicle_history': vehicle_history,
            'density_level': self._calculate_density_level(int(representative_count)),
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_density_level(self, vehicle_count):
        """Classify traffic density level"""
        if vehicle_count < 5:
            return 'Low'
        elif vehicle_count < 15:
            return 'Medium'
        elif vehicle_count < 30:
            return 'High'
        else:
            return 'Critical'
    
    def draw_detections(self, image_path, output_path):
        """
        Draw bounding boxes on image with detections.
        
        Args:
            image_path: Input image path
            output_path: Output image path
        """
        image = cv2.imread(image_path)
        if image is None:
            return False
        
        results = self.model(image, conf=self.confidence_threshold)
        
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    
                    if class_id in self.TRAFFIC_VEHICLES:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        label = f"{self.VEHICLE_CLASSES.get(class_id, 'vehicle')} {confidence:.2f}"
                        cv2.putText(image, label, (x1, y1 - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        cv2.imwrite(output_path, image)
        return True


def get_traffic_detector():
    """Factory function to get or create detector instance (lazy loading)"""
    global _detector
    if '_detector' not in globals():
        try:
            _detector = TrafficDetector()
        except Exception as e:
            print(f"Warning: Could not load YOLO model: {e}")
            print("The model will be downloaded when you first use traffic detection.")
            _detector = None
    return _detector
