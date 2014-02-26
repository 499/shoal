import web
import json
import math
import operator
import tornado.template
import time
from shoal import SquidNode
from config import settings
from shoal_server import utilities

from __version__ import version

t_globals = dict(
    datestr=web.datestr,
    version=version,
    squid_active_time=settings["squid"]["inactive_time"]
)

TEMPLATES = 'templates/'


def view_index(size=100):
    """
        returns an index template with a sorted_shoal list with upper
        and lower bounds from the given size
    """
    # For testing purposes
    squid = SquidNode(1, 'somehost', '1111', '1.2.3.4', '5.6.7.8', '6.5.4.3', '100',
                      {'city': 'Victoria', 'region': 'NA', 'country': 'CA',
                       'longitude': 123, 'latitude': 456})

    test_shoal = {1: squid}
    total = len(test_shoal)
    page = 1

    try:
        size = int(size)
    except (ValueError, TypeError):
        size = 20
    try:
        pages = int(math.ceil(len(test_shoal) / float(size)))
    except ZeroDivisionError:
        #TODO: handle this
        raise

    if page < 1:
        page = 1
    if page > pages:
        page = pages

    lower, upper = int(size * (page - 1)), int(size * page)
    loader = tornado.template.Loader(TEMPLATES)
    #TODO: use actual squid active time value
    return loader.load("index.html").generate(total=total, shoal=test_shoal, now=time.time(),
                                              page=page, pages=pages, size=size, squid_active_time=120)


def view_nearest(count):
    """
        returns the nearest squid as a JSON formatted str
    """
    try:
        count = int(count)
    except (ValueError, TypeError):
        count = 5

    ip = web.ctx['ip']

    squids = utilities.get_nearest_squids(ip,count)

    if squids:
        squid_json = {}
        for i,squid in enumerate(squids):
            squid_json[i] = squid[0].jsonify()
            squid_json[i]['distance'] = squid[1]
        return json.dumps(squid_json)
    else:
        return json.dumps(None)


def view_wpad(**k):
    """
        returns data as a wpad
    """
    data = render.wpad(utilities.generate_wpad(web.ctx['ip']))
    return data
