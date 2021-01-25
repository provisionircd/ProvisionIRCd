"""
webstats support
"""

import time

import ircd
from handle.functions import logging, match

# API calls are special requests that you can send to the server upon establishing a connection.
# If successful, the IRCd will return a JSON dict with your requested data.
# The connection will be terminated immediately after the response.


# This is a dictionary of IP addresses that are allowed to make this API call.
# The key "rate_limit" contains a tuple in format: requests, seconds
# This is your rate control, allowing "requests" requests per "seconds" seconds.
# Order matters! It wil use the first matching rate_limit, so always keep your
# public rate_limit at the bottom.
allowed_ips = {
    "84.106.*.*": {"rate_limit": (100, 3600,)},
    "*": {"rate_limit": (10, 3600,)},
}


# First parameter is the name of the API call, in this case WEBSTATS. This is required.
# The second parameter is optional, yet reommended, and is the IP address where the call comes from.
# Usually localhost, your local Django server. If you use an outside server, place its IP address instead.
# You will also want to add or modify exceptions.conf->throttle. This defaults to None, allowing all.
# The third parameter is also optional, and takes a password for extra authentication.
# You will need to configure your Django server to send it along. Defaults to None.
@ircd.Modules.api('webstats', '127.0.0.1')
def process_webstats(self, localServer, recv):
    global allowed_ips
    ip = [i for i in allowed_ips if match(i, recv[1])]
    if not ip or ip[0] not in allowed_ips:
        return self._send('WEBSTATS 403 You are not allowed to make that API call.')
    if "rate_limit" in allowed_ips[ip[0]]:
        rate_limit = allowed_ips[ip[0]]["rate_limit"]
    else:
        rate_limit = (9999, 1)  # 2 Unlimited.
    ip = recv[1]
    if ip not in localServer.webstats_ip_requests:
        localServer.webstats_ip_requests[ip] = {}
        localServer.webstats_ip_requests[ip]['calls'] = {}
        localServer.webstats_ip_requests[ip]['ctime'] = int(time.time())  # First API call for this IP.
    logging.debug('Rate limit: {}'.format(rate_limit))
    ago = int(time.time()) - localServer.webstats_ip_requests[ip]['ctime']
    if len(localServer.webstats_ip_requests[ip]['calls']) >= rate_limit[0]:
        logging.debug("Max. calls exceeded for IP: {}".format(ip))
        return self._send('WEBSTATS 403 Rate limited.')
    response = {}
    response['users'] = [u.nickname for u in localServer.users if u.registered]
    response['channels'] = [c.name for c in localServer.channels if 's' not in c.modes and 'p' not in c.modes]
    self._send('WEBSTATS 200 {}'.format(response))
    localServer.webstats_ip_requests[ip]['calls'][int(round(time.time() * 1000))] = 1
    calls = len(localServer.webstats_ip_requests[ip]['calls'])
    logging.debug("This IP made {} call{} this session, first call was {} second{} ago.".format(calls, '' if calls == 1 else 's', ago, '' if ago == 1 else 's'))


@ircd.Modules.hooks.loop()
def webstats_ratelimit(localServer):
    global allowed_ips
    for ip in dict(localServer.webstats_ip_requests):
        rate_ip = [i for i in allowed_ips if match(i, ip)]
        if not rate_ip:
            logging.debug('Something went wrong. Could not find a rate_limit for IP "{}", removing from dict.'.format(ip))
            del localServer.webstats_ip_requests[ip]
            break
        rate_limit = allowed_ips[rate_ip[0]]["rate_limit"]
        if int(time.time()) - localServer.webstats_ip_requests[ip]['ctime'] > rate_limit[1]:
            del localServer.webstats_ip_requests[ip]
            logging.debug("API rate limit for {} reset.".format(ip))


def init(ircd, reload=False):
    print('yo')
    ircd.webstats_ip_requests = {}
