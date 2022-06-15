#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

import pywps.configuration
import pywps.dblog

pywps.configuration.load_configuration(sys.argv[1])

print(pywps.dblog.get_process_counts())

# remove all queued request
while pywps.dblog.pop_first_stored() is not None:
    pass
