import asyncio
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
from sys import argv
import logging
from getpass import getpass

from datetime import datetime, timedelta

# logging.basicConfig()
# logging.root.setLevel(logging.DEBUG)

email = argv[1]
if len(argv) > 2:
    password = argv[2]
else:
    password = getpass()


async def vehicles() -> None:
    conn = Connection(email, password)
    client = Client(conn)

    vehicles = await client.getVehicles()
    vin = ""

    # Pick the first vehicle
    for vehicle in vehicles:
        print(
            f"VIN: {vehicle['vin']} Model: {vehicle['modelDescription']} Year: {vehicle['modelYear']}"
        )
        vin = vehicle["vin"]
        break

    # Create timer for 4 hours from now, non-repeating, climate and charge active
    time = datetime.now() + timedelta(hours=4)
    result = await client.newTimer(
        vin, time, active=True, climate=True, charge=True, target_charge=25
    )

    # Uncomment to update timer #2 for 4 hours from now, repeating M/W/F,
    # only charging active with target of 25%
    # TODO: Repeating timer creation not working yet
    # (Updating of timers works fine, including updating nonrepeating
    # into repeating timers)
    # result = await client.updateTimer(vin, time, timerID="2", active=True, charge=True, target_charge=25, repeat_days=[0,2,4])

    # Uncomment to delete timer #2
    # result = await client.deleteTimer(vin, timerID="2")

    await conn.close()


loop = asyncio.get_event_loop()
loop.run_until_complete(vehicles())
