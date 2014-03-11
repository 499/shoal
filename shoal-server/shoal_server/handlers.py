import json
import tornado.web
import time
import utilities


class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        shoal = self.application.shoal
        sorted_shoal = [shoal[k] for k in sorted(shoal, key=shoal.get, reverse=True)]
        inactive_time = self.application.global_settings['squid']['inactive_time']
        self.render("index.html", shoal=sorted_shoal, inactive_time=inactive_time, now=time.time())

class NearestHandler(tornado.web.RequestHandler):
    def get(self, slug=None):
        if slug:
            count = slug
        else:
            count = 10

        squids = utilities.get_nearest_squids(
            self.application.shoal,
            self.application.global_settings['general']['geolitecity_path'],
            self.request.remote_ip,
            count=count)

        if squids:
            self.write(json.dumps(squids))
        else:
            json.dumps({})
