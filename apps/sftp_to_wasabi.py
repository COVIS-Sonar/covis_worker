#!/usr/bin/env python3

# from pprint import pprint
import argparse
# import sys
# import json
import logging
import shutil

import boto3
from botocore.exceptions import ClientError

from pymongo import MongoClient
# from bson import json_util
from decouple import config
from covis_db import db, hosts, misc
from datetime import datetime

from paramiko.client import SSHClient,AutoAddPolicy
from urllib.parse import urlparse
import getpass

#from covis_worker import process

parser = argparse.ArgumentParser()

# parser.add_argument('--config', default=config('PROCESS_CONFIG',""),
#                     help="Process.json files.  Can be a path, URL, or '-' for stdin")

parser.add_argument('--log', metavar='log', nargs='?',
                    default=config('LOG_LEVEL', default='WARNING'),
                    help='Logging level')
#
# parser.add_argument('--job', metavar='log', nargs='?',
#                     help='Job name')
#
# parser.add_argument('--count', default=0, type=int,
#                     metavar='N',
#                     help="Only queue N entries (used for debugging)")

parser.add_argument('--force', dest='force', action='store_true')

parser.add_argument('--dry-run', dest='dryrun', action='store_true')

# parser.add_argument("--run-local", dest='runlocal', action='store_true')

parser.add_argument('--privkey', nargs='?')

parser.add_argument('sftpurl', action='store')

# parser.add_argument('--skip-dmas', dest='skipdmas', action='store_true',
#                     help='Skip files which are only on DMAS')

args = parser.parse_args()
logging.basicConfig( level=args.log.upper() )

## Open db client
srcurl = urlparse(args.sftpurl)
username = srcurl.username if srcurl.username else getpass.getuser()
port = srcurl.port if srcurl.port else 22

logging.info("Connecting to %s:%d as %s with privkey %s" % (srcurl.hostname, port, username,args.privkey))

client = SSHClient()
client.set_missing_host_key_policy(AutoAddPolicy)  ## Ignore host key for now...
client.connect(srcurl.hostname,
                username=username,
                key_filename=args.privkey,
                passphrase="",
                port=port,
                allow_agent=True)

sftp = client.open_sftp()
logging.info("Changing to path %s" % srcurl.path)
sftp.chdir(srcurl.path)

## Meanwhile, setup the S3 connection as well

s3 = boto3.resource('s3',
                    endpoint_url = 'https://s3.us-west-1.wasabisys.com',
                    aws_access_key_id = config("S3_ACCESS_KEY"),
                    aws_secret_access_key = config("S3_SECRET_KEY"))

bucket_name = "covis-raw"
bucket = s3.Bucket(bucket_name)

out_msgs = []

for remote_file in sftp.listdir():

    logging.info("Considering remote file %s" % remote_file)

    if not misc.is_covis_file(remote_file):
        logging.info("   ... not a COVIS raw file, skipping...")
        continue


    try:
        s3.Object(bucket_name, str(remote_file)).load()
    except ClientError as e:
        if int(e.response['Error']['Code']) == 404:
            ## Object does not exist
            pass
        else:
            ## Some other error
            raise
    else:
        logging.info("The object %s exists in the S3 bucket" % remote_file)
        if not args.force:
            continue

        logging.info("   ... but --force specified, so doing it anyway")




    logging.info("File %s does not exist, uploading ..." % remote_file )

    if args.dryrun:
        logging.info(" .... dry run, skipping")
        continue

    #     ## Attempt to add to dest
    #
    #     logging.info("Uploading to destination host %s" % args.desthost)
    #
    #     run = db.make_run(basename=basename)
    #     raw = run.add_raw(args.desthost, make_filename=True)
    #     accessor = raw.accessor()
    #
    #     if not accessor:
    #         logging.error("Unable to get accessor for %s" % args.desthost)

    with sftp.open(remote_file) as sftpfile:

        statinfo = sftpfile.stat()

        logging.info("Writing %d bytes to S3 as \"%s\"" % (statinfo.st_size,remote_file))
        bucket.upload_fileobj(sftpfile, remote_file)

    out_msgs.append("Uploaded %s" % remote_file)
    logging.warning("Uploaded %s" % remote_file)


client.close()

if len(out_msgs) > 0:
    ## Report results

    subject = "sftp_to_wasabi %s" % datetime.now().strftime("%c")


    sg_key = config("SENDGRID_API_KEY",None)
    if sg_key:
        import sendgrid
        from sendgrid.helpers.mail import *

        sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))
        from_email = Email("amarburg@uw.edu")
        to_email = Email("amarburg@uw.edu")
        content = Content("text/plain", "\n".join(out_msgs))
        mail = Mail(from_email, subject, to_email, content )
        response = sg.client.mail.send.post(request_body=mail.get())

    mg_key = config("MAILGUN_API_KEY",None)
    if mg_key:
        import requests

        domain = "sandboxc489483675804e3dbbc362207206219c.mailgun.org"

        response = requests.post(
            "https://api.mailgun.net/v3/%s/messages" % domain,
            auth=("api", mg_key),
            data={"from": "amarburg@uw.edu",
                  "to": ["amarburg@uw.edu"],
                  "subject": subject,
                  "text": "\n".join(out_msgs)})

        logging.debug(response)


    #
    #
    #     logging.info("Upload successful, updating DB")
    #
    #     run = db.insert_run(run)
    #     if not run:
    #         logging.info("Error inserting into db...")
    #
    #     ## Ugliness
    #     run.insert_raw(raw)
    #





## If given, load JSON, otherwise initialize an empty config struct
#
# config = {}
#
# if args.config:
#     if Path(args.config).exist:
#         with open(args.config) as fp:
#             logging.info("Loading configuration from %s" % args.config)
#             config = json.load(args.config)
#
#     elif args.config == '-':
#         config = json.load(sys.stdin)
#
#
# if args.basename:
#     config["selector"] = { "basename": { "$in": args.basename } }
#
# if args.job:
#     config["job_id"] = args.job
#
#
# if not config["selector"]:
#     logging.error("No basenames provided")
#     exit()
#
# ## Default
# config["dest"] = { "minio": { "host": "covis-nas",
#                             "bucket": "postprocessed" }}
#
# # Validate configuration
# if "dest" not in config:
#     logging.error("No destination provided")
#     exit()
#
# prefix = ""
# if "job_id" in config:
#     prefix = "by_job_id/%s" % config["job_id"]
# else:
#     prefix = "no_job_id/%s" % datetime.now().strftime("%Y%m%d-%H%M%S")
#
# ## If specified, load the JSON configuration
# with client.runs.find(config["selector"]) as results:
#
#     for r in results:
#         print(r)
#
#         if not args.dryrun:
#
#             if args.runlocal:
#                 job = process.process(r['basename'], config["dest"],
#                                         job_prefix = prefix,
#                                         process_json = config.get("process_json", ""),
#                                         plot_json = config.get("plot_json", ""))
#             else:
#                 job = process.process.delay(r['basename'],config["dest"],
#                                         job_prefix = prefix,
#                                         process_json = config.get("process_json", ""),
#                                         plot_json = config.get("plot_json", ""))
#         else:
#             print("Dry run, skipping...")
#
# # # Validate destination hostname
# # if not hosts.validate_host(args.desthost):
# #     print("Can't understand destination host \"%s\"" % args.desthost)
# #     exit()
# #
#
# #
# # # Find run which are _not_ on NAS
# # result = client.runs.aggregate( [
# #     {"$match": { "$and":
# #                 [ { "raw.host": { "$not": { "$eq": "COVIS-NAS" } } }
# #                 ]
# #     } }
# # ])
# #
# # #                  { "mode":     {"$eq": "DIFFUSE"}} ]
# #
# #
# # # result = client.runs.aggregate( [
# # #     {"$match": { "$and":
# # #                 [ { "raw.host": { "$not": { "$eq": "COVIS-NAS" } } } ]
# # #     } }
# # # ])
# #
# # i = 0
# # for elem in result:
# #
# #     run = db.CovisRun(elem)
# #
# #     logging.info("Considering basename %s" % (run.basename))
# #
# #     locations = [raw.host for raw in run.raw]
# #
# #     if args.skipdmas and locations == ["DMAS"]:
# #         logging.info("    File only on DMAS, skipping...")
# #         continue
# #
# #
# #     logging.info("Queuing rezip job for %s on %s" % (run.basename, ','.join(locations)))
# #
# #     if not args.dryrun:
# #         job = rezip.rezip.delay(run.basename,args.desthost)
# #     else:
# #         print("Dry run, skipping...")
# #
# #     i = i+1
# #     if args.count > 0 and i > args.count:
# #         break
