INFLUXDB_HOST = "localhost"
INFLUXDB_PORT = 8086
INFLUXDB_URL = f'http://{INFLUXDB_HOST}:{INFLUXDB_PORT}'
INFLUXDB_DATABASE = "ethonrpi"
INFLUXDB_USER = "geth"
INFLUXDB_PASSWORD = "geth"
RETENTION_POLICY = "autogen"
DEFAULT_DELAY_BOTH_ACTIVE = 7.0
DEFAULT_INFLUXDB_FLUSH_INTERVAL = int(1000.0 * (DEFAULT_DELAY_BOTH_ACTIVE + 0.05))
DEFAULT_INFLUXDB_BATCH_SIZE = 75
LOG_FILE = "logs_rob_lh.txt"
MAX_QUEUE_LEN = 200
DELAY_BETWEEN_STATE_SAVES = 10
SYNC_STAGES = {
    "Looking for peers": [False, "looking_for_peers"],
    "Syncing: chain download in progress": [False, "downloading_chain"],
    "Syncing: state download in progress": [False, "downloading_state"],
    "Syncing: state healing in progress": [False, "healing_state"],
    "Upgrading chain index": [False, "upgrading_chain_index"],
    "Generating state snapshot": [False, "generating_state_snapshot", "Resuming state snapshot generation"],
}