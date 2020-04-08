#---- Tasks designed to be run _INSIDE THE DOCKER CONTAINER_ ----
# This file is copied to "Makefile" in the Dockerfile

## Use the ENV variable preferentially, otherwise here's a default
CELERY_BROKER ?= amqp://user:bitnami@localhost

flower:
	celery flower -A covis_worker --broker=${CELERY_BROKER}

worker:
	celery -A covis_worker worker -l info --concurrency 1 --without-mingle --without-gossip --events

idle:
	while true; do sleep 3600; done

covis_import_sftp_to_nas:
	apps/import_sftp.py --run-local --log INFO sftp://covis@pi.ooirsn.uw.edu/data/COVIS

covis_import_sftp_to_nas_and_postprocess:
	apps/import_sftp.py --run-local --log INFO --postprocess sftp://covis@pi.ooirsn.uw.edu/data/COVIS

covis_import_sftp_to_s3:
	apps/sftp_to_wasabi.py --bucket covis-raw --log INFO ftp://covis@pi.ooirsn.uw.edu/data/COVIS
	apps/sftp_to_wasabi.py --bucket covis-eng --log INFO ftp://covis@pi.ooirsn.uw.edu/data/COVIS-ENG

## ==

.PHONY:  flower worker idle \
					load_seed_data