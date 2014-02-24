#!/usr/bin/env python
import sys
import web
import json
import urllib
import logging
import pika
import socket
import uuid
from time import time, sleep
from threading import Thread
from config import settings

from shoal_server import config
from shoal_server import utilities


class SquidNode(object):
    """
    Basic class to store and update information about each squid server.
    """

    def __init__(self, key, hostname, squid_port, public_ip, private_ip, external_ip, load, geo_data,
                 last_active=time()):
        """constructor for SquidNode, time created is current time"""
        self.key = key
        self.created = time()
        self.last_active = last_active
        self.hostname = hostname
        self.squid_port = squid_port
        self.public_ip = public_ip
        self.private_ip = private_ip
        self.external_ip = external_ip
        self.geo_data = geo_data
        self.load = load

    def update(self, load):
        """updates SquidNode with current time and load"""
        self.last_active = time()
        self.load = load

    def jsonify(self):
        """returns a dictionary with current Squid data"""
        return dict({
                "created": self.created,
                "last_active": self.last_active,
                "hostname": self.hostname,
                "squid_port": self.squid_port,
                "public_ip": self.public_ip,
                "private_ip": self.private_ip,
                "external_ip": self.external_ip,
                "geo_data": self.geo_data,
                "load": self.load,
                },
            )


class ThreadMonitor(Thread):
    """
    Main application that will monitor RabbitMQ and ShoalUpdate threads.
    """

    def __init__(self, shoal):
        """constructor for ThreadMonitor, sets up and threads together RabbitMQConsumer and ShoalUpdate threads, also checks and downloads update as needed"""
        # check if geolitecity database needs updating
        if utilities.check_geolitecity_need_update():
            utilities.download_geolitecity()

        Thread.__init__(self)

        self.shoal = shoal
        self.threads = []

        rabbitmq_thread = RabbitMQConsumer(self.shoal)
        rabbitmq_thread.daemon = True
        self.threads.append(rabbitmq_thread)

        update_thread = ShoalUpdate(self.shoal)
        update_thread.daemon = True
        self.threads.append(update_thread)

    def run(self):
        """runs ThreadMonitor threads"""
        for thread in self.threads:
            logging.info("starting", thread)
            thread.start()
        while True:
            for thread in self.threads:
                if not thread.is_alive():
                    logging.error('{0} died. Stopping application...'.format(thread))
                    sys.exit(1)
            sleep(1)

    def stop(self):
        """stops ThreadMonitor threads"""
        logging.info("Shutting down Shoal-Server... Please wait.")
        try:
            self.rabbitmq.stop()
            self.update.stop()
        except Exception as e:
            logging.error(e)
            sys.exit(1)
        finally:
            sleep(2)
        sys.exit()


class ShoalUpdate(Thread):
    """
    ShoalUpdate is used for trimming inactive squids every set interval.
    """

    INTERVAL = settings["squid"]["cleanse_interval"]
    INACTIVE = settings["squid"]["inactive_time"]

    def __init__(self, shoal):
        """constructor for ShoalUpdate, uses parent Thread constructor as well"""
        Thread.__init__(self)
        self.shoal = shoal
        self.running = False

    def run(self):
        """runs ShoalUpdate"""
        self.running = True
        while self.running:
            sleep(self.INTERVAL)
            self.update()

    def update(self):
        """updates and pops squid from shoal if it's inactive"""
        curr = time()
        for squid in self.shoal.values():
            if curr - squid.last_active > self.INACTIVE:
                self.shoal.pop(squid.key)

    def stop(self):
        """stops ShoalUpdate"""
        self.running = False


class WebpyServer(Thread):
    """
    Webpy webserver used to serve up active squid lists and API calls. Can run as either the development server or under mod_wsgi.
    """

    def __init__(self, shoal):
        """constructor for WebpyServer, uses parent Thread constructor as well, and uses values from config file and web"""
        Thread.__init__(self)
        web.shoal = shoal
        web.config.debug = False
        self.app = None
        self.urls = (
            '/nearest/?(\d+)?/?', 'shoal_server.view.nearest',
            '/wpad.dat', 'shoal_server.view.wpad',
            '/(\d+)?/?', 'shoal_server.view.index',
        )

    def run(self):
        """runs web application"""
        try:
            self.app = web.application(self.urls, globals())
            self.app.run()
        except Exception as e:
            logging.error("Could not start webpy server.\n{0}".format(e))
            sys.exit(1)

    def wsgi(self):
        """returns Web Server Gateway Interface for application"""
        return web.application(self.urls, globals()).wsgifunc()

    def stop(self):
        """stops web application"""
        self.app.stop()


class RabbitMQConsumer(Thread):
    """
    Basic RabbitMQ async consumer. Consumes messages from a unique queue that is declared when Shoal server first starts.
    The consumer takes the json in message body, and tracks it in the dictionary `shoal`
    """

    # sets defaults for RabbitMQ consumer
    QUEUE = socket.gethostname() + "-" + uuid.uuid1().hex
    EXCHANGE = settings["rabbitmq"]["amqp_exchange"]
    EXCHANGE_TYPE = settings["rabbitmq"]["amqp_exchange_type"]
    ROUTING_KEY = '#'
    INACTIVE = settings["squid"]["inactive_time"]

    def __init__(self, shoal):
        """constructor for RabbitMQConsumer, uses parent Thread constructor as well, and uses values from config file"""
        Thread.__init__(self)
        self.host = "{0}/{1}".format(settings["rabbitmq"]["host"], urllib.quote_plus(settings["rabbitmq"]["virtual_host"]))
        self.shoal = shoal
        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None

    def connect(self):
        """establishes a connection to the AMQP server with SSL options"""
        # gets SSL options from config files
        failed_connection_attempts = 0
        ssl_options = {}
        try:
            if settings["rabbitmq"]["use_ssl"]:
                ssl_options["ca_certs"] = settings["rabbitmq"]["ca_cert"]
                ssl_options["certfile"] = settings["rabbitmq"]["client_cert"]
                ssl_options["keyfile"] = settings["rabbitmq"]["client_key"]
        except Exception as e:
            logging.error("Could not read SSL files")
            logging.error(e)

        # tries to establish a connection with AMQP server
        # will retry a number of times before passing the exception up
        while True:
            try:
                connection = pika.SelectConnection(
                    pika.ConnectionParameters(
                        host=settings["rabbitmq"]["host"],
                        port=settings["rabbitmq"]["port"],
                        ssl=settings["rabbitmq"]["use_ssl"],
                        ssl_options=ssl_options
                    ),
                    self.on_connection_open,
                    stop_ioloop_on_close=False)
                return connection
            except pika.exceptions.AMQPConnectionError as e:
                failed_connection_attempts += 1
                if failed_connection_attempts >= settings["error"]["reconnect_attempts"]:
                    logging.error("Was not able to establish connection to AMQP server after {0} attempts.".format(failed_connection_attempts))
                    logging.error(e)
                    raise e
                logging.error("Could not connect to AMQP Server. Retrying in {0} seconds..."
                              .format(settings["error"]["reconnect_time"]))
                sleep(settings["error"]["reconnect_time"])
                continue

    def close_connection(self):
        """closes connections with AMQP server"""
        self._connection.close()

    def add_on_connection_close_callback(self):
        """adds a connection and closes callback"""
        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        """stops IO connection loop"""
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            logging.warning('Connection closed, reopening in 5 seconds: (%s) %s',
                           reply_code, reply_text)
            self._connection.add_timeout(5, self.reconnect)

    def on_connection_open(self, unused_connection):
        """opens channel and connection"""
        self.add_on_connection_close_callback()
        self.open_channel()

    def reconnect(self):
        """stops current IO loop and then reconnects"""
        # This is the old connection IOLoop instance, stop its ioloop
        self._connection.ioloop.stop()
        if not self._closing:
            # Create a new connection
            self._connection = self.connect()
            # There is now a new connection, needs a new ioloop to run
            self._connection.ioloop.start()

    def add_on_channel_close_callback(self):
        """adds a channel and closes callback"""
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        """closes connection on channel"""
        logging.warning('Channel was closed: (%s) %s', reply_code, reply_text)
        self._connection.close()

    def on_channel_open(self, channel):
        """opens connection on channel"""
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.EXCHANGE)

    def setup_exchange(self, exchange_name):
        """establishes exchange"""
        self._channel.exchange_declare(self.on_exchange_declareok,
                                       exchange_name,
                                       self.EXCHANGE_TYPE)

    def on_exchange_declareok(self, unused_frame):
        """callback for exchange"""
        self.setup_queue(self.QUEUE)

    def setup_queue(self, queue_name):
        """establishes queue, automatically deletes after disconnecting"""
        self._channel.queue_declare(self.on_queue_declareok, queue_name, auto_delete=True)

    def on_queue_declareok(self, method_frame):
        """callback for queue"""
        self._channel.queue_bind(self.on_bindok, self.QUEUE,
                                 self.EXCHANGE, self.ROUTING_KEY)

    def add_on_cancel_callback(self):
        """cancels callback"""
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        """closes channel on consumer"""
        if self._channel:
            self._channel.close()

    def acknowledge_message(self, delivery_tag):
        """acknowledges that consumer has received the message"""
        self._channel.basic_ack(delivery_tag)

    def on_cancelok(self, unused_frame):
        """calls close channel"""
        self.close_channel()

    def stop_consuming(self):
        """stops consuming, exits out of basic consume"""
        if self._channel:
            self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def start_consuming(self):
        """starts consuming registered callbacks"""
        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(self.on_message,
                                                         self.QUEUE)

    def on_bindok(self, unused_frame):
        """callback for bind"""
        self.start_consuming()

    def close_channel(self):
        """closes channel"""
        self._channel.close()

    def open_channel(self):
        """opens channel"""
        self._connection.channel(on_open_callback=self.on_channel_open)

    def run(self):
        """sets up connection and starts IO loop"""
        try:
            self._connection = self.connect()
        except Exception as e:
            logging.error("Unable to connect ot RabbitMQ Server. {0}".format(e))
            sys.exit(1)
        self._connection.ioloop.start()

    def stop(self):
        """stops consuming and closes IO loop"""
        self._closing = True
        self.stop_consuming()
        self._connection.ioloop.start()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        """Retreives information from data, and then updates each squid load in
       shoal if the public/private ip matches. Shoal's key will update with
       the load if there's a key in Shoal. geo_data will update or create a
       new SquidNode if the time since the last timestamp is less than the
       inactive time and a public/private ip exists"""
        external_ip = public_ip = private_ip = None
        curr = time()

        # extracts information from data from body
        try:
            data = json.loads(body)
        except ValueError as e:
            logging.error("Message body could not be decoded. Message: {1}".format(body))
            self.acknowledge_message(basic_deliver.delivery_tag)
            return
        try:
            key = data['uuid']
            hostname = data['hostname']
            time_sent = data['timestamp']
            load = data['load']
            squid_port = data['squid_port']
        except KeyError as e:
            logging.error("Message received was not the proper format (missing:{0}), discarding...".format(e))
            self.acknowledge_message(basic_deliver.delivery_tag)
            return
        try:
            external_ip = data['external_ip']
        except KeyError:
            pass
        try:
            public_ip = data['public_ip']
        except KeyError:
            pass
        try:
            private_ip = data['private_ip']
        except KeyError:
            pass

        # for each squid in shoal, if public or private ip matches,
        # load for the squid will update and send a acknowledgment message
        for squid in self.shoal.values():
           if squid.public_ip == public_ip or squid.private_ip == private_ip:
              squid.update(load)
              self.acknowledge_message(basic_deliver.delivery_tag)
              return

        # if there's a key in shoal, shoal's key will update with the load
        if key in self.shoal:
            self.shoal[key].update(load)
        # if the difference in time since the last timestamp is less than the inactive time
        # and there exists a public or private ip, then the geo_data will update its location
        # or create a new SquidNode for shoal if the geo_data doesn't exist
        elif (curr - time_sent < self.INACTIVE) and (public_ip or private_ip):
            geo_data = utilities.get_geolocation(public_ip)
            if not geo_data:
                geo_data = utilities.get_geolocation(external_ip)
            if not geo_data:
                logging.error("Unable to generate geo location data, discarding message")
            else:
                new_squid = SquidNode(key, hostname, squid_port, public_ip, private_ip, external_ip, load, geo_data, time_sent)
                self.shoal[key] = new_squid

        self.acknowledge_message(basic_deliver.delivery_tag)
