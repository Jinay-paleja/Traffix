"""
Smart Traffic Signal Optimizer
Optimizes traffic signal timing based on vehicle count and traffic patterns.
"""

from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple
import math


class SignalOptimizer:
    """
    Optimizes traffic signal timing using vehicle count and AI algorithms.
    """
    
    def __init__(self, cycle_time=120):
        """
        Initialize signal optimizer.
        
        Args:
            cycle_time: Total time for one signal cycle (seconds)
        """
        self.cycle_time = cycle_time
        self.min_green_time = 15  # Minimum green time per direction
        self.max_green_time = 90  # Maximum green time per direction
        self.yellow_time = 5      # Yellow light duration
        self.all_red_time = 2     # All-red time for safety
    
    def optimize_signal(self, intersection_data):
        """
        Calculate optimal signal timing for an intersection.
        
        Args:
            intersection_data: dict with traffic info per direction
                {
                    'North': {'vehicles': 10, 'priority': 2},
                    'South': {'vehicles': 5, 'priority': 1},
                    'East': {'vehicles': 20, 'priority': 3},
                    'West': {'vehicles': 3, 'priority': 1}
                }
        
        Returns:
            dict with optimized timing
        """
        if not intersection_data or len(intersection_data) == 0:
            return self._get_default_timing()
        
        # Calculate priority scores
        scores = {}
        for direction, data in intersection_data.items():
            vehicle_count = data.get('vehicles', 0)
            priority = data.get('priority', 1)
            
            # Score based on vehicles and priority
            score = (vehicle_count / 10.0) * (priority / 3.0)
            scores[direction] = max(score, 0.1)
        
        # Normalize scores to total available time
        total_score = sum(scores.values())
        available_time = self.cycle_time - (len(scores) * (self.yellow_time + self.all_red_time))
        
        green_times = {}
        for direction, score in scores.items():
            # Allocate proportional time
            green_time = (score / total_score) * available_time
            
            # Clamp to min/max bounds
            green_time = max(self.min_green_time, min(self.max_green_time, green_time))
            green_times[direction] = int(green_time)
        
        return {
            'cycle_time': self.cycle_time,
            'green_times': green_times,
            'yellow_time': self.yellow_time,
            'all_red_time': self.all_red_time,
            'total_time': sum(green_times.values()) + (len(green_times) * (self.yellow_time + self.all_red_time)),
            'timestamp': datetime.now().isoformat(),
            'efficiency': self._calculate_efficiency(intersection_data, green_times)
        }
    
    def get_signal_schedule(self, intersection_data):
        """
        Generate detailed signal schedule with timing for display.
        
        Args:
            intersection_data: Traffic data per direction
        
        Returns:
            dict with full schedule
        """
        optimization = self.optimize_signal(intersection_data)
        schedule = {}
        
        current_time = 0
        directions = list(optimization['green_times'].keys())
        
        for direction in directions:
            green = optimization['green_times'][direction]
            yellow = optimization['yellow_time']
            all_red = optimization['all_red_time']
            
            schedule[direction] = {
                'phase': f"Green {green}s + Yellow {yellow}s + AllRed {all_red}s",
                'green_duration': green,
                'yellow_duration': yellow,
                'all_red_duration': all_red,
                'total_duration': green + yellow + all_red,
                'start_time': current_time,
                'end_time': current_time + green + yellow + all_red
            }
            
            current_time += green + yellow + all_red
        
        return {
            'schedule': schedule,
            'total_cycle_time': current_time,
            'intersection': intersection_data,
            'timestamp': datetime.now().isoformat()
        }
    
    def adaptive_timing(self, vehicle_counts: Dict[str, int], historical_avg: Dict[str, float] = None):
        """
        Adaptive timing that learns from historical patterns.
        
        Args:
            vehicle_counts: Current vehicle count per direction
            historical_avg: Average vehicles per direction (optional)
        
        Returns:
            dict with adaptive timing recommendations
        """
        # If we have historical data, blend with current
        adjusted_counts = vehicle_counts.copy()
        
        if historical_avg:
            for direction in adjusted_counts:
                if direction in historical_avg:
                    # Blend 70% current, 30% historical
                    adjusted_counts[direction] = int(
                        vehicle_counts[direction] * 0.7 + historical_avg[direction] * 0.3
                    )
        
        # Convert to required format
        intersection_data = {
            direction: {'vehicles': count, 'priority': self._get_priority(count)}
            for direction, count in adjusted_counts.items()
        }
        
        return self.optimize_signal(intersection_data)
    
    def _get_priority(self, vehicle_count: int):
        """Determine priority level based on vehicle count"""
        if vehicle_count < 5:
            return 1
        elif vehicle_count < 15:
            return 2
        elif vehicle_count < 30:
            return 3
        else:
            return 4
    
    def _calculate_efficiency(self, traffic_data, green_times):
        """
        Calculate optimization efficiency score (0-100).
        Higher is better - indicates more balanced waiting times.
        """
        if not traffic_data or not green_times:
            return 50
        
        wait_scores = []
        for direction, data in traffic_data.items():
            vehicles = data.get('vehicles', 0)
            green_time = green_times.get(direction, 30)
            
            if vehicles > 0:
                # Lower ratio of vehicles to green time = better
                score = min(100, (green_time / max(vehicles, 1)) * 10)
                wait_scores.append(score)
        
        if not wait_scores:
            return 50
        
        return round(sum(wait_scores) / len(wait_scores))
    
    def compare_timing_strategies(self, intersection_data):
        """
        Compare different timing strategies.
        
        Args:
            intersection_data: Traffic data
        
        Returns:
            dict with comparison
        """
        # Strategy 1: Proportional (current method)
        proportional = self.optimize_signal(intersection_data)
        
        # Strategy 2: Equal time for all directions
        num_directions = len(intersection_data)
        equal_green_time = int((self.cycle_time - num_directions * (self.yellow_time + self.all_red_time)) / num_directions)
        equal_times = {d: equal_green_time for d in intersection_data.keys()}
        
        # Strategy 3: Priority-based (more aggressive)
        aggressive = self._aggressive_timing(intersection_data)
        
        return {
            'strategies': {
                'proportional': proportional,
                'equal_distribution': {
                    'green_times': equal_times,
                    'efficiency': self._calculate_efficiency(intersection_data, equal_times)
                },
                'aggressive_priority': aggressive
            },
            'recommendation': 'proportional',  # Default to proportional strategy
            'timestamp': datetime.now().isoformat()
        }
    
    def _aggressive_timing(self, intersection_data):
        """Apply aggressive priority-based timing"""
        scores = {}
        for direction, data in intersection_data.items():
            vehicles = data.get('vehicles', 0)
            priority = data.get('priority', 1)
            # More aggressive weighting
            score = (vehicles * priority) / 5.0
            scores[direction] = max(score, 0.1)
        
        total_score = sum(scores.values())
        available_time = self.cycle_time - (len(scores) * (self.yellow_time + self.all_red_time))
        
        green_times = {}
        for direction, score in scores.items():
            green_time = (score / total_score) * available_time
            green_time = max(self.min_green_time, min(self.max_green_time, green_time))
            green_times[direction] = int(green_time)
        
        return {
            'green_times': green_times,
            'efficiency': self._calculate_efficiency(intersection_data, green_times)
        }
    
    def get_recommendations(self, intersection_data, current_congestion_score=0):
        """
        Get optimization recommendations based on current state.
        
        Args:
            intersection_data: Traffic data
            current_congestion_score: Overall congestion level (0-100)
        
        Returns:
            dict with recommendations
        """
        optimization = self.optimize_signal(intersection_data)
        recommendations = []
        
        # Analyze each direction
        for direction, data in intersection_data.items():
            vehicles = data.get('vehicles', 0)
            green_time = optimization['green_times'][direction]
            
            if vehicles > 25:
                recommendations.append({
                    'direction': direction,
                    'message': f'High congestion ({vehicles} vehicles)',
                    'severity': 'high',
                    'action': f'Extend green time beyond {green_time}s if adjacent directions allow'
                })
            elif vehicles == 0:
                recommendations.append({
                    'direction': direction,
                    'message': 'No vehicles detected',
                    'severity': 'low',
                    'action': 'Reduce green time, skip phase if safe'
                })
        
        if current_congestion_score > 80:
            recommendations.append({
                'direction': 'All',
                'message': 'Intersection at critical capacity',
                'severity': 'critical',
                'action': 'Consider traffic diversions or incident management'
            })
        
        return {
            'optimization': optimization,
            'recommendations': recommendations,
            'congestion_level': self._classify_congestion(current_congestion_score),
            'timestamp': datetime.now().isoformat()
        }

    def build_phase_decision(self, intersection_data):
        """
        Build a controller-friendly decision from the optimized timing plan.

        Returns:
            dict with the lane that should receive green next and the lanes that
            should remain stopped for the current phase.
        """
        optimization = self.optimize_signal(intersection_data)
        green_times = optimization.get('green_times', {})
        if not green_times:
            return {
                'go_direction': None,
                'stop_directions': [],
                'reason': 'No traffic data available.',
                'green_time': 0,
                'timestamp': datetime.now().isoformat()
            }

        ranked = sorted(
            green_times.items(),
            key=lambda item: (
                item[1],
                intersection_data.get(item[0], {}).get('vehicles', 0),
                intersection_data.get(item[0], {}).get('priority', 0)
            ),
            reverse=True
        )
        go_direction, green_time = ranked[0]
        stop_directions = [direction for direction in green_times if direction != go_direction]
        vehicle_count = intersection_data.get(go_direction, {}).get('vehicles', 0)

        return {
            'go_direction': go_direction,
            'green_time': green_time,
            'stop_directions': stop_directions,
            'reason': (
                f"{go_direction} has the strongest demand with {vehicle_count} detected vehicles "
                f"and receives the highest optimized green time."
            ),
            'ranked_directions': [
                {
                    'direction': direction,
                    'green_time': timing,
                    'vehicles': intersection_data.get(direction, {}).get('vehicles', 0),
                    'priority': intersection_data.get(direction, {}).get('priority', 0),
                }
                for direction, timing in ranked
            ],
            'timestamp': datetime.now().isoformat()
        }
    
    def _classify_congestion(self, score):
        """Classify congestion level"""
        if score < 20:
            return 'Free Flow'
        elif score < 40:
            return 'Light'
        elif score < 60:
            return 'Moderate'
        elif score < 80:
            return 'Heavy'
        else:
            return 'Critical'
    
    def _get_default_timing(self):
        """Return default timing when no data available"""
        return {
            'cycle_time': self.cycle_time,
            'green_times': {
                'North': 30,
                'South': 30,
                'East': 30,
                'West': 30
            },
            'yellow_time': self.yellow_time,
            'all_red_time': self.all_red_time,
            'note': 'Default timing - no traffic data available'
        }


def get_signal_optimizer():
    """Factory function to get optimizer instance"""
    return SignalOptimizer()
