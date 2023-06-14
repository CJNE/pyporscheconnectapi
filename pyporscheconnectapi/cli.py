import argparse
import asyncio
import configparser
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
from pyporscheconnectapi.exceptions import WrongCredentials
import os
import sys
import logging
import json
from getpass import getpass

try:
    from rich import print
except ImportError:
    pass

logging.basicConfig()
logging.root.setLevel(logging.WARNING)

_LOGGER = logging.getLogger(__name__)

async def main(args):
    try:
        with open(args.session_file) as json_file:
            tokens = json.load(json_file)
    except FileNotFoundError:
        tokens = {}
    except json.decoder.JSONDecodeError:
        tokens = {}

    if args.debug:
        logging.root.setLevel(logging.DEBUG)

    email = args.email or input("Please enter Porsche Connect email: ")
    password = args.password or getpass()
    conn = Connection(
        email, password, tokens=tokens, country=args.country, language=args.language
    )

    client = Client(
        conn, country=args.country, language=args.language, timezone=args.timezone
    )

    try:
        if args.command == "list":
            data = await client.getVehicles()
            print(json.dumps(data, indent=2))
        elif args.command == "tokens":
            data = await client.getAllTokens()
            print(json.dumps(data, indent=2))
        else:
            vins = []
            if args.vin is not None:
                vins = [args.vin]
            elif args.all:
                vehicles = await client.getVehicles()
                vins = map(lambda v: v["vin"], vehicles)
            else:
                sys.exit("--vin or --all is required")
            for vin in vins:
                data = {}
                if args.command == "overview":
                    if args.nowait:
                        data = await client.getStoredOverview(vin)
                    else:
                        data = await client.getCurrentOverview(vin)
                elif args.command == "maintenance":
                    data = await client.getMaintenance(vin)
                elif args.command == "summary":
                    data = await client.getSummary(vin)
                elif args.command == "capabilities":
                    data = await client.getCapabilities(vin)
                elif args.command == "permissions":
                    data = await client.isAllowed(vin)
                elif args.command == "services":
                    data = await client.getServices(vin)
                elif args.command == "position":
                    data = await client.getPosition(vin)
                elif args.command == "emobility":
                    data = await client.getEmobility(vin, model=args.model)
                elif args.command == "triplongterm":
                    data = await client.getTripLongTerm(vin)
                elif args.command == "tripshortterm":
                    data = await client.getTripShortTerm(vin)
                elif args.command == "speedalerts":
                    data = await client.getSpeedAlerts(vin)
                elif args.command == "theftalerts":
                    data = await client.getTheftAlerts(vin)
                elif args.command == "climate-on":
                    data = await client.climateOn(
                        vin, waitForConfirmation=not args.nowait
                    )
                elif args.command == "climate-off":
                    data = await client.climateOff(
                        vin, waitForConfirmation=not args.nowait
                    )
                elif args.command == "directcharge-on":
                    data = await client.directChargeOn(
                        vin, model=args.model, waitForConfirmation=not args.nowait
                    )
                elif args.command == "directcharge-off":
                    data = await client.directChargeOff(
                        vin, model=args.model, waitForConfirmation=not args.nowait
                    )
                elif args.command == "chargingprofile":
                    data = await client.updateChargingProfile(
                        vin,
                        model=args.model,
                        profileId=args.profileid,
                        minimumChargeLevel=args.minimumchargelevel,
                        profileActive=args.profileactive,
                        long=args.long,
                        lat=args.lat,
                        waitForConfirmation=not args.nowait
                    )
                elif args.command == "honk":
                    data = await client.honkAndFlash(
                        vin, waitForConfirmation=not args.nowait
                    )
                elif args.command == "flash":
                    data = await client.flash(vin, waitForConfirmation=not args.nowait)
                elif args.command == "lock":
                    data = await client.lock(vin, waitForConfirmation=not args.nowait)
                elif args.command == "unlock":
                    pin = args.pin
                    if pin is None:
                        pin = getpass("PIN code: ")
                    data = await client.unlock(
                        vin, pin, waitForConfirmation=not args.nowait
                    )

                print(json.dumps(data, indent=2))
    except WrongCredentials as e:
        sys.exit(e.message)

    await conn.close()
    with open(args.session_file, "w", encoding="utf-8") as json_file:
        json.dump(conn.tokens, json_file, ensure_ascii=False, indent=2)


def add_arg_vin(parser):
    group = parser.add_mutually_exclusive_group(required=True,)
    group.add_argument("-v", "--vin", dest="vin", default=None)
    group.add_argument("-a", "--all", dest="all", action="store_true")

def add_arg_model(parser):
    parser.add_argument("-m", "--model", dest="model", default=None)

def cli():
    config = configparser.ConfigParser()
    config["porsche"] = {
        "email": "",
        "password": "",
        "session_file": ".session",
        "country": "DE",
        "language": "de",
        "timezone": "Europe/Stockholm",
    }
    config.read([".porscheconnect.cfg", os.path.expanduser("~/.porscheconnect.cfg")])
    parser = argparse.ArgumentParser(description="Porsche Connect CLI")
    subparsers = parser.add_subparsers(help='command help', dest='command')

    parser.add_argument("-d", "--debug", dest="debug", action="store_true")
    parser.add_argument(
        "-e", "--email", dest="email", default=config.get("porsche", "email")
    )
    parser.add_argument(
        "-p", "--password", dest="password", default=config.get("porsche", "password")
    )
    parser.add_argument(
        "-s",
        "--sessionfile",
        dest="session_file",
        default=config.get("porsche", "session_file"),
    )
    parser.add_argument(
        "-c", "--country", dest="country", default=config.get("porsche", "country")
    )
    parser.add_argument(
        "-l", "--language", dest="language", default=config.get("porsche", "language")
    )
    parser.add_argument(
        "-z", "--timezone", dest="timezone", default=config.get("porsche", "timezone")
    )
    parser.add_argument("--nowait", dest="nowait", action="store_true")


    parser_command_list = subparsers.add_parser('list')

    parser_command_services = subparsers.add_parser('services')
    add_arg_vin(parser_command_services)

    parser_command_overview = subparsers.add_parser('overview')
    add_arg_vin(parser_command_overview)

    parser_command_maintenance = subparsers.add_parser('maintenance')
    add_arg_vin(parser_command_maintenance)

    parser_command_summary = subparsers.add_parser('summary')
    add_arg_vin(parser_command_summary)

    parser_command_capabilities = subparsers.add_parser('capabilities')
    add_arg_vin(parser_command_capabilities)

    parser_command_permissions = subparsers.add_parser('permissions')
    add_arg_vin(parser_command_permissions)

    parser_command_emobility = subparsers.add_parser('emobility')
    add_arg_vin(parser_command_emobility)
    add_arg_model(parser_command_emobility)

    parser_command_position = subparsers.add_parser('position')
    add_arg_vin(parser_command_position)

    parser_command_triplongterm = subparsers.add_parser('triplongterm')
    add_arg_vin(parser_command_triplongterm)

    parser_command_tripshortterm = subparsers.add_parser('tripshortterm')
    add_arg_vin(parser_command_tripshortterm)

    parser_command_speedalerts = subparsers.add_parser('speedalerts')
    add_arg_vin(parser_command_speedalerts)

    parser_command_theftalerts = subparsers.add_parser('theftalerts')
    add_arg_vin(parser_command_theftalerts)

    parser_command_tokens = subparsers.add_parser('tokens')

    parser_command_lock = subparsers.add_parser('lock')
    add_arg_vin(parser_command_lock)

    parser_command_unlock = subparsers.add_parser('unlock')
    add_arg_vin(parser_command_unlock)
    parser_command_unlock.add_argument("-n", "--pin", required=True, dest="pin", default=None)

    parser_command_climateon = subparsers.add_parser('climate-on')
    add_arg_vin(parser_command_climateon)

    parser_command_climateoff = subparsers.add_parser('climate-off')
    add_arg_vin(parser_command_climateoff)

    parser_command_directchargeon = subparsers.add_parser('directcharge-on')
    add_arg_vin(parser_command_directchargeon)
    add_arg_model(parser_command_directchargeon)

    parser_command_directchargeoff = subparsers.add_parser('directcharge-off')
    add_arg_vin(parser_command_directchargeoff)
    add_arg_model(parser_command_directchargeoff)

    parser_command_honk = subparsers.add_parser('honk')
    add_arg_vin(parser_command_honk)

    parser_command_flash = subparsers.add_parser('flash')
    add_arg_vin(parser_command_flash)

    parser_command_chargingprofile = subparsers.add_parser('chargingprofile', help='Update parameters in configured charging profile')
    add_arg_vin(parser_command_chargingprofile)
    add_arg_model(parser_command_chargingprofile)
    parser_command_chargingprofile.add_argument('--profileid', dest="profileid", type=int, required=True, help='Profile ID')
    parser_command_chargingprofile.add_argument('--chargelevel', dest="minimumchargelevel", type=int, required=False, default=None, help='Minimun charge level')
    parser_command_chargingprofile.add_argument('--profileactive', dest="profileactive", type=bool, required=False, default=None, help='Profile active status')
    parser_command_chargingprofile.add_argument('--long', dest="long", type=float, required=False, default=None, help='Longitude (WGS84 decimal)')
    parser_command_chargingprofile.add_argument('--lat', dest="lat", type=float, required=False, default=None, help='Latitude (WGS84 decimal)')


    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args))
