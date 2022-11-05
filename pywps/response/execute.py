##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################
import copy
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
from .basic import WPSResponse
from pywps.inout.formats import FORMATS
from pywps.inout.outputs import ComplexOutput

import urllib.parse as urlparse
from urllib.parse import urlencode

from pywps import dblog

LOGGER = logging.getLogger("PYWPS")

WPS, OWS = get_ElementMakerForVersion("1.0.0")


class ExecuteResponseRaw(Response):

    def __init__(self, uuid, mimetype):

        status = dblog.get_status_record(uuid)
        if status is None:
            raise NoApplicableCode("Invalid uuid for status request", code=500)

        # TODO: update
        if status == WPS_STATUS.FAILED:
            return NoApplicableCode(self.message)
        else:
            wps_output_identifier = next(iter(self.wps_request.outputs))  # get the first key only
            wps_output_value = self.outputs[wps_output_identifier]
            response = wps_output_value.data
            if response is None:
                return NoApplicableCode("Expected output was not generated")
            suffix = ''
            # if isinstance(wps_output_value, ComplexOutput):
            data_format = None
            if hasattr(wps_output_value, 'output_format'):
                # this is set in the response, thus should be more precise
                data_format = wps_output_value.output_format
            elif hasattr(wps_output_value, 'data_format'):
                # this is set in the process' response _handler function, thus could have a few supported formats
                data_format = wps_output_value.data_format
            if data_format is not None:
                mimetype = data_format.mime_type
                if data_format.extension is not None:
                    suffix = data_format.extension
            else:
                # like LitearlOutput
                mimetype = self.wps_request.outputs[wps_output_identifier].get('mimetype', None)
            if not isinstance(response, (str, bytes, bytearray)):
                if not mimetype:
                    mimetype = self.mimetype
                json_response = mimetype and 'json' in mimetype
                if json_response:
                    mimetype = 'application/json'
                    suffix = '.json'
                    response = json.dumps(response, cls=ArrayEncoder, indent=get_json_indent())
                else:
                    response = str(response)
            if not mimetype:
                mimetype = None

        super().__init__(response, mimetype=mimetype,
                            headers={'Content-Disposition': 'attachment; filename="{}"'
                                     .format(wps_output_identifier + suffix)})

    def _get_serviceinstance(self):

        url = config.get_config_value("server", "url")
        params = {'request': 'GetCapabilities', 'service': 'WPS'}

        url_parts = list(urlparse.urlparse(url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query.update(params)

        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts).replace("&", "&amp;")

    @Request.application
    def __call__(self, request):
        if self.status == WPS_STATUS.FAILED:
            return NoApplicableCode(self.message)
        else:
            wps_output_identifier = next(iter(self.wps_request.outputs))  # get the first key only
            wps_output_value = self.outputs[wps_output_identifier]
            response = wps_output_value.data
            if response is None:
                return NoApplicableCode("Expected output was not generated")
            suffix = ''
            # if isinstance(wps_output_value, ComplexOutput):
            data_format = None
            if hasattr(wps_output_value, 'output_format'):
                # this is set in the response, thus should be more precise
                data_format = wps_output_value.output_format
            elif hasattr(wps_output_value, 'data_format'):
                # this is set in the process' response _handler function, thus could have a few supported formats
                data_format = wps_output_value.data_format
            if data_format is not None:
                mimetype = data_format.mime_type
                if data_format.extension is not None:
                    suffix = data_format.extension
            else:
                # like LitearlOutput
                mimetype = self.wps_request.outputs[wps_output_identifier].get('mimetype', None)
            if not isinstance(response, (str, bytes, bytearray)):
                if not mimetype:
                    mimetype = self.mimetype
                json_response = mimetype and 'json' in mimetype
                if json_response:
                    mimetype = 'application/json'
                    suffix = '.json'
                    response = json.dumps(response, cls=ArrayEncoder, indent=get_json_indent())
                else:
                    response = str(response)
            if not mimetype:
                mimetype = None
            return Response(response, mimetype=mimetype,
                            headers={'Content-Disposition': 'attachment; filename="{}"'
                                     .format(wps_output_identifier + suffix)})



class ExecuteResponse(WPSResponse):

    def __init__(self, http_request, json_data):
        """constructor

        :param pywps.app.WPSRequest.WPSRequest wps_request:
        :param pywps.app.Process.Process process:
        :param uuid: string this request uuid
        """

        super(ExecuteResponse, self).__init__(http_request, wps_request, uuid)

        self.process = kwargs["process"]
        self.outputs = {o.identifier: copy.deepcopy(o) for o in self.process.outputs}
        self.store_status_file = False

        # select the output mimetype
        accept_mimetypes = getattr(self.http_request, 'accept_mimetypes', None)
        self.mimetype = select_response_mimetype(accept_mimetypes, self.wps_request.default_mimetype)

    def _get_serviceinstance(self):

        url = config.get_config_value("server", "url")
        params = {'request': 'GetCapabilities', 'service': 'WPS'}

        url_parts = list(urlparse.urlparse(url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query.update(params)

        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts).replace("&", "&amp;")

    @Request.application
    def __call__(self, request):
        if self.wps_request.raw:
            if self.status == WPS_STATUS.FAILED:
                return NoApplicableCode(self.message)
            else:
                wps_output_identifier = next(iter(self.wps_request.outputs))  # get the first key only
                wps_output_value = self.outputs[wps_output_identifier]
                response = wps_output_value.data
                if response is None:
                    return NoApplicableCode("Expected output was not generated")
                suffix = ''
                # if isinstance(wps_output_value, ComplexOutput):
                data_format = None
                if hasattr(wps_output_value, 'output_format'):
                    # this is set in the response, thus should be more precise
                    data_format = wps_output_value.output_format
                elif hasattr(wps_output_value, 'data_format'):
                    # this is set in the process' response _handler function, thus could have a few supported formats
                    data_format = wps_output_value.data_format
                if data_format is not None:
                    mimetype = data_format.mime_type
                    if data_format.extension is not None:
                        suffix = data_format.extension
                else:
                    # like LitearlOutput
                    mimetype = self.wps_request.outputs[wps_output_identifier].get('mimetype', None)
                if not isinstance(response, (str, bytes, bytearray)):
                    if not mimetype:
                        mimetype = self.mimetype
                    json_response = mimetype and 'json' in mimetype
                    if json_response:
                        mimetype = 'application/json'
                        suffix = '.json'
                        response = json.dumps(response, cls=ArrayEncoder, indent=get_json_indent())
                    else:
                        response = str(response)
                if not mimetype:
                    mimetype = None
                return Response(response, mimetype=mimetype,
                                headers={'Content-Disposition': 'attachment; filename="{}"'
                                         .format(wps_output_identifier + suffix)})
        else:
            # Here StatusResponse need only outputs and their value.
            # They are picked in json['process']['outputs']
            return StatusResponse(self.json, self.mimetype)
