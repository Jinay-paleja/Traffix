"""
Traffic Detection Module using YOLO
Detects vehicles in traffic footage and analyzes traffic density.
"""

import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
import json
from datetime import datetime


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
        self.vehicle_count = 0
        self.density_level = 'Low'
        self.confidence_threshold = 0.5
    
    def detect_vehicles(self, image_path):
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
        
        # Run inference
        results = self.model(image, conf=self.confidence_threshold)
        
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
    
    def detect_vehicles_in_video(self, video_path, max_frames=100):
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
        
        while frame_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            results = self.model(frame, conf=self.confidence_threshold)
            
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
            frame_count += 1
        
        cap.release()
        
        avg_vehicles = total_vehicles / max(frame_count, 1)
        
        return {
            'frames_processed': frame_count,
            'total_vehicles_detected': total_vehicles,
            'avg_vehicles_per_frame': round(avg_vehicles, 2),
            'max_vehicles_in_frame': max_vehicles,
            'vehicle_history': vehicle_history,
            'density_level': self._calculate_density_level(int(avg_vehicles)),
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
