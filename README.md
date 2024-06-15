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

Setup will add a cli under the name porschecli, see below for usage.


## CLI usage

A simple cli is provided with this library, it will cache tokens to a file to speed up invocations.

If no email or password is supplied as input arguments and no config file with those details is found you will be prompted. Same goes for PIN (used to lock or unlock).

The --nowait option will just request the action (or stored information) without waiting for confirmation.

The --help option will provide help for usage.


## Config file (for CLI)

A config file is searched for in ~/.porscheconnect.cfg and ./.porscheconnect.cfg
The format is:

```
[porsche]
email=<your email>
password=<your password>
```

## Library usage

Install pyporscheconnectapi using pip (requires python > 3.6). For examples on usage, c.f. to the examples directory.
