#!/usr/bin/python
# -*- coding: utf-8 -*-
#Loic Lambiel ©
# License MIT

import sys, getopt, argparse
import logging, logging.handlers
import time
from datetime import datetime, timedelta
from pprint import pprint
import sys
import socket

try:
    from libcloud.compute.types import Provider
    from libcloud.compute.providers import get_driver
    from libcloud.compute.deployment import ScriptDeployment
    from libcloud.compute.deployment import MultiStepDeployment 
except ImportError:
    print "It look like libcloud module isn't installed. Please install it using pip install apache-libcloud"
    sys.exit(1)
 

try:
    import bernhard
except ImportError:
    print "It look like riemann client (bernard) isn't installed. Please install it using pip install bernhard"
    sys.exit(1)


start_time = time.time()
logfile = "/var/log/cloud-canary.log"
logging.basicConfig(format='%(asctime)s %(pathname)s %(levelname)s:%(message)s', level=logging.DEBUG,filename=logfile)
logging.getLogger().addHandler(logging.StreamHandler())


def main():
    parser = argparse.ArgumentParser(description='This script spawn an instance on exoscale public cloud and execute a dummy command thru SSH. If any error occur during the process, an alarm is being sent to riemann monitoring')
    parser.add_argument('-version', action='version', version='%(prog)s 1.0, Loic Lambiel, exoscale')
    parser.add_argument('-acskey', help='Cloudstack API user key', required=True, type=str, dest='acskey')
    parser.add_argument('-acssecret', help='Cloudstack API user secret', required=True, type=str, dest='acssecret')
    parser.add_argument('-riemannhost', help='Riemann monitoring host', required=True, type=str, dest='RIEMANNHOST')
    args = vars(parser.parse_args())
    return args

 
def deploy_instance(args):
    API_KEY = args['acskey']
    API_SECRET_KEY = args['acssecret']

    cls = get_driver(Provider.EXOSCALE)
    driver = cls(API_KEY, API_SECRET_KEY)
	 
    size = [size for size in driver.list_sizes() if size.name == 'Micro'][0]
    image = [image for image in driver.list_images() if 'Ubuntu 14.04 LTS 64-bit'
             in image.name][0]
	 
    name = 'canary-check'

    script = ScriptDeployment('echo Iam alive !')
    msd = MultiStepDeployment([script])

    logging.info('Deploying instance %s', name)
    
    node = driver.deploy_node(name=name, image=image, size=size,
    			      max_tries=1,
    			      deploy=msd)

    nodename = str(node.name)
    nodeid = str(node.uuid)
    nodeip = str(node.public_ips)
    logging.info('Instance successfully deployed : %s, %s, %s', nodename,nodeid,nodeip)
    # The stdout of the deployment can be checked on the `script` object
    pprint(script.stdout)
    
    logging.info('Successfully executed echo command thru SSH')
    logging.info('Destroying the instance now')
    # destroy our canary node
    destroynode = driver.destroy_node(node)
    
    logging.info('Successfully destroyed the instance %s', name)
    logging.info('The whole check took %s seconds', exectime)
    logging.info('Script completed')

#main
if __name__ == "__main__":
    args = main()
    RIEMANNHOST = args['RIEMANNHOST']
    try:
        deploy_instance(args)
    except Exception as e:
        pass
        logging.exception("An exception occured. Exception is: %s", e)
        client=bernhard.Client(host=RIEMANNHOST)
        host = socket.gethostname()
        txt = 'An exception occurred on cloud_canary.py: %s. See logfile %s for more info' % (e,logfile)
        client.send({'host': host,
                     'service': "Cloud_canary.check",
                     'description': txt,
                     'state': 'warning',
                     'tags': ['cloud_canary.py'],
                     'ttl': 3800,
                     'metric': 1})
        sys.exit(1)
    finally:
        exectime = time.time() - start_time
        client=bernhard.Client(host=RIEMANNHOST)
        host = socket.gethostname()
        client.send({'host': host,
                     'service': "Cloud_canary.check.exectime",
                     'state': 'ok',
                     'tags': ['cloud_canary.py'],
                     'ttl': 3800,
                     'metric': exectime})
