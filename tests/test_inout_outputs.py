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

from pywps.inout.outputs import ComplexOutput, LiteralOutput, BoundingBoxOutput, \
    ReferenceOutput


DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


def get_data_format(mime_type):
    return Format(mime_type=mime_type, validate=get_validator(mime_type))


class ComplexOutputTest(unittest.TestCase):
    """ComplexOutput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        self.spec = pywps.ComplexOutput(
            identifier="netcdf",
            title="NetCDF output",
            supported_formats=[get_data_format('application/x-netcdf')],
            validate_mode=MODE.NONE)

        input = {
            'identifier': 'netcdf',
            'mimetype': 'application/x-netcdf',
            # 'schema': None,
            # 'encoding': None
        }

        self.complex_out = ComplexOutput(self.spec, input, workdir=self.tmp_dir)

        self.ncfile = os.path.join(DATA_DIR, 'netcdf', 'time.nc')

        with open(self.ncfile, "rb") as fi:
            self.reference_data = fi.read()

    # Validate json as expected for serialization and for output template
    def _validate_json(self, o):
        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('data' in o, 'data does not exist')
        self.assertTrue('translations' in o, 'title does not exist')

        self.assertTrue('mimetype' in o, 'mimetype does not exist')
        self.assertTrue('schema' in o, 'schema does not exist')
        self.assertTrue('encoding' in o, 'encoding does not exist')
        self.assertTrue('type' in o, 'type does not exist')

        self.assertEqual(o['type'], ComplexOutput.type, 'type set')
        self.assertEqual(o['mimetype'], 'application/x-netcdf', 'type set')

    def test_contruct(self):
        self.assertIsInstance(self.complex_out, ComplexOutput)

    def test_data_format(self):
        self.assertIsInstance(self.complex_out.data_format, Format)


    def test_file_handler(self):
        self.complex_out.file = self.ncfile
        self.assertEqual(self.complex_out.data, self.reference_data)
        with self.complex_out.stream as s:
            self.assertEqual(s.read(), self.reference_data)

        self._validate_json(self.complex_out.json)


    def test_data_handler(self):
        self.complex_out.data = self.reference_data
        print(self.complex_out.file)
        with open(self.complex_out.file, "rb") as f:
            self.assertEqual(f.read(), self.reference_data)
        self._validate_json(self.complex_out.json)

    def test_base64(self):
        self.complex_out.data = self.reference_data
        b = self.complex_out.base64
        self.assertEqual(base64.b64decode(b), self.reference_data)
        self._validate_json(self.complex_out.json)

    # Should we implement it ?
    # def test_url_handler(self):
    #     wfsResource = 'http://demo.mapserver.org/cgi-bin/wfs?' \
    #                   'service=WFS&version=1.1.0&' \
    #                   'request=GetFeature&' \
    #                   'typename=continents&maxfeatures=2'
    #     self.complex_out.url = wfsResource
    #     self.complex_out.storage = DatabaseStorage()
    #     url = self.complex_out.export()
    #     self.assertEqual('http', urlparse(url).scheme)


# class ComplexOutputTest(unittest.TestCase):
#     """ComplexOutput test cases"""
#
#     def setUp(self):
#         self.tmp_dir = tempfile.mkdtemp()
#
#         self.spec0 = pywps.ComplexOutput(
#             identifier="complexoutput",
#             title='Complex Output',
#             data_format=get_data_format('application/json'),
#             supported_formats=[get_data_format('application/json')],
#             validate_mode=MODE.NONE,
#             translations={"fr-CA": {"title": "Mon output",
#                                     "abstract": "Une description"}},
#         )
#
#         self.spec1 = pywps.ComplexOutput(
#             identifier="netcdf",
#             title="NetCDF output",
#             data_format=get_data_format('application/x-netcdf'),
#             supported_formats=[get_data_format('application/x-netcdf')],
#             validate_mode=MODE.NONE)
#
#         self.complex_out = ComplexOutput(self.spec1)
#
#         self.data = json.dumps({'a': 1, 'unicodé': 'éîïç', })
#         self.ncfile = os.path.join(DATA_DIR, 'netcdf', 'time.nc')
#
#         self.test_fn = os.path.join(self.complex_out.workdir, 'test.json')
#         with open(self.test_fn, 'w') as f:
#             f.write(self.data)
#
#     def test_contruct(self):
#         self.assertIsInstance(self.complex_out, inout.outputs.ComplexOutput)
#
#     def test_data_format(self):
#         self.assertIsInstance(self.complex_out.data_format, Format)
#
#     def test_storage(self):
#         class Storage(object):
#             pass
#         storage = Storage()
#         self.complex_out.store = storage
#         self.assertEqual(self.complex_out.store, storage)
#
#     def test_file_handler(self):
#         self.complex_out.file = self.test_fn
#         self.assertEqual(self.complex_out.data, self.data)
#         with self.complex_out.stream as s:
#             self.assertEqual(s.read(), bytes(self.data, encoding='utf8'))
#
#     def test_file_handler_netcdf(self):
#         self.complex_out_nc.file = self.ncfile
#         self.complex_out_nc.base64
#
#     def test_data_handler(self):
#         self.complex_out.data = self.data
#         with open(self.complex_out.file) as f:
#             self.assertEqual(f.read(), self.data)
#
#     def test_base64(self):
#         self.complex_out.data = self.data
#         b = self.complex_out.base64
#         self.assertEqual(base64.b64decode(b).decode(), self.data)
#
#     def test_url_handler(self):
#         wfsResource = 'http://demo.mapserver.org/cgi-bin/wfs?' \
#                       'service=WFS&version=1.1.0&' \
#                       'request=GetFeature&' \
#                       'typename=continents&maxfeatures=2'
#         self.complex_out.url = wfsResource
#         self.complex_out.storage = DatabaseStorage()
#         url = self.complex_out.export()
#         self.assertEqual('http', urlparse(url).scheme)
#
#     def test_json(self):
#         new_output = inout.outputs.ComplexOutput.from_json(self.complex_out.json)
#         self.assertEqual(new_output.identifier, 'complexoutput')
#         self.assertEqual(
#             new_output.translations,
#             {"fr-ca": {"title": "Mon output", "abstract": "Une description"}},
#             'translations does not exist'
#         )

class ReferenceOutputTest(unittest.TestCase):
    """ComplexOutput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        self.spec = pywps.ComplexOutput(
            identifier="netcdf",
            title="NetCDF output",
            supported_formats=[get_data_format('application/x-netcdf')],
            validate_mode=MODE.NONE)

        self.ncfile = os.path.join(DATA_DIR, 'netcdf', 'time.nc')

        with open(self.ncfile, "rb") as fi:
            self.reference_data = fi.read()

        output = {
            'identifier': "netcdf",
            'mimetype': 'application/x-netcdf',
            # 'schema': None,
            # 'encoding': None
        }
        self.complex_out = ReferenceOutput(self.spec, output)

    def test_contruct(self):
        self.assertIsInstance(self.complex_out, ReferenceOutput)

    def test_data_format(self):
        self.assertIsInstance(self.complex_out.data_format, Format)

    def test_storage(self):
        class Storage(object):
            pass
        storage = Storage()
        self.complex_out.store = storage
        self.assertEqual(self.complex_out.store, storage)

    def test_file_handler(self):
        self.complex_out.file = self.ncfile

    def test_data_handler(self):
        self.complex_out.data = self.reference_data

    def test_base64(self):
        self.complex_out.data = self.reference_data


class LiteralOutputTest(unittest.TestCase):
    """LiteralOutput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        spec = pywps.LiteralOutput(
            "literaloutput",
            data_type="integer",
            title="Literal Output",
            uoms=[UOM("km / h", "custom reference"),
                  UOM("degrees")],
            translations={"fr-CA": {"title": "Mon output",
                                    "abstract": "Une description"}},
        )

        output = {
            'identifier': "literaloutput",
            'uom': "degrees"
        }

        self.literal_output = LiteralOutput(spec, output, workdir=self.tmp_dir)

    # Validate json as expected for serialization and for output template
    def _validate_json(self, o):
        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('data' in o, 'data does not exist')
        self.assertTrue('translations' in o, 'title does not exist')

        self.assertTrue('uom' in o, 'uom does not exist')
        self.assertTrue('data_type' in o, 'data_type does not exist')
        self.assertTrue('type' in o, 'type does not exist')

        self.assertEqual(o['type'], LiteralOutput.type, 'type set')
        self.assertEqual(o['data_type'], 'integer')

    def test_contruct(self):
        self.assertIsInstance(self.literal_output, LiteralOutput)

    def test_data_handler(self):
        self.literal_output.data = 10
        self._validate_json(self.literal_output.json)


class BoundingBoxOutputTest(unittest.TestCase):
    """BoundingBoxOutput test cases"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        self.spec = pywps.BoundingBoxOutput(
            "bboxoutput",
            title="BBox output",
            dimensions=2,
            crss=['epsg:3857', 'epsg:4326'],
            translations={"fr-CA": {"title": "Mon output",
                                    "abstract": "Une description"}}
        )

        output = {
            'identifier': 'bboxoutput'
        }

        self.bbox_out = BoundingBoxOutput(self.spec, output, workdir=self.tmp_dir)

    # Validate json as expected for serialization and for output template
    def _validate_json(self, o):
        self.assertTrue('identifier' in o, 'identifier exists')
        self.assertTrue('title' in o, 'title does not exist')
        self.assertTrue('abstract' in o, 'abstract does not exist')
        self.assertTrue('data' in o, 'data does not exist')
        self.assertTrue('translations' in o, 'title does not exist')

        self.assertTrue('crs' in o)
        self.assertTrue('dimensions' in o)
        self.assertTrue('type' in o)
        self.assertTrue('ll' in o)
        self.assertTrue('ur' in o)

        self.assertEqual(o['type'], BoundingBoxOutput.type)

    def test_contruct(self):
        self.assertIsInstance(self.bbox_out, BoundingBoxOutput)

    def test_data_handler(self):
        self.bbox_out.data = [0,1,2,3]


# class TestMetaLink(unittest.TestCase):
#     tmp_dir = tempfile.mkdtemp()
#
#     def metafile(self):
#         mf = MetaFile('identifier', 'title', fmt=FORMATS.JSON)
#         mf.data = json.dumps({'a': 1})
#         mf._set_workdir(self.tmp_dir)
#         return mf
#
#     def metafile_with_url(self):
#         mf = MetaFile('identifier', 'title', fmt=FORMATS.JSON)
#         mf.url = "https://pywps.org/"
#         mf._set_workdir(self.tmp_dir)
#         return mf
#
#     def test_metafile(self):
#         mf = self.metafile()
#         self.assertEqual('identifier', mf.identity)
#
#     def metalink(self):
#         ml = MetaLink(identity='unittest', description='desc', files=(self.metafile(), ), workdir=self.tmp_dir)
#         return ml
#
#     def metalink4(self):
#         ml = MetaLink4(identity='unittest', description='desc', files=(self.metafile(), ), workdir=self.tmp_dir)
#         return ml
#
#     def test_metalink(self):
#         from pywps.validator.complexvalidator import validatexml
#
#         spec = pywps.ComplexOutput(
#             'metatest', 'MetaLink Test title',
#             abstract='MetaLink test abstract',
#             supported_formats=[FORMATS.METALINK, ]
#         )
#
#         out = inout.outputs.ComplexOutput(spec, as_reference=True)
#         out.workdir = self.tmp_dir
#         ml = self.metalink()
#
#         out.data = ml.xml
#         self.assertTrue(validatexml(out, MODE.STRICT))
#
#     def test_metalink4(self):
#         from pywps.validator.complexvalidator import validatexml
#
#         spec = pywps.ComplexOutput(
#             'metatest', 'MetaLink4 Test title',
#             abstract='MetaLink4 test abstract',
#             supported_formats=[FORMATS.META4, ]
#         )
#         out = inout.outputs.ComplexOutput(spec, as_reference=True)
#         out.workdir = self.tmp_dir
#         ml = self.metalink4()
#
#         out.data = ml.xml
#         self.assertTrue(validatexml(out, MODE.STRICT))
#
#     def test_hash(self):
#         ml = self.metalink()
#         assert 'hash' not in ml.xml
#
#         ml.checksums = True
#         assert 'hash' in ml.xml
#
#         ml4 = self.metalink4()
#         assert 'hash' not in ml4.xml
#
#         ml4.checksums = True
#         assert 'hash' in ml4.xml
#
#     def test_size(self):
#         ml4 = self.metalink4()
#         ml4.append(self.metafile_with_url())
#         assert 'size' in ml4.xml
#
#     def test_no_size(self):
#         ml4 = self.metalink4()
#         mf = self.metafile_with_url()
#         mf.size = 0
#         ml4.files = [mf]
#         assert 'size' not in ml4.xml
#
#     def test_set_size(self):
#         ml4 = self.metalink4()
#         mf = self.metafile_with_url()
#         mf.size = 100
#         ml4.files = [mf]
#         assert '<size>100</size>' in ml4.xml



