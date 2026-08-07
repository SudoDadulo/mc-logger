# MeshCore Remote Logger
#### Video Demo:  <URL>
#### Description:
MeshCore Remote Logger is a command-line interface (CLI) application written in Python meant for remote data collection over LoRa and requires a connected device with the Meshcore Companion USB firmware.

## Installation

Clone the repository and `cd` to the project directory.

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

## Project Structure & File Breakdown

### `project.py` file

This file contains code divided into blocks:

#### The `main` function block

This block contains only the `main` function. It is responsible for:

  - estabilishing a connection to the MeshCore Companion USB device
  - finding the target node in contacts
  - logging into the target repeater
  - calling the `create_file` function to create needed files
  - writing the csv header
  - subscribing to events
  - starting data collection loop using `asyncio.gather(list_of_tasks)`

#### The command-line argument parsing block

This block is nested under the `if __name__ == "__main__":` statement to only call `main()` and only to parse CLI arguments when `project.py` was executed directly. This code block is responsible for:

  - parsing CLI arguments
  - enforcing valid CLI arguments and their combinations
  - starting the main function with `asyncio.run(main())`
  - printing program runtime statistics after exiting

#### Tasks block

This block contains functions that are executed using `asyncio.gather(list_of_tasks)`.

* `idle`
  
  Disconnects from the serial port after all of the tasks are set as done. This makes the port available for running multiple instances of the MeshCore Remote Logger in a seperate terminal tabs. This is useful for collecting data from multiple target nodes simultaneously. 
  
  It is only added to the list_of_tasks if the `--disconnect-while-idle` flag is active. 

* `req_telemetry`

  Requests telemetry data sync from target node in intervals and if succeeds it triggers a `TELEMETRY_RESPONSE` event which is handled by the `on_telemetry` event handler function. If it fails then it attemps 3 times to sync telemetry data. If never succeeds it sleeps until the next interval.

  Works for both companion and repeater nodes.

* `req_status` 

  TODO dopln o tom intervale ktory potrebuje dostat od zariadenia

  Requests status data sync from target repeater in intervals and if succeeds it triggers a `STATUS_RESPONSE` event which is handled by the `on_status` event handler function. If it fails then it attemps 3 times to sync status data. If never succeeds it sleeps until the next interval.

  Works only for repeater nodes.

* `req_mma`

  Requests Min/Max/Avg data sync from target node in intervals and if succeeds it triggers a `MMA_RESPONSE` event which is handled by the `on_mma` event handler function. If it fails then it attemps 3 times to sync Min/Max/Avg data. If never succeeds it sleeps until the next interval.

  Not yet tested as I don't own any device which supports this feature.

#### Event handlers

This block contains functions which handle events when triggered. These events are: `TELEMETRY_RESPONSE`, `STATUS_RESPONSE`, `MMA_RESPONSE`. At the start of `on_telemetry` and `on_status` the function gets the current ISO 8601 formatted timestamp using the `datetime` module which is imported as `dt` by:

  ```python
  timestamp = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
  ``` 

Event handler functions:

* `on_telemetry`

  This function is triggered on a `TELEMETRY_RESPONSE` event. 

  Based on the provided CLI arguments it executes different code:

  - If the `-l/--listen` flag is active the function prints the received telemetry payload and the timestamp.
  - If the `--write-log` flag is active the function calls `write_line` that writes the received telemetry payload and the timestamp to the .log file.
  - If the `--write-csv` flag is active the function parses the received telemetry payload and passes it to `write_row` that writes the parsed payload with the timestamp to the .csv file.

  Example terminal telemetry output:

  ```bash
  Received telemetry at '2026-07-27T13:29:04':

  voltage = 3.75
  illuminance = 20.0
  temperature = 22.5
  ```

  Example telemetry .log file:

  ```bash
  {'timestamp': '2026-07-27T13:29:04', 'tag': 'a1b2c3d4', 'lpp': [{'channel': 1, 'type': 'voltage', 'value': 3.75}, {'channel': 1, 'type': 'illuminance', 'value': 20.0}, {'channel': 1, 'type': 'temperature', 'value': 22.5}], 'pubkey_prefix': 'ee62a6472807'}
  ```

  Example telemetry .csv file:

  ```bash
  timestamp,voltage,illuminance,temperature
  2026-07-27T13:29:04,3.75,20.0,22.5
  ```

* `on_status`

  This function is triggered on a `STATUS_RESPONSE` event. 

  Based on the provided CLI arguments it executes different code:

  - If the `-l/--listen` flag is active the function prints the received status payload and the timestamp.
  - If the `--write-log` flag is active the function calls `write_line` that writes the received status payload and the timestamp to the .log file.
  - If the `--write-csv` flag is active the function calls `write_row` that writes the status payload with the timestamp to the .csv file.

  Example terminal status output:

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

  Example status .log file:

  ```bash
  {'timestamp': '2026-07-27T13:29:04', 'pubkey_pre': 'ee62a6472807', 'bat': 3760, 'tx_queue_len': 0, 'noise_floor': -108, 'last_rssi': -26, 'nb_recv': 43, 'nb_sent': 19, 'airtime': 10, 'uptime': 3334, 'sent_flood': 15, 'sent_direct': 4, 'recv_flood': 2, 'recv_direct': 41, 'full_evts': 0, 'last_snr': 17.25, 'direct_dups': 0, 'flood_dups': 0, 'rx_airtime': 24, 'recv_errors': 0}

  ```

  Example status .csv file:

  ```bash
  timestamp,pubkey_pre,bat,tx_queue_len,noise_floor,last_rssi,nb_recv,nb_sent,airtime,uptime,sent_flood,sent_direct,recv_flood,recv_direct,full_evts,last_snr,direct_dups,flood_dups,rx_airtime,recv_errors
  2026-07-27T13:29:04,ee62a6472807,3760,0,-107,-28,68,39,22,4300,19,20,2,66,0,15.5,0,0,34,0

  ```

* `on_mma`

  This function is triggered on a `MMA_RESPONSE` event. 
  
  It calculates the timestamp interval:

  ```python
  # Get now timestamp
  end_timestamp = dt.datetime.now().timestamp()

  # Convert the frequency argument to a timedelta object
  delta_timestamp = dt.timedelta(seconds=args.frequency)

  # Calculate the starting timestamp
  start_timestamp = end_timestamp - delta_timestamp
  ```
  And then it string formats it to a valid ISO 8601 timestamp interval format:

  ```python
  # ISO-8601 format for time intervals in log and csv
  # 2007-03-01T13:00:00/2008-05-11T15:30:00
  timestamp_interval = f"{start_timestamp.strftime('%Y-%m-%dT%H:%M:%S')}/{end_timestamp.strftime('%Y-%m-%dT%H:%M:%S')}"
  ```

  Based on the provided CLI arguments it executes different code:

  - If the `-l/--listen` flag is active the function prints the received Min/Max/Avg payload and the timestamp interval.
  - If the `--write-log` flag is active the function calls `write_line` that writes the received Min/Max/Avg payload and the timestamp interval to the .log file.
  - If the `--write-csv` flag is active the function parses the received Min/Max/Avg payload passes it to `write_row` that writes the parsed Min/Max/Avg payload with the timestamp interval to the .csv file.

  Example Min/Max/Avg terminal output:

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

  Example Min/Max/Avg .log file:

  ```bash
  {'timestamp': '2026-07-27T13:29:04/2026-07-26T21:42:13', 'tag': 'a1b2c3d4', 'mma_data': [{'channel': 1, 'type': 'temperature', 'min': 15.5, 'max': 28.3, 'avg': 22.1 }, {'channel': 2, 'type': 'humidity', 'min': 45.0, 'max': 78.2,'avg': 62.4}], "pubkey_prefix": "ee62a6472807"}
  ```

  Example Min/Max/Avg .csv file:

  ```bash
  timestamp,temperature_min,temperature_max,temperature_avg,humidity_min,humidity_max,humidity_avg,
  2026-07-26T20:42:13/2026-07-26T21:42:13,15.5,28.3,22.1,45.0,78.2,62.4
  ```

#### File creation & I/O

This code block contains functions that either create needed files (`create_file`) or write data to a file (`write_line`, `write_row`).

* `create_file`

  This function is only called in `main` and its purpose is to create files. The function has 3 positional parameters: `path: str`, `data: str`, `file_type: str`.

  It converts the parameter `path` to a Path object:
  
  ```python
  path = Path(path)
  ```

  Generates the file name with the other params `data` which is the type of data the file is going to contain and `file_type` is the file extension:

  ```python
  # Generate file name with this naming scheme: "mc_data_log_yyyymmdd_HHMMSS.ext" e. g. "mc_telemetry_log_20260101_123030.log"
  file_name = (f"mc_{data}_log_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}.{file_type}")
  ```

  The function returns a tuple with the file name and the absolute path to file

* `write_line`

  This function is called by the event handler functions (`on_telemetry`, `on_status`, `on_mma`) and its purpose is to write data to a log file.

* `write_row`

  This function is called by the event handler functions (`on_telemetry`, `on_status`, `on_mma`) and its purpose is to write data to a csv file.

#### strtobool function

  This function is a function thats converts strings (usually user CLI input) to `True` or `False`. It needs a positional parameter `val: str`. There is an optional named parameter `default_val` which has the defaults to `None`, but it can be set to a `bool`.
  
  Returns `True`: `if val in ('yes', 'y')`
  
  Returns `False`: `if val in ('no', 'n')`

  Returns `default_val`: `if default_val is not None and val == ''` (`val` is an empty string)

  Raises `ValueError`: when no if statement is `True`
  
  Basic example usage:

  ```python
  >>> strtobool('y')
  True
  >>> strtobool('no')
  False
  >>> strtobool('', default_val=True)
  True
  ```

  What this function was meant to solve:

  ```bash
  Do you want to continue? (y/n)
  ```

  ### `test_project.py` file

  This file contains the test functions for `strtobool`, `write_line` and `write_row`. I used pytest to verify string conversion, writing data to a log file and writing data to a csv file.

  ### `requirements.txt` file

  This file contains the requirements needed to run `project.py` and `test_project.py`.

  ```txt
  meshcore
  ```