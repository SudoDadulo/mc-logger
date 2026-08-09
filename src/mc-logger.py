import asyncio
import argparse
import csv
import datetime as dt
import time
import sys
import os

from pathlib import Path

from meshcore import MeshCore, EventType

from runtime_tracker import RuntimeTracker

class MeshCoreLogger:

    def __init__(self, mc: MeshCore, contact: dict, args: argparse.Namespace):
        self.mc = mc
        self.contact = contact
        self.args = args

        self.is_logged_in: bool = False

        self.metrics: list[str] = []

        self.tasks: list[asyncio.coroutine] = []

        # Flags that store task completion
        self.completion_flags: list[asyncio.Event] = []

        # Store output paths as e.g. ()"telemetry", "csv"): path
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
                with open(path, "r") as file:

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
                print(f"  Error reading {path}: {e}")

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

        # Extract sensor types and corresponding values
        sensors = [sensor["type"] for sensor in lpp_data]
        values = [value["value"] for value in lpp_data]

        # Combine lists into a dict
        sensor_values = dict(zip(sensors, values))

        if "telemetry" in self.args.listen:

            print(f"\nReceived telemetry at '{timestamp}':\n")

            for sensor in sensor_values:
                print(f"{sensor} = {sensor_values[sensor]}")

        if "telemetry" in self.args.write_log:
            write_line(event.payload, timestamp, self.get_path("telemetry", "log"))

            if not self.args.quiet:
                print("\nTelemetry data written to log file.")

        if "telemetry" in self.args.write_csv:
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

        if "status" in self.args.write_log:
            write_line(
                status, timestamp, self.get_path("status", "log")
                )

            if not self.args.quiet:
                print("\nStatus data written to log file.")

        if "status" in self.args.write_csv:
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

        if "mma" in self.args.write_log:
            write_line(
                event.payload, timestamp_interval, self.get_path("mma", "log")
                )

            if not self.args.quiet:
                print("\nMin/Max/Avg data written to log file.")

        if "mma" in self.args.write_csv:
                
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

    # Generate file name with this naming scheme: "mc_data_filetype_yyyymmdd_HHMMSS.ext" e. g. "mc_telemetry_log_20260101_123030.log"
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
    
    with open(path, "w", newline="") as csvfile:
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
    with open(path, "a", newline="") as logfile:
        logline = {"timestamp": timestamp} | data
        logfile.write(f"{str(logline)}\n")


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
    with open(path, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["timestamp", *data])

        writer.writerow({"timestamp": timestamp} | data)

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
    while True:

        loop_start_time = time.monotonic()

        next_request = dt.datetime.now() + dt.timedelta(seconds=frequency)

        if not mc_logger.args.quiet:
            print("Requesting telemetry...")

        # First request
        request = await mc.commands.req_telemetry_sync(
            contact, timeout=0, min_timeout=5.0
        )

        # If failed retry request 3 times
        if request is None:
            print("Telemetry request failed!")

            for attempt in range(3):

                print(f"Retrying telemetry request...")

                request = await mc.commands.req_telemetry_sync(
                    contact, timeout=0, min_timeout=5.0
                )

                if request is not None:
                    break

                print("Telemetry request failed!", end=" ")
                print(f"(Attempt: {attempt + 1}/3)")

        # Signal completion even if fail to not stall forever
        completion_flag.set()

        # Print next request datetime 
        if not mc_logger.args.quiet:
            print(f"\nRequesting telemetry again at {next_request.strftime('%Y-%m-%d %H:%M:%S')}")

        # Calculate time it took to finish request and subtract it from the frequency
        loop_finish_time = time.monotonic() - loop_start_time
        await asyncio.sleep(max(0.0, frequency - loop_finish_time))


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
    while True:

        loop_start_time = time.monotonic()

        next_request = dt.datetime.now() + dt.timedelta(seconds=frequency)

        if not mc_logger.args.quiet:
            print("Requesting status...")

        # First request
        request = await mc.commands.req_status_sync(contact, timeout=0, min_timeout=5.0)

        # If failed retry request 3 times
        if request is None:
            print("Status request failed!")

            for attempt in range(3):

                print("Retrying status request...")

                request = await mc.commands.req_status_sync(
                    contact, timeout=0, min_timeout=5.0
                )

                if request is not None:
                    break

                print("Status request failed!", end=" ")
                print(f"(Attempt: {attempt + 1}/3)")

        # Signal completion even if fail to not stall forever
        completion_flag.set()

        # Print next request datetime 
        if not mc_logger.args.quiet:
            print(f"\nRequesting status again at {next_request.strftime('%Y-%m-%d %H:%M:%S')}")

        # Calculate time it took to finish request and subtract it from the frequency
        loop_finish_time = time.monotonic() - loop_start_time
        await asyncio.sleep(max(0.0, frequency - loop_finish_time))


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
        sync_event (asyncio.Event): Event flag signaled when the request cycle completes.

    Returns:
        None
    """
    while True:

        loop_start_time = time.monotonic()

        next_request = dt.datetime.now() + dt.timedelta(seconds=frequency)

        if not mc_logger.args.quiet:
            print("Requesting Min/Max/Avg...")

        end_time = int(time.time())
        start_time = end_time - frequency

        request = await mc.commands.req_mma_sync(
            contact, start=start_time, end=end_time, min_timeout=15.0
        )

        # If failed retry request 3 times
        if request is None:
            print("Min/Max/Avg request failed!")

            for attempt in range(3):

                print("Retrying Min/Max/Avg request...")

                request = await mc.commands.req_mma_sync(
                    contact, start=start_time, end=end_time, min_timeout=15.0
                )

                if request is not None:
                    break

                print("Min/Max/Avg request failed!", end=" ")
                print(f"(Attempt: {attempt + 1}/3)")

        # Signal completion even if fail to not stall forever
        completion_flag.set()

        # Print next request datetime 
        if not mc_logger.args.quiet:
            print(f"\nRequesting Min/Max/Avg again at {next_request.strftime('%Y-%m-%d %H:%M:%S')}")

        # Calculate time it took to finish request and subtract it from the frequency
        loop_finish_time = time.monotonic() - loop_start_time
        await asyncio.sleep(max(0.0, frequency - loop_finish_time))

# * LOGIN AND LOGOUT
async def send_login(mc, contact: dict, password: str) -> EventType.LOGIN_SUCCESS | None:

    print("Logging in...")

    # Send login request and wait for response
    login  = await mc.commands.send_login_sync(
        contact, password, timeout=0, min_timeout=10
        )

    # If login failed retry request 3 times
    if login  is None:
        print("Login failed!")

        for attempt in range(3):

            print("Retrying login...")

            login = await mc.commands.send_login_sync(
                contact, password, timeout=0, min_timeout=10
                )

            # If login success
            if login is not None:
                break

            print("Login failed!", end=" ")
            print(f"(Attempt: {attempt + 1}/3)")

    return login


async def send_logout(mc, contact: dict) -> EventType.ERROR | EventType.OK:

    # When the --disconnect-while-idle flag is active the connected device over serial
    # cant send logout request so we have to connect to send it
    if not mc.is_connected:
        await mc.connect()
        print("Connected just to send logout to repeater.")

    print("Logging out...")

    # Send login request and wait for response
    logout  = await mc.commands.send_logout(contact)

    # If login failed retry request 3 times
    if logout == EventType.ERROR:
        print("Logout failed!")

        for attempt in range(3):

            print("Retrying logout...")

            logout = await mc.commands.send_logout(contact)

            # If login success
            if logout == EventType.OK:
                break

            print("Logout failed!", end=" ")
            print(f"(Attempt: {attempt + 1}/3)")

    return logout

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
    mc = await MeshCore.create_serial(args.port, args.baudrate, debug=args.debug)
    print("Device connected!")

    try:

        # Make sure that the device has ANY contacts before searching
        if not await mc.ensure_contacts():
            print("Couldn't fetch contacts.")
            return

        # Assigns the advert name or key to the variable
        # This works because one of them is always None
        query = args.companion or args.repeater

        if not args.quiet:
            print(f"Finding companion/repeater in contacts using '{query}' ...")

        # Search the contacts for the contact search query
        # Assign it to contact for sending requests
        contact = await search_contacts(mc, query)

        # End the program because no contacts found using the search query or user inputted false or quit
        if contact is None:
            return

        # * Instantiate the MeshCoreLogger class
        mc_logger = MeshCoreLogger(mc, contact, args)

        # Login to repeater
        if args.repeater:

            # Send login to repeater
            login = await send_login(mc, contact, args.password)

            # End the program when login failed
            if login is None:
                print("The password you entered may be incorrect or the repeater may be unreachable.")
                return

            # Set state as logged in
            mc_logger.is_logged_in = True

            print("Success logging in!")

        # Exit the program if there is nothing to do
        if not args.listen and not args.write_log and not args.write_csv:
            print("Nothing to do.")
            return

        # Add metrics to the list of metrics to collect
        for metric in ["telemetry", "status", "mma"]:

            if metric in (args.listen or args.write_log or args.write_csv):
                mc_logger.add_metric(metric)

        # Create files and store paths in MeshCoreLogger.output_paths: dict[tuple[str, str], Path]
        for metric in mc_logger.metrics:

            for ext, write_flag in [("log", args.write_log), ("csv", args.write_csv)]:
                
                if metric in write_flag:

                    path = create_file(metric, ext, args.path)
                    mc_logger.store_path(metric, ext, path)

                    if not args.quiet:
                        print(f"Created {metric} {ext} file.")

                    if args.verbose:
                        print(f"Path to {metric} {ext} file: '{path}'")

        #* FIND SENSORS AND SUBSCRIBE TO EVENTS

        # This list will be passed to idle() function to track which tasks are finished
        sync_events = []

        if "telemetry" in mc_logger.metrics:

            if not args.quiet:
                print("Finding sensors...")

            telemetry = await mc.commands.req_telemetry_sync(
                contact, timeout=0, min_timeout=10.0
            )

            if telemetry is None:
                print("Failed to get sensors! Please try again!")
                return

            # This list comprehension extracts the sensor type
            sensors = [sensor["type"] for sensor in telemetry]

            # Print found sensors
            if not args.quiet:
                for sensor in sensors:
                    print(f"Found {sensor} sensor!")

            # Write telemetry csv header
            if "telemetry" in args.write_csv:

                header: list = write_header(
                    mc_logger.get_path("telemetry", "csv"), sensors
                    )

                if args.verbose:
                    print("Telemetry csv header:", end=" ")
                    print(*header, sep=", ")

            # Subscribe to event
            mc.subscribe(EventType.TELEMETRY_RESPONSE, mc_logger.on_telemetry)

            # Create asyncio.Event which gets asyncio.Event.set() when request is done
            telemetry_flag = mc_logger.create_completion_flag()

            # Append the telemetry request to the list of tasks
            mc_logger.add_task(
                req_telemetry(mc, contact, args.frequency, mc_logger, telemetry_flag)
            )

            if not args.quiet:
                print("Created telemetry request task!")

        if "status" in mc_logger.metrics:

            # Write status header
            if "status" in args.write_csv:

                status = await mc.commands.req_status_sync(
                    contact, timeout=0, min_timeout=10.0
                )

                if status is None:
                    print("Failed to get status! Please try again!")
                    return

                header: list = write_header(
                    mc_logger.get_path("status", "csv"), status
                )

                if args.verbose:
                    print("Status csv header:", end=" ")
                    print(*header, sep=", ")

            # Subscribe to event
            mc.subscribe(EventType.STATUS_RESPONSE, mc_logger.on_status)

            # Create asyncio.Event which gets asyncio.Event.set() when request is done
            status_flag = mc_logger.create_completion_flag()

            # Append the telemetry request to the list of tasks
            mc_logger.add_task(
                req_status(mc, contact, args.frequency, mc_logger, status_flag)
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

            if "mma" in args.write_csv:

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
                req_mma(mc, contact, args.frequency, mc_logger, mma_flag)
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
                await send_logout(mc, contact)

        # Diconnect cleanly, only if device is connected
        if mc.is_connected:
            await mc.disconnect()
            print("\nDisconnected from device.")

        if mc_logger is not None:
            mc_logger.print_file_stats()

if __name__ == "__main__":

    # * GLOBAL CLI ARGSPARSE BLOCK
    parser = argparse.ArgumentParser(description="MeshCore Remote Logger")

    # Positional argument port
    parser.add_argument("port", help="Serial port (e.g. 'COM4', '/dev/ttyUSB0')")

    # Mutually exclusive device group, either -c/--companion or -r/--repeater
    device_group = parser.add_mutually_exclusive_group(required=True)

    # Doesn't need password
    device_group.add_argument(
        "-c",
        "--companion",
        metavar="NAME | KEY",
        help="Target companion node",
    )

    # Needs password
    device_group.add_argument(
        "-r",
        "--repeater",
        metavar="NAME | KEY",
        help="Target repeater node (-pw/--password required)",
    )

    # Password has to be provided! if repeater
    parser.add_argument(
        "-pw", "--password", help="Password for repeater login (required if -r/--repeater)"
    )

    parser.add_argument(
        "-b",
        "--baudrate",
        metavar="BAUDRATE",
        type=int,
        default=115200,
        help="Serial baudrate (default: 115200)",
    )

    # 'What to do with data' arguments
    parser.add_argument(
        "-l",
        "--listen",
        nargs="+",
        help="Print chosen data to terminal",
        choices=["telemetry", "status", "mma"],
        default=[],
    )
    parser.add_argument(
        "--write-log",
        nargs="+",
        help="Write chosen data to .log file",
        choices=["telemetry", "status", "mma"],
        default=[],
    ),

    parser.add_argument(
        "--write-csv",
        nargs="+",
        help="Write chosen data to .csv file",
        choices=["telemetry", "status", "mma"],
        default=[],
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
        "-p",
        "--path",
        default=os.getcwd(),
        help="Directory for output files (default: current directory)",
    )

    parser.add_argument(
        "--disconnect-while-idle",
        action="store_true",
        help="Disconnect from serial port while idle",
    )

        # Mutually exclusive verbosity group, either --verbose or --quiet
    verbosity_group = parser.add_mutually_exclusive_group(required=False)

    verbosity_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose to terminal output",
    )
    verbosity_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Supress terminal output",
    )

    # --interactive cannot be used with quiet
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Enable interactive mode"
    )

    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Argument validity checking

    # Login required for repeater
    if args.repeater and not args.password:
        parser.error("argument -pw/--password: required if -r/--repeater")

    # Cant use --interactive with --quiet
    if args.quiet and args.interactive:
        parser.error("argument -q/--quiet: not allowed with argument -i/--interactive/")

    # Cant specify path if not writing
    if (
        args.path != os.getcwd()
        and (args.write_csv == [])
        and (args.write_log == [])
    ):
        parser.error(
            "argument -p/--path: not allowed without argument --write-log | --write-csv"
        )

    # If the user specified path doesn't exist, sys.exit()
    # If the user didnt use --path flag the default is the current dir which will get through the if statement
    if not os.path.exists(args.path):
        parser.error("argument -p/--path: path doesn't exist")

    # Cannot get status of a companion only a repeater for some reason :(
    if "status" in args.listen and args.companion:

        parser.error(
            "argument -c/--companion: not allowed with argument: --listen/-l ['status']"
        )

    if "status" in args.write_log and args.companion:

        parser.error(
            "argument -c/--companion: not allowed with argument: --write-log ['status']"
        )

    if "status" in args.write_csv and args.companion:

        parser.error(
            "argument -c/--companion: not allowed  with argument: --write-csv ['status']"
        )

    # Verbosity modes

    if args.quiet:
        print("Running in quiet mode...")

    if args.debug:
        print("Running in debug mode!")

    if args.interactive:
        print("Running in interactive mode!")

    if args.verbose:
        print("Running in verbose mode!")

        print("Printing active flags and their values if active!")

        # -c/--companion active
        if args.companion:
            print(
                f"Flag '-c/--companion' is active, will try to find target companion in contacts using {args.companion!r}"
            )

        # -r/--repeater active
        elif args.repeater:
            print(
                f"Flag '-r/--repeater' is active, will try to find target repeater in contacts using {args.repeater!r}"
            )
            print(
                f"Flag '-pw/--password' is active, will try to login with {args.password!r}"
            )

        if args.baudrate != 115200:

            print(f"Flag '-b/--baudrate' is active, set to {args.baudrate!r}")

        else:
            print(
                f"Flag '-b/--baudrate' is not active, baudrate set to default: {args.baudrate}"
            )

        if args.listen:

            print("Flag '-l/--listen' is active, will print", end=" ")
            print(*[f"{arg} data" for arg in args.listen], sep=", ")

        if args.write_log:

            print(f"Flag '--write-log' is active, will collect", end=" ")
            print(*[f"{arg} data" for arg in args.write_log], sep=", ")

        if args.write_csv:

            print(f"Flag '--write-csv' is active, will collect", end=" ")
            print(*[f"{arg} data" for arg in args.write_csv], sep=", ")

        if args.frequency != 1800:
            print(
                f"Flag '-f/--frequency' is active, will request data every {args.frequency} seconds"
            )
        else:
            print(
                f"Flag '-f/--frequency' is not active, frequency set to default: {args.frequency} seconds"
            )

        if args.path != os.getcwd():
            print(f"Flag '-p/--path' is active, will save files to {args.path!r}")

        # If args.path is the current working dir just print the cwd 
        else:

            if (args.write_log != [] or args.write_csv != []):
                print(
                    f"Flag '-p/--path' is not active, will save files to the current working directory:",
                    f"cwd={os.getcwd()!r}",
                    sep="\n"
                )

        if args.disconnect_while_idle:
            print(
                f"Flag '--disconnect-while-idle' is active! Will disconnect after all tasks are done and connect before the next cycle."
            )

    if args.interactive:
        print("Continue with specified arguments?", end=" ")

        while True:
            try:
                if strtobool(input("(Y/n) "), default_val=True):
                    break

                else:
                    raise SystemExit

            except ValueError:
                print("Please choose a valid option.", end=" ")

            except SystemExit:
                print("Exited.")
                sys.exit()

            except KeyboardInterrupt:
                print("\nProgram cancelled by user.")
                sys.exit()

    # * START PROGRAM

    with RuntimeTracker():
        
        try:
            asyncio.run(main())
        
        except Exception as e:
            
            # Reraises the exception
            if args.debug:
                raise
            
            else:
                print(f"\nError: {e}")