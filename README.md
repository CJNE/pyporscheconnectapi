# pyporscheconnectapi
A python library for Porsche Connect API

*NOTE:* This work is not officially supported by Porsche and functionality can stop working at any time without warning

## Usage

Install pyporscheconnectapi using pip (requires python > 3.6)

Example 
```
import asyncio
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
email = ..your porsche connect email...
password = ...your porsche connect password...

async def vehicles() -> None:
    conn = Connection(email, password)
    client = Client(conn)

    vehicles = await client.getVehicles()
    for vehicle in vehicles:
        print(f"VIN: {vehicle['vin']} Model: {vehicle['modelDescription']} Year: {vehicle['modelYear']}")

    await conn.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(vehicles())
```


## Credits
[evcc](https://github.com/andig/evcc) was a good resource for figuring out the Authentication flow



