"""Example code for using the pyporscheconnectapi library."""

import asyncio
import contextlib
from sys import argv

from pyporscheconnectapi.account import PorscheConnectAccount
from pyporscheconnectapi.connection import Connection

email = argv[1]
password = argv[2]


async def vehicles() -> None:
    """Make request to the API and parse out batteri level and vehicle lock status."""
    conn = Connection(email, password)
    client = PorscheConnectAccount(connection=conn)

    vehicles = await client.get_vehicles()
    for vehicle_obj in vehicles:
        vehicle = vehicle_obj.data

        print(
            f"VIN: {vehicle['vin']}, Model: {vehicle['modelName']}, Year: {vehicle['modelType']['year']}",
        )
        mf = ["BATTERY_LEVEL", "LOCK_STATE_VEHICLE"]
        measurements = "mf=" + "&mf=".join(mf)
        data = await conn.get(
            f"/connect/v1/vehicles/{vehicle['vin']}?{measurements}",
        )

        soc = (next((x for x in data["measurements"] if x["key"] == mf[0]), None))[
            "value"
        ]["percent"]
        locked = (next((x for x in data["measurements"] if x["key"] == mf[1]), None))[
            "value"
        ]["isLocked"]

        print(f"Battery level is at {soc}%")
        print(f"The vehicle is locked: {locked}")

    await conn.close()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with contextlib.suppress(KeyboardInterrupt):
        loop.run_until_complete(vehicles())
