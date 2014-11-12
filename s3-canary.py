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
    import boto
    import boto.s3.connection
    from boto.s3.key import Key
except ImportError:
    print "It look like boto module isn't installed. Please install it using pip install boto"
    sys.exit(1)
 

try:
    import bernhard
except ImportError:
    print "It look like riemann client (bernard) isn't installed. Please install it using pip install bernhard"
    sys.exit(1)


logfile = "/var/log/s3-canary.log"
logging.basicConfig(format='%(asctime)s %(pathname)s %(levelname)s:%(message)s', level=logging.DEBUG,filename=logfile)
logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger('boto').setLevel(logging.CRITICAL)

class FailedtoReadTestFile(Exception):
    """Exception: Unable to read back the created test file"""

def main():
    parser = argparse.ArgumentParser(description='This script create a file, read it and delete it on a s3 compliant storage. If any error occur during the process, an alarm is being sent to riemann monitoring. time metric is also sent to riemann')
    parser.add_argument('-version', action='version', version='%(prog)s 1.0, Loic Lambiel, exoscale')
    parser.add_argument('-key', help='S3 user key', required=True, type=str, dest='key')
    parser.add_argument('-secret', help='S3 user secret', required=True, type=str, dest='secret')
    parser.add_argument('-host', help='S3 host', required=True, type=str, dest='host')
    parser.add_argument('-bucket', help='S3 bucket', required=True, type=str, dest='bucket')
    parser.add_argument('-riemannhost', help='Riemann monitoring host', required=True, type=str, dest='RIEMANNHOST')
    args = vars(parser.parse_args())
    return args

 
def s3test(args):
    KEY = args['key']
    SECRET = args['secret']
    HOST = args['host']
    BUCKET = args['bucket']
   
    conn = boto.connect_s3(
        aws_access_key_id = KEY,
        aws_secret_access_key = SECRET,
        host = HOST,
        calling_format = boto.s3.connection.OrdinaryCallingFormat(),
        )
    
    bucket = conn.create_bucket(BUCKET)


    k = Key(bucket)
    k.key = 's3-canary'
    k.set_contents_from_string('This is a test of S3')

    if k.get_contents_as_string() != "This is a test of S3":
        raise FailedtoReadTestFile

    bucket.delete_key(k)

#main
if __name__ == "__main__":
    args = main()
    RIEMANNHOST = args['RIEMANNHOST']
    start_time = time.time()
    try:
        s3test(args)
        exectime = time.time() - start_time
        client=bernhard.Client(host=RIEMANNHOST)
        host = socket.gethostname()
        client.send({'host': host,
                     'service': "s3_canary.exectime",
                     'state': 'ok',
                     'tags': ['duration'],
                     'ttl': 600,
                     'metric': exectime})
        client.send({'host': host,
                     'service': "s3_canary.check",
                     'state': 'ok',
                     'tags': ['s3_canary.py', 'duration'],
                     'ttl': 600,
                     'metric': 0})

        logging.info('Script completed successfully')

    except Exception as e:
        pass
        logging.exception("An exception occured. Exception is: %s", e)
        client=bernhard.Client(host=RIEMANNHOST)
        host = socket.gethostname()
        exectime = 61
        txt = 'An exception occurred on s3_canary.py: %s. See logfile %s for more info' % (e,logfile)
        client.send({'host': host,
                     'service': "s3_canary.check",
                     'description': txt,
                     'state': 'critical',
                     'tags': ['s3_canary.py', 'duration'],
                     'ttl': 600,
                     'metric': 1})
        client.send({'host': host,
                     'service': "s3_canary.exectime",
                     'state': 'ok',
                     'tags': ['duration'],
                     'ttl': 600,
                     'metric': exectime})
        sys.exit(1)

