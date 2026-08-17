import asyncio
import argparse
import csv
import datetime as dt
import time
import sys
import os
import json
import serial

from pathlib import Path

from serial.serialutil import SerialException

from meshcore import MeshCore, EventType

from runtime_tracker import RuntimeTracker

CONTACT_TYPES = {
    0: "NO_TYPE",
    1: "COMP",
    2: "REPEAT",
    3: "ROOM",
    4: "SENS",
}

class MeshCoreLogger:

    def __init__(self, mc: MeshCore, contact: dict, args: argparse.Namespace):
        self.mc = mc
        self.contact = contact
        self.args = args

        self._logged_in: bool = False

        self._contact_type = contact.get("type", 0)
        self.contact_typename = CONTACT_TYPES.get(self._contact_type, "UNKNOWN")

        # List to metrics to collect
        self.metrics: list[str] = []

        # List of tasks passed to asyncio.gather()
        self.tasks: list[asyncio.coroutine] = []

        # Flags that store task completion
        self.completion_flags: list[asyncio.Event] = []

        # Store output paths as e.g. ("telemetry", "csv"): path
        self.output_paths: dict[tuple[str, str], Path] = {}
    
    def add_metric(self, metric) -> None:
        self.metrics.append(metric)

    def add_task(self, task) -> None:
        self.tasks.append(task)

    def store_path(self, metric: str, file_ext: str, path: Path) -> None:
        self.output_paths[(metric, file_ext)] = path

    def get_path(self, metric: str, file_ext: str) -> Path | None:
        return self.output_paths.get((metric, file_ext))

    def create_completion_flag(self):
        event = asyncio.Event()
        self.completion_flags.append(event)
        return event

    def print_file_stats(self):
        
        # If no files written
        if not self.output_paths:
            return

        print("\nFile statistics:")
        for (metric, ext), path in self.output_paths.items():

            try:
                
                line_count = 0
                with open(path, "r", encoding="utf-8") as file:

                    for line_count, _ in enumerate(file, start=1):
                        pass  # Just iterate

                # Don't count header
                if ext == "csv": 
                        
                    # Make sure that row_count is never < 0
                    row_count = max(0, line_count - 1)
                    print(f"  {metric.capitalize()} CSV: wrote {row_count} rows")
                    
                else:
                    print(f"  {metric.capitalize()} Log: wrote {line_count} lines")

            except OSError as e:
                print(f"Error: couldn't read {path}: {e}")

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    @is_logged_in.setter
    def is_logged_in(self, value: bool) -> None:
        self._logged_in = value

    async def ensure_logged_in(self) -> bool:

        if self.contact_typename not in ("REPEAT", "SENS") or self._logged_in:
            return True
        
        login = await node_login(self.mc, self.contact, self.args.password)

        if login is not None:
            self._logged_in = True
            return True

        self._logged_in = False
        return False

    async def on_connected(self, event):
        print(f"Connected: {event.payload}")
        
        if event.payload.get('reconnected'):
            
            if not self.args.quiet:
                print("Successfully reconnected!")

    async def on_disconnected(self, event):
        print(f"Disconnected: {event.payload['reason']}")
        
        if event.payload.get('max_attempts_exceeded'):
            print("Max reconnection attempts exceeded")

        # Reset logged in flag on unexpected disconnection
        self._logged_in = False

    async def on_telemetry(self, event: EventType.TELEMETRY_RESPONSE) -> None:
        """
        Handle a telemetry response event.

        Args:
            event (EventType.TELEMETRY_RESPONSE): Telemetry event data

        Returns:
            None
        """
        if not self.args.quiet:
            print("\nSuccess requesting telemetry!")

        # Get the lpp formatted data
        lpp_data = event.payload["lpp"]

        timestamp = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        if "telemetry" in self.args.listen:

            print(f"\nReceived telemetry at '{timestamp}':\n")

            for channel_data in lpp_data:
                print(f"Channel {channel_data['channel']}: "
                    f"{channel_data['type']} = {channel_data['value']}")

        if "telemetry" in self.args.log:
            write_line(event.payload, timestamp, self.get_path("telemetry", "log"))

            if not self.args.quiet:
                print("\nTelemetry data written to log file.")

        if "telemetry" in self.args.csv:
            
            sensor_values = {
                f"ch{sensor['channel']}_{sensor['type']}": sensor["value"] for sensor in lpp_data
            }

            write_row(sensor_values, timestamp, self.get_path("telemetry", "csv"))

            if not self.args.quiet:
                print("\nTelemetry data written to csv file.")

    async def on_status(self, event: EventType.STATUS_RESPONSE) -> None:
        """
        Handle a status response event.

        Args:
            event (EventType.STATUS_RESPONSE): Status event data

        Returns:
            None
        """
        if not self.args.quiet:
            print("\nSuccess requesting status!")

        # Get status
        status = event.payload

        # Get timestamp
        timestamp = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        if "status" in self.args.listen:

            print(f"\nReceived status at '{timestamp}':\n")

            print(f"Battery: {status['bat']} mV")
            print(f"Last RSSI: {status['last_rssi']} dBm")
            print(f"Last SNR: {status['last_snr']} dB")
            print(f"Noise Floor: {status['noise_floor']} dBm")
            print(f"Uptime: {status['uptime']} seconds")
            print(f"TX Queue: {status['tx_queue_len']} packets")
            print(f"Packets Received: {status['nb_recv']}")
            print(f"Packets Sent: {status['nb_sent']}")
            print(f"Airtime: {status['airtime']} ms")
            print(f"RX Airtime: {status['rx_airtime']} ms")
            print(f"Flood packets sent: {status['sent_flood']}")
            print(f"Direct packets sent: {status['sent_direct']}")
            print(f"Flood packets received: {status['recv_flood']}")
            print(f"Direct packets received: {status['recv_direct']}")
            print(f"Full buffer events: {status['full_evts']}")
            print(f"Duplicate direct: {status['direct_dups']}")
            print(f"Duplicate flood: {status['flood_dups']}")

        if "status" in self.args.log:
            write_line(
                status, timestamp, self.get_path("status", "log")
                )

            if not self.args.quiet:
                print("\nStatus data written to log file.")

        if "status" in self.args.csv:
            write_row(
                status, timestamp, self.get_path("status", "csv")
                )

            if not self.args.quiet:
                print("\nStatus data written to csv file.")

    async def on_mma(self, event: EventType.MMA_RESPONSE) -> None:
        """
        Handle a Min/Max/Avg response event.

        Args:
            event (EventType.MMA_RESPONSE): Min/Max/Avg event data

        Returns:
            None
        """
        if not self.args.quiet:
            print("\nSuccess requesting Min/Max/Avg!")

        # Get the lpp formatted data
        mma_data = event.payload["mma_data"]

        # Get now timestamp
        end_timestamp = dt.datetime.now()

        # Convert the frequency argument to a timedelta object
        delta_timestamp = dt.timedelta(seconds=self.args.frequency)

        start_timestamp = end_timestamp - delta_timestamp

        # ISO-8601 format for time intervals in log and csv
        # 2007-03-01T13:00:00/2008-05-11T15:30:00
        timestamp_interval = f"{start_timestamp.strftime('%Y-%m-%dT%H:%M:%S')}/{end_timestamp.strftime('%Y-%m-%dT%H:%M:%S')}"

        if "mma" in self.args.listen:

            print(f"\nReceived Min/Max/Avg at '{end_timestamp.strftime('%Y-%m-%dT%H:%M:%S')}' :")

            print(
                f"\nTime range: {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {end_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            for mma in mma_data:

                print(f"\nChannel {mma['channel']}: {mma['type']}")
                print(f"  Min: {mma['min']}")
                print(f"  Max: {mma['max']}")
                print(f"  Avg: {mma['avg']}")

        if "mma" in self.args.log:
            write_line(
                event.payload, timestamp_interval, self.get_path("mma", "log")
                )

            if not self.args.quiet:
                print("\nMin/Max/Avg data written to log file.")

        if "mma" in self.args.csv:
                
            mma_sensor_values = {}
            for mma_sensor in mma_data:

                sensor_type = mma_sensor["type"]

                mma_sensor_values.update({f"{sensor_type}_min": mma_sensor['min']})
                mma_sensor_values.update({f"{sensor_type}_max": mma_sensor['max']})
                mma_sensor_values.update({f"{sensor_type}_avg": mma_sensor['avg']})

            write_row(
                mma_sensor_values, timestamp_interval, self.get_path("mma", "csv")
                )

            if not self.args.quiet:
                print("\nMin/Max/Avg data written to csv file.")

# * STRTOBOOL FUNCTION
def strtobool(val: str, default_val: bool | None = None) -> bool:
    """
    Convert string into a bool.

    Args:
        val (str): String to convert.
        default_val (bool | None, optional): Set the default truth value to return if the user inputs
            an empty string.

    Returns:
        bool: True if val in ('y', 'yes'), False if val in ('n', 'no'),
            The value of default_val if val equals an empty string.

    Raises:
        ValueError: If val not in ('y', 'yes', 'n', 'no', '').

    Examples:

        >>> strtobool('y')
        True

        >>> strtobool('no')
        False

        >>> strtobool('', default_val=True)
        True

    """
    val = val.lower().strip()
    if val in ("y", "yes"):
        return True
    if val in ("n", "no"):
        return False
    if default_val is not None and val == "":
        return default_val
    raise ValueError(f"Invalid truth value {val!r}")


# * FILE MANIPULATION
def create_file(metric: str, file_type: str, path: str) -> Path:
    """
    Try to create file on path with naming scheme: 'mc_{data}_log_yyyymmdd_HHMMSS.{file_type}'.

    Args:
        file_type (str): 'log' or 'csv' or any file extension
        data (str): type of data the file is going to store e.g. 'telemetry'
        path (Path): Path to file directory

    Returns:
        tuple (str, Path): Tuple with a file name str and the absolute file path Path object

    Raises:
        FileExistsError: If file exists, prompt to overwrite. This exception won't be usually raised with name
            generation from the file naming scheme
    """

    path = Path(path)

    # Generate file name with this naming scheme: "mc_metric_log_yyyymmdd_HHMMSS.ext" e. g. "mc_telemetry_log_20260101_123030.log"
    file_name = (
        f"mc_{metric}_log_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_type}"
    )

    abs_file_path = (path / file_name).resolve()

    try:
        with open(f"{abs_file_path}", "x"):
            pass

    # Exception that practically never gets raised as with the current naming scheme it never has the same file name
    except FileExistsError:
        print("File already exists. Continue?", end=" ")
        while True:
            try:
                if strtobool(input("(y/n) ", default_val=None)):
                    print("Overwriting file.")
                    # This truncates the file, opens it and closes
                    with open(f"{abs_file_path}", "w"):
                        pass
                    break
                
                else:
                    print(f"Exited without overwriting file.")
                    sys.exit()

            except ValueError:
                print("Please choose a valid option. ")

    return abs_file_path

def write_header(path, fieldnames: list) -> list[str]:
    
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["timestamp", *fieldnames])
        writer.writeheader()

        return writer.fieldnames

def write_line(data: dict, timestamp: str, path: Path) -> None:
    """
    Append line to log file.

    Args:
        data (dict): Key-value pairs.
        timestamp (str): Timestamp.
        path (Path): Path to file.

    Returns:
        None
    """
    with open(path, "a", newline="", encoding="utf-8") as logfile:
        logline = {"timestamp": timestamp} | data
        logfile.write(f"{json.dumps(logline)}\n")


def write_row(data: dict, timestamp: str, path: Path) -> None:
    """
    Append row to csv file.

    Args:
        data (dict): Key-value pairs.
        timestamp (str): Timestamp.
        path (Path): Path to file.

    Returns:
        None
    """
    with open(path, "a", newline="",encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["timestamp", *data])

        writer.writerow({"timestamp": timestamp} | data)

def get_sleep_duration(anchor: float) -> float:
    return max(0.0, anchor - time.monotonic())

def print_next_request(sleep_duration: float, metric: str) -> None:
    next_request = dt.datetime.now() + dt.timedelta(seconds=round(sleep_duration))
    print(f"\nNext {metric} request at {next_request.strftime('%Y-%m-%dT%H:%M:%S')}")

# * TASKS
async def idle(
    mc: MeshCore, 
    frequency: int, 
    mc_logger: MeshCoreLogger,
    ) -> None:
    """
    Disconnect while idle, wait until all requests are finished.

    Args:
        mc (MeshCore): Connected MeshCore instance.
        frequency (int): Time in seconds between disconnecting and connecting.
        mc_logger (MeshCoreLogger): MeshCoreLogger instance containing the state.

    Returns:
        None
    """

    while True:

        if not mc.is_connected:
            await mc.connect()
            print("Connected to device.")

        if mc_logger.args.verbose:
            print(
                f"Waiting for all active backround tasks to finish before disconnecting..."
            )

        # Wait until every flag in the list has been set to True
        await asyncio.gather(*[flag.wait() for flag in mc_logger.completion_flags])

        # Padding to allow event handlers to finish
        await asyncio.sleep(1.5)

        if mc.is_connected:
            await mc.disconnect()
            print(f"\nDisconnected from device, will connect again before next cycle.")

        # Reset all flags to False for the next cycle
        for flag in mc_logger.completion_flags:
            flag.clear()

        # Sleep until just before next cycle
        await asyncio.sleep(max(0.0, frequency - 5))


async def req_telemetry(
    mc: MeshCore, 
    contact: dict, 
    frequency: int, 
    mc_logger: MeshCoreLogger, 
    completion_flag: asyncio.Event
    ) -> None:
    """
    Periodically request telemetry from a contact and signal loop completion.

    Args:
        mc (MeshCore): Connected MeshCore instance.
        contact (dict): Target contact from which to request telemetry.
        frequency (int): Interval in seconds between telemetry requests.
        mc_logger (MeshCoreLogger): MeshCoreLogger instance containing the state.
        completion_flag (asyncio.Event): Event flag signaled when the request cycle completes.

    Returns:
        None
    """

    anchor_time = time.monotonic()

    while True:

        anchor_time += frequency

        # Ensure login, sleeps if failure, returns true if node doesnt need login
        if not await mc_logger.ensure_logged_in():
            print("Warning: Skipping telemetry request due to login failure.")
            
            completion_flag.set()

            sleep_duration = get_sleep_duration(anchor_time)
            
            if not mc_logger.args.quiet:
                print_next_request(sleep_duration, "telemetry")
            
            await asyncio.sleep(sleep_duration)
            continue

        if not mc_logger.args.quiet:
            print("Requesting telemetry...")

        request = None
        for attempt in range(4): # first telemetry request attempt + 3 retries
            if attempt > 0:
                print(f"Retrying telemetry request... (Attempt {attempt}/3)")
    
            try:
                
                request = await mc.commands.req_telemetry_sync(
                    contact, timeout=0, min_timeout=5.0
                )

                if request is not None:
                    break

            except (SerialException, OSError, asyncio.TimeoutError) as e:
                err = f": {e}" if mc_logger.args.verbose else ""
                print(f"Warning: Transport error during telemetry request{err}")
                request = None

                # If disconnected dont retry
                if not mc.is_connected:
                    break

        if request is None and mc.is_connected:
            
            if mc_logger.contact_typename == "COMP":
                print("Error: The companion may be unreachable or you don't have the permission to access telemetry.")

            else:
                print("Error: The node may be unreachable or the session is not authenticated.")
                mc_logger.is_logged_in = False

        # Signal completion even if fail to not stall forever
        completion_flag.set()

        sleep_duration = get_sleep_duration(anchor_time)

        if not mc_logger.args.quiet:
            print_next_request(sleep_duration, "telemetry")

        # sleep_duration = max(0.0, anchor_time - time.monotonic())
        await asyncio.sleep(sleep_duration)


async def req_status(
    mc: MeshCore, 
    contact: dict, 
    frequency: int,
    mc_logger: MeshCoreLogger, 
    completion_flag: asyncio.Event
    ) -> None:
    """
    Periodically request status from a repeater contact and signal loop completion.

    Args:
        mc (MeshCore): Connected MeshCore instance.
        contact (dict): Target repeater contact from which to request status.
        frequency (int): Interval in seconds between telemetry requests.
        mc_logger (MeshCoreLogger): MeshCoreLogger instance containing the state.
        completion_flag (asyncio.Event): Event flag signaled when the request cycle completes.

    Returns:
        None
    """

    # Set absolute starting time aka anchor e. g. T = 100 s
    anchor_time = time.monotonic()

    while True:

        # add the frequency to calculate when the next loop *must* begin
        # if f = 1800 s -> T = 1900 s
        anchor_time += frequency

        # Ensure repeater login, sleeps if failure, returns true if repeater
        if not await mc_logger.ensure_logged_in():
            print("Warning: Skipping status request due to login failure.")
            
            completion_flag.set()

            sleep_duration = get_sleep_duration(anchor_time)

            if not mc_logger.args.quiet:
                print_next_request(sleep_duration, "status")

            await asyncio.sleep(sleep_duration)
            continue

        if not mc_logger.args.quiet:
            print("Requesting status...")

        request = None
        for attempt in range(4): # first status request attempt + 3 retries
            if attempt > 0:
                print(f"Retrying status request... (Attempt {attempt}/3)")
    
            try:
                
                request = await mc.commands.req_status_sync(
                    contact, timeout=0, min_timeout=5.0
                )

                if request is not None:
                    break

            except (SerialException, OSError, asyncio.TimeoutError) as e:
                err = f": {e}" if mc_logger.args.verbose else ""
                print(f"Warning: Transport error during status request{err}")
                request = None

                # If disconnected dont retry
                if not mc.is_connected:
                    break

        if request is None and mc.is_connected:
            
            print("Error: The node may be unreachable or the session is not authenticated.")
            mc_logger.is_logged_in = False

        # Signal completion even if fail to not stall forever
        completion_flag.set()

        sleep_duration = get_sleep_duration(anchor_time)

        if not mc_logger.args.quiet:
            print_next_request(sleep_duration, "status")

        await asyncio.sleep(sleep_duration)


async def req_mma(
    mc: MeshCore, 
    contact: dict, 
    frequency: int, 
    mc_logger: MeshCoreLogger,
    completion_flag: asyncio.Event
    ) -> None:
    """
    Periodically request Min/Max/Avg telemetry data from a contact.

    Args:
        mc (MeshCore): Connected MeshCore instance.
        contact (dict): Target contact from which to request Min/Max/Avg telemetry.
        frequency (int): Interval in seconds between Min/Max/Avg requests.
        mc_logger (MeshCoreLogger): MeshCoreLogger instance containing the state.
        completion_flag (asyncio.Event): Event flag signaled when the request cycle completes or fails.

    Returns:
        None
    """
    
    anchor_time = time.monotonic()
    
    while True:

        anchor_time += frequency

        # Ensure repeater login, sleeps if failure, returns true if repeater
        if not await mc_logger.ensure_logged_in():
            print("Warning: Skipping Min/Max/Avg request due to login failure.")
            
            completion_flag.set()

            sleep_duration = get_sleep_duration(anchor_time)
        
            if not mc_logger.args.quiet:
                print_next_request(sleep_duration, "Min/Max/Avg")

            await asyncio.sleep(sleep_duration)
            continue

        if not mc_logger.args.quiet:
            print("Requesting Min/Max/Avg...")

        end_time = int(time.time())
        start_time = end_time - frequency

        request = None
        for attempt in range(4): # first request attempt + 3 retries
            if attempt > 0:
                print(f"Retrying Min/Max/Avg request... (Attempt {attempt}/3)")
    
            try:
                
                request = await mc.commands.req_mma_sync(
                    contact, start_time, end_time, timeout=0, min_timeout=10.0
                )

                if request is not None:
                    break

            except (SerialException, OSError, asyncio.TimeoutError) as e:
                err = f": {e}" if mc_logger.args.verbose else ""
                print(f"Warning: Transport error during Min/Max/Avg request{err}")
                request = None

                # If disconnected dont retry
                if not mc.is_connected:
                    break

        if request is None and mc.is_connected:
            
            print("Error: The node may be unreachable or the session is not authenticated.")
            mc_logger.is_logged_in = False
        
        # Signal completion even if fail to not stall forever
        completion_flag.set()

        sleep_duration = get_sleep_duration(anchor_time)
        
        if not mc_logger.args.quiet:
            print_next_request(sleep_duration, "Min/Max/Avg")

        await asyncio.sleep(sleep_duration)


# * LOGIN AND LOGOUT
async def node_login(
    mc: MeshCore, 
    contact: dict, 
    password: str, 
    ) -> EventType.LOGIN_SUCCESS | None:

    print("Logging in...")

    login = None
    for attempt in range(4): # first login attempt + 3 retries
        if attempt > 0:
            print(f"Retrying login... (Attempt {attempt}/3)")
    
        try:
            
            login = await mc.commands.send_login_sync(
                contact, password, timeout=0, min_timeout=10
                )

            if login is not None:
                break

        except (SerialException, OSError, asyncio.TimeoutError) as e:
            print(f"Warning: Transport error during login: {e}")
            login = None
            # If disconnected dont retry
            if not mc.is_connected:
                break

    return login

async def node_logout(mc, contact: dict) -> EventType.ERROR | EventType.OK:

    logout_event = EventType.ERROR

    # When the --disconnect-while-idle flag is active the connected device over serial
    # cant send logout request so we have to connect to send it
    if not mc.is_connected:
        try:
            await mc.connect()
            print("Connected just to send logout.")

        except (SerialException, OSError, asyncio.TimeoutError) as e:
            print(f"Warning: Could not reconnect to send logout: {e}")
            return EventType.ERROR

    print("Logging out...")

    for attempt in range(4): # first login attempt + 3 retries
        if attempt > 0:
            print(f"Retrying logout... (Attempt {attempt}/3)")
    
        try:
            logout_event = await mc.commands.send_logout(contact)

            if logout_event != EventType.ERROR:
                break

        except (SerialException, OSError, asyncio.TimeoutError) as e:
            print(f"Warning: Transport error during logout: {e}")
            logout_event = EventType.ERROR
            
            # If disconnected dont retry
            if not mc.is_connected:
                break

    return logout_event

# * SEARCH CONTACTS
async def search_contacts(mc, query: str) -> dict | None:

    # Try to find contact by name and by pubkey prefix
    by_name = mc.get_contact_by_name(query)
    by_key = mc.get_contact_by_key_prefix(query)

    contact: dict | None = by_name or by_key

    if contact is not None:
        print(
            f"Found {contact['adv_name']!r} in contacts! (public key prefix: {contact['public_key'][:12]!r})"
        )
        return contact

    # If the contact wasn't found by name or key
    print(
        f"Couldn't find companion/repeater in contacts using '{query}'."
    )
    print("Print available contacts?", end=" ")

    while True:
        try:

            if strtobool(input("(Y/n) "), default_val=True):
                
                response = await mc.commands.get_contacts()
                contacts = response.payload
                
                print(f"\nAvailable contacts: {len(contacts)}\n")
                
                for key, contact in contacts.items():
                    print(f"{contact['adv_name']:<30}{key:>40}")

            break

        except (KeyboardInterrupt, EOFError):
            print("\nProgram cancelled by user.")
            break

        except ValueError:
            print("Please choose a valid option.", end=" ")

    # If contact was not found or user inputted False or quit
    return None

async def main():

    # To avoid UnboundLocalError if the user quits too early
    mc_logger = None

    if not args.quiet:
        print(f"Connecting to '{args.port}'...")

    # Connect to the device
    mc = await MeshCore.create_serial(
        args.port, args.baud, debug=args.debug, auto_reconnect=True, max_reconnect_attempts=5
        )

    try:

        # Make sure that the device has ANY contacts before searching
        if not await mc.ensure_contacts():
            print("Couldn't fetch contacts.")
            return

        if not args.quiet:
            print(f"Finding target node in contacts using '{args.node}' ...")

        # Search for contact
        contact = await search_contacts(mc, args.node)

        # End the program because no contacts found using the search query or user inputted false or quit
        if contact is None:
            return

        # * Instantiate the MeshCoreLogger class
        mc_logger = MeshCoreLogger(mc, contact, args)

        # Unsupported node types
        if mc_logger.contact_typename in ("NO_TYPE", "ROOM", "UNKNOWN"):
            print(f"Error: Unsupported node type: {mc_logger.contact_typename}")
            return
        
        # # Exit early if the node type doesn't allow for status
        # if mc_logger.contact_typename in ("COMP", "SENS") and "status" in (args.log, args.csv):
        #     print("Error: Companion/Sensor nodes don't support requesting status.")
        #     return

        # Exit early if mma from comp or repeat
        if mc_logger.contact_typename in ("COMP", "REPEAT") and "mma" in (args.log, args.csv):
            print("Error: Companion/Repeater nodes don't support requesting Min/Max/Avg.")
            return

        # Subscribe to connection events, before login to allow reconnnect as early
        mc.subscribe(EventType.CONNECTED, mc_logger.on_connected)
        mc.subscribe(EventType.DISCONNECTED, mc_logger.on_disconnected)

        # Nodes that need login
        if mc_logger.contact_typename in ("REPEAT", "SENS"):
            
            login = await node_login(mc, contact, args.password)

            # End the program when login failed
            if login is None:
                if mc.is_connected:
                
                    if args.password == "":
                        print("Error: You didn't enter a password. Access may be disabled or the node may be unreachable.")
                    else:
                        print("Error: The password you entered may be incorrect or the node may be unreachable.") 
                
                return

            mc_logger.is_logged_in = True
            print("Success logging in!")

        # Add metrics to the list of metrics to collect
        for metric in ["telemetry", "status", "mma"]:

            if metric in (args.listen or args.log or args.csv):
                mc_logger.add_metric(metric)

        # Create files and store paths in MeshCoreLogger.output_paths: dict[tuple[str, str], Path]
        for metric in mc_logger.metrics:

            for ext, arg in [("log", args.log), ("csv", args.csv)]:
                
                if metric in arg:

                    if ext == "log" and args.log_dir:
                        path = create_file(metric, ext, args.log_dir)
                    
                    elif ext == "csv" and args.csv_dir:
                        path = create_file(metric, ext, args.csv_dir)

                    else:
                        path = create_file(metric, ext, args.output)
                        
                    mc_logger.store_path(metric, ext, path)

                    if not args.quiet:
                        print(f"Created {metric} {ext} file.")

                    if args.verbose:
                        print(f"Path to {metric} {ext} file: '{path}'")

        #* FIND SENSORS AND SUBSCRIBE TO EVENTS

        if "telemetry" in mc_logger.metrics:

            if not args.quiet:
                print("Finding sensors...")

            telemetry = await mc.commands.req_telemetry_sync(
                contact, timeout=0, min_timeout=10.0
            )

            if telemetry is None:
                print("Error: Failed to get sensors! The node may be unreachable.")
                return

            # This list comprehension extracts the sensor type
            sensors = [sensor["type"] for sensor in telemetry]

            # Print found sensors
            if not args.quiet:
                for sensor in sensors:
                    print(f"Found {sensor} sensor!")

            # Write telemetry csv header
            if "telemetry" in args.csv:

                header = [f"ch{sensor['channel']}_{sensor['type']}" for sensor in telemetry]

                fieldnames: list = write_header(
                    mc_logger.get_path("telemetry", "csv"), header
                    )

                if args.verbose:
                    print("Telemetry csv header:", end=" ")
                    print(*fieldnames, sep=", ")

            # Subscribe to event
            mc.subscribe(EventType.TELEMETRY_RESPONSE, mc_logger.on_telemetry)

            # Create asyncio.Event which gets asyncio.Event.set() when request is done
            telemetry_flag = mc_logger.create_completion_flag()

            # Append the telemetry request to the list of tasks
            mc_logger.add_task(
                req_telemetry(mc, contact, args.frequency, mc_logger, telemetry_flag), 
            )

            if not args.quiet:
                print("Created telemetry request task!")

        if "status" in mc_logger.metrics:

            # Write status header
            if "status" in args.csv:

                status = await mc.commands.req_status_sync(
                    contact, timeout=0, min_timeout=10.0
                )

                if status is None:
                    print("Failed to get status! Please try again!")
                    return

                fieldnames: list = write_header(
                    mc_logger.get_path("status", "csv"), status
                )

                if args.verbose:
                    print("Status csv header:", end=" ")
                    print(*fieldnames, sep=", ")

            # Subscribe to event
            mc.subscribe(EventType.STATUS_RESPONSE, mc_logger.on_status)

            # Create asyncio.Event which gets asyncio.Event.set() when request is done
            status_flag = mc_logger.create_completion_flag()

            # Append the telemetry request to the list of tasks
            mc_logger.add_task(
                req_status(mc, contact, args.frequency, mc_logger, status_flag), 
            )

            if not args.quiet:
                print("Created status request task!")

        if "mma" in mc_logger.metrics:

            if not args.quiet:
                print("Finding sensors that support Min/Max/Avg data output...")

            end_time = int(time.time())
            start_time = end_time - 3600

            mma = await mc.commands.req_mma_sync(
                contact, start=start_time, end=end_time, min_timeout=15.0
            )

            if mma is None:
                print(
                    "Failed getting Min/Max/Avg data! Make sure that the companion/repeater supports it!"
                )
                return

            # Extract sensors
            sensors = [sensor["type"] for sensor in mma]

            if not args.quiet:
                for sensor in sensors:
                    print(f"Found {sensor} sensor!")

            if "mma" in args.csv:

                # Format sensor headers
                sensor_header = []
                for sensor in sensors:
                    sensor_header.append(f"{sensor}_min")
                    sensor_header.append(f"{sensor}_max")
                    sensor_header.append(f"{sensor}_avg")

                header: list = write_header(
                    mc_logger.get_path("mma", "csv"), sensor_header
                )
                
                if args.verbose:
                    print("Min/Max/Avg csv header:", end=" ")
                    print(*header, sep=", ")

            # Subscribe to event
            mc.subscribe(EventType.MMA_RESPONSE, mc_logger.on_mma)

            # Create asyncio.Event which gets asyncio.Event.set() when request is done
            mma_flag = mc_logger.create_completion_flag()

            # Append the telemetry request to the list of tasks
            mc_logger.add_task(
                req_mma(mc, contact, args.frequency, mc_logger, mma_flag), 
            )

            if not args.quiet:
                print("Created Min/Max/Avg request task!")

        # Insert the idle task to the start of mc_logger.tasks
        if args.disconnect_while_idle:
            mc_logger.tasks.insert(
                0, idle(mc, args.frequency, mc_logger)
                )

        #* START TASKS
        await asyncio.gather(*mc_logger.tasks)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nProgram cancelled by user.")

    finally:

        if mc_logger is not None:
            
            if mc_logger.is_logged_in:
                logout_event = await node_logout(mc, contact)

                if logout_event == EventType.ERROR:
                    print("Still logged in!")

                if logout_event == EventType.OK and not args.quiet:
                    print("Logged out successfully!")

        # Diconnect cleanly, only if device is connected
        if mc.is_connected:
            await mc.disconnect()
            print("\nDisconnected from device.")

        if mc_logger is not None:
            mc_logger.print_file_stats()

if __name__ == "__main__":

    #* CONFIG PARSER
    config_parser = argparse.ArgumentParser(add_help=False)

    config_parser.add_argument("--config", type=Path,)
    
    config_args, _ = config_parser.parse_known_args()

    # * MAIN PARSER
    parser = argparse.ArgumentParser(
        description="Python CLI tool for automated remote data collection over the MeshCore LoRa network."
        )

    # Positional argument port
    parser.add_argument(
        "port", 
        nargs="?",
        help="Serial port (e.g. 'COM4', '/dev/ttyUSB0')"
    )

    parser.add_argument(
        "-n", 
        "--node",
        metavar="NAME | KEY",
        help="Target node name or public key prefix"
    )

    parser.add_argument(
        "-pw", 
        "--password",
        default="",
        help="Password for target node login"
    )

    parser.add_argument(
        "-b",
        "--baud",
        metavar="BAUD",
        type=int,
        default=115200,
        help="Serial baudrate (default: 115200)",
    )

    parser.add_argument(
        "-l",
        "--listen",
        nargs="+",
        choices=["telemetry", "status", "mma"],
        default=[],
        help="Print chosen data to terminal",
    )
    
    parser.add_argument(
        "--log",
        nargs="+",
        choices=["telemetry", "status", "mma"],
        default=[],
        help="Write chosen metrics to .log file(s)"
    )

    parser.add_argument(
        "--csv",
        nargs="+",
        choices=["telemetry", "status", "mma"],
        default=[],
        help="Write chosen metrics to .csv file(s)",
    )

    parser.add_argument(
        "-f",
        "--frequency",
        metavar="SECONDS",
        type=int,
        default=1800,
        help="Request frequency in seconds (default: 1800)",
    )

    parser.add_argument(
        "-o",
        "--output",
        default=os.getcwd(),
        metavar="DIR",
        help="Output directory for files (default: current directory)",
    )

    parser.add_argument(
        "--log-dir",
        metavar="DIR",
        help="Override output directory specifically for .log files"
    )

    parser.add_argument(
        "--csv-dir",
        metavar="DIR",
        help="Override output directory specifically for .csv files"
    )

    parser.add_argument(
        "--disconnect-while-idle",
        action="store_true",
        help="Disconnect from serial port while idle",
    )

    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help="Path to JSON configuration file"
    )

    parser.add_argument(
        "--save-config",
        type=Path,
        metavar="PATH",
        help="Save current configuration to a JSON file"
    )

    # Mutually exclusive verbosity group, either --verbose or --quiet
    verbosity_group = parser.add_mutually_exclusive_group(required=False)

    verbosity_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose terminal output",
    )
    verbosity_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Supress terminal output",
    )

    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")

    # Load configuration from file before parsing
    if config_args.config:

        if not config_args.config.is_file():
            parser.error(f"argument --config: path {config_args.config!r} does not exist")

        try:

            with open(config_args.config, "r", encoding="utf-8") as f:
                config = json.load(f)
                parser.set_defaults(**config)

        except json.JSONDecodeError as e:
            parser.error(f"argument --config: invalid JSON file {config_args.config!r}: {e}")

    #* PARSE ARGS
    args = parser.parse_args()
    
    if config_args.config:
        if not args.quiet:
            print(f"Using configuration from {config_args.config!r}")

    if args.save_config:
        
        if not args.save_config.suffix.lower() != "json":
            parser.error(
                "argument --save-config: configuration file must have a .json extension"
                )

        config = {}
            
        for key, value in vars(args).items():
                
            if key in ("config", "save_config"):
                continue

            if value in (None, False, []):
                continue

            if isinstance(value, Path):
                value = str(value)

            config[key] = value

        with open(args.save_config, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        if not args.quiet:
            print(f"Configuration saved to JSON file: {args.save_config}")

    #* Argument validity checking

    if not args.port or not args.node:
        parser.error("missing required argument(s): port, -n/--node")

    # Test if port is valid before proceeding
    if args.port:

        try:
            with serial.Serial(args.port) as ser: pass

        except SerialException as e:
            parser.error(f"argument port: cannot open {args.port!r} ({e})")

    # Exit the program if there is nothing to do
    if not any((args.listen, args.log, args.csv)):
        parser.error("atleast one the following arguments is required: -l/--listen, --log, --csv")

    # Cant specify output path if not writing
    if args.output != os.getcwd() and not (args.log or args.csv):
        parser.error(
            "argument -o/--output: not allowed without argument(s): --log, --csv"
        )
    
    if args.log_dir and not args.log:
        parser.error("argument --log-dir: not allowed without argument: --log")

    if args.csv_dir and not args.csv:
        parser.error("argument --csv-dir: not allowed without argument: --csv")

    if not os.path.exists(args.output):
        parser.error(f"argument -o/--output: path {args.output!r} does not exist")

    # If overrides weren't provided default to cwd
    log_path = Path(args.log_dir) if args.log_dir else Path(args.output)
    csv_path = Path(args.csv_dir) if args.csv_dir else Path(args.output)

    # Check if overrides valid
    if args.log_dir and not log_path.exists():
        parser.error(f"argument --log-dir: path {args.log_dir!r} does not exist")

    if args.csv_dir and not csv_path.exists():
        parser.error(f"argument --csv-dir: path {args.csv_dir!r} does not exist")

    # Modes
    if args.quiet:
        print("Running in quiet mode...")

    if args.verbose:
        print("Running in verbose mode!")

    if args.debug:
        print("Running in debug mode!")
        print(f"Debug: Parsed configuration: {vars(args)}")

    # * START PROGRAM

    with RuntimeTracker():
        
        try:
            asyncio.run(main())
        
        except Exception as e:
            
            # Reraises the exception if debug
            if args.debug:
                raise
            
            else:
                print(f"\nError: {e}")