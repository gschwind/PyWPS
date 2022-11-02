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

from pywps.util import uri_to_path
from pywps.inout.literaltypes import convert, AllowedValue, AnyValue
from pywps.inout.outputs import MetaFile, MetaLink, MetaLink4
from io import StringIO
from urllib.parse import urlparse
from pywps.validator.base import emptyvalidator
from pywps.exceptions import InvalidParameterValue
from pywps.validator.mode import MODE
from pywps.inout.spec import UOM
from pywps.inout.storage.database import DatabaseStorage
from pywps.tests import service_ok
from pywps.translations import get_translation

from pywps.inout.spec import ComplexOutput, ComplexInput, LiteralInput, \
    LiteralOutput, BoundingBoxInput, BoundingBoxOutput



DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


def get_data_format(mime_type):
    return Format(mime_type=mime_type, validate=get_validator(mime_type))


class ComplexInputTest(unittest.TestCase):
    """pywps.ComplexInput test cases"""

    def setUp(self):
        data_format = get_data_format('application/json')

        self.spec = ComplexInput(
            identifier="complexinput",
            title='MyComplex',
            abstract='My complex input',
            keywords=['kw1', 'kw2'],
            supported_formats=[data_format]
        )

    def test_contruct(self):
        self.assertIsInstance(self.spec, ComplexInput)

    def test_data_format(self):
        self.assertIsInstance(self.spec.supported_formats[0], Format)

    def test_json_export_for_describe_template(self):
        o = self.spec.json

        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('translations' in o, 'title does not exist')
        self.assertTrue('min_occurs' in o)
        self.assertTrue('max_occurs' in o)

        self.assertTrue('data_format' in o)
        self.assertTrue('supported_formats' in o)

        self.assertIsInstance(o['data_format'], dict)
        self.assertIsInstance(o['supported_formats'], list)

        self.assertTrue('mime_type' in o['data_format'])
        for f in o['supported_formats']:
            self.assertTrue('mime_type' in f)


class ComplexOutputTest(unittest.TestCase):
    """ComplexOutput test cases"""

    def setUp(self):
        self.spec = pywps.ComplexOutput(
            identifier="complexoutput",
            title='Complex Output',
            data_format=get_data_format('application/json'),
            supported_formats=[get_data_format('application/json')],
            validate_mode=MODE.NONE,
            translations={"fr-CA": {"title": "Mon output",
                                    "abstract": "Une description"}},
        )

    def test_contruct(self):
        self.assertIsInstance(self.spec, ComplexOutput)

    def test_data_format(self):
        self.assertIsInstance(self.spec.data_format, Format)


    def test_json_export_for_describe_template(self):
        o = self.spec.json

        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('translations' in o, 'title does not exist')

        self.assertTrue('data_format' in o)
        self.assertTrue('supported_formats' in o)

        self.assertIsInstance(o['data_format'], dict)
        self.assertIsInstance(o['supported_formats'], list)

        self.assertTrue('mime_type' in o['data_format'])
        for f in o['supported_formats']:
            self.assertTrue('mime_type' in f)


class LiteralInputTest(unittest.TestCase):
    """LiteralInput test cases"""

    def setUp(self):
        self.spec = LiteralInput(
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

    def test_contruct(self):
        self.assertIsInstance(self.spec, LiteralInput)
        self.assertEqual(len(self.spec.allowed_values), 3)
        self.assertIsInstance(self.spec.allowed_values[0], AllowedValue)
        self.assertIsInstance(self.spec.allowed_values[2], AllowedValue)
        self.assertEqual(self.spec.allowed_values[2].spacing, 3)
        self.assertEqual(self.spec.allowed_values[2].minval, 3)


    def test_json_out(self):
        o = self.spec.json

        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('translations' in o, 'title does not exist')

        self.assertTrue('uoms' in o)

        self.assertIsInstance(o['uoms'], list)

        self.assertEqual(o['uoms'][0]["uom"], "metre")
        self.assertEqual(o['uoms'][1]["uom"], "km / h")
        self.assertEqual(o['uoms'][1]["reference"], "custom reference")
        self.assertEqual(o['uom']["uom"], "metre")
        self.assertEqual(o['data_type'], 'integer', 'Data type is integer')
        self.assertEqual(len(o['allowed_values']), 3, '3 allowed values')
        self.assertEqual(o['allowed_values'][0]['value'], 1, 'allowed value 1')
        self.assertEqual(
            o['translations'],
            {"fr-ca": {"title": "Mon input", "abstract": "Une description"}},
            'translations does not exist'
        )

    def test_translations(self):
        title_fr = get_translation(self.spec, "title", "fr-CA")
        assert title_fr == "Mon input"
        abstract_fr = get_translation(self.spec, "abstract", "fr-CA")
        assert abstract_fr == "Une description"
        identifier = get_translation(self.spec, "identifier", "fr-CA")
        assert identifier == self.spec.identifier


class LiteralOutputTest(unittest.TestCase):
    """LiteralOutput test cases"""

    def setUp(self):
        self.spec = LiteralOutput(
            "literaloutput",
            data_type="integer",
            title="Literal Output",
            uoms=[UOM("km / h", "custom reference"),
                  UOM("m / s", "other reference")],
            translations={"fr-CA": {"title": "Mon output",
                                    "abstract": "Une description"}},
        )

    def test_contruct(self):
        self.assertIsInstance(self.spec, LiteralOutput)

    def test_json_out(self):
        o = self.spec.json

        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('translations' in o, 'title does not exist')

        # Not mandatory
        self.assertTrue('uoms' in o)
        self.assertIsInstance(o['uoms'], list)


class BoundingBoxInputTest(unittest.TestCase):
    """BountingBoxInput test cases"""

    def setUp(self):
        self.spec = BoundingBoxInput(
            "bboxinput",
            title="BBox input",
            dimensions=2,
            translations={
                "fr-CA": {"title": "Mon input", "abstract": "Une description"}}
        )

    def test_contruct(self):
        self.assertIsInstance(self.spec, BoundingBoxInput)

    def test_json_out(self):
        o = self.spec.json

        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('translations' in o, 'translations does not exist')

        self.assertTrue('crs' in o)
        self.assertTrue('crss' in o)

        self.assertEqual(
            o['translations'],
            {"fr-ca": {"title": "Mon input", "abstract": "Une description"}},
            'translations does not exist'
        )


class BoundingBoxOutputTest(unittest.TestCase):
    """BoundingBoxOutput test cases"""

    def setUp(self):
        self.spec = BoundingBoxOutput(
            "bboxoutput",
            title="BBox output",
            dimensions=2,
            crss=['epsg:3857', 'epsg:4326'],
            translations={"fr-CA": {"title": "Mon output",
                                    "abstract": "Une description"}}
        )

    def test_contruct(self):
        self.assertIsInstance(self.spec, BoundingBoxOutput)

    def test_json_out(self):
        o = self.spec.json

        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('translations' in o, 'translations does not exist')

        self.assertTrue('crs' in o)
        self.assertTrue('crss' in o)
