##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################
from copy import deepcopy
import json
import logging
import time
from werkzeug.wrappers import Request

import pywps.dblog
from pywps import get_ElementMakerForVersion
from pywps.app.basic import select_response_mimetype, get_json_indent, get_default_response_mimetype
from pywps.exceptions import NoApplicableCode
import pywps.configuration as config
from werkzeug.wrappers import Response

from pywps.inout.array_encode import ArrayEncoder
from pywps.response.status import WPS_STATUS, StatusResponse

from pywps.inout.formats import FORMATS
from pywps.inout.outputs import ComplexOutput

import urllib.parse as urlparse
from urllib.parse import urlencode

from .WPSRequest import WPSRequest
from pywps.dblog import store_status

LOGGER = logging.getLogger("PYWPS")

WPS, OWS = get_ElementMakerForVersion("1.0.0")


class WPSExecuteResponse(object):
    """
    WPSExecuteResponse is the handler of outputs data for the user it will be
    used within an ExecuteResponse or StatusResponse if needed.

    It should be able to store it into the database to
    """

    def __init__(self, spec, wps_request: WPSRequest):
        """constructor

        Create output for the user API
        """
        self.wps_request = wps_request
        self.spec = spec
        self.uuid = wps_request.uuid

        # Initialized when workdir is set
        self.outputs = None

    # forward to request
    def __getattr__(self, item):
        return getattr(self.wps_request, item)

    def set_workdir(self, workdir : str):
        self.outputs = dict()
        for o in self.spec.outputs:
            json = self.wps_request.outputs.get(o.identifier, dict())
            self.outputs[o.identifier] = o.create(json=json, workdir=workdir)

    # override WPSResponse._update_status
    def _update_status(self, status, message, status_percentage):
        """
        Updates status report of currently running process instance:

        * Updates the status document.
        * Updates the status file (if requested).
        * Cleans the working directory when process has finished.

        This method is *only* called by pywps internally.
        """
        self._xupdate_status(status, message, status_percentage)
        LOGGER.debug(f"_update_status: status={status}")

        pywps.dblog.update_status_record(self.uuid, self.get_json_status())

    def _xupdate_status(self, status, message, status_percentage):
        """
        Update status report of currently running process instance

        :param str message: Message you need to share with the client
        :param int status_percentage: Percent done (number betwen <0-100>)
        :param pywps.response.status.WPS_STATUS status: process status - user should usually
            ommit this parameter
        """
        self.message = message
        self.status = status
        self.status_percentage = status_percentage
        store_status(self.uuid, self.status, self.message, self.status_percentage)

    def update_status(self, message, status_percentage=None):
        """
        Update status report of currently running process instance.

        This method is *only* called by the user provided process.
        The status is handled internally in pywps.

        :param str message: Message you need to share with the client
        :param int status_percentage: Percent done (number betwen <0-100>)
        """
        if status_percentage is None:
            status_percentage = self.status_percentage
        self._update_status(self.status, message, status_percentage, False)

    def _process_accepted(self):
        percent = int(self.status_percentage)
        if percent > 99:
            percent = 99
        return {
            "status": "accepted",
            "time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime()),
            "percent_done": str(percent),
            "message": self.message
        }

    def _process_started(self):
        data = self._process_accepted()
        data.update({
            "status": "started",
        })
        return data

    def _process_paused(self):
        data = self._process_accepted()
        data.update({
            "status": "paused",
        })
        return data

    def _process_succeeded(self):
        data = self._process_accepted()
        data.update({
            "status": "succeeded",
            "percent_done": "100"
        })
        return data

    def _process_failed(self):
        data = self._process_accepted()
        data.update({
            "status": "failed",
            "code": "NoApplicableCode",
            "locator": "None",
        })
        return data

    def _get_serviceinstance(self):

        url = config.get_config_value("server", "url")
        params = {'request': 'GetCapabilities', 'service': 'WPS'}

        url_parts = list(urlparse.urlparse(url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query.update(params)

        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts).replace("&", "&amp;")


    def get_json_status(self):
        """Return the json(python) representation of the status"""
        # FIXME: What is the purpose ??
        # if self.status == WPS_STATUS.SUCCEEDED and \
        #         hasattr(self.wps_request, 'preprocess_response') and \
        #         self.wps_request.preprocess_response:
        #     self.outputs = self.wps_request.preprocess_response(self.outputs,
        #                                                         request=self.wps_request,
        #                                                         http_request=self.http_request)
        #     self.preprocess_response = None

        data = dict()
        data["language"] = self.wps_request.language
        # data["service_instance"] = self._get_serviceinstance()

        # Replace by the identifier.
        data["process"] = self.spec.json
        data["version"] = self.version

        base_url = pywps.configuration.get_config_value('server', 'url').rstrip('/')
        data["status_locations"] = f"{base_url}/status?uuid={self.wps_request.uuid}"

        if self.status == WPS_STATUS.ACCEPTED:
            self.message = 'PyWPS Process {} accepted'.format(self.spec.identifier)
            data["status"] = self._process_accepted()
        elif self.status == WPS_STATUS.STARTED:
            data["status"] = self._process_started()
        elif self.status == WPS_STATUS.FAILED:
            # check if process failed and display fail message
            data["status"] = self._process_failed()
        elif self.status == WPS_STATUS.PAUSED:
            # TODO: handle paused status
            data["status"] = self._process_paused()
        elif self.status == WPS_STATUS.SUCCEEDED:
            data["status"] = self._process_succeeded()
            # Process outputs XML
            print(self.outputs)
            data["outputs"] = [o.json for o in self.outputs.values()]
        # lineage: add optional lineage when process has finished
        if self.status in [WPS_STATUS.SUCCEEDED, WPS_STATUS.FAILED]:
            # DataInputs and DataOutputs definition XML if lineage=true
            if self.wps_request.lineage == 'true':
                data["lineage"] = True

                xinputs = list()
                for i in self.spec.inputs:
                    if i.identifier in self.wps_request.inputs:
                        l = deepcopy(self.wps_request.inputs[i.identifier])
                        for x in l:
                            x.update({
                                'identifier': i.identifier,
                                'title': i.title,
                                'abstract': i.abstract,
                                'translations': i.translations
                            })
                        xinputs += l
                data["input_definitions"] = xinputs

                xoutputs = list()
                for i in self.spec.outputs:
                    # Expect all outputs even if not outputs where requested ?
                    l = deepcopy(self.wps_request.outputs.get(i.identifier,[{}]))
                    for x in l:
                        x.update({
                            'identifier': i.identifier,
                            'title': i.title,
                            'abstract': i.abstract,
                            'translations': i.translations
                        })
                    xoutputs += l
                data["output_definitions"] = xoutputs


        return data

