import asyncio
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.account import PorscheConnectAccount
from sys import argv
import logging

logging.basicConfig()

# Invoke like this: python ./examples/example.py <your email> <your password>
# By default the root logger is set to WARNING and all loggers you define
# inherit that value. Here we set the root logger to NOTSET. This logging
# level is automatically inherited by all existing and new sub-loggers
# that do not set a less verbose level.
logging.root.setLevel(logging.DEBUG)

email = argv[1]
password = argv[2]


async def vehicles() -> None:
    conn = Connection(email, password)
    client = PorscheConnectAccount(connection=conn)

    vehicles = await client.get_vehicles()
    for vehicle in vehicles:
        print(
            f"VIN: {vehicle.vin}, Model: {vehicle.model_name}, Year: {vehicle.model_year}"
        )

    await conn.close()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(vehicles())
    except KeyboardInterrupt:
        pass
