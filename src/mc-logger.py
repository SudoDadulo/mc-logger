import asyncio
import argparse
import csv
import datetime as dt
import time
import sys
import os

from pathlib import Path

from meshcore import MeshCore, EventType

# * GLOBAL VARIABLES

"""
I don't know how else to get these variables to the event handlers, so instead I made them global.
They are declared as global in main()

telemetry_log_path
telemetry_csv_path

status_log_path
status_csv_path

mma_log_path
mma_csv_path
"""


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
def create_file(file_type: str, data: str, path: str) -> tuple[str, Path]:
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
        f"mc_{data}_log_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}.{file_type}"
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
                    sys.exit(f"Exited cleanly without overwriting file.")

            except ValueError:
                print("Please choose a valid option. ")

    return file_name, abs_file_path


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


# * EVENT HANDLERS
async def on_telemetry(event: EventType.TELEMETRY_RESPONSE) -> None:
    """
    Handle a telemetry response event.

    Args:
        event (EventType.TELEMETRY_RESPONSE): Telemetry event data

    Returns:
        None
    """
    if not args.quiet:
        print("\nSuccess requesting telemetry!")

    # Get the lpp formatted data
    lpp_data = event.payload["lpp"]

    timestamp = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Extract sensor types and corresponding values
    sensors = [sensor["type"] for sensor in lpp_data]
    values = [value["value"] for value in lpp_data]

    # Combine lists into a dict
    sensor_values = dict(zip(sensors, values))

    if "telemetry" in args.listen:

        print(f"\nReceived telemetry at '{timestamp}':\n")

        for sensor in sensor_values:
            print(f"{sensor} = {sensor_values[sensor]}")

    if "telemetry" in args.write_log:
        write_line(event.payload, timestamp, telemetry_log_path)

        if not args.quiet:
            print("\nTelemetry data written to log file.")

    if "telemetry" in args.write_csv:
        write_row(sensor_values, timestamp, telemetry_csv_path)

        if not args.quiet:
            print("\nTelemetry data written to csv file.")


async def on_status(event: EventType.STATUS_RESPONSE) -> None:
    """
    Handle a status response event.

    Args:
        event (EventType.STATUS_RESPONSE): Status event data

    Returns:
        None
    """
    if not args.quiet:
        print("\nSuccess requesting status!")

    # Assing the payload to var
    status = event.payload

    # Get timestamp
    timestamp = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    if "status" in args.listen:

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

    if "status" in args.write_log:
        write_line(status, timestamp, status_log_path)

        if not args.quiet:
            print("\nStatus data written to log file.")

    if "status" in args.write_csv:
        write_row(status, timestamp, status_csv_path)

        if not args.quiet:
            print("\nStatus data written to csv file.")


async def on_mma(event: EventType.MMA_RESPONSE) -> None:
    """
    Handle a Min/Max/Avg response event.

    Args:
        event (EventType.MMA_RESPONSE): Min/Max/Avg event data

    Returns:
        None
    """
    if not args.quiet:
        print("\nSuccess requesting Min/Max/Avg!")

    # assing the payload to var
    mma_data = event.payload["mma_data"]

    # Get now timestamp
    end_timestamp = dt.datetime.now().timestamp()

    # Convert the frequency argument to a timedelta object
    delta_timestamp = dt.timedelta(seconds=args.frequency)

    start_timestamp = end_timestamp - delta_timestamp

    # ISO-8601 format for time intervals in log and csv
    # 2007-03-01T13:00:00/2008-05-11T15:30:00
    timestamp_interval = f"{start_timestamp.strftime('%Y-%m-%dT%H:%M:%S')}/{end_timestamp.strftime('%Y-%m-%dT%H:%M:%S')}"

    if "mma" in args.listen:

        print(f"\nReceived Min/Max/Avg at '{end_timestamp.strftime("%Y-%m-%dT%H:%M:%S")}' :")

        print(
            f"\nTime range: {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {end_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        for mma in mma_data:

            print(f"\nChannel {mma['channel']}: {mma['type']}")
            print(f"  Min: {mma['min']}")
            print(f"  Max: {mma['max']}")
            print(f"  Avg: {mma['avg']}")

    if "mma" in args.write_log:
        write_line(event.payload, timestamp_interval, mma_log_path)

        if not args.quiet:
            print("\nMin/Max/Avg data written to log file.")

    if "mma" in args.write_csv:
            
        mma_sensor_values = {}
        for mma_sensor in mma_data:

            sensor_type = mma_sensor["type"]

            mma_sensor_values.update({f"{sensor_type}_min": mma_sensor['min']})
            mma_sensor_values.update({f"{sensor_type}_max": mma_sensor['max']})
            mma_sensor_values.update({f"{sensor_type}_avg": mma_sensor['avg']})

        write_row(mma_sensor_values, timestamp_interval, mma_csv_path)

        if not args.quiet:
            print("\nMin/Max/Avg data written to csv file.")


# * TASKS
async def idle(mc, frequency: int, sync_events: list[asyncio.Event]) -> None:
    """
    Disconnect while idle, wait until all requests are finished.

    Args:
        mc (Meshcore instance): Connected MeshCore instance.
        frequency (int): Time in seconds between disconnecting and connecting.
        sync_events (list[asyncio.Event]): Tasks that need to finish before disconnecting.

    Returns:
        None
    """

    while True:

        if not mc.is_connected:
            await mc.connect()
            print("Connected to device.")

        if args.verbose:
            print(
                f"Waiting for all active backround tasks to finish before disconnecting..."
            )

        # Wait until every event in the list has been set to True
        await asyncio.gather(*[event.wait() for event in sync_events])

        # Padding to allow event handlers to finish
        await asyncio.sleep(1.5)

        if mc.is_connected:
            await mc.disconnect()
            print(f"\nDisconnected from device, will connect again before next cycle.")

        # Reset all events to False for the next cycle
        for event in sync_events:
            event.clear()

        # Sleep until just before next cycle
        await asyncio.sleep(frequency - 5)


async def req_telemetry(
    mc, contact: dict, frequency: int, sync_event: asyncio.Event
) -> None:
    """
    Request telemetry from contact and trigger a telemetry response event.

    Args:
        mc (MeshCore instance): Connected MeshCore instance
        contact (dict): Contact from which to request telemetry
        frequency (int): Time in seconds between telemetry requests

    Returns:
        None
    """

    while True:

        loop_start_time = time.monotonic()

        next_request = dt.datetime.now() + dt.timedelta(seconds=frequency)

        if not args.quiet:
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
        sync_event.set()

        # Print next request datetime 
        if not args.quiet:
            print(f"\nRequesting telemetry again at {next_request.strftime('%Y-%m-%d %H:%M:%S')}")

        # Calculate time it took to finish request and subtract it from the frequency
        loop_finish_time = time.monotonic() - loop_start_time
        await asyncio.sleep(frequency - loop_finish_time)


async def req_status(
    mc, contact: dict, frequency: int, sync_event: asyncio.Event
) -> None:
    """
    Request status from contact and trigger a status response event.

    Args:
        mc (MeshCore instance): Connected MeshCore instance
        contact (dict): Contact from which to request status
        frequency (int): Time in seconds between status requests

    Returns:
        None
    """

    while True:

        loop_start_time = time.monotonic()

        next_request = dt.datetime.now() + dt.timedelta(seconds=frequency)

        if not args.quiet:
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
        sync_event.set()

        # Print next request datetime 
        if not args.quiet:
            print(f"\nRequesting status again at {next_request.strftime('%Y-%m-%d %H:%M:%S')}")

        # Calculate time it took to finish request and subtract it from the frequency
        loop_finish_time = time.monotonic() - loop_start_time
        await asyncio.sleep(frequency - loop_finish_time)


async def req_mma(mc, contact: dict, frequency: int, sync_event: asyncio.Event) -> None:
    """
    Request Min/Max/Avg from contact and trigger a MMA response event.

    Args:
        mc (MeshCore instance): Connected MeshCore instance
        contact (dict): Contact from which to request Min/Max/Avg
        frequency (int): Time in seconds between Min/Max/Avg requests

    Returns:
        None
    """

    while True:

        loop_start_time = time.monotonic()

        next_request = dt.datetime.now() + dt.timedelta(seconds=frequency)

        if not args.quiet:
            print("Requesting Min/Max/Avg...")

        end_time = int(time.time())
        start_time = end_time - 3600

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
        sync_event.set()

        # Print next request datetime 
        if not args.quiet:
            print(f"\nRequesting Min/Max/Avg again at {next_request.strftime('%Y-%m-%d %H:%M:%S')}")

        # Calculate time it took to finish request and subtract it from the frequency
        loop_finish_time = time.monotonic() - loop_start_time
        await asyncio.sleep(frequency - loop_finish_time)


async def send_login(contact: dict, password: str) -> EventType.LOGIN_SUCCESS | None:

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
    if login == EventType.ERROR:
        print("Login failed!")

        for attempt in range(3):

            print("Retrying login...")

            login = await mc.commands.send_logout(contact)

            # If login success
            if login == EventType.OK:
                break

            print("Login failed!", end=" ")
            print(f"(Attempt: {attempt + 1}/3)")

    return login

def search_contacts(mc, query: str) -> dict | None:

    # Try to find contact by name and return it
    by_name = mc.get_contact_by_name(query)

    if by_name is not None:
        contact: dict = by_name
        
        return contact

    # Try to find contact by public key prefix and return it
    by_key = mc.get_contact_by_key_prefix(query)

    if by_key is not None:
        contact: dict = by_key

        return contact

    # If contact was not found
    return None

async def main():

    # These values are difficult to access cleanly so I made them global
    global telemetry_log_path
    global telemetry_csv_path

    global status_log_path
    global status_csv_path

    global mma_log_path
    global mma_csv_path

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

        # Set the contacts search query for a companion
        if args.companion:

            query = args.companion

            if not args.quiet:
                print(f"Finding companion in contacts using '{query}' ...")

        # Set the contacts search query for a repeater
        if args.repeater:

            query = args.repeater

            if not args.quiet:
                print(f"Finding repeater in contacts using '{query}' ...")

        # Search the contacts for the contact search query
        # Assign it to contact for sending requests
        contact = search_contacts(mc, query)

        # If the contact wasn't found by name or key
        if contact is None:

            print(
                f"Couldn't find companion/repeater in contacts using '{query}'."
            )
            print("Print available contacts?", end=" ")

            response = await mc.commands.get_contacts()
            contacts = response.payload

            while True:
                try:

                    if strtobool(input("(Y/n) "), default_val=True):
                        print("\nAvailable contacts:")
                        
                        for contact in contacts.values():
                            print(f"{contact['adv_name']}: {contact['public_key']}")

                    break

                except ValueError:
                    print("Please choose a valid option.", end=" ")

            # Ends the program because no contacts found using the search query
            return

        # Login to repeater
        if args.repeater:

            # Send login to repeater
            login = await send_login(contact, args.password)

            # End the program when login failed
            if login is None:
                return

            print("Success logging in!")

        # * Construct task list, data to request list and sync events list

        # This list used to provide list of tasks to asyncio.gather()
        list_of_tasks = []

        # This is a list to determine to which event to subscribe to using meshcore.subscribe()
        data_to_request = []

        # This list will be passed to idle() function to track which tasks are finished
        sync_events = []

        if not args.listen and not args.write_log and not args.write_csv:
            print("Nothing to do.")
            return

        #*LISTEN BRANCH

        if "telemetry" in args.listen:

            data_to_request.append("telemetry")

        if "status" in args.listen:

            data_to_request.append("status")

        if "mma" in args.listen:

            data_to_request.append("mma")

        #* LOG BRANCH

        if "telemetry" in args.write_log:

            data_to_request.append("telemetry")

            # gets the csv name and the telemetry csv path (global)
            telemetry_log_name, telemetry_log_path = create_file(
                "log", "telemetry", args.path
            )

            if not args.quiet:
                print("Created telemetry log file.")

            if args.verbose:
                print(f"Path to telemetry log file: '{telemetry_log_path}'")

        if "status" in args.write_log:

            data_to_request.append("status")

            status_log_name, status_log_path = create_file(
                "log", "status", args.path
            )

            if not args.quiet:
                print("Created status log file.")

            if args.verbose:
                print(f"Path to status log file: '{status_log_path}'")

        if "mma" in args.write_log:

            data_to_request.append("mma")

            mma_log_name, mma_log_path = create_file("log", "mma", args.path)

            if not args.quiet:
                print("Created Min/Max/Avg log file.")

            if args.verbose:
                print(f"Path to Min/Max/Avg log file: '{mma_log_path}'")

        #* CSV BRANCH

        if "telemetry" in args.write_csv:

            data_to_request.append("telemetry")

            # gets the telemetry csv name and the telemetry csv path (global)
            telemetry_csv_name, telemetry_csv_path = create_file(
                "csv", "telemetry", args.path
            )

            if not args.quiet:
                print("Created telemetry csv file.")

            if args.verbose:
                print(f"Path to telemetry csv file: '{telemetry_csv_path}'")

        if "status" in args.write_csv:

            data_to_request.append("status")

            # gets the status csv name and the status csv path (global)
            status_csv_name, status_csv_path = create_file(
                "csv", "status", args.path
            )

            if not args.quiet:
                print("Created status csv file.")

            if args.verbose:
                print(f"Path to status csv file: '{status_csv_path}'")

        if "mma" in args.write_csv:

            data_to_request.append("mma")

            # gets the mma csv name and the mma csv path (global)
            mma_csv_name, mma_csv_path = create_file("csv", "mma", args.path)

            if not args.quiet:
                print("Created Min/Max/Avg csv file.")

            if args.verbose:
                print(f"Path to Min/Max/Avg csv file: '{mma_csv_path}'")

        # Remove duplicates from data_to_request
        data_to_request = list(set(data_to_request))

        #* FIND SENSORS AND SUBSCRIBE TO EVENTS

        if "telemetry" in data_to_request:

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

                with open(telemetry_csv_path, "w", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["timestamp", *sensors])
                    writer.writeheader()

                    if args.verbose:
                        print("Telemetry csv header:", end=" ")
                        print(*writer.fieldnames, sep=", ")

            # Subscribe to event
            mc.subscribe(EventType.TELEMETRY_RESPONSE, on_telemetry)

            # Create a asyncio event to only disconnect when all tasks are done
            # This is for the --disconnect-while-idle flag
            tele_event = asyncio.Event()
            sync_events.append(tele_event)

            # Append the telemetry request to the list of tasks
            list_of_tasks.append(req_telemetry(mc, contact, args.frequency, tele_event))

            if not args.quiet:
                print("Created telemetry request task!")

        if "status" in data_to_request:

            # Write status header
            if "status" in args.write_csv:

                status = await mc.commands.req_status_sync(
                    contact, timeout=0, min_timeout=10.0
                )

                if status is None:
                    print("Failed to get status! Please try again!")
                    return

                with open(status_csv_path, "w", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["timestamp", *status])
                    writer.writeheader()

                    if args.verbose:
                        print("Status csv header:", end=" ")
                        print(*writer.fieldnames, sep=", ")

            # Subscribe to event
            mc.subscribe(EventType.STATUS_RESPONSE, on_status)

            # Create a asyncio event to only disconnect when all tasks are done
            # This is for the --disconnect-while-idle flag
            stat_event = asyncio.Event()
            sync_events.append(stat_event)

            # Append the telemetry request to the list of tasks
            list_of_tasks.append(req_status(mc, contact, args.frequency, stat_event))

            if not args.quiet:
                print("Created status request task!")

        if "mma" in data_to_request:

            if not args.quiet:
                print("Finding sensors that support Min/Max/Avg data output...")

            end_time = int(time.time())
            start_time = start_time = end_time - 3600

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

                with open(mma_csv_path, "w", newline="") as csvfile:
                    writer = csv.DictWriter(
                        csvfile, fieldnames=["timestamp", *sensor_header]
                    )
                    writer.writeheader()

                    if args.verbose:
                        print("Min/Max/Avg csv header:", end=" ")
                        print(*writer.fieldnames, sep=", ")

            # Subscribe to event
            mc.subscribe(EventType.MMA_RESPONSE, on_mma)

            # Create a asyncio event to only disconnect when all tasks are done
            # This is for the --disconnect-while-idle flag
            mma_event = asyncio.Event()
            sync_events.append(mma_event)

            # Append the telemetry request to the list of tasks
            list_of_tasks.append(req_mma(mc, contact, args.frequency, mma_event))

            if not args.quiet:
                print("Created Min/Max/Avg request task!")

        # Insert the idle tasks to the start of list_of_tasks
        if args.disconnect_while_idle:
            list_of_tasks.insert(0, idle(mc, args.frequency, sync_events))

        #* START TASKS
        await asyncio.gather(*list_of_tasks)

    finally:

        #if args.repeater:

            # Send logout
            #logout = await send_logout(mc, contact)

            #if logout is EventType.ERROR:
            #    print("Still logged in!")

            #if logout is EventType.OK:
            #    print("Logged out successfully.")

        # Diconnect cleanly if device is connected
        if mc.is_connected:
            await mc.disconnect()
            print("\nDisconnected from device.")


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
        help="Target repeater node (pw required)",
    )

    # Password has to be provided! if repeater
    parser.add_argument(
        "-pw", "--password", help="Password for repeater login (required if --repeater)"
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
                f"Flag '-f/--frequency' is not active, frequecy set to default: {args.frequency} seconds"
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
                    print("Exited.")
                    sys.exit()

            except ValueError:
                print("Please choose a valid option.", end=" ")

    # * START PROGRAM

    prog_start_time = dt.datetime.now()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram cancelled by user.")
    except asyncio.exceptions.CancelledError:
        print("\nProgram cancelled by user.")
    #except Exception as e:
        #print(f"Error: {e}")

    finally:

        prog_end_time = dt.datetime.now()
        prog_run_time = prog_end_time - prog_start_time

        print(f"\nProgram runtime statistics:")
        print(f"Start: {prog_start_time.strftime("%Y-%m-%d %H:%M:%S")}")
        print(f"End: {prog_end_time.strftime("%Y-%m-%d %H:%M:%S")}")
        print(f"Runtime: {prog_run_time.days} days, {prog_run_time.seconds} seconds")

        # Needs to be inside a try block if the paths of the files weren't defined it will raise a NameError and do nothing
        try:

            # LOG FILE STATISTICS

            if "telemetry" in args.write_log and telemetry_log_path is not None:

                with open(telemetry_log_path, "r") as logfile:
                    for line_number, line_content in enumerate(logfile, start=1):
                        pass  # Just iterate

                print(f"Telemetry log: wrote {line_number} lines")

            if "status" in args.write_log and status_log_path is not None:

                with open(status_log_path, "r") as logfile:
                    for line_number, line_content in enumerate(logfile, start=1):
                        pass  # Just iterate

                print(f"Status log: wrote {line_number} lines")

            if "mma" in args.write_log and mma_log_path is not None:

                with open(mma_log_path, "r") as logfile:
                    for line_number, line_content in enumerate(logfile, start=1):
                        pass  # Just iterate

                print(f"Min/Max/Avg log: wrote {line_number} lines")

            # CSV FILE STATISTICS
            # Substracting 1 from every row to not count the header

            if "telemetry" in args.write_csv and telemetry_csv_path is not None:

                with open(telemetry_csv_path, "r") as csvfile:
                    for row_number, row_content in enumerate(csvfile, start=1):
                        pass  # Just iterate

                print(f"Telemetry csv: wrote {row_number - 1} rows")

            if "status" in args.write_csv and status_csv_path is not None:

                with open(status_csv_path, "r") as csvfile:
                    for row_number, row_content in enumerate(csvfile, start=1):
                        pass  # Just iterate

                print(f"Status csv: wrote {row_number - 1} rows")

            if "mma" in args.write_csv and mma_csv_path is not None:

                with open(mma_csv_path, "r") as csvfile:
                    for row_number, row_content in enumerate(csvfile, start=1):
                        pass  # Just iterate

                print(f"Min/Max/Avg csv: wrote {row_number - 1} rows")

        # Just not to show an exception to the user
        # Catches the exception that is trown if any of the paths to files are undefined
        except NameError:
            pass
