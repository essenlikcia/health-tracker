from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

def calculate_age(birth_date_str: str) -> float | None:
    if not birth_date_str:
        return None

    try:
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        today = date.today()
        age = (today - birth_date).days / 365.25
        return round(age, 1)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating age: {e}")
        return None

def calculate_bmi(weight_kg: float, height_cm: float) -> float | None:
    if not weight_kg or not height_cm:
        return None

    try:
        height_m = height_cm / 100
        bmi = weight_kg / (height_m ** 2)
        return round(bmi, 1)
    except (TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating BMI: {e}")
        return None

def validate_water_intake(water_intake: float) -> float | None:
    if not water_intake or water_intake < 0:
        return None
    return round(water_intake, 2)

def validate_sleep_duration(sleep_hours: float) -> float | None:
    if not sleep_hours or sleep_hours < 0 or sleep_hours > 24:
        return None
    return round(sleep_hours, 1)