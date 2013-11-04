from os.path import exists, join, expanduser, abspath
import sys
import ConfigParser
import logging

# Shoal Options Module

# set default values
shoal_server_url = 'http://localhost:8080/nearest'
default_squid_proxy   = ""

def setup(path=None):
    """Setup shoal using config file.
       setup will look for a configuration file specified in /etc/shoal/shoal_client.conf
       or ~/.shoal/shoal_client.conf
    """
    global shoal_server_url
    global default_squid_proxy

    homedir = expanduser('~')
    # find config file
    if not path:
        if exists("/etc/shoal/shoal_client.conf"):
            path = "/etc/shoal/shoal_client.conf"
        elif exists(abspath(homedir + "/shoal/shoal-client/shoal_client.conf")):
            path =  abspath(homedir + "/shoal/shoal-client/shoal_client.conf")
        else:
            print >> sys.stderr, "Configuration file problem: There doesn't " \
                  "seem to be a configuration file. " \
                  "You can specify one in /etc/shoal/shoal_client.conf or ~/.shoal/shoal_client.conf"
            sys.exit(1)

    # Read config file
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

    if config_file.has_option("general", "shoal_server_url"):
        shoal_server_url = config_file.get("general",
                                                "shoal_server_url")

    if config_file.has_option("general", "default_squid_proxy"):
        default_squid_proxy = config_file.get("general",
                                                "default_squid_proxy")
    else:
        print "Configuration file problem: default_squid_proxy must be set. " \
              "Please check configuration file:", path
        sys.exit(1)
