# mc-logger

Python CLI tool for automated remote data collection over a MeshCore LoRa network. This tool requires a connected device with the Meshcore Companion USB firmware.

## Installation

Clone the repository and `cd` to the project directory.

```bash
git clone https://github.com/SudoDadulo/mc-logger.git
cd mc-logger
```

Create a virtual environment and install the required dependencies:

**Linux**
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

Connect a MeshCore Companion USB device, identify the COM/TTY serial port the device is connected to, then execute `project.py <port> (-c/--companion | -r/--repeater) <NAME | KEY> [options]`.

### Command-Line Arguments (--help)
```
usage: project.py [-h] (-c NAME | KEY | -r NAME | KEY) [-pw PASSWORD] [-b BAUDRATE] 
                  [-l {telemetry,status,mma} [{telemetry,status,mma} ...]] 
                  [--write-log {telemetry,status,mma}[{telemetry,status,mma} ...]]
                  [--write-csv {telemetry,status,mma} [{telemetry,status,mma} ...]] 
                  [-f SECONDS] [-p PATH] [--disconnect-while-idle] 
                  [-v | -q] [-i] [-d]
                  port

MeshCore Remote Logger

positional arguments:
  port                  Serial port (e.g. 'COM4', '/dev/ttyUSB0')

options:
  -h, --help            show this help message and exit
  -c, --companion NAME | KEY
                        Target companion node
  -r, --repeater NAME | KEY
                        Target repeater node (pw required)
  -pw, --password PASSWORD
                        Password for repeater login (required if --repeater)
  -b, --baudrate BAUDRATE
                        Serial baudrate (default: 115200)
  -l, --listen {telemetry,status,mma} [{telemetry,status,mma} ...]
                        Print chosen data to terminal
  --write-log {telemetry,status,mma} [{telemetry,status,mma} ...]
                        Write chosen data to .log file
  --write-csv {telemetry,status,mma} [{telemetry,status,mma} ...]
                        Write chosen data to .csv file
  -f, --frequency SECONDS
                        Request frequency in seconds (default: 1800)
  -p, --path PATH       Directory for output files (default: current directory)
  --disconnect-while-idle
                        Disconnect from serial port while idle
  -v, --verbose         Verbose to terminal output
  -q, --quiet           Supress terminal output
  -i, --interactive     Enable interactive mode
  -d, --debug           Enable debug mode
```

### Example Usage

Listening to remote telemetry from a companion node named seed2 on COM4:

```
python project.py COM4 --companion seed2 --listen telemetry   
Connecting to 'COM4'...
INFO:meshcore:Serial Connection started
Device connected!
Finding companion in contacts using 'seed2' ...
Companion 'seed2' found!
Finding sensors...
Found voltage sensor!
Found illuminance sensor!
Found temperature sensor!
Created telemetry request task!
Requesting telemetry...

Success requesting telemetry!

Received telemetry at '2026-07-27T13:29:04':

voltage = 3.75
illuminance = 20.0
temperature = 22.5

Requesting telemetry again at 2026-07-27 14:29:04

...
```

### Example Output

  Listening to telemetry with `--listen telemetry`:
  
  ```bash
  Received telemetry at '2026-07-27T13:29:04':

  voltage = 3.75
  illuminance = 20.0
  temperature = 22.5
  ```

  Logging telemetry to a log file with `--write-log telemetry`:

  ```bash
  {'timestamp': '2026-07-27T13:29:04', 'tag': 'a1b2c3d4', 'lpp': [{'channel': 1, 'type': 'voltage', 'value': 3.75}, {'channel': 1, 'type': 'illuminance', 'value': 20.0}, {'channel': 1, 'type': 'temperature', 'value': 22.5}], 'pubkey_prefix': 'ee62a6472807'}
  ```

  Logging telemetry to a CSV file with `--write-csv telemetry`:

  ```bash
  timestamp,voltage,illuminance,temperature
  2026-07-27T13:29:04,3.75,20.0,22.5
  ```

  Listening to status with `--listen status`:

  ```bash
  Received status at '2026-07-27T13:29:04':

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

  Logging status to a log file with `--write-log status`:

  ```bash
  {'timestamp': '2026-07-27T13:29:04', 'pubkey_pre': 'ee62a6472807', 'bat': 3760, 'tx_queue_len': 0, 'noise_floor': -108, 'last_rssi': -26, 'nb_recv': 43, 'nb_sent': 19, 'airtime': 10, 'uptime': 3334, 'sent_flood': 15, 'sent_direct': 4, 'recv_flood': 2, 'recv_direct': 41, 'full_evts': 0, 'last_snr': 17.25, 'direct_dups': 0, 'flood_dups': 0, 'rx_airtime': 24, 'recv_errors': 0}

  ```

  Logging status to a CSV file with `--write-csv status`:

  ```bash
  timestamp,pubkey_pre,bat,tx_queue_len,noise_floor,last_rssi,nb_recv,nb_sent,airtime,uptime,sent_flood,sent_direct,recv_flood,recv_direct,full_evts,last_snr,direct_dups,flood_dups,rx_airtime,recv_errors
  2026-07-27T13:29:04,ee62a6472807,3760,0,-107,-28,68,39,22,4300,19,20,2,66,0,15.5,0,0,34,0

  ```

  Listening to Min/Max/Avg with `--listen status`:

  ```bash
  Received Min/Max/Avg at '2026-07-27 13:29:04:

  Time range: 2026-07-27T13:29:04 - 2026-07-27T13:59:04

  Channel 1: temperature
    Min: 15.5
    Max: 28.3
    Avg: 22.1

  Channel 2: humidity
    Min: 45.0
    Max: 78.2
    Avg: 62.4
  ```

  Logging Min/Max/Avg to a log file with `--write-log mma`:

  ```bash
  {'timestamp': '2026-07-27T13:29:04/2026-07-26T21:42:13', 'tag': 'a1b2c3d4', 'mma_data': [{'channel': 1, 'type': 'temperature', 'min': 15.5, 'max': 28.3, 'avg': 22.1 }, {'channel': 2, 'type': 'humidity', 'min': 45.0, 'max': 78.2,'avg': 62.4}], "pubkey_prefix": "ee62a6472807"}
  ```

  Logging Min/Max/Avg to a CSV file with `--write-csv mma`

  ```bash
  timestamp,temperature_min,temperature_max,temperature_avg,humidity_min,humidity_max,humidity_avg,
  2026-07-26T20:42:13/2026-07-26T21:42:13,15.5,28.3,22.1,45.0,78.2,62.4
  ```