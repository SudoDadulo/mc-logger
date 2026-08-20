# mc-logger

`mc_logger` is a Python CLI tool made to periodically request environmental and status data from a remote MeshCore node over LoRa. Received data can be displayed directly in the terminal or stored for long-term monitoring as structured NDJSON logs or CSV files. A locally connected serial device with the MeshCore Companion USB firmware is required to send the requests over LoRa.

### Key Features

* **Active polling**: Sends requests to specific remote nodes at user defined intervals rather than passively listening to broadcasts.

* **Configuration file support**: Export CLI arguments to a .json config file with `--save-config` and easily load the saved settings with `--config`.

* **Multi-node support**: Free used serial port in-between requests cycles with `--disconnect-while-idle` to allow multiple instances of mc-logger to request from multiple nodes.

* **Drift-free timing**: Ensures that request intervals stay strictly on schedule without drift. Supports `--start-at`, allowing you to align request cycles with clean time boundaries (e.g. 2026-01-01T00:00:00)

## Disclaimer !

LoRa uses a shared, low-speed radio channel with strict legal duty-cycle limits. Rapid polling wastes precious airtime, causes packet collisions, and overloads local repeaters. Please use reasonable request intervals to keep the mesh reliable for everyone.

## Installation

Clone the repository and `cd` to the mc-logger/ directory.

```bash
git clone https://github.com/SudoDadulo/mc-logger.git
cd mc-logger
```

Create a virtual environment and install the required dependencies:

**Linux / macOS**
```Bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows Command Prompt**
```DOS
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

## Usage & Command-Line Options

Connect a MeshCore Companion USB device, identify the COM/TTY serial port the device is connected to, then execute the program with `python src/mc_logger.py <port> -n/--node <NAME | KEY> [options]`.

### Command-Line Arguments (--help)
```
usage: mc_logger.py [-h] [-n NAME | KEY] [-pw PASSWORD] [-b BAUD] 
                    [-l {telemetry,status,mma} [{telemetry,status,mma} ...]] 
                    [--log {telemetry,status,mma} [{telemetry,status,mma} ...]]
                    [--csv {telemetry,status,mma} [{telemetry,status,mma} ...]] 
                    [-f SECONDS] [-t SECONDS] [--start-at DATETIME] 
                    [-o DIR] [--log-dir DIR] [--csv-dir DIR] 
                    [--disconnect-while-idle] 
                    [--config PATH] [--save-config PATH] 
                    [-v | -q] [-d]
                    [port]

Python CLI tool for automated remote data collection over the MeshCore LoRa network.

positional arguments:
  port                  Serial port (e.g. 'COM4', '/dev/ttyUSB0')

options:
  -h, --help            show this help message and exit
  -n, --node NAME | KEY
                        Target node name or public key prefix
  -pw, --password PASSWORD
                        Password for target node login
  -b, --baud BAUD       Serial baudrate (default: 115200)
  -l, --listen {telemetry,status,mma} [{telemetry,status,mma} ...]
                        Print chosen data to terminal
  --log {telemetry,status,mma} [{telemetry,status,mma} ...]
                        Write chosen metrics to .log file(s)
  --csv {telemetry,status,mma} [{telemetry,status,mma} ...]
                        Write chosen metrics to .csv file(s)
  -f, --frequency SECONDS
                        Request frequency in seconds (default: 1800)
  -t, --timeout SECONDS
                        Set timeout in seconds (default: 10)
  --start-at DATETIME   Delay request loop start until datetime (YYYY-MM-DDTHH:MM:SS)
  -o, --output DIR      Output directory for files (default: current directory)
  --log-dir DIR         Override output directory specifically for .log files
  --csv-dir DIR         Override output directory specifically for .csv files
  --disconnect-while-idle
                        Disconnect from serial port while idle
  --config PATH         Path to JSON configuration file
  --save-config PATH    Save current configuration to a JSON file
  -v, --verbose         Verbose terminal output
  -q, --quiet           Supress terminal output
  -d, --debug           Enable debug mode
```

### Example Usage

Listening to remote telemetry from a companion node named 'seeed' on COM4:

```
python src/mc_logger.py COM4 --node seeed --listen telemetry   
Connecting to 'COM4'...
INFO:meshcore:Serial Connection started
Finding target node in contacts using 'seeed' ...
Found 'seeed' in contacts! (public key prefix: 'a1b2c3d4f5g6')
Finding sensors...
Found voltage sensor!
Found illuminance sensor!
Found temperature sensor!
Created telemetry request task!
Requesting telemetry...

Success requesting telemetry!

Received telemetry at '2026-08-15T19:10:34':

voltage = 3.73
illuminance = 0.0
temperature = 23.9

Requesting telemetry again at 2026-08-15T19:40:34

...
```

### Example Output

  Listening to telemetry with `-l/--listen telemetry`:
  
  ```bash
  Received telemetry at '2026-01-01T12:00:01':

  Channel 1: voltage = 3.75
  Channel 1: illuminance = 20.0
  Channel 1: temperature = 22.5

  Next telemetry request at 2026-01-01T12:30:00
  ```

  Logging telemetry to a log file with `--log telemetry`:

  ```bash
  {"timestamp": "2026-01-01T12:00:01", "tag": "a1b2c3d4", "lpp": [{"channel": 1, "type": "voltage", "value": 3.75}, {"channel": 1, "type": "illuminance", "value": 20.0}, {"channel": 1, "type": "temperature", "value": 22.5}], "pubkey_prefix": "a1b2c3d4f5g6"}
  ```

  Logging telemetry to a CSV file with `--csv telemetry`:

  ```bash
  timestamp,ch1_voltage,ch1_illuminance,ch1_temperature
  2026-07-27T12:00:01,3.75,20.0,22.5
  ```

  Listening to status with `-l/--listen status`:

  ```bash
  Received status at '2026-01-01T12:00:01':

  Battery: 3760 mV
  Last RSSI: -26 dBm
  Last SNR: 17.25 dB
  Noise Floor: -108 dBm
  Uptime: 3334 seconds
  TX Queue: 0 packets
  Packets Received: 43
  Packets Sent: 19
  Airtime: 10 ms
  RX Airtime: 24 ms
  Flood packets sent: 2
  Direct packets sent: 5
  Flood packets received: 2
  Direct packets received: 41
  Full buffer events: 0
  Duplicate direct: 0
  Duplicate flood: 0
  ```

  Logging status to a log file with `--log status`:

  ```bash
  {"timestamp": "2026-01-01T12:00:01", "pubkey_pre": "a1b2c3d4f5g6", "bat": 3760, "tx_queue_len": 0, "noise_floor": -118, "last_rssi": -103, "nb_recv": 16517, "nb_sent": 6419, "airtime": 1635, "uptime": 325180, "sent_flood": 6026, "sent_direct": 393, "recv_flood": 14430, "recv_direct": 2083, "full_evts": 0, "last_snr": 11.25, "direct_dups": 34, "flood_dups": 8427, "rx_airtime": 4085, "recv_errors": 526}
  ```

  Logging status to a CSV file with `--csv status`:

  ```bash
  timestamp,pubkey_pre,bat,tx_queue_len,noise_floor,last_rssi,nb_recv,nb_sent,airtime,uptime,sent_flood,sent_direct,recv_flood,recv_direct,full_evts,last_snr,direct_dups,flood_dups,rx_airtime,recv_errors
  2026-07-27T12:00:01,a1b2c3d4f5g6,3760,0,-107,-28,68,39,22,4300,19,20,2,66,0,15.5,0,0,34,0

  ```

  Listening to Min/Max/Avg with `--listen mma`:

  ```bash
  Received Min/Max/Avg at '2026-01-01T12:00:01:

  Time range: 2026-01-01T11:30:01 - 2026-01-01T12:00:01

  Channel 1: temperature
    Min: 15.5
    Max: 28.3
    Avg: 22.1

  Channel 2: humidity
    Min: 45.0
    Max: 78.2
    Avg: 62.4
  ```

  Logging Min/Max/Avg to a log file with `--log mma`:

  ```bash
  {"timestamp": "2026-01-01T11:30:01/2026-01-01T12:00:01", "tag": "a1b2c3d4", "mma_data": [{"channel": 1, "type": "temperature", "min": 15.5, "max": 28.3, "avg": 22.1 }, {"channel": 2, "type": "humidity", "min": 45.0, "max": 78.2,"avg": 62.4}], "pubkey_prefix": "a1b2c3d4f5g6"}
  ```

  Logging Min/Max/Avg to a CSV file with `--csv mma`

  ```bash
  timestamp,temperature_min,temperature_max,temperature_avg,humidity_min,humidity_max,humidity_avg,
  2026-07-26T20:42:13/2026-07-26T21:42:13,15.5,28.3,22.1,45.0,78.2,62.4
  ```

## Configuration Files

To save current configuration you can generate a reusable config file with `--save-config`:

```bash
python src/mc_logger.py /dev/ttyUSB0 -n SENSOR-01 -pw PASSWORD -f 900 --log telemetry mma --save-config config.json
```

This creates a `config.json` file:

```json
{
  "port": "/dev/ttyUSB0",
  "node": "SENSOR-01",
  "password": "PASSWORD",
  "frequency": 900,
  "log": ["telemetry", "mma"],
  "disconnect_while_idle": true
}
```

Run `mc-logger` using the configuration saved in a JSON file with:

```bash
python src/mc_logger.py --config config.json
```

## TODO

- [ ] **Custom channel mapping:** Allow custom naming for sensor channels to support logging from non-standard Cayenne LPP sensors (e.g. particulate matter sensors)
- [ ] **Systemd service teplate** Create a systemd service template for `mc-logger`
- [ ] **Newline-delimited JSON support** Add option to log data to `.ndjson` files

## Contributing

Feedback, bug reports, and feature ideas are always welcome! Since this is my first personal project feel free to reach out or contribute in whatever way is easiest.