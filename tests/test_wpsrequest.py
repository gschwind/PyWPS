##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################
import copy
import unittest
from pywps.app import WPSRequest
import tempfile
import datetime
import json
from owslib.crs import Crs
from io import BytesIO
import werkzeug

from pywps.inout.literaltypes import AnyValue

XML = \
"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<wps:Execute service="WPS" version="1.0.0"
    xmlns:wps="http://www.opengis.net/wps/1.0.0"
    xmlns:ows="http://www.opengis.net/ows/1.1"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://schemas.opengis.net/wps/1.0.0 wpsExecute_request.xsd">
<ows:Identifier>compute_polygon</ows:Identifier>
<wps:DataInputs>
    <wps:Input>
        <ows:Identifier>json</ows:Identifier>
        <wps:Data><wps:ComplexData mimeType="application/json" >
            { "a": 34.0, "b": "]]&gt;", "c": "&lt;!CDADA[[" }
        </wps:ComplexData></wps:Data>
    </wps:Input>
    <wps:Input>
        <ows:Identifier>binary</ows:Identifier>
        <wps:Data><wps:ComplexData mimeType="application/zip" encoding="base64" >
            SGVsbG8gd29ybGQh
        </wps:ComplexData></wps:Data>
    </wps:Input>
    <wps:Input>
        <ows:Identifier>username</ows:Identifier>
        <wps:Data><wps:LiteralData>none</wps:LiteralData></wps:Data>
    </wps:Input>
</wps:DataInputs>
<wps:ResponseForm>
    <wps:ResponseDocument lineage="false" storeExecuteResponse="true" status="true">
        <wps:Output asReference="true" mimeType="application/x-netcdf">
            <ows:Identifier>result</ows:Identifier>
        </wps:Output>
    </wps:ResponseDocument>
</wps:ResponseForm>
</wps:Execute>"""

fake_environ = {
    'wsgi.version': (1, 0),
    'wsgi.url_scheme': 'http',
    'wsgi.multithread': False,
    'wsgi.multiprocess': False,
    'wsgi.run_once': False,
    'SERVER_SOFTWARE': 'Werkzeug/2.1.1',
    'REQUEST_METHOD': 'POST',
    'SCRIPT_NAME': '',
    'PATH_INFO': '/service/wps',
    'QUERY_STRING': 'Service=WPS&version=1.0.0',
    'REQUEST_URI': '/service/wps?Service=WPS&version=1.0.0',
    'RAW_URI': '/service/wps?Service=WPS&version=1.0.0',
    'REMOTE_ADDR': '127.0.0.1',
    'REMOTE_PORT': 55272,
    'SERVER_NAME': '127.0.0.1',
    'SERVER_PORT': '8080',
    'SERVER_PROTOCOL': 'HTTP/1.1',
    'HTTP_ACCEPT_ENCODING': 'identity',
    'CONTENT_LENGTH': str(len(XML)),
    'HTTP_HOST': 'localhost:8080',
    'HTTP_USER_AGENT': 'Python-urllib/3.9',
    'CONTENT_TYPE': 'application/xml; charset=UTF-8',
    'HTTP_CONNECTION': 'close'
}



class WPSRequestTest(unittest.TestCase):

    def setUp(self):

        self.request = WPSRequest()
        self.tempfile = tempfile.mktemp()

        x = open(self.tempfile, 'w')
        x.write("ahoj")
        x.close()

    def test_json_in(self):

        obj = {
            'operation': 'getcapabilities',
            'version': '1.0.0',
            'language': 'eng',
            'identifier': 'ahoj',
            'identifiers': 'ahoj',  # TODO: why identifierS?
            'store_execute': True,
            'status': True,
            'lineage': True,
            'inputs': {
                'myin': [{
                    'identifier': 'myin',
                    'type': 'complex',
                    'supported_formats': [{
                        'mime_type': 'tralala'
                    }],
                    'file': self.tempfile,
                    'data_format': {'mime_type': 'tralala'}
                }],
                'myliteral': [{
                    'identifier': 'myliteral',
                    'type': 'literal',
                    'data_type': 'integer',
                    'allowed_values': [{'type': 'anyvalue'}],
                    'data': 1
                }]
            },
            'outputs': {},
            'raw': False
        }

        self.request = WPSRequest()
        self.request.json = obj

        self.assertEqual(self.request.inputs['myliteral'][0].data, 1, 'Data are in the file')
        self.assertEqual(self.request.inputs['myin'][0].data, 'ahoj', 'Data are in the file')
        self.assertListEqual(self.request.inputs['myliteral'][0].allowed_values, [AnyValue()], 'Any value not set')
        self.assertTrue(self.request.inputs['myliteral'][0].any_value, 'Any value set')

    def test_json_inout_datetime(self):
        obj = {
            'operation': 'getcapabilities',
            'version': '1.0.0',
            'language': 'eng',
            'identifier': 'moinmoin',
            'identifiers': 'moinmoin',  # TODO: why identifierS?
            'store_execute': True,
            'status': True,
            'lineage': True,
            'inputs': {
                'datetime': [{
                    'identifier': 'datetime',
                    'type': 'literal',
                    'data_type': 'dateTime',
                    'data': '2017-04-20T12:00:00',
                    'allowed_values': [{'type': 'anyvalue'}],
                }],
                'date': [{
                    'identifier': 'date',
                    'type': 'literal',
                    'data_type': 'date',
                    'data': '2017-04-20',
                    'allowed_values': [{'type': 'anyvalue'}],
                }],
                'time': [{
                    'identifier': 'time',
                    'type': 'literal',
                    'data_type': 'time',
                    'data': '09:00:00',
                    'allowed_values': [{'type': 'anyvalue'}],
                }],
            },
            'outputs': {},
            'raw': False
        }

        self.request = WPSRequest()
        self.request.json = obj

        self.assertEqual(self.request.inputs['datetime'][0].data, datetime.datetime(2017, 4, 20, 12), 'Datatime set')
        self.assertEqual(self.request.inputs['date'][0].data, datetime.date(2017, 4, 20), 'Data set')
        self.assertEqual(self.request.inputs['time'][0].data, datetime.time(9, 0, 0), 'Time set')

        # dump to json and reload
        dump = self.request.json
        self.request.json = json.loads(dump)

        self.assertEqual(self.request.inputs['datetime'][0].data, datetime.datetime(2017, 4, 20, 12), 'Datatime set')
        self.assertEqual(self.request.inputs['date'][0].data, datetime.date(2017, 4, 20), 'Data set')
        self.assertEqual(self.request.inputs['time'][0].data, datetime.time(9, 0, 0), 'Time set')

    def test_json_inout_bbox(self):
        obj = {
            'operation': 'getcapabilities',
            'version': '1.0.0',
            'language': 'eng',
            'identifier': 'arghhhh',
            'identifiers': 'arghhhh',  # TODO: why identifierS?
            'store_execute': True,
            'status': True,
            'lineage': True,
            'inputs': {
                'bbox': [{
                    'identifier': 'bbox',
                    'type': 'bbox',
                    'bbox': '6.117602,46.176194,6.22283,46.275832',
                    'crs': 'urn:ogc:def:crs:EPSG::4326',
                    'crss': ['epsg:4326'],
                    'dimensions': 2,
                    'translations': None
                }],
            },
            'outputs': {},
            'raw': False
        }

        self.request = WPSRequest()
        self.request.json = obj

        self.assertEqual(self.request.inputs['bbox'][0].data, [6.117602, 46.176194, 6.22283, 46.275832], 'BBox data set')
        self.assertTrue(isinstance(self.request.inputs['bbox'][0].crs, str), 'CRS is a string')
        self.assertEqual(self.request.inputs['bbox'][0].crs, 'epsg:4326', 'CRS data correctly parsed')

        # dump to json and reload
        dump = self.request.json
        self.request.json = json.loads(dump)

        self.assertEqual(self.request.inputs['bbox'][0].data, [6.117602, 46.176194, 6.22283, 46.275832], 'BBox data set')
        self.assertTrue(isinstance(self.request.inputs['bbox'][0].crs, str), 'CRS is a string')
        self.assertEqual(self.request.inputs['bbox'][0].crs, 'epsg:4326', 'CRS data correctly parsed')


    def test_with_xml(self):
        environ = copy.deepcopy(fake_environ)
        environ.update({
            'wsgi.input': BytesIO(XML.encode("utf-8")),
            'wsgi.errors': BytesIO()
        })
        http_request = werkzeug.wrappers.request.Request(environ)
        wps_request = WPSRequest(http_request=http_request)

        self.assertEqual(json.loads(wps_request.inputs['json'][0]['data']), { "a": 34.0, "b": "]]>", "c": "<!CDADA[[" })
        assert wps_request.inputs['binary'][0]['data'] == b'Hello world!'
        assert wps_request.inputs['username'][0]['data'] == 'none'

        wps_request2 = WPSRequest()

        # test serialisation/deserialisation
        #wps_request2.json = json.loads(wps_request.json)
        #self.assertEqual(wps_request, wps_request2)


def load_tests(loader=None, tests=None, pattern=None):
    if not loader:
        loader = unittest.TestLoader()
    suite_list = [
        loader.loadTestsFromTestCase(WPSRequestTest)
    ]
    return unittest.TestSuite(suite_list)
