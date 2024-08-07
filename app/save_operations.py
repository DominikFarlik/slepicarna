import logging
import sqlite3
import threading
import time

from .config import read_config

import requests  # type: ignore
import datetime
from requests.auth import HTTPBasicAuth  # type: ignore

config = read_config()

DB_PATH = config.get('DB', 'file_path')
lock = threading.Lock()
con = sqlite3.connect(DB_PATH, check_same_thread=False)
con.row_factory = sqlite3.Row

# api constants
username = config.get('API', 'username')
password = config.get('API', 'password')
time_zone_offset = config.getint('API', 'timezone_offset')
url = config.get('API', 'url')
resend_timer = config.getint('API', 'resend_timer')
fail_limit = config.getint('API', 'fail_limit')


def save_record(chip_id: int, reader_id: int, event_time: str, event_type: int) -> None:
    """Saves record to database, then try to send to api and check if it was successful"""
    record_id = write_event_to_db(chip_id, reader_id, event_time, event_type)
    in_api = create_api_record(record_id, event_time, chip_id, event_type, reader_id)
    if in_api:
        with con:
            cursor = con.cursor()
            cursor.execute("UPDATE events SET in_api = 1 WHERE id = ?", (record_id,))
            con.commit()


def compare_api_db_id() -> None:
    """Debug function to check if last id in database is equal to last id in api"""
    with con:
        cursor = con.cursor()
        cursor.execute("SELECT MAX(id) FROM events")
        last_db_id = cursor.fetchone()
        last_db_id = last_db_id[0]
        starting_api_id = get_starting_id_from_api()

    if starting_api_id == -1:
        logging.warning("Could not check if ids are synchronized!")
    elif starting_api_id == last_db_id:
        logging.info("Last api and db ids are matching.")
    elif last_db_id is None or last_db_id < starting_api_id:
        logging.warning("Last api id greater than last db id or db is empty! Synchronizing...")
        sync_db_with_api(starting_api_id)
        logging.info("Synchronized")
    elif starting_api_id < last_db_id:
        pass  # it could only be caused by failed previous request


def resend_failed_records(stop_event) -> None:
    """Repeatedly sends failed records to api till its successful or FAIL_LIMIT"""
    while not stop_event.is_set():
        records_to_resend = fetch_failed_api_records()
        for record in records_to_resend:
            with lock:
                with con:
                    cursor = con.cursor()
                    cursor.execute("UPDATE events SET api_attempts = api_attempts + 1 WHERE id = ?", (record['id'],))
                    con.commit()

            in_api = create_api_record(record['id'], record['event_time'], record['chip_id'], record['event_type'], record['reader_id'])
            if in_api:
                make_record_sent(record['id'])
            else:
                with con:
                    cursor = con.cursor()
                    cursor.execute("SELECT api_attempts FROM events WHERE id = ?", (record['id'],))
                    api_attempts = cursor.fetchone()[0]

                if api_attempts >= fail_limit:
                    send_to_error_endpoint(record['id'], record['event_time'], record['chip_id'], record['event_type'], record['reader_id'])
                    make_record_sent(record['id'])

        time.sleep(resend_timer)


# db operations
def write_event_to_db(chip_id: int, reader_id: int, event_time: str, event_type: int) -> int:
    """Writes received data to the database."""
    with lock:
        with con:
            cursor = con.cursor()
            cursor.execute(
                "INSERT INTO events (chip_id, reader_id, event_type, event_time) VALUES (?, ?, ?, ?)",
                (chip_id, reader_id, event_type, event_time),
            )
            con.commit()
            return cursor.lastrowid


def get_number_of_unsent_records() -> int:
    """Returns the number of unsent records in the database."""
    database_initialization()
    with con:
        cursor = con.cursor()
        cursor.execute("SELECT count(*) FROM events WHERE in_api = 0")
        data = cursor.fetchone()
        number_of_unsent_records = data[0]
    return number_of_unsent_records


def fetch_failed_api_records() -> list:
    """Returns the list of 5 failed records"""
    with con:
        cursor = con.cursor()
        cursor.execute("SELECT * FROM events WHERE in_api = 0 LIMIT 5")
        records = cursor.fetchall()
    return records


def database_initialization() -> None:
    with con:
        cursor = con.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chip_id INTEGER NOT NULL,
                event_time TIMESTAMP,
                reader_id TEXT NOT NULL,
                event_type INTEGER NOT NULL,
                in_api INTEGER NOT NULL DEFAULT 0,
                api_attempts INTEGER DEFAULT 1)
                """)


def sync_db_with_api(starting_id: int) -> None:
    with lock:
        with con:
            cursor = con.cursor()
            cursor.execute(
                "INSERT INTO events (id, chip_id, reader_id, event_type, in_api) VALUES (?, ?, ?, ?, ?)",
                (starting_id, 0, "None", 0, 1),
            )
            con.commit()


# api operations
def create_api_record(record_id: int, event_time: str, rfid: int, record_type: int, reader_id: int) -> bool:
    """Sending new time attendance record to api"""
    params = {
        "TerminalTime": event_time,
        "TerminalTimeZone": time_zone_offset,
        "IsImmediate": False,
        "TimeAttendanceRecords": [
            {
                "RecordId": record_id,
                "RecordType": record_type,
                "RFID": rfid,
                "Punched": datetime.datetime.now().isoformat(),
                "HWSource": reader_id
            }
        ]
    }

    try:
        response = requests.post(f'{url}/api/TimeAttendance',
                                 json=params,
                                 auth=HTTPBasicAuth(username, password))
        response.raise_for_status()  # Ensure we raise an error for bad responses
        logging.info(f"Successfully created API record with ID: {record_id}")
        return True

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to create API record: {e}")
        if "Terminal_TimeOfTheTerminalIsNotSetCorrectly" in str(e) or "Records_RecordAlreadyExists" in str(e):
            logging.info(f"Handled error: {e}. Record ID: {record_id} considered delivered.")
            return True
        else:
            return False


def get_starting_id_from_api() -> int:
    """Get last id from api"""
    try:
        response = requests.get(f'{url}/api/TimeAttendanceRecordId',
                                auth=HTTPBasicAuth(username, password))
        response.raise_for_status()  # Ensure we raise an error for bad responses
        data = response.json()
        logging.info(f"Retrieved last record ID from api: {data['LastTimeAttendanceRecordId']}")
        return data['LastTimeAttendanceRecordId']
    except requests.RequestException as e:
        logging.error(f"Failed to get last ID from API: {e}")
        return -1


def make_record_sent(record_id: int) -> None:
    """Update in_api var in db to 1(successful)"""
    with lock:
        with con:
            cursor = con.cursor()
            cursor.execute("UPDATE events SET in_api = 1 WHERE id = ?", (record_id,))
            con.commit()


def send_to_error_endpoint(record_id: int, event_time: str, rfid: int, record_type: int, reader_id: str) -> None:
    """After many failed sent records, send them to error endpoint."""
    params = {
        "TerminalTime": event_time,
        "TerminalTimeZone": time_zone_offset,
        "IsImmediate": False,
        "TimeAttendanceRecords": [
            {
                "RecordId": record_id,
                "RecordType": record_type,
                "RFID": rfid,
                "Punched": datetime.datetime.now().isoformat(),
                "HWSource": reader_id[-1]
            }
        ]
    }

    try:
        response = requests.post(f'{url}/api/ErrorReporting',
                                 json=params,
                                 auth=HTTPBasicAuth(username, password))

        response.raise_for_status()

    except requests.RequestException as e:
        logging.error(f"Failed to sent record to error endpoint: {e}")
