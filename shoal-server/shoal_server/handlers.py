import json
import tornado.web
import time
from utilities import get_nearest_squids, generate_wpad
from tornado import gen


class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        shoal = self.application.shoal
        sorted_shoal = [shoal[k] for k in sorted(shoal.keys(), key=lambda key: shoal[key]['last_active'], reverse=True)]
        inactive_time = self.application.global_settings['squid']['inactive_time']
        self.render("index.html", shoal=sorted_shoal, inactive_time=inactive_time, now=time.time())


class NearestHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self, count=10):
        squids = yield gen.Task(
            get_nearest_squids,
            self.application.shoal,
            self.application.global_settings['general']['geolitecity_path'],
            self.request.remote_ip,
            count=count
        )

        if squids:
            self.write(json.dumps(squids))
        else:
            json.dumps({})
        self.finish()

class AllSquidHandler(tornado.web.RequestHandler):
    def get(self):
        shoal = self.application.shoal
        sorted_shoal = [shoal[k] for k in sorted(shoal.keys(), key=lambda key: shoal[key]['last_active'], reverse=True)]

        self.write(json.dumps(sorted_shoal))

class WPADHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def get(self):
        ip = self.request.remote_ip
        db_path = self.application.global_settings['general']['geolitecity_path']
        shoal = self.application.shoal
        proxy = yield gen.Task(generate_wpad, shoal, ip, db_path)
        self.set_header('Content-Type', 'application/x-ns-proxy-autoconfig')
        if proxy:
            wpad = "function FindProxyForURL(url, host) { return \"%s DIRECT\";}" % proxy
            self.set_header('Content-Length', len(wpad))
            self.write(wpad)
        else:
            wpad = "function FindProxyForURL(url, host) { return \"DIRECT\";})"
            self.set_header('Content-Length', len(wpad))
            self.write(wpad)
        self.finish()


