# pyporscheconnectapi
A python library for Porsche Connect API

This library will let you access your car equipped with Porsche Connect. It does not work with the predecessor Porsche Car Connect.
Porsche Connect is available for the following Porsche models:

* Taycan
* 911 (from 992)
* Cayenne (from 2017, E3)
* Panamera (from 2021, G2 PA)

You can also take a look here, select your model and see if your model has support for Porsche Connect:
https://connect-store.porsche.com/

A Porsche Connect subscription alse needs to be active for it to work.

*NOTE:* This work is not officially supported by Porsche and functionality can stop working at any time without warning

## Installation

The easiest method is to install using pip3/pip (venv is also a good idea)
```
pip install pyporscheconnectapi
```

to update to the latest version

```
pip install pyporscheconnectapi -U
```

Setup will add a cli under the name porschecli, see below for usage


## CLI usage

A simple cli is provided with this library, it will cache tokens to a file to speed up invocations. It does not yet support the create/update/delete timer functionality which is present in the library.

If no email or password is supplied as input arguments and no config file with those details is found you will be prompted. Same goes for PIN (used to lock or unlock).
The --nowait option will just request the action (or stored information) without waiting for confirmation.
```
usage: cli.py [-h] [-e EMAIL] [-p PASSWORD] [-s SESSION_FILE] [-v VIN]
              [-n PIN] [-m MODEL] [-a] [-c COUNTRY] [-l LANGUAGE]
              [-z TIMEZONE] [--nowait]
              {list,overview,maintenance,summary,capabilities,emobility,position,triplongterm,tripshortterm,speedalerts,theftalerts,tokens,lock,unlock,climate-on,climate-off,directcharge-on,directcharge-off}

Porsche Connect CLI.

positional arguments:
  {list,overview,maintenance,summary,capabilities,emobility,position,triplongterm,tripshortterm,speedalerts,theftalerts,tokens,lock,unlock,climate-on,climate-off,directcharge-on,directcharge-off}

optional arguments:
  -h, --help            show this help message and exit
  -e EMAIL, --email EMAIL
  -p PASSWORD, --password PASSWORD
  -s SESSION_FILE, --sessionfile SESSION_FILE
  -v VIN, --vin VIN
  -n PIN, --pin PIN
  -m MODEL, --model MODEL
  -a, --all
  -c COUNTRY, --country COUNTRY
  -l LANGUAGE, --language LANGUAGE
  -z TIMEZONE, --timezone TIMEZONE
  --nowait
```

## Config file (for CLI)

A config file is searched for in ~/.porscheconnect.cfg and ./.porscheconnect.cfg
The format is:

```
[porsche]
email=<your email>
password=<your password>
country=<country iso code, default DE>
language=<lang abbreviation, default de>
timezone=<default Europe/Stockholm>
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
