import asyncio
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
from sys import argv
import logging

#logging.basicConfig()

# By default the root logger is set to WARNING and all loggers you define
# inherit that value. Here we set the root logger to NOTSET. This logging
# level is automatically inherited by all existing and new sub-loggers
# that do not set a less verbose level.
#logging.root.setLevel(logging.INFO)

email = argv[1]
password = argv[2]

async def vehicles() -> None:
    conn = Connection(email, password)
    client = Client(conn)

    vehicles = await client.getVehicles()
    for vehicle in vehicles:
        print(f"VIN: {vehicle['vin']} Model: {vehicle['modelDescription']} Year: {vehicle['modelYear']}")
        data = await conn.get(f"https://api.porsche.com/core/api/v3/se/sv_SE/vehicles/{vehicle['vin']}")
        print(f"Battery at {data['carControlData']['batteryLevel']['value']}%")

    await conn.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(vehicles())
