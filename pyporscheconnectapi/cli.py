import argparse
import asyncio
from pyporscheconnectapi.connection import Connection
from pyporscheconnectapi.client import Client
from pyporscheconnectapi.exceptions import WrongCredentials
import sys
import logging
import json

logging.basicConfig()
logging.root.setLevel(logging.WARNING)


async def main(args):
    try:
        with open(args.session_file) as json_file:
            tokens = json.load(json_file)
    except FileNotFoundError:
        tokens = {}
    except json.decoder.JSONDecodeError:
        tokens = {}

    conn = Connection(args.email, args.password, tokens=tokens, country=args.country, language=args.language)
    client = Client(conn)

    try:
        if args.command == "list":
            data = await client.getVehicles()
            print(json.dumps(data, indent=2))
        elif args.command == "tokens":
            data = await client.getAllTokens()
            print(json.dumps(data, indent=2))
        else:
            vins = []
            if args.vin is not None: vins = [ args.vin ]
            elif args.all:
                vehicles = await client.getVehicles()
                vins = map(lambda v : v['vin'], vehicles)
            else:
                sys.exit("--vin or --all is required")
            for vin in vins:
                data = {}
                if args.command == "overview":
                    data = await client.getOverview(vin)
                elif args.command == "maintenance":
                    data = await client.getMaintenance(vin)
                elif args.command == "summary":
                    data = await client.getSummary(vin)
                elif args.command == "capabilities":
                    data = await client.getCapabilities(vin)
                elif args.command == "position":
                    data = await client.getPosition(vin)
                elif args.command == "emobility":
                    data = await client.getEmobility(vin, model=args.model, country=args.country, language=args.language, timezone=args.timezone)
                elif args.command == "triplongterm":
                    data = await client.getTripLongTerm(vin, country=args.country, language=args.language)
                elif args.command == "tripshortterm":
                    data = await client.getTripShortTerm(vin, country=args.country, language=args.language)
                elif args.command == "speedalerts":
                    data = await client.getSpeedAlerts(vin, country=args.country, language=args.language)
                elif args.command == "theftalerts":
                    data = await client.getTheftAlerts(vin)
                print(json.dumps(data, indent=2))
    except WrongCredentials:
        sys.exit("Wrong email or password")

    await conn.close()
    with open(args.session_file, 'w', encoding='utf-8') as json_file:
        json.dump(conn.tokens, json_file, ensure_ascii=False, indent=2)

def cli():
    parser = argparse.ArgumentParser(description='Porsche Connect CLI.')
    parser.add_argument('command', choices=['list', 'overview', 'maintenance', 'summary', 'capabilities', 'emobility',
        'position', 'triplongterm', 'tripshortterm', 'speedalerts', 'theftalerts', 'tokens'])
    parser.add_argument('-e', '--email', dest='email', required=True)
    parser.add_argument('-p', '--password', dest='password', required=True)
    parser.add_argument('-s', '--sessionfile', dest='session_file', default='.session')
    parser.add_argument('-v', '--vin', dest='vin', default=None)
    parser.add_argument('-m', '--model', dest='model', default=None)
    parser.add_argument('-a', '--all', dest='all', action='store_true')
    parser.add_argument('-c', '--country', dest='country', default='de')
    parser.add_argument('-l', '--language', dest='language', default='DE')
    parser.add_argument('-z', '--timezone', dest='timezone', default='Europe/Stockholm')

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args))
