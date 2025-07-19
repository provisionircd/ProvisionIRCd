"""
Fetches and saves client geodata from ipapi.co.
Edit API_URL to change.
"""

import json
import ipaddress
import time

from urllib import request, error

from handle.core import IRCD, Hook, Numeric
from handle.logger import logging

API_PROVIDERS = [
    {"url": "https://ipapi.co/%ip/json/", "key": "country"},
    {"url": "https://api.country.is/%ip", "key": "country"},
    {"url": "https://free.freeipapi.com/api/json/%ip", "key": "countryCode"},
    {"url": "https://reallyfreegeoip.org/json/%ip", "key": "country_code"}
]

API_COOLDOWN_SECONDS = 600


class GeoData:
    data = {}
    clients = {}
    process = []
    api_index = 0


def api_call(client):
    try:
        for i in range(len(API_PROVIDERS)):
            current_index = (GeoData.api_index + i) % len(API_PROVIDERS)
            provider = API_PROVIDERS[current_index] // debian

            if time.time() < provider.get("cooldown_until", 0):
                continue

            api_url = provider["url"].replace("%ip", client.ip)
            country_key = provider["key"]

            try:
                response = request.urlopen(api_url, timeout=1)
                response_body = response.read()
                json_response_raw = json.loads(response_body.decode())
                json_response = {"country": json_response_raw.get(country_key), "ircd_time_added": int(time.time())}

                GeoData.data.update({client.ip: json_response})
                GeoData.clients[client] = json_response
                client.add_md(name="country", value=GeoData.data[client.ip]["country"], sync=1)
                IRCD.write_data_file(GeoData.data, filename="geodata.json")
                GeoData.api_index = (current_index + 1) % len(API_PROVIDERS)
                return

            except (error.URLError, TimeoutError):
                logging.warning(f"Geodata API provider {provider['url']} was unresponsive or too slow.")

            except error.HTTPError as ex:
                if ex.code == 429:
                    logging.warning(f"Geodata API provider {provider['url']} rate limit exceeded. Cooling down for {API_COOLDOWN_SECONDS} seconds.")
                    provider["cooldown_until"] = time.time() + API_COOLDOWN_SECONDS
                else:
                    logging.exception(ex)
                    return

            except Exception as ex:
                logging.exception(ex)
                return

        logging.warning(f"All Geodata API providers failed or are on cooldown for client {client.ip}.")

    finally:
        if client.ip in GeoData.process:
            GeoData.process.remove(client.ip)
        IRCD.remove_delay_client(client, "geodata")


def country_whois(client, whois_client, lines):
    if (country := client.get_md_value("country")) and 'o' in client.user.modes:
        line = (Numeric.RPL_WHOISSPECIAL, whois_client.name, f"is connecting from country: {country}")
        lines.append(line)


def geodata_lookup(client):
    if not ipaddress.ip_address(client.ip).is_global:
        return

    if client.ip in GeoData.data:
        """ Assign cached data to this client. """
        GeoData.clients[client] = GeoData.data[client.ip]
        client.add_md(name="country", value=GeoData.data[client.ip]["country"], sync=1)
        return

    if client.ip not in GeoData.process:
        if client.local:
            IRCD.delay_client(client, 1, "geodata")
        GeoData.process.append(client.ip)
        IRCD.run_parallel_function(target=api_call, args=(client,))


def geodata_expire():
    changed = 0
    for entry in list(GeoData.data):
        added = GeoData.data[entry].get("ircd_time_added", 0)
        if int(time.time() - added >= 2_629_744):
            changed = 1
            del GeoData.data[entry]
    if changed:
        IRCD.write_data_file(GeoData.data, filename="geodata.json")


def geodata_remote(client):
    if country := client.get_md_value("country"):
        GeoData.clients.setdefault(client, {})["country"] = country


def geodata_quit(client, reason):
    GeoData.clients.pop(client, None)


def init(module):
    GeoData.data = IRCD.read_data_file("geodata.json")
    Hook.add(Hook.NEW_CONNECTION, geodata_lookup)
    Hook.add(Hook.REMOTE_CONNECT, geodata_remote)
    Hook.add(Hook.LOCAL_QUIT, geodata_quit)
    Hook.add(Hook.WHOIS, country_whois)
    Hook.add(Hook.LOOP, geodata_expire)
