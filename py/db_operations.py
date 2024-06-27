import logging
import sqlite3
import threading
from config import read_config

config = read_config()

DB_PATH = config.get('DB', 'file_path')


def write_event_to_db(
        chip_id: int, reader_id: str, event_time: str, event_type: str
) -> None:
    """Writes received data to the database."""
    lock = threading.Lock()
    with lock:
        try:
            with sqlite3.connect(DB_PATH) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO events (chip_id, reader_id, event_type, event_time) VALUES (?, ?, ?, ?)",
                    (chip_id, reader_id, event_type, event_time),
                )
                connection.commit()
                #  logging.info(f"Event written to DB: {chip_id}, {reader_id}, {event_type}, {event_time}")
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")