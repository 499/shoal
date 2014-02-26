import web
import json
import math
import operator
from config import settings
from shoal_server import utilities
import tornado.template
from __version__ import version

t_globals = dict(
    datestr=web.datestr,
    version=version,
    squid_active_time=settings["squid"]["inactive_time"]
)

TEMPLATES = '../templates/'


def view_index(size=100):
    """
        returns an index template with a sorted_shoal list with upper
        and lower bounds from the given size
    """
    #params = web.input()
    #page = params.page if hasattr(params, 'page') else 1
    sorted_shoal = sorted(web.shoal.values(), key=operator.attrgetter('last_active'))
    sorted_shoal.reverse()
    total = len(sorted_shoal)
    #page = int(page)
    page = 1
    sorted_shoal = []

    try:
        size = int(size)
    except (ValueError, TypeError):
        size = 20
    try:
        pages = int(math.ceil(len(sorted_shoal) / float(size)))
    except ZeroDivisionError:
        #TODO: handle this
        raise

    if page < 1:
        page = 1
    if page > pages:
        page = pages

    lower, upper = int(size * (page - 1)), int(size * page)
    loader = tornado.template.Loader(TEMPLATES)
    return loader.load("index.html").generate(total=total)


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
