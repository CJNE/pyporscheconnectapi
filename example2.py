import asyncio
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
from sys import argv
import logging

# logging.basicConfig()
# logging.root.setLevel(logging.DEBUG)

email = argv[1]
password = argv[2]

async def vehicles() -> None:
    conn = Connection(email, password)
    client = Client(conn)

    vehicles = await client.getVehicles()
    for vehicle in vehicles:
        print(f"VIN: {vehicle['vin']} Model: {vehicle['modelDescription']} Year: {vehicle['modelYear']}")
        data = await conn.get(f"https://api.porsche.com/service-vehicle/se/sv_SE/vehicle-data/{vehicle['vin']}/stored")
        #if data['batteryLevel'] is not None:
        print(f"Battery at {data['batteryLevel']['value']}%")
        print(f"Locked or open? {data['overallOpenStatus']}")

    await conn.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(vehicles())
