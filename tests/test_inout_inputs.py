# -*- coding: utf-8 -*-

"""Unit tests for IOs
"""
##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################


import requests
import os
import tempfile
import unittest
import json
import pywps
from pywps import inout
import base64

from pywps import Format, FORMATS
from pywps.app.Common import Metadata
from pywps.validator import get_validator

from pywps.inout.basic import IOHandler, SOURCE_TYPE, _is_textfile
from pywps.inout.inputs import BoundingBoxInput, ComplexInput, LiteralInput, \
    ReferenceInput

from pywps.util import uri_to_path
from pywps.inout.literaltypes import convert, AllowedValue, AnyValue
from io import StringIO
from urllib.parse import urlparse
from pywps.validator.base import emptyvalidator
from pywps.exceptions import InvalidParameterValue
from pywps.validator.mode import MODE
from pywps.inout.basic import UOM
from pywps.inout.storage.database import DatabaseStorage
from pywps.tests import service_ok
from pywps.translations import get_translation



DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


def get_data_format(mime_type):
    return Format(mime_type=mime_type, validate=get_validator(mime_type))


class ComplexInputTest(unittest.TestCase):
    """ComplexInput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        data_format = get_data_format('application/json')

        self.spec = pywps.ComplexInput(
            identifier="complexinput",
            title='MyComplex',
            abstract='My complex input',
            keywords=['kw1', 'kw2'],
            supported_formats=[data_format]
        )

        json = {
            'data': "Hallo world!"
        }

        self.complex_in = ComplexInput(self.spec, json, workdir=self.tmp_dir)

    # def test_validator(self):
    #     self.assertEqual(self.complex_in.data_format.validate,
    #                      get_validator('application/json'))
    #     self.assertEqual(self.complex_in.validator,
    #                      get_validator('application/json'))
    #     frmt = get_data_format('application/json')
    #
    #     def my_validate():
    #         return True
    #
    #     frmt.validate = my_validate
    #     self.assertNotEqual(self.complex_in.validator, frmt.validate)

    def test_contruct(self):
        self.assertIsInstance(self.complex_in, ComplexInput)

    # def test_data_format(self):
    #     self.assertIsInstance(self.complex_in.supported_formats[0], Format)


class SerializationComplexInputTest(unittest.TestCase):
    """ComplexInput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        self.spec = pywps.ComplexInput(
            identifier="complexinput",
            title='MyComplex',
            abstract='My complex input',
            keywords=['kw1', 'kw2'],
            supported_formats=[get_data_format('application/json')],
            metadata=[Metadata("special data")],
            default="/some/file/path",
            default_type=SOURCE_TYPE.FILE,
            translations={
                "fr-CA": {"title": "Mon input", "abstract": "Une description"}},
        )

    def assert_complex_equals(self, complex_1, complex_2):
        self.assertEqual(complex_1.workdir, complex_2.workdir)
        self.assertEqual(complex_1.mimetype, complex_2.mimetype)
        self.assertEqual(complex_1.encoding, complex_2.encoding)
        self.assertEqual(complex_1.schema, complex_2.schema)

    def test_complex_input_data(self):
        input = {
            'data': 'some data'
        }

        complex0 = ComplexInput(self.spec, input, workdir=self.tmp_dir)
        complex1 = ComplexInput(complex0.spec, complex0.json)
        self.assert_complex_equals(complex0, complex1)
        self.assertEqual(complex0.prop, 'data')
        self.assertEqual(complex1.prop, 'data')
        self.assertEqual(complex0.data, complex1.data)

    def test_complex_input_base64(self):
        input = {
            'encoding' : 'base64',
            'data': base64.b64encode(b'some data').decode("utf-8")
        }
        complex0 = ComplexInput(self.spec, input, workdir=self.tmp_dir)
        complex1 = ComplexInput(complex0.spec, complex0.json)
        self.assert_complex_equals(complex0, complex1)
        self.assertEqual(complex0.prop, 'data')
        self.assertEqual(complex1.prop, 'data')
        self.assertEqual(complex0.data, complex1.data)
        self.assertEqual(complex0.data, b'some data')


    # def test_complex_input_url(self):
    #     complex = self.make_complex_input()
    #     complex.url = "http://test.opendap.org:80/opendap/netcdf/examples/sresa1b_ncar_ccsm3_0_run1_200001.nc"
    #     complex2 = ComplexInput.from_json(complex.json)
    #     self.assert_complex_equals(complex, complex2)
    #     self.assertEqual(complex.prop, 'url')


class SerializationLiteralInputTest(unittest.TestCase):
    """LiteralInput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        self.spec = pywps.LiteralInput(
            identifier="complexinput",
            title='MyComplex',
            data_type='string',
            abstract="some description",
            keywords=['kw1', 'kw2'],
            metadata=[Metadata("special data")],
            uoms=['metre', 'unity'],
            min_occurs=2,
            max_occurs=5,
            mode=MODE.STRICT,
            allowed_values=[AllowedValue(value='something'),
                            AllowedValue(value='something else'), AnyValue()],
            default="something else",
            default_type=SOURCE_TYPE.DATA,
        )


    def make_literal_input(self):

        json = {
            'data': 'something',
            'uom':  UOM('unity')
        }

        literal = LiteralInput(self.spec, json, workdir=self.tmp_dir)
        return literal

    def assert_literal_equals(self, literal_1, literal_2):
        self.assertEqual(literal_1.src_data, literal_2.src_data)
        self.assertEqual(literal_1.uom, literal_2.uom)
        self.assertEqual(literal_1.data_type, literal_2.data_type)

    def test_literal_input(self):
        literal1 = self.make_literal_input()
        literal2 = LiteralInput(literal1.spec, literal1.json)
        self.assert_literal_equals(literal1, literal2)


class SerializationBoundingBoxInputTest(unittest.TestCase):
    """LiteralInput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        self.spec = pywps.BoundingBoxInput(
            identifier="bbox",
            title='BBox',
            crss=['epsg:3857', 'epsg:4326'],
            abstract="some description",
            keywords=['kw1', 'kw2'],
            dimensions=2,
            metadata=[Metadata("bbox")],
            min_occurs=2,
            max_occurs=5,
            mode=MODE.NONE,
            default="0,50,20,70",
            default_type=SOURCE_TYPE.DATA
        )

    def make_bbox_input(self):
        input = {
            'data': "1,2,3,4"
        }
        bbox = BoundingBoxInput(self.spec, input, workdir=self.tmp_dir)
        return bbox

    def assert_bbox_equals(self, bbox_1, bbox_2):
        self.assertEqual(bbox_1.crs, bbox_2.crs)
        self.assertEqual(bbox_1.dimensions, bbox_2.dimensions)
        self.assertEqual(bbox_1.workdir, bbox_2.workdir)
        self.assertEqual(bbox_1.ll, bbox_2.ll)
        self.assertEqual(bbox_1.ur, bbox_2.ur)

    def test_bbox_input(self):
        bbox1 = self.make_bbox_input()
        bbox2 = BoundingBoxInput(bbox1.spec, bbox1.json)
        self.assert_bbox_equals(bbox1, bbox2)


class DodsReferenceInputTest(unittest.TestCase):
    """ComplexInput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        data_format = get_data_format('application/x-ogc-dods')
        self.spec = pywps.ComplexInput(
            identifier="complexinput",
            title='MyComplex',
            abstract='My complex input',
            keywords=['kw1', 'kw2'],
            data_format=data_format,
            supported_formats=[data_format,
                               get_data_format('application/x-netcdf')]
        )

        json = {
            'href': "http://test.opendap.org:80/opendap/netcdf/examples/sresa1b_ncar_ccsm3_0_run1_200001.nc"
        }

        self.complex_in = ReferenceInput(self.spec, json, workdir=self.tmp_dir)

    # def test_validator(self):
    #     self.assertEqual(self.complex_in.data_format.validate,
    #                      get_validator('application/x-ogc-dods'))
    #     self.assertEqual(self.complex_in.validator,
    #                      get_validator('application/x-ogc-dods'))
    #     frmt = get_data_format('application/x-ogc-dods')
    #
    #     def my_validate():
    #         return True
    #
    #     frmt.validate = my_validate
    #     self.assertNotEqual(self.complex_in.validator, frmt.validate)

    def test_contruct(self):
        self.assertIsInstance(self.complex_in, ReferenceInput)


class LiteralInputTest(unittest.TestCase):
    """LiteralInput test cases"""

    def setUp(self):
        self.spec = pywps.LiteralInput(
            identifier="literalinput",
            title="Literal Input",
            data_type='integer',
            validate_mode=2,
            allowed_values=(1, 2, (3, 3, 12)),
            default=6,
            uoms=(UOM("metre"), UOM("km / h", "custom reference")),
            translations={
                "fr-CA": {"title": "Mon input", "abstract": "Une description"}}
        )

        self.literal_input = LiteralInput(self.spec, { 'data': 9, 'datatype': 'integer' })

    # TODO: implement
    # def test_valid(self):
    #     self.assertEqual(self.literal_input.data, 6)
    #     self.literal_input.data = 1
    #     self.assertEqual(self.literal_input.data, 1)
    #
    #     with self.assertRaises(InvalidParameterValue):
    #         self.literal_input.data = 5
    #
    #     with self.assertRaises(InvalidParameterValue):
    #         self.literal_input.data = "a"
    #
    #     with self.assertRaises(InvalidParameterValue):
    #         self.literal_input.data = 15
    #
    #     self.literal_input.data = 6
    #     self.assertEqual(self.literal_input.data, 6)

    def test_json_out(self):
        out = self.literal_input.json

        # Required for Execupte XML when lineage=True
        self.assertEqual(out['identifier'], 'literalinput', 'identifier set')
        self.assertTrue(out['title'], 'title does not exist')
        self.assertFalse(out['abstract'], 'abstract exist')
        self.assertEqual(out['data'], 9, 'data set')

        # Required for serialization
        self.assertEqual(out['uom']['uom'], "metre")
        self.assertEqual(out['uom']['reference'], "urn:ogc:def:uom:OGC:1.0:metre")
        self.assertFalse(out['workdir'], 'Workdir exist')
        self.assertEqual(out['type'], 'literal', 'it\'s literal input')

    def test_json_out_datetime(self):
        spec = pywps.LiteralInput(
            identifier="datetime",
            title="Literal Input",
            validate_mode=2,
            data_type='dateTime'
        )
        inpt = LiteralInput(spec, {'data': "2017-04-20T12:30:00"})
        out = inpt.json
        self.assertEqual(out['data'], '2017-04-20T12:30:00', 'datetime set')

    def test_json_out_time(self):
        spec = pywps.LiteralInput(
            identifier="time",
            title="Literal Input",
            validate_mode=2,
            data_type='time'
        )
        inpt = LiteralInput(spec, { 'data': "12:30:00" })
        out = inpt.json
        self.assertEqual(out['data'], '12:30:00', 'time set')

    def test_json_out_date(self):
        spec = pywps.LiteralInput(
            identifier="date",
            title="Literal Input",
            validate_mode=2,
            data_type='date'
        )
        inpt = LiteralInput(spec, {'data': "2017-04-20"})
        out = inpt.json
        self.assertEqual(out['data'], '2017-04-20', 'date set')

    def test_translations(self):
        title_fr = get_translation(self.literal_input.json, "title", "fr-CA")
        assert title_fr == "Mon input"
        abstract_fr = get_translation(self.literal_input.json, "abstract", "fr-CA")
        assert abstract_fr == "Une description"
        identifier = get_translation(self.literal_input.json, "identifier", "fr-CA")
        assert identifier == self.literal_input.json['identifier']


class BoundingBoxInputTest(unittest.TestCase):
    """BountingBoxInput test cases"""

    def setUp(self):
        self.spec = pywps.BoundingBoxInput(
            "bboxinput",
            title="BBox input",
            dimensions=2,
            translations={
                "fr-CA": {"title": "Mon input", "abstract": "Une description"}}
        )

        input = {
            'data': [0, 1, 2, 4]
        }

        self.bbox_input = inout.inputs.BoundingBoxInput(self.spec, input)

    def test_contruct(self):
        self.assertIsInstance(self.bbox_input, BoundingBoxInput)

    def test_json_out(self):
        out = self.bbox_input.json

        self.assertTrue(out['identifier'], 'identifier exists')
        self.assertTrue(out['title'], 'title does not exist')
        self.assertFalse(out['abstract'], 'abstract set')
        self.assertEqual(out['type'], 'bbox', 'type set')
        self.assertEqual(out['data'], [0, 1, 2, 4], 'data are there')

        # This field are required for ExecuteResponse template with lineage=True
        self.assertEqual(out['ll'], [0, 1], 'data are there')
        self.assertEqual(out['ur'], [2, 4], 'data are there')

        # Default crs when not specified
        self.assertEqual(out['crs'], 'epsg:4326', 'data are there')
        self.assertEqual(out['dimensions'], 2, 'Dimensions set')

    # TODO: Test serialization