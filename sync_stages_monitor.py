import re
import subprocess
import time
from influxdb_client import InfluxDBClient
from datetime import datetime, timedelta, timezone
from influxdb_client.client.write_api import WriteOptions
from tzlocal import get_localzone
from zoneinfo import ZoneInfo
from requests.exceptions import RequestException
import config

INFLUXDB_HOST = config.INFLUXDB_HOST
INFLUXDB_PORT = config.INFLUXDB_PORT
INFLUXDB_URL = config.INFLUXDB_URL
INFLUXDB_DATABASE = config.INFLUXDB_DATABASE
INFLUXDB_USER = config.INFLUXDB_USER
INFLUXDB_PASSWORD = config.INFLUXDB_PASSWORD
RETENTION_POLICY = config.RETENTION_POLICY
DEFAULT_DELAY_BOTH_ACTIVE = config.DEFAULT_DELAY_BOTH_ACTIVE
DEFAULT_INFLUXDB_FLUSH_INTERVAL = config.DEFAULT_INFLUXDB_FLUSH_INTERVAL
DEFAULT_INFLUXDB_BATCH_SIZE = config.DEFAULT_INFLUXDB_BATCH_SIZE
MAX_QUEUE_LEN = config.MAX_QUEUE_LEN
SYNC_STAGES = config.SYNC_STAGES
DELAY_BETWEEN_STATE_SAVES = config.DELAY_BETWEEN_STATE_SAVES
TIMESTAMP_PATTERN = re.compile(r"(\d{2}-\d{2}\|\d{2}:\d{2}:\d{2})")

def connect_to_influx():
    try:
        client = InfluxDBClient(url=INFLUXDB_URL, token=f'{INFLUXDB_USER}:{INFLUXDB_PASSWORD}', org='-')
        bucket = f'{INFLUXDB_DATABASE}/{RETENTION_POLICY}'

        if not client.ping():
            print(f"InfluxDB: could not connect to remote host: {INFLUXDB_URL} "
                    f"with provided credentials, user: {INFLUXDB_USER}, pass: {INFLUXDB_PASSWORD}")
            exit
        try:
            client.query_api().query(f'from(bucket:"{bucket}") |> range(start: -1ms)')
        except:
            print(f"InfluxDB: Database '{INFLUXDB_DATABASE}' not present or accessible.\n")
            client.close()

        wo = WriteOptions(batch_size=DEFAULT_INFLUXDB_BATCH_SIZE, flush_interval=DEFAULT_INFLUXDB_FLUSH_INTERVAL)
        write_api = client.write_api(write_options=wo)
        print('Connected to InfluxDB')
        return client, write_api
    except Exception as e:
        print('Failed to connect to InfluxDB: {e}')
        return None, None

offset_us = 1
def get_unique_timestamp(base_time):
    global offset_us
    unique_timestamp = base_time + timedelta(microseconds=offset_us)
    offset_us += 1
    if offset_us > 1000:
          offset_us = 1
    return unique_timestamp

def safe_write_to_influx(data, max_retries=9):
    global client, write_api

    for attempt in range(max_retries):
        try:
            if not client or not write_api:
                print("Lost connection with InfluxDB, trying to reconnect...")
                client, write_api = connect_to_influx()
                if not client:
                    raise ConnectionError("Unable to restore connection to InfluxDB")

            write_api.write(bucket=f'{INFLUXDB_DATABASE}/{RETENTION_POLICY}', record=data)
            return

        except (RequestException, ConnectionError) as e:
            print(f"Attempt No. {attempt+1}/{max_retries}: Failed saving to InfluxDB - {e}")
            time.sleep(2 ** attempt)

        except Exception as e:
            print(f"Unexpected error {e}")
            break

    print(f"All {max_retries} attempts failed. Data not saved to InfluxDB.")

def timestamp_from_log(log):
    match = TIMESTAMP_PATTERN.search(log)
    if not match:
        return None
    date_part, time_part = match.group(1).strip("[]").split("|")
    current_year = datetime.now().year
    full_datetime_str = f"{current_year}-{date_part} {time_part}"
    timestamp = datetime.strptime(full_datetime_str, "%Y-%m-%d %H:%M:%S")
    local_tz = get_localzone()
    local_timestamp = timestamp.replace(tzinfo=local_tz)
    utc_timestamp = local_timestamp.astimezone(ZoneInfo("UTC"))
    return utc_timestamp

def is_pattern_in_logs(logs, key):
        for log in logs:
                if re.search(key, log):
                        return True
        return False

def are_other_patterns_in_logs(logs, key):
        for pattern, stage in SYNC_STAGES.items():
                if key == pattern:
                        for p in stage[2:]:
                            for log in logs:
                                if re.search(p, log):
                                    return True
        return False

def search_all_patterns_in_logs(logs):
        lines = []
        lines.append(logs)
        patterns_found = []
        for line in lines:
                for pattern, stage in SYNC_STAGES.items():
                        if re.search(pattern, line):
                                patterns_found.append(pattern)
                        else:
                            for p in stage[2:]:
                                    if re.search(p, line):
                                        patterns_found.append(p)
        return patterns_found

def add_log(queue, new_log, timestamp):
        if len(queue) >= MAX_QUEUE_LEN:
                popped_log = queue.pop(0)
                popped_log_patterns = search_all_patterns_in_logs(popped_log)
        else:
                popped_log_patterns = []
        new_log_patterns = search_all_patterns_in_logs(new_log)

        if (len(popped_log_patterns) > 0 and len(new_log_patterns) > 0):
                if(new_log_patterns[0] == popped_log_patterns[0]):
                        queue.append(new_log)
                        return # new log has the same pattern as removed one
        if (len(new_log_patterns) == 0 and len(popped_log_patterns) == 0):
                queue.append(new_log)
                return # no pattern found in both

        if len(popped_log_patterns) > 0:
                if not is_pattern_in_logs(queue, popped_log_patterns[0]):
                        if not are_other_patterns_in_logs(queue, popped_log_patterns[0]):
                            for pattern, stage in SYNC_STAGES.items():
                                    stage_finished = False
                                    if re.search(pattern, popped_log_patterns[0]):
                                            stage_finished = True
                                    else:
                                        for p in stage[2:]:
                                                if re.search(p, popped_log_patterns[0]):
                                                        stage_finished = True
                                    if stage_finished:
                                            finish_timestamp = timestamp_from_log(popped_log)
                                            stage[0] = False
                                            print(f"Finished {stage[1]}")
                                            write_to_influx(stage=f'{stage[1]}', time=finish_timestamp, stage_type="finish")
                                            write_state_to_influx(timestamp)

        if len(new_log_patterns) > 0:
                if not is_pattern_in_logs(queue, new_log_patterns[0]):
                        for pattern, stage in SYNC_STAGES.items():
                                start_stage = False
                                if re.search(pattern, new_log_patterns[0]):
                                        if not stage[0]:
                                            start_stage = True
                                else:
                                     for p in stage[2:]:
                                             if re.search(p, new_log_patterns[0]):
                                                 if not stage[0]:
                                                     start_stage = True
                                if start_stage:
                                    stage[0] = True
                                    print(f"Started {stage[1]}")
                                    write_to_influx(f'{stage[1]}', time=timestamp, stage_type="start")
                                    write_state_to_influx(timestamp)
        queue.append(new_log)
        return

def write_to_influx(stage, time, stage_type):
    json_body = [
        {
            "measurement": "sync_status",
            "tags": {
                "service": "w3p_geth"
            },
            "time": get_unique_timestamp(time),
            "fields": {
                "stage": stage,
                "type": stage_type
            }
        }
    ]
    safe_write_to_influx(json_body)

def write_state_to_influx(time):
    json_body = []

    for pattern, stage in SYNC_STAGES.items():
        state_to_write =''
        if stage[0]:
              state_to_write = stage[1]
        else:
              state_to_write = f'Not {stage[1]}'
        json_body.append({
            "measurement": "sync_status",
            "tags": {
                "service": "w3p_geth"
            },
            "time": get_unique_timestamp(time),
            "fields": {
                f"state_{stage[1]}": state_to_write
            }
        })
    safe_write_to_influx(json_body)

def get_journal_logs(since_time):
    try:
        result = subprocess.run(
            ["journalctl", "-u", "w3p_geth", "--since", since_time], 
            capture_output=True, text=True, check=True
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error while fetching logs: {e}")
        return []

def monitor_logs_with_intervals(queue):
    local_tz = get_localzone()
    local_timestamp = datetime.now(local_tz)
    last_checked_time = local_timestamp
    while True:
        since_time = last_checked_time.strftime("%Y-%m-%d %H:%M:%S")
        latest_logs = get_journal_logs(since_time)

        for line in latest_logs:
            match = TIMESTAMP_PATTERN.search(line)
            if match:
                timestamp = timestamp_from_log(line)
                add_log(queue, line.strip(), timestamp)

        local_tz = get_localzone()
        local_timestamp = datetime.now(local_tz)
        last_checked_time = local_timestamp

        write_state_to_influx(last_checked_time)

        time.sleep(DELAY_BETWEEN_STATE_SAVES)

client, write_api = connect_to_influx()
queue = []
monitor_logs_with_intervals(queue)