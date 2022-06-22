#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

import pywps.configuration
import pywps.dblog as db
from pywps.response.status import WPS_STATUS

pywps.configuration.load_configuration(sys.argv[1])

print(db.get_process_counts())

session = db.get_session()
unfinished_request_list = []
for p in session.query(db.ProcessInstance).filter(db.ProcessInstance.percent_done < 100):
    unfinished_request_list.append(p.uuid)

for u in unfinished_request_list:
    db.store_status(u, WPS_STATUS.FAILED, 'crashed', 100)

# remove all queued request
while pywps.dblog.pop_first_stored() is not None:
    pass

