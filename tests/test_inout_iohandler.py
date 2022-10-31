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
from pywps.inout.spec import BoundingBoxInput, BoundingBoxOutput, \
    ComplexInput, ComplexOutput, LiteralOutput, LiteralInput, BasicIO

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



DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')


def get_data_format(mime_type):
    return Format(mime_type=mime_type, validate=get_validator(mime_type))


class IOHandlerTest(unittest.TestCase):
    """IOHandler test cases"""

    def setUp(self):
        tmp_dir = tempfile.mkdtemp()
        spec = BasicIO("someinput")
        self.iohandler = IOHandler(spec, workdir=tmp_dir)
        self._value = 'lalala'

    def tearDown(self):
        pass

    def test_basic_IOHandler(self):
        """Test basic IOHandler"""
        self.assertTrue(os.path.isdir(self.iohandler.workdir))

    def _test_outout(self, source_type, suffix=''):
        """Test all outputs"""

        self.assertEqual(source_type, self.iohandler.source_type,
                         'Source type properly set')

        self.assertEqual(self._value, self.iohandler.data, 'Data obtained')

        if self.iohandler.source_type == SOURCE_TYPE.URL:
            self.assertEqual('http', urlparse(self.iohandler.url).scheme)
        else:
            self.assertEqual('file', urlparse(self.iohandler.url).scheme)

        if self.iohandler.source_type == SOURCE_TYPE.STREAM:
            source = StringIO(str(self._value))
            self.iohandler.stream = source

        file_path = self.iohandler.file
        self.assertTrue(file_path.endswith(suffix))
        file_handler = open(file_path)
        self.assertEqual(self._value, file_handler.read(), 'File obtained')
        file_handler.close()

        if self.iohandler.source_type == SOURCE_TYPE.STREAM:
            source = StringIO(str(self._value))
            self.iohandler.stream = source

        stream_val = self.iohandler.stream.read()
        self.iohandler.stream.close()

        if isinstance(stream_val, bytes):
            self.assertEqual(self._value, stream_val.decode('utf-8'),
                             'Stream obtained')
        else:
            self.assertEqual(self._value, stream_val,
                             'Stream obtained')

        if self.iohandler.source_type == SOURCE_TYPE.STREAM:
            source = StringIO(str(self._value))
            self.iohandler.stream = source

        # self.assertEqual(stream_val, self.iohandler.memory_object,
        #                 'Memory object obtained')

    def test_data(self):
        """Test data input IOHandler"""
        self.iohandler.data = self._value
        self.iohandler.data_format = Format('foo', extension='.foo')
        self._test_outout(SOURCE_TYPE.DATA, '.foo')

    def test_stream(self):
        """Test stream input IOHandler"""
        source = StringIO(str(self._value))
        self.iohandler.stream = source
        self._test_outout(SOURCE_TYPE.STREAM)

    def test_file(self):
        """Test file input IOHandler"""
        fd, tmp_file = tempfile.mkstemp()
        source = tmp_file
        file_handler = open(tmp_file, 'w')
        file_handler.write(self._value)
        file_handler.close()
        self.iohandler.file = source
        self._test_outout(SOURCE_TYPE.FILE)
        with self.assertRaises(TypeError):
            self.iohandler[0].data = '5'

    def test_url(self):
        if not service_ok('https://demo.mapserver.org'):
            self.skipTest("mapserver is unreachable")
        wfsResource = 'http://demo.mapserver.org/cgi-bin/wfs?' \
                      'service=WFS&version=1.1.0&' \
                      'request=GetFeature&' \
                      'typename=continents&maxfeatures=2'
        # self._value = requests.get(wfsResource).text

        url = {
            'href': wfsResource,
            'header': None,
            'body': None,
            'bodyreference': None
        }

        self.iohandler.url = wfsResource
        self._test_outout(SOURCE_TYPE.URL)


    def test_url2(self):
        if not service_ok('https://demo.mapserver.org'):
            self.skipTest("mapserver is unreachable")
        wfsResource = 'http://demo.mapserver.org/cgi-bin/wfs?' \
                      'service=WFS&version=1.1.0&' \
                      'request=GetFeature&' \
                      'typename=continents&maxfeatures=2'
        self._value = requests.get(wfsResource).text

        url = {
            'href': wfsResource,
            'header': None,
            'body': None,
            'bodyreference': None
        }

        self.iohandler.url2 = url
        self._test_outout(SOURCE_TYPE.URL)

    def test_workdir(self):
        """Test workdir"""
        workdir = tempfile.mkdtemp()
        self.iohandler.workdir = workdir
        self.assertTrue(os.path.isdir(self.iohandler.workdir))

        # make another
        workdir = tempfile.mkdtemp()
        self.iohandler.workdir = workdir
        self.assertTrue(os.path.isdir(self.iohandler.workdir))

    def test_memory(self):
        """Test data input IOHandler"""
        self.skipTest('Memory object not implemented')

    def test_data_bytes(self):
        self._value = self._value.encode("utf-8")

        self.iohandler.data = self._value
        self.assertEqual(self.iohandler.source_type, SOURCE_TYPE.DATA,
                         'Source type properly set')

        # test the data handle
        self.assertEqual(self._value, self.iohandler.data, 'Data obtained')

        # test the file handle
        file_handler = open(self.iohandler.file, 'rb')
        self.assertEqual(self._value, file_handler.read(), 'File obtained')
        file_handler.close()

        # test the stream handle
        stream_data = self.iohandler.stream.read()
        self.iohandler.stream.close()
        self.assertEqual(self._value, stream_data, 'Stream obtained')

    def test_is_textfile(self):
        geotiff = os.path.join(DATA_DIR, 'geotiff', 'dem.tiff')
        self.assertFalse(_is_textfile(geotiff))
        gml = os.path.join(DATA_DIR, 'gml', 'point.gml')
        self.assertTrue(_is_textfile(gml))
        geojson = os.path.join(DATA_DIR, 'json', 'point.geojson')
        self.assertTrue(_is_textfile(geojson))
