##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################
import base64
import re
from pywps import xml_util as etree
import logging


from pywps.app.Common import Metadata
from pywps.exceptions import InvalidParameterValue
from pywps.inout.formats import Format
from pywps.inout import basic
from copy import deepcopy
from pywps.validator.mode import MODE
from pywps.inout.literaltypes import AnyValue, NoValue, ValuesReference, AllowedValue

from .basic import UOM
from .literaltypes import convert

CDATA_PATTERN = re.compile(r'<!\[CDATA\[(.*?)\]\]>')

LOGGER = logging.getLogger("PYWPS")


class BoundingBoxInput(basic.IOHandler):
    type = 'bbox'

    # TODO: doc string
    def __init__(self, spec, json, *args, **kwargs):
        super().__init__(spec, *args, **kwargs)

        self.workdir = self.workdir or json.get('workdir', None)

        self.crs = json.get('crs', self.spec.crss[0])
        if self.crs not in self.spec.crss:
            raise InvalidParameterValue(f"Not supported CRS: {self.crs}")

        self.dimensions = json.get('dimensions', 2)
        self.src_data = json['data']

        # Initialize IOHandler
        self.data = self.src_data

    def as_json(self):
        # Store actual request data.
        return {
            # Required for lineage=True
            'crs': self.crs,
            'dimensions': self.dimensions,
            'data': self.src_data,
            'll': self.ll,
            'ur': self.ur,

            'identifier': self.spec.identifier,
            'title': self.spec.title,
            'abstract': self.spec.abstract,
            'translations': self.spec.translations,

            # Required for serialization
            'type': BoundingBoxInput.type,
            'workdir': self.workdir
        }


    @property
    def json(self):
        return self.as_json()

    @classmethod
    def from_json(cls, *args, **kwargs):
        raise NotImplementedError("Use ComplexInput.__init__ instead")

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        if isinstance(value, list):
            self._data = [float(number) for number in value]
        elif isinstance(value, str):
            self._data = [float(number) for number in value.split(',')[:4]]
        else:
            raise InvalidParameterValue(f"Invalid bounding box value: {value}")

    @property
    def ll(self):
        if self.data:
            return self.data[:2]
        return []

    @property
    def ur(self):
        if self.data:
            return self.data[2:]
        return []


class ComplexInput(basic.IOHandler):
    type = 'complex'

    # TODO: doc string
    def __init__(self, spec, json, *args, workdir=None, **kwargs):
        super().__init__(spec, *args, workdir=workdir, **kwargs)

        self.mimetype = json.get('mimeType', None)
        self.encoding = json.get('encoding', None)
        self.schema = json.get('schema', None)

        self.workdir = self.workdir or json.get('workdir', None)

        # Keep original request data.
        self.src_data = json['data']

        if self.mimetype is None:
            self.data_format = spec.supported_formats[0]
        else:
            self.data_format = spec.get_format(self.mimetype)
            if self.data_format is None:
                raise InvalidParameterValue(
                    'Invalid mimeType value {} for input {}'.format(
                        json.get('mimeType'), spec.identifier),
                    'mimeType')

        self._init_iohandler()


    # Interpret current state to initialize iohandler
    def _init_iohandler(self):
        # Initialize input data for the user
        if self.encoding == 'base64':
            # FIXME: ignore data_format ?
            self.data = base64.b64decode(self.src_data)
        else:

            # Ensure valid XML data
            if self.data_format.mime_type in ["application/xml", "application/gml+xml", "text/xml"]:
                # FIXME: Ignore schema ?
                # Note that in a client-server round trip, the original and returned file will not be identical.
                data_doc = etree.parse(self.file)
                self.data = etree.tostring(data_doc, pretty_print=True).decode('utf-8')
            else:
                self.data = self.src_data


    # Used in execute/status outputs XML if lineage=True
    # and to store the request in database
    def as_json(self):
        # Store actual request data.
        return {
            # Required for lineage=True
            'mimeType': self.mimetype,
            'encoding': self.encoding,
            'schema': self.schema,
            'data': self.src_data,

            'identifier': self.spec.identifier,
            'title': self.spec.title,
            'abstract': self.spec.abstract,
            'translations': self.spec.translations,

            # Required for serialization
            'type': ComplexInput.type,
            'workdir': self.workdir
        }

    @property
    def json(self):
        return self.as_json()

    @classmethod
    def from_json(cls, *args, **kwargs):
        raise NotImplementedError("Use ComplexInput.__init__ instead")


class LiteralInput(basic.IOHandler):
    type = 'literal'

    # TODO: doc string
    def __init__(self, spec, json, *args, **kwargs):
        super().__init__(spec, *args, **kwargs)

        self.workdir = self.workdir or json.get('workdir', None)

        # TODO: check datatype

        default_uom = None
        if self.spec.uoms is not None and len(self.spec.uoms) > 0:
            default_uom = self.spec.uoms[0]
        self.uom = json.get('uom', default_uom)
        if isinstance(self.uom, str):
            self.uom = UOM(self.uom)
        elif isinstance(self.uom, dict):
            self.uom = UOM(self.uom['uom'], self.uom['reference'])

        self.data_type = json.get('datatype', None)

        self.src_data = json['data']

        # Initialize IOHandler
        # TODO: make beter converted
        self.data = convert(self.spec.data_type, self.src_data)


    # Used in execute/status outputs XML if lineage=True
    # and to store the request
    @property
    def json(self):
        """Get JSON representation of the input
        """

        return {
            # Required for lineage=True
            'uom': None if self.uom is None else self.uom.json,
            'datatype': self.data_type,
            'data': self.src_data,

            'identifier': self.spec.identifier,
            'title': self.spec.title,
            'abstract': self.spec.abstract,
            'translations': self.spec.translations,

            # Required for serialization
            'type': LiteralInput.type,
            'workdir': self.workdir
        }

    @classmethod
    def from_json(cls, json_input):
        raise NotImplementedError("Use LiteralInput.__init__ instead")


class ReferenceInput(basic.IOHandler):
    type = 'reference'

    # TODO: doc string
    def __init__(self, spec, json, *args, **kwargs):
        super().__init__(spec, *args, **kwargs)

        self.workdir = self.workdir or json.get('workdir', None)

        for a in ['href', 'mimetype', 'method', 'header', 'body', 'bodyreference']:
            setattr(self, a, json.get(a, None))

        if self.mimetype is None:
            self.data_format = spec.supported_formats[0]
        else:
            self.data_format = spec.get_format(self.mimetype)
            if self.data_format is None:
                raise InvalidParameterValue(
                    'Invalid mimeType value {} for input {}'.format(
                        json.get('mimeType'), spec.identifier),
                    'mimeType')

        # Initialize IOHandler
        self.url2 = json


    # Used in execute/status outputs XML if lineage=True
    # and to store the request
    @property
    def json(self):
        """Get JSON representation of the input
        """
        # Store actual request data.
        # TODO: actually not properly implemented
        data = { a : getattr(self, a, None) for a in
                 ['href', 'mimeTypes', 'method', 'header', 'body', 'bodyreference'] }

        data["type"] = ReferenceInput.type

        # This fields are required for lineage
        for a in ['identifier', 'title', 'abstract']:
            data[a] = getattr(self.spec, a)

        return data

    @property
    def json(self):
        return self.as_json()

    @classmethod
    def from_json(cls, json_input):
        raise NotImplementedError("Use ReferenceInput.__init__ instead")


# FIXME: Broken
def input_from_json(json_data):
    data_type = json_data.get('type', 'literal')
    if data_type in 'complex':
        inpt = ComplexInput.from_json(json_data)
    elif data_type == 'literal':
        inpt = LiteralInput.from_json(json_data)
    elif data_type == 'bbox':
        inpt = BoundingBoxInput.from_json(json_data)
    elif data_type == 'reference':
        inpt = ReferenceInput.from_json(json_data)
    else:
        raise InvalidParameterValue("Input type not recognized: {}".format(data_type))
    return inpt
