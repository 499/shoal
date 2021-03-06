from os.path import join, expanduser, exists, abspath
import sys
import ConfigParser
import logging

"""Setup shoal using config file.
   setup will look for a configuration file specified in the following order:
     directory of shoal-server
     /etc/shoal/shoal_server.conf
     ~/.shoal/shoal_server.conf
   The first one found will be used.
"""

SHOAL_DIR = '/var/shoal/'

# set default values dictionary,
# add new keys here, and they will automatically be populated
settings = {
    # Tornado Specific Section
    'tornado': {
        'static_path':        { 'default_value': join(SHOAL_DIR, 'static'),
                                'type': 'string' },
        'template_path':     { 'default_value': join(SHOAL_DIR, 'templates'),
                                'type': 'string' },
        'port':               { 'default_value': 80,
                                'type': 'int' },
    },
    # General Section
    'general': {
        'geolitecity_path':   { 'default_value': join(SHOAL_DIR, 'bin'),
                                'type': 'string' },
        'geolitecity_url':    { 'default_value': 'http://geolite.maxmind.com/download/geoip/database/GeoLiteCity.dat.gz',
                                'type': 'string' },
        'geolitecity_update': { 'default_value':2592000,
                                'type': 'int' },
    },
    # Squid Section
    'squid': {
        'cleanse_interval': { 'default_value': 15,
                              'type': 'int' },
        'inactive_time':    { 'default_value': 180,
                              'type': 'int' },
    },
    # Redis Section
    'redis': {
        'port': { 'default_value': 6379,
                  'type': 'int' },
        'host': { 'default_value': 'localhost',
                  'type': 'string' },
        'db':   { 'default_value': 0,
                  'type': 'int' },
    },
    # RabbitMQ Section
    'rabbitmq': {
        'host':          { 'default_value': 'localhost',
                           'type': 'string' },
        'port':          { 'default_value': 5672,
                           'type': 'int' },
        'virtual_host':  { 'default_value': '/',
                           'type': 'string' },
        'exchange':      { 'default_value': 'shoal',
                           'type': 'string' },
        'exchange_type': { 'default_value': 'topic',
                           'type': 'string' },
        'use_ssl':       { 'default_value': False,
                           'type': 'bool' },
        'ca_cert':       { 'default_value': '',
                           'type': 'string' },
        'client_cert':   { 'default_value': '',
                           'type': 'string' },
        'client_key':    { 'default_value': '',
                           'type': 'string' },
        'reconnection_attempts': { 'default_value': 10,
                                   'type': 'int' },
    },
    'logging': {
        'config_file': { 'default_value': 'logging.conf',
                         'type': 'string' }
    },
}

def setup():
    homedir = expanduser('~')

    # find config file by checking the directory of the calling script and sets path
    if  exists(abspath(sys.path[0]+"/shoal_server.conf")):
        path = abspath(sys.path[0]+"/shoal_server.conf")
    elif exists("/etc/shoal/shoal_server.conf"):
        path = "/etc/shoal/shoal_server.conf"
    elif exists(abspath(homedir + "/.shoal/shoal_server.conf")):
        path = abspath(homedir + "/.shoal/shoal_server.conf")
    else:
        print >> sys.stderr, "Configuration file problem: There doesn't " \
                             "seem to be a configuration file. " \
                             "You can specify one in /etc/shoal/shoal_server.conf"
        sys.exit(1)

    # Read config file from the given path above
    config_file = ConfigParser.ConfigParser()
    try:
        config_file.read(path)
    except IOError:
        print >> sys.stderr, "Configuration file problem: There was a " \
                             "problem reading %s. Check that it is readable," \
                             "and that it exists. " % path
        raise
    except ConfigParser.ParsingError:
        print >> sys.stderr, "Configuration file problem: Couldn't " \
                             "parse your file. Check for spaces before or after variables."
        raise
    except:
        print "Configuration file problem: There is something wrong with " \
              "your config file."
        raise

    # Get values set in config file and update settings dictionary
    for section in settings.keys():
        for key in settings[section]:
            try:
                if config_file.has_option(section, key):
                    if settings[section][key]['type'] == 'int':
                        try:
                            settings[section][key] = config_file.getint(section, key)
                        except ValueError:
                            print "Configuration file problem: %s must be an " \
                                    "int value." % key
                            exit(1)
                    elif settings[section][key]['type'] == 'bool':
                        try:
                            settings[section][key] = config_file.getboolean(section, key)
                        except ValueError:
                            print "Configuration file problem: %s must be an " \
                                    "boolean value." % key
                            exit(1)
                    else:
                        settings[section][key] = config_file.get(section, key)
                else:
                    settings[section][key] = settings[section][key]['default_value']
            except Exception as e:
                pass

def setup_ssl():
    try:
        settings['rabbitmq']['ca_cert'] = abspath(config_file.get("rabbitmq", "ca_cert"))
        settings['rabbitmq']['client_cert'] = abspath(config_file.get("rabbitmq", "client_cert"))
        settings['rabbitmq']['client_key']  = abspath(config_file.get("rabbitmq", "client_key"))
    except Exception as e:
        print "Configuration file problem: could not load SSL certs"
        print e
        sys.exit(1)

def setup_logging():
    import logging.config
    import json
    path = settings['logging']['config_file']

    try:
        with open(path, 'rt') as f:
            conf = json.loads(f.read())
    except IOError as e:
        logging.error("Unable to open logging configuration file, please specify in configuration file.")
        sys.exit(1)

    logging.config.dictConfig(conf)


setup()
setup_logging()
if settings['rabbitmq']['use_ssl']:
    setup_ssl()

