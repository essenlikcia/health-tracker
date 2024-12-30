import os
import json
import psycopg2
import logging
import time
import threading
import shutil
import prometheus_client as pc

from typing import Dict
from dotenv import load_dotenv
from datetime import datetime, date

DEFAULT_PORT = 9100
DEFAULT_UPDATE_INTERVAL = 7 * 24 * 60 * 60
DEFAULT_DB_NAME = 'healthcheck'
DEFAULT_DB_USER = 'healthdbuser'
DEFAULT_DB_PORT = '5432'
DEFAULT_DB_HOST = 'localhost'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthTracker:
    def __init__(self):
        load_dotenv()

        self.metrics_file = os.getenv('METRICS_FILE_PATH', '/app/config/health_metrics.json')
        self.update_interval = int(os.getenv('UPDATE_INTERVAL', DEFAULT_UPDATE_INTERVAL))

        self.conn_params = {
            'dbname': os.getenv('POSTGRES_DB', DEFAULT_DB_NAME),
            'user': os.getenv('POSTGRES_USER', DEFAULT_DB_USER),
            'password': os.getenv('POSTGRES_PASSWORD'),
            'host': os.getenv('POSTGRES_HOST', DEFAULT_DB_HOST),
            'port': os.getenv('POSTGRES_PORT', DEFAULT_DB_PORT)
        }

        if not self.conn_params['password']:
            raise ValueError("Database password is required")

        self.metrics: Dict[str, pc.Gauge] = {
            'body_weight': pc.Gauge('body_weight', 'Body Weight in Kilograms'),
            'body_height': pc.Gauge('body_height', 'Body Height in Centimeters'),
            'age': pc.Gauge('age', 'Precise Age'),
            'bmi': pc.Gauge('bmi', 'Body Mass Index')
        }

    def calculate_age(self, birth_date_str):
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

    def calculate_bmi(self, weight_kg, height_cm):
        if not weight_kg or not height_cm:
            return None

        try:
            height_m = height_cm / 100

            bmi = weight_kg / (height_m ** 2)

            return round(bmi, 1)
        except (TypeError, ZeroDivisionError) as e:
            logger.error(f"Error calculating BMI: {e}")
            return None

    def read_metrics(self):
        try:
            temp_file = self.metrics_file + '.tmp'
            shutil.copy2(self.metrics_file, temp_file)

            with open(temp_file, 'r') as f:
                raw_metrics = json.load(f)

            os.remove(temp_file)

            metrics = {}

            metrics['body_weight'] = raw_metrics.get('body_weight')
            metrics['body_height'] = raw_metrics.get('body_height')

            if 'birth_date' in raw_metrics:
                metrics['age'] = self.calculate_age(raw_metrics['birth_date'])

            metrics['bmi'] = self.calculate_bmi(
                raw_metrics.get('body_weight'),
                raw_metrics.get('body_height')
            )

            return metrics
        except FileNotFoundError:
            logger.warning(f"Metrics file {self.metrics_file} not found.")
            return None
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {self.metrics_file}")
            return None

    def connect_db(self):
        try:
            return psycopg2.connect(**self.conn_params)
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise

    def db_operations(self):
        try:
            conn_params = self.conn_params.copy()
            conn_params['dbname'] = 'postgres'
            with psycopg2.connect(**conn_params) as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.conn_params['dbname'],))
                    if not cur.fetchone():
                        cur.execute(f"CREATE DATABASE {self.conn_params['dbname']}")
                        logger.info(f"Database {self.conn_params['dbname']} created successfully")

            with self.connect_db() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS health_metrics (
                            id SERIAL PRIMARY KEY,
                            body_weight FLOAT,
                            body_height FLOAT,
                            age FLOAT,
                            bmi FLOAT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    logger.info("Health metrics table created/verified successfully")
        except Exception as e:
            logger.error(f"Database/table creation error: {e}")
            raise

    def record_health_metrics(self, metrics):
        try:
            self.db_operations()

            with self.connect_db() as conn:
                with conn.cursor() as cur:
                    query = """
                    INSERT INTO health_metrics (
                        body_weight,
                        body_height,
                        age,
                        bmi
                    ) VALUES (
                        %(body_weight)s,
                        %(body_height)s,
                        %(age)s,
                        %(bmi)s
                    )
                    """

                    db_metrics = {
                        'body_weight': metrics.get('body_weight'),
                        'body_height': metrics.get('body_height'),
                        'age': metrics.get('age'),
                        'bmi': metrics.get('bmi')
                    }

                    cur.execute(query, db_metrics)
                    conn.commit()
                    logger.info(f"Updated metrics: {metrics}")
                    logger.info("Health metrics recorded successfully")

                    for metric_name, value in metrics.items():
                        if value is not None and metric_name in self.metrics:
                            self.metrics[metric_name].set(value)

        except Exception as e:
            logger.error(f"Database recording error: {e}")
            raise

    def start_metrics_server(self, port: int = 9100):
        pc.start_http_server(port)
        logger.info(f"Metrics server started on port {port}")

    def periodic_update(self):
        while True:
            try:
                logger.info("Starting metrics update...")
                metrics = self.read_metrics()
                logger.info(f"Read metrics: {metrics}")

                if metrics:
                    self.record_health_metrics(metrics)
                    logger.info("Prometheus metrics updated successfully")

                logger.info(f"Waiting {self.update_interval} seconds until next update...")
                time.sleep(self.update_interval)

            except Exception as e:
                logger.error(f"Error in periodic update: {e}")
                time.sleep(self.update_interval)

if __name__ == '__main__':
    try:
        tracker = HealthTracker()
        tracker.db_operations()
        logger.info("Database and table initialization completed")

        tracker.start_metrics_server(DEFAULT_PORT)

        updater_thread = threading.Thread(target=tracker.periodic_update, daemon=True)
        updater_thread.start()

        # Keep the main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Gracefully shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        logger.info("Shutdown complete")