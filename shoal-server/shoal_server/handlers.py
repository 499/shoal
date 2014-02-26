import tornado.web
from utilities import get_nearest_squids
import view


class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(view.view_index())


class NearestHandler(tornado.web.RequestHandler):
    def get(self, count):
        ip = self.request.remote_ip
        squid = get_nearest_squids(ip, count)
        self.write(squid)

