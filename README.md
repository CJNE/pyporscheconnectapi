# pyporscheconnectapi
A python library for Porsche Connect API

This is a very early release, things are changing rapidly so use at your own risk!

*NOTE:* This work is not officially supported by Porsche and functionality can stop working at any time without warning

## CLI usage

A simple cli is provided with this library, it will cache tokens to a file to speed up invocations

```
usage: porschecli [-h] -e EMAIL -p PASSWORD [-s SESSION_FILE] [-v VIN] [-m MODEL]
              [-a] [-c COUNTRY] [-l LANGUAGE] [-z TIMEZONE]
              {list,overview,maintenance,summary,capabilities,emobility,position,triplongterm,tripshortterm,speedalerts,theftalerts}

Porsche Connct CLI.

positional arguments:
  {list,overview,maintenance,summary,capabilities,emobility,position,triplongterm,tripshortterm,speedalerts,theftalerts}

optional arguments:
  -h, --help            show this help message and exit
  -e EMAIL, --email EMAIL
  -p PASSWORD, --password PASSWORD
  -s SESSION_FILE, --sessionfile SESSION_FILE
  -v VIN, --vin VIN
  -m MODEL, --model MODEL
  -a, --all
  -c COUNTRY, --country COUNTRY
  -l LANGUAGE, --language LANGUAGE
  -z TIMEZONE, --timezone TIMEZONE
```

## Library usage

Install pyporscheconnectapi using pip (requires python > 3.6)


### Example client usage
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

### Example connection usage for custom requests 
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
        # Using connection.get will automatically add auth headers 
        data = await conn.get(f"https://api.porsche.com/core/api/v3/se/sv_SE/vehicles/{vehicle['vin']}")
        print(f"Battery at {data['carControlData']['batteryLevel']['value']}%")

    await conn.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(vehicles())
```




## Credits
[evcc](https://github.com/andig/evcc) was a good resource for figuring out the Authentication flow



