import pytest
import csv

from project import strtobool, write_line, write_row

TIMESTAMP = "2026-07-26T20:42:13"

TIMESTAMP_INTERVAL = "2026-07-26T20:42:13/2026-07-26T21:42:13"

TELEMETRY_PAYLOAD = {
    "tag": "8eef5c6a",
    "lpp": [
        {"channel": 1, "type": "voltage", "value": 3.85},
        {"channel": 1, "type": "illuminance", "value": 0.0},
        {"channel": 1, "type": "temperature", "value": 23.7},
    ],
    "pubkey_prefix": "ee62a6472807",
}

STATUS_PAYLOAD = {
    "pubkey_pre": "ee62a6472807",
    "bat": 4200,
    "tx_queue_len": 0,
    "noise_floor": -120,
    "last_rssi": -85,
    "nb_recv": 1234,
    "nb_sent": 567,
    "airtime": 12345,
    "uptime": 86400,
    "sent_flood": 234,
    "sent_direct": 123,
    "recv_flood": 456,
    "recv_direct": 789,
    "full_evts": 12,
    "last_snr": 5.25,
    "direct_dups": 5,
    "flood_dups": 8,
    "rx_airtime": 67890,
}

MMA_PAYLOAD = {
    "tag": "a1b2c3d4",
    "mma_data": [
        {"channel": 1, "type": "temperature", "min": 15.5, "max": 28.3, "avg": 22.1},
        {"channel": 2, "type": "humidity", "min": 45.0, "max": 78.2, "avg": 62.4},
    ],
    "pubkey_prefix": "ee62a6472807",
}


def test_strtobool():

    # Basic tests that are expected to pass
    assert strtobool("y") == True
    assert strtobool("n") == False
    assert strtobool("yes") == True
    assert strtobool("no") == False
    assert strtobool("", default_val=True) == True
    assert strtobool("", default_val=False) == False

    # Tests that test invalid input raises exception

    with pytest.raises(ValueError) as excinfo:
        strtobool("yes.")
    assert str(excinfo.value) == "Invalid truth value 'yes.'"

    with pytest.raises(ValueError) as excinfo:
        strtobool("nope")
    assert str(excinfo.value) == "Invalid truth value 'nope'"

    with pytest.raises(ValueError) as excinfo:
        strtobool("", default_val=None)
    assert str(excinfo.value) == "Invalid truth value ''"

    with pytest.raises(ValueError) as excinfo:
        strtobool("True")
    assert str(excinfo.value) == "Invalid truth value 'true'"

    with pytest.raises(ValueError) as excinfo:
        strtobool("ye")
    assert str(excinfo.value) == "Invalid truth value 'ye'"

    # Capitalization
    assert strtobool("YES") == True
    assert strtobool("yES") == True
    assert strtobool("No") == False
    assert strtobool("N") == False

    # Whitespace
    assert strtobool("yes ") == True
    assert strtobool("  n") == False
    assert strtobool(" ", default_val=True) == True


def test_write_line(tmp_path):

    # Telemetry log test
    telemetry_log_file = tmp_path / "mc_telemetry_test.log"

    write_line(TELEMETRY_PAYLOAD, TIMESTAMP, telemetry_log_file)

    expected_line = {"timestamp": TIMESTAMP} | TELEMETRY_PAYLOAD

    content = telemetry_log_file.read_text()

    assert str(expected_line) in content

    # Status log test
    status_log_file = tmp_path / "mc_status_test.log"

    write_line(STATUS_PAYLOAD, TIMESTAMP, status_log_file)

    expected_line = {"timestamp": TIMESTAMP} | STATUS_PAYLOAD

    content = status_log_file.read_text()

    assert str(expected_line) in content

    # Min/Max/Avg log test
    mma_log_file = tmp_path / "mc_mma_test.log"

    write_line(MMA_PAYLOAD, TIMESTAMP, mma_log_file)

    expected_line = {"timestamp": TIMESTAMP} | MMA_PAYLOAD

    content = mma_log_file.read_text()

    assert str(expected_line) in content


def test_write_row(tmp_path):

    # Telemetry csv test
    telemetry_csv_file = tmp_path / "mc_telemetry_test.csv"

    sensors = [sensor["type"] for sensor in TELEMETRY_PAYLOAD["lpp"]]
    values = [value["value"] for value in TELEMETRY_PAYLOAD["lpp"]]

    sensor_values = dict(zip(sensors, values))

    with open(telemetry_csv_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["timestamp", *sensors])
        writer.writeheader()

    write_row(sensor_values, TIMESTAMP, telemetry_csv_file)

    expected_row = f"{TIMESTAMP},3.85,0.0,23.7"

    content = telemetry_csv_file.read_text()

    assert str(expected_row) in content

    # Status csv test
    status_csv_file = tmp_path / "mc_status_test.csv"

    with open(status_csv_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["timestamp", *STATUS_PAYLOAD])
        writer.writeheader()

    write_row(STATUS_PAYLOAD, TIMESTAMP, status_csv_file)

    expected_row = f"{TIMESTAMP},ee62a6472807,4200,0,-120,-85,1234,567,12345,86400,234,123,456,789,12,5.25,5,8,67890"

    content = status_csv_file.read_text()

    assert str(expected_row) in content

    # Min/Max/Avg csv test
    mma_csv_file = tmp_path / "mc_mma_test.csv"

    sensors = [sensor["type"] for sensor in MMA_PAYLOAD["mma_data"]]

    sensor_header = []
    for sensor in sensors:
        sensor_header.append(f"{sensor}_min")
        sensor_header.append(f"{sensor}_max")
        sensor_header.append(f"{sensor}_avg")

    with open(mma_csv_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["timestamp", *sensor_header])
        writer.writeheader()

    mma_data = MMA_PAYLOAD["mma_data"]

    mma_sensor_values = {}
    for mma_sensor in mma_data:
        sensor_type = mma_sensor["type"]
        mma_sensor_values.update({f"{sensor_type}_min": mma_sensor["min"]})
        mma_sensor_values.update({f"{sensor_type}_max": mma_sensor["max"]})
        mma_sensor_values.update({f"{sensor_type}_avg": mma_sensor["avg"]})

    write_row(mma_sensor_values, TIMESTAMP_INTERVAL, mma_csv_file)

    expected_row = (
        "2026-07-26T20:42:13/2026-07-26T21:42:13,15.5,28.3,22.1,45.0,78.2,62.4"
    )

    content = mma_csv_file.read_text()

    assert str(expected_row) in content
