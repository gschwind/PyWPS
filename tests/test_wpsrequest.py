##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

import unittest

import pywps.inout.outputs
from pywps.app import WPSRequest
import tempfile
import datetime
import json
import uuid
from owslib.crs import Crs

from pywps.inout.literaltypes import AnyValue
from pywps import Process, ComplexInput, ComplexOutput, LiteralInput, \
    LiteralOutput, BoundingBoxInput, BoundingBoxOutput

from pywps import Format
from pywps.validator import get_validator

def get_data_format(mime_type):
    return Format(mime_type=mime_type, validate=get_validator(mime_type))

class WPSRequestTest(unittest.TestCase):

    def setUp(self):

        self.spec = Process(
           lambda x, y: None,
            identifier = 'ahoj',
            version='1.0',
            title='some title',
            abstract='some abstract',
            store_supported=True,
            status_supported=True,
            inputs=[
                ComplexInput(
                    identifier='mycomplex',
                    supported_formats=[get_data_format('application/json')]
                ),
                LiteralInput(
                    identifier='myinteger',
                    data_type='integer',
                    max_occurs=10
                ),
                LiteralInput(
                    identifier='mydatetime',
                    data_type='dateTime',
                    max_occurs=10
                ),
                LiteralInput(
                    identifier='mytime',
                    data_type='time',
                    max_occurs=10
                ),
                LiteralInput(
                    identifier='mydate',
                    data_type='date',
                    max_occurs=10
                ),
                BoundingBoxInput(
                    identifier='mybbox',
                    crss=['urn:ogc:def:crs:EPSG::4326', 'epsg:4326']
                )
            ],
            outputs=[]

        )

        self.json_base = {
            'uuid': str(uuid.uuid1()),
            'is_async': False,
            'operation': 'getcapabilities', #< ???
            'version': '1.0.0',
            'language': 'eng',
            'identifier': 'ahoj',
            'identifiers': 'ahoj',  #< Identifiers are used for describe process
            'store_execute': True,
            'status': True,
            'lineage': True,
            'outputs': dict(),
            'raw': False
        }

    def test_json_literal_integer(self):
        obj = self.json_base
        obj['inputs'] = {
            'myinteger': [{
                'identifier': 'myinteger',
                'type': 'literal',
                'data': 1
            }, {
                'identifier': 'myinteger',
                'type': 'literal',
                'data': 2
            }]
        }

        self.request = WPSRequest(json=obj)
        self.assertTrue('myinteger' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['myinteger'], list)
        # self.assertEqual(self.request.inputs['myinteger'][0].data, 1)
        # self.assertEqual(self.request.inputs['myinteger'][1].data, 2)

        # dump to json and reload
        obj = self.request.json
        self.request = WPSRequest(json=obj)
        self.assertTrue('myinteger' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['myinteger'], list)
        # self.assertEqual(self.request.inputs['myinteger'][0].data, 1)
        # self.assertEqual(self.request.inputs['myinteger'][1].data, 2)

    def test_json_complex(self):
        obj = self.json_base
        obj['inputs'] = {
            'mycomplex': [{
                'identifier': 'myin',
                'type': 'complex',
                'data': 'ahoj',
                'mimetype': None,
                'schema': None,
                'encoding': None
            }],
        }

        self.request = WPSRequest(json=obj)

        self.assertTrue('mycomplex' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mycomplex'], list)
        # self.assertIsInstance(self.request.inputs['mycomplex'][0], pywps.inout.inputs.ComplexInput)
        # self.assertEqual(self.request.inputs['mycomplex'][0].data, 'ahoj')

    def test_json_literal_datetime(self):
        obj = self.json_base
        obj['inputs'] = {
            'mydatetime': [{
                'identifier': 'mydatetime',
                'type': 'literal',
                'data': '2017-04-20T12:00:00'
            }]
        }

        self.request = WPSRequest(json=obj)

        self.assertTrue('mydatetime' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mydatetime'], list)
        # self.assertEqual(self.request.inputs['mydatetime'][0].data, datetime.datetime(2017, 4, 20, 12))

        # dump to json and reload
        obj = self.request.json

        self.request = WPSRequest(json=obj)

        self.assertTrue('mydatetime' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mydatetime'], list)
        # self.assertEqual(self.request.inputs['mydatetime'][0].data, datetime.datetime(2017, 4, 20, 12))

    def test_json_literal_date(self):
        obj = self.json_base
        obj['inputs'] = {
            'mydate': [{
                'identifier': 'mydate',
                'type': 'literal',
                 'data': '2017-04-20'
            }]
        }

        self.request = WPSRequest(json=obj)
        self.assertTrue('mydate' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mydate'], list)
        # self.assertEqual(self.request.inputs['mydate'][0].data, datetime.date(2017, 4, 20))

        # dump to json and reload
        obj = self.request.json
        self.request = WPSRequest(json=obj)
        self.assertTrue('mydate' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mydate'], list)
        # self.assertEqual(self.request.inputs['mydate'][0].data, datetime.date(2017, 4, 20))

    def test_json_literal_time(self):
        obj = self.json_base
        obj['inputs'] = {
            'mytime': [{
                'identifier': 'mytime',
                'type': 'literal',
                'data': '09:00:00'
            }]
        }

        self.request = WPSRequest(json=obj)
        self.assertTrue('mytime' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mytime'], list)
        # self.assertEqual(self.request.inputs['mytime'][0].data, datetime.time(9, 0, 0), 'Time set')

        # dump to json and reload
        obj = self.request.json
        self.request = WPSRequest(json=obj)
        self.assertTrue('mytime' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mytime'], list)
        # self.assertEqual(self.request.inputs['mytime'][0].data, datetime.time(9, 0, 0), 'Time set')

    def test_json_inout_bbox(self):
        obj = self.json_base
        obj['inputs'] = {
            'mybbox': [{
                'identifier': 'mybbox',
                'type': 'bbox',
                'data': '6.117602,46.176194,6.22283,46.275832',
                'crs': 'urn:ogc:def:crs:EPSG::4326',
                'dimensions': 2
            }]
        }

        self.request = WPSRequest(json=obj)
        self.assertTrue('mybbox' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mybbox'], list)
        # self.assertEqual(self.request.inputs['mybbox'][0].data, [6.117602, 46.176194, 6.22283, 46.275832], 'BBox data set')
        # self.assertTrue(isinstance(self.request.inputs['mybbox'][0].crs, str), 'CRS is a string')
        # self.assertEqual(self.request.inputs['mybbox'][0].crs, 'urn:ogc:def:crs:EPSG::4326', 'CRS data correctly parsed')

        # dump to json and reload
        obj = self.request.json
        self.request = WPSRequest(json=obj)
        self.assertTrue('mybbox' in self.request.inputs)
        self.assertIsInstance(self.request.inputs['mybbox'], list)
        # self.assertEqual(self.request.inputs['mybbox'][0].data, [6.117602, 46.176194, 6.22283, 46.275832], 'BBox data set')
        # self.assertTrue(isinstance(self.request.inputs['mybbox'][0].crs, str), 'CRS is a string')
        # self.assertEqual(self.request.inputs['mybbox'][0].crs, 'urn:ogc:def:crs:EPSG::4326', 'CRS data correctly parsed')
