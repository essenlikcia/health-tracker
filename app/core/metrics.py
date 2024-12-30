import prometheus_client as pc
from typing import Dict, Any
from .utils import calculate_age, calculate_bmi, validate_water_intake, validate_sleep_duration

class HealthMetrics:
    def __init__(self):
        self.metrics: Dict[str, pc.Gauge] = {
            'body_weight': pc.Gauge('body_weight', 'Body Weight in Kilograms'),
            'body_height': pc.Gauge('body_height', 'Body Height in Centimeters'),
            'age': pc.Gauge('age', 'Precise Age'),
            'bmi': pc.Gauge('bmi', 'Body Mass Index'),
            'water_intake': pc.Gauge('water_intake', 'Daily Water Intake in Liters'),
            'sleep_duration': pc.Gauge('sleep_duration', 'Daily Sleep Duration in Hours')
        }

    def process_raw_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, float]:
        processed = {}

        processed['body_weight'] = raw_metrics.get('body_weight')
        processed['body_height'] = raw_metrics.get('body_height')
        processed['water_intake'] = validate_water_intake(raw_metrics.get('water_intake'))
        processed['sleep_duration'] = validate_sleep_duration(raw_metrics.get('sleep_duration'))

        if 'birth_date' in raw_metrics:
            processed['age'] = calculate_age(raw_metrics['birth_date'])

        processed['bmi'] = calculate_bmi(
            raw_metrics.get('body_weight'),
            raw_metrics.get('body_height')
        )

        return processed

    def update_prometheus_metrics(self, metrics: Dict[str, float]) -> None:
        for metric_name, value in metrics.items():
            if value is not None and metric_name in self.metrics:
                self.metrics[metric_name].set(value)