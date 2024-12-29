# pyporscheconnectapi
A python library for Porsche Connect API

This library will let you access your car equipped with Porsche Connect. It does not work with the predecessor Porsche Car Connect.
Porsche Connect is available for the following Porsche models:

* Boxster & Cayman (718)
* 911 (from 992)
* Taycan
* Panamera (from 2021, G2 PA)
* Macan (EV, from 2024)
* Cayenne (from 2017, E3)

You can also take a look here, select your model and see if your model has support for Porsche Connect:
https://connect-store.porsche.com/

A Porsche Connect subscription alse needs to be active for it to work.

*NOTE:* This work is not officially supported by Porsche and functionality can stop working at any time without warning.

## Installation

The easiest method is to install using pip3/pip (venv is also a good idea).
```
pip install pyporscheconnectapi
```

to update to the latest version

```
pip install pyporscheconnectapi -U
```

Setup will add a cli under the name porschecli, see below for usage.


## CLI usage

A simple cli is provided with this library, it will cache tokens to a file to speed up invocations.

If no email or password is supplied as input arguments and no config file with those details is found you will be prompted.
```
usage: porschecli [-h] [-d] [-e EMAIL] [-p PASSWORD] [-s SESSION_FILE] [--nowait]
                  {list,token,capabilities,currentoverview,storedoverview,trip_statistics,pictures,location,climatise_on,climatise_off,direct_charge_on,direct_charge_off,flash_indicators,honk_and_flash,lock_vehicle,unlock_vehicle,vehicle_closed,doors_and_lids,tire_pressure_status,tire_pressures,chargingprofile}
                  ...

Porsche Connect CLI

positional arguments:
  {list,token,capabilities,currentoverview,storedoverview,trip_statistics,pictures,location,climatise_on,climatise_off,direct_charge_on,direct_charge_off,flash_indicators,honk_and_flash,lock_vehicle,unlock_vehicle,vehicle_closed,doors_and_lids,tire_pressure_status,tire_pressures,chargingprofile}
                        command help
    battery             Prints the main battery level (BEV)
    capabilities        Get vehicle capabilities
    chargingprofile     Update parameters in configured charging profile
    climatise_off       Stop remote climatisation
    climatise_on        Start remote climatisation
    connected           Check if vehicle is on-line
    currentoverview     Get stored overview for vehicle
    direct_charge_off   Disable direct charging
    direct_charge_on    Enable direct charging
    doors_and_lids      List status of all doors and lids
    flash_indicators    Flash indicators
    honk_and_flash      Flash indicators and sound the horn
    location            Show location of vehicle
    lock_vehicle        Lock vehicle
    pictures            Get vehicle pictures url
    storedoverview      Poll vehicle for current overview
    tire_status         Check if tire pressure are ok
    tire_pressures      Get tire pressure readings
    trip_statistics     Get trip statistics from backend
    unlock_vehicle      Unlock vehicle
    vehicle_closed      Check if all doors and lids are closed

options:
  -h, --help            show this help message and exit
  -d, --debug
  -e EMAIL, --email EMAIL
  -p PASSWORD, --password PASSWORD
  -s SESSION_FILE, --sessionfile SESSION_FILE

```

## Config file (for CLI)

A config file is searched for in ~/.porscheconnect.cfg and ./.porscheconnect.cfg
The format is:

```
[porsche]
email=<your email>
password=<your password>
session_file=<file to store session information>
```

## Library usage

Install pyporscheconnectapi using pip (requires python >= 3.10)


### Example client usage

Please refer to the examples provided in the repository.
