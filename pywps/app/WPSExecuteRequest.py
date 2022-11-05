##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

import logging

import lxml
from pywps import xml_util as etree
from werkzeug.exceptions import MethodNotAllowed
from pywps import get_ElementMakerForVersion
import base64
import datetime
from pywps.app.basic import get_xpath_ns, parse_http_url
from pywps.inout.inputs import input_from_json
from pywps.exceptions import NoApplicableCode, OperationNotSupported, MissingParameterValue, VersionNegotiationFailed, \
    InvalidParameterValue, FileSizeExceeded
from pywps import configuration
from pywps.configuration import wps_strict
from pywps import get_version_from_ns

import json
import uuid
from urllib.parse import unquote

LOGGER = logging.getLogger("PYWPS")
default_version = '1.0.0'


class WPSExecuteRequest(object):

    def __init__(self, spec, wps_request):
        self.spec = spec
        self.request = wps_request

        # Uninitialized until workdir is set
        self.inputs = None

    # Keep previous behaviours
    def __getattr__(self, item):
        LOGGER.warning(f"Deprecated access to WPSExecuteRequest.{item}")
        return getattr(self.request, item)

    def set_workdir(self, workdir):
        """Parse input data for the given process and update wps_request accordingly
        """
        LOGGER.debug('Checking if all mandatory inputs have been passed')
        inputs = dict()
        for i in self.spec.inputs:
            # Replace the dicts with the dict of Literal/Complex inputs
            # set the input to the type defined in the process.
            request_inputs = self.request.inputs.get(i.identifier, None)
            if request_inputs is None:
                if i._default is not None:
                    inputs[i.identifier] = i.create([{'data':i._default}], workdir=workdir)
                continue
            inputs[i.identifier] = i.create(request_inputs, workdir=workdir)

        self.inputs = inputs

