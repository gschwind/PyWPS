##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################
"""
WPS Output classes
"""
from typing import Optional, Sequence, Dict, Union

from pywps import xml_util as etree
import os
import re
from pywps.app.Common import Metadata
from pywps.exceptions import InvalidParameterValue
from pywps.inout import basic
from pywps.inout.storage import new_storage
from pywps.inout.types import Translations
from pywps.validator.mode import MODE
from pywps import configuration as config
from pywps.inout.formats import Format, Supported_Formats, FORMATS

from .basic import StorageHandler, IOHandler
from .spec import UOM


class BoundingBoxOutput(IOHandler):
    type = 'bbox'

    def __init__(self, spec, json, *args, workdir=None, **kwargs):
        super().__init__(spec, *args, workdir=workdir, **kwargs)

        if json is not None:
            self.workdir = self.workdir or json.get('workdir', None)

            self.crs = json.get('crs', self.spec.crss[0])
            if self.crs not in self.spec.crss:
                raise InvalidParameterValue(f"Not supported CRS: {self.crs}")

            self.dimensions = json.get('dimensions', 2)

            # Initialize IOHandler
            if 'data' in json:
                self.data = json['data']

    def as_json(self):
        o = {
            # Required for lineage=True
            'crs': self.crs,
            'dimensions': self.dimensions,
            'll': self.ll,
            'ur': self.ur,

            'identifier': self.spec.identifier,
            'title': self.spec.title,
            'abstract': self.spec.abstract,
            'translations': self.spec.translations,

            # Required for serialization
            'type': BoundingBoxOutput.type,
            'workdir': self.workdir
        }

        # TODO: make data in the good format
        if self._iohandler:
            o['data'] = self.data


    # Used for serialisation and within the excecute template.
    @property
    def json(self):
        """Get JSON representation of the output
        """
        return self.as_json()

    @classmethod
    def from_json(cls, json_output):
        raise NotImplementedError("Use BoundingBoxOutput.__init__ instead")


class ComplexOutput(IOHandler):
    type = 'complex'
    """
    :param identifier: The name of this output.
    :param title: Readable form of the output name.
    :param supported_formats: List of supported
        formats. The first format in the list will be used as the default.
    :type supported_formats: (pywps.inout.formats.Format, )
    :param str abstract: Description of the output
    :param pywps.validator.mode.MODE mode: validation mode (none to strict)
    :param metadata: List of metadata advertised by this process. They
                     should be :class:`pywps.app.Common.Metadata` objects.
    :param dict[str,dict[str,str]] translations: The first key is the RFC 4646 language code,
        and the nested mapping contains translated strings accessible by a string property.
        e.g. {"fr-CA": {"title": "Mon titre", "abstract": "Une description"}}
    """

    # TODO: doc string
    def __init__(self, spec, json, *args, workdir=None, **kwargs):
        super().__init__(spec, *args, workdir=workdir, **kwargs)

        self.mimetype = json.get('mimetype', None)
        self.encoding = json.get('encoding', None)
        self.schema = json.get('schema', None)

        self.workdir = self.workdir or json.get('workdir', None)

        if self.mimetype is None:
            self.data_format = spec.supported_formats[0]
        else:
            self.data_format = spec.get_format(self.mimetype)
            if self.data_format is None:
                raise InvalidParameterValue(
                    'Invalid mimetype value {} for input {}'.format(
                        json.get('mimeType'), spec.identifier),
                    'mimeType')

        # Initialize IOHandler
        if 'data' in json:
            self.data = json['data']

    def as_json(self):
        # Store actual request data.
        return {
            # Required for output template
            'mimetype': self.mimetype,
            'encoding': self.encoding,
            'schema': self.schema,
            'data': self.data, #< TODO: Maybe too simple

            'identifier': self.spec.identifier,
            'title': self.spec.title,
            'abstract': self.spec.abstract,
            'translations': self.spec.translations,

            # Required for serialization
            'type': ComplexOutput.type,
            'workdir': self.workdir
        }

    @property
    def json(self):
        return self.as_json()

    @classmethod
    def from_json(cls, json_output):
        raise NotImplementedError("Use ComplexOutput.__init__ instead")


    # FIXME: TODO
    def _data(self):
        if self.data:
            if self.data_format.mime_type in [FORMATS.GEOJSON.mime_type, FORMATS.JSON.mime_type]:
                return self.data
            elif self.data_format.mime_type in ["application/xml", "application/gml+xml", "text/xml"]:
                # Note that in a client-server round trip, the original and returned file will not be identical.
                data_doc = etree.parse(self.file)
                return etree.tostring(data_doc, pretty_print=True).decode('utf-8')

            else:
                if self.data_format.encoding == 'base64':
                    return self.base64.decode('utf-8')
                else:
                    # Match only data that are safe CDATA pattern.
                    CDATA_PATTERN = re.compile(r'^<!\[CDATA\[((?!\]\]>).)*\]\]>$')

                    # Otherwise we assume all other formats are unsafe and need to be enclosed in a CDATA tag.
                    if isinstance(self.data, bytes):
                        # Try to inline data as text but if fail encode is in base64
                        if self.data_format.encoding == 'utf-8':
                            out = self.data.decode('utf-8')
                            # If data is already enclosed with CDATA pattern, do not add it twice
                            if CDATA_PATTERN.match(out):
                                data["data"] = out
                            else:
                                # Check if the data does not contain ]]> patern if is safe to use CDATA
                                # other wise we fallback to base64 encoding.
                                if not re.search('\\]\\]>', out):
                                    data["data"] = '<![CDATA[{}]]>'.format(out)
                                else:
                                    data['encoding'] = 'base64'  # override the unsafe encoding
                                    data["data"] = self.base64.decode('utf-8')
                        else:
                            data['encoding'] = 'base64'  # override the unsafe encoding
                            data["data"] = self.base64.decode('utf-8')
                    else:
                        out = str(self.data)
                        # If data is already enclose with CDATApatern do not add it twise
                        if CDATA_PATTERN.match(out):
                            data["data"] = out
                        else:
                            # Check if the data does not contain ]]> patern if is safe to use CDATA
                            # other wise we fallback to base64 encoding.
                            if not re.search('\\]\\]>', out):
                                data["data"] = '<![CDATA[{}]]>'.format(out)
                            else:
                                data['encoding'] = 'base64'  # override the unsafe encoding
                                data["data"] = self.base64.decode('utf-8')

        return data


class LiteralOutput(IOHandler):
    type = 'literal'
    """
    :param identifier: The name of this output.
    :param str title: Title of the input
    :param pywps.inout.literaltypes.LITERAL_DATA_TYPES data_type: data type
    :param str abstract: Input abstract
    :param str uoms: units
    :param pywps.validator.mode.MODE mode: validation mode (none to strict)
    :param metadata: List of metadata advertised by this process. They
                     should be :class:`pywps.app.Common.Metadata` objects.
    :param dict[str,dict[str,str]] translations: The first key is the RFC 4646 language code,
        and the nested mapping contains translated strings accessible by a string property.
        e.g. {"fr-CA": {"title": "Mon titre", "abstract": "Une description"}}
    """

    def __init__(self, spec, json, *args, workdir=None, **kwargs):
        super().__init__(spec, *args, workdir=workdir, **kwargs)

        if json is not None:
            self.workdir = self.workdir or json.get('workdir', None)

            # TODO: check datatype

            default_uom = None
            if self.spec.uoms is not None and len(self.spec.uoms) > 0:
                default_uom = self.spec.uoms[0]
            self.uom = json.get('uom', default_uom)
            if isinstance(self.uom, str):
                self.uom = self._lookup_uom(self.uom)
                if self.uom is None:
                    raise InvalidParameterValue(
                        f"Invalid uom `{json.get('uom', default_uom)}` for parameter {self.spec.identifier}")
            elif isinstance(self.uom, dict):
                self.uom = UOM(self.uom['uom'], self.uom['reference'])

            self.data_type = json.get('datatype', None)

            # Initialize IOHandler
            if 'data' in json:
                self.data = json['data']

    # Lookup for UOM within spec
    def _lookup_uom(self, s):
        for u in self.spec.uoms:
            if s == u.reference:
                return u
            if s == u.uom:
                return u
        return None



    @property
    def json(self):
        """Get JSON representation of the input
        """

        return {
            # Used by execute template
            'uom': None if self.uom is None else self.uom.json,
            'data': self.data, #< TODO: To simple for now

            'identifier': self.spec.identifier,
            'title': self.spec.title,
            'abstract': self.spec.abstract,
            'data_type': self.spec.data_type,
            'translations': self.spec.translations,

            # Required for serialization
            'type': LiteralOutput.type,
            'workdir': self.workdir
        }

    @classmethod
    def from_json(cls, json_output):
        raise NotImplementedError("Use LiteralOutput.__init__ instead")


class ReferenceOutput(StorageHandler):
    type = 'reference'

    # TODO: doc string
    def __init__(self, spec, json, *args, **kwargs):
        super().__init__(spec, *args, **kwargs)

        self.mimetype = json.get('mimetype', None)
        self.encoding = json.get('encoding', None)
        self.schema = json.get('schema', None)

        if self.mimetype is None:
            self.data_format = spec.supported_formats[0]
        else:
            self.data_format = spec.get_format(self.mimetype)
            if self.data_format is None:
                raise InvalidParameterValue(
                    'Invalid mimeType value {} for input {}'.format(
                        json.get('mimeType'), spec.identifier),
                    'mimeType')

    # TODO: if storage init storage

    def as_json(self):
        # Store actual request data.
        return {
            # Required for output template
            'mimetype': self.mimetype,
            'encoding': self.encoding,
            'schema': self.schema,
            'data': self.export(), #< TODO: Maybe too simple

            'identifier': self.spec.identifier,
            'title': self.spec.title,
            'abstract': self.spec.abstract,
            'translations': self.spec.translations,

            # Required for serialization
            'type': ComplexOutput.type,
            'workdir': self.workdir,
            # 'uuid': self._uuid
        }

    @property
    def json(self):
        return self.as_json()

    @classmethod
    def from_json(cls, json_input):
        raise NotImplementedError("Use ReferenceInput.__init__ instead")



class MetaFile:
    """MetaFile object."""

    def __init__(self, identity=None, description=None, fmt=None):
        """Create a `MetaFile` object.

        :param str identity: human readable identity.
        :param str description: human readable file description.
        :param pywps.FORMAT fmt: file mime type.

        The content of each metafile is set like `ComplexOutputs`, ie
        using either the `data`, `file`, `stream` or `url` properties.

        The metalink document is created by a `MetaLink` instance, which
        holds a number of `MetaFile` instances.
        """
        self._size = None
        self._output = ComplexOutput(
            identifier=identity or '',
            title=description or '',
            as_reference=True,
            supported_formats=[fmt, ],
        )

    def _set_workdir(self, workdir):
        self._output.workdir = workdir

    @property
    def hash(self):
        """Text construct that conveys a cryptographic hash for a file.

        All hashes are encoded in lowercase hexadecimal format.  Hashes
        are used to verify the integrity of a complete file or portion
        of a file to determine if the file has been transferred without
        any errors.
        """
        import hashlib
        m = hashlib.sha256()
        with open(self.file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                m.update(chunk)
        return m.hexdigest()

    @property
    def identity(self):
        """Human-readable identity."""
        return self._output.identifier

    @property
    def name(self):
        """Indicate a specific file in a document describing multiple files."""
        js = self._output.json
        (_, name) = os.path.split(js.get('href', 'http:///'))
        return name

    @property
    def size(self):
        """Size of the linked content in bytes."""
        if self._size is None:
            self._size = self._output.size
        return self._size

    @size.setter
    def size(self, value):
        """Set size to avoid size calculation."""
        self._size = int(value)

    @property
    def urls(self):
        js = self._output.json
        return [js.get('href', ''), ]

    @property
    def mediatype(self):
        """Multipurpose Internet Mail Extensions (MIME) media type
        [RFC4288] of the metadata file available at the IRI."""
        return self._output.data_format.mime_type

    @property
    def data(self):
        return self._output.data

    @data.setter
    def data(self, value):
        self._output.data = value

    @property
    def file(self):
        return self._output.file

    @file.setter
    def file(self, value):
        self._output.file = value

    @property
    def url(self):
        return self._output.url

    @url.setter
    def url(self, value):
        self._output.url = value

    @property
    def stream(self):
        return self._output.stream

    @stream.setter
    def stream(self, value):
        self._output.stream = value

    def __str__(self):
        out = "MetaFile {}:".format(self.name)
        for url in self.urls:
            out += "\n\t{}".format(url)
        return out

    def __repr__(self):
        return "<pywps.inout.outputs.MetaFile {}>".format(self.name)


class MetaLink:
    _xml_template = 'metalink/3.0/main.xml'
    # Specs: https://www.metalinker.org/Metalink_3.0_Spec.pdf

    def __init__(self, identity=None, description=None, publisher=None, files=(),
                 workdir=None, checksums=False):
        """Create a MetaLink v3.0 instance.

        :param str identity: human readable identity.
        :param str description: human readable file description.
        :param str publisher: The name of the file's publisher.
        :param tuple files: Sequence of files to include in Metalink. Can also be added using `append`.
        :param str workdir: Work directory to store temporary files.
        :param bool checksums: Whether to compute checksums on files.

        To use, first append `MetaFile` instances, then write the metalink using the `xml`
        property.

        Methods:
            - `append`: add a `MetaFile` instance
        """
        self.identity = identity
        self.description = description
        self.workdir = workdir
        self.publisher = publisher
        self.files = []
        self.checksums = checksums

        for file in files:
            self.append(file)
        self._load_template()

    def append(self, file):
        """Append a `MetaFile` instance."""
        if not isinstance(file, MetaFile):
            raise ValueError("file must be a MetaFile instance.")
        file._set_workdir(self.workdir)
        self.files.append(file)

    @property
    def xml(self):
        return self._template.render(meta=self)

    @property
    def origin(self):
        """IRI where the Metalink Document was originally published.
        If the dynamic attribute of metalink:origin is "true", then
        updated versions of the Metalink can be found at this IRI.
        """
        return ""

    @property
    def published(self):
        """Date construct indicating an instant in time associated
        with an event early in the life cycle of the entry."""
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    @property
    def generator(self):
        """Generating agent name and version used to generate a
        Metalink Document, for debugging and other purposes."""
        import pywps
        return "PyWPS/{}".format(pywps.__version__)

    @property
    def url(self):
        """Return the server URL."""
        return config.get_config_value('server', 'url')

    def _load_template(self):
        from pywps.response import RelEnvironment
        from jinja2 import PackageLoader

        template_env = RelEnvironment(
            loader=PackageLoader('pywps', 'templates'),
            trim_blocks=True, lstrip_blocks=True,
            autoescape=True, )

        self._template = template_env.get_template(self._xml_template)


class MetaLink4(MetaLink):
    _xml_template = 'metalink/4.0/main.xml'
    # Specs: https://tools.ietf.org/html/rfc5854


def output_from_json(json_data):
    data_type = json_data.get('type', 'literal')
    if data_type == 'complex':
        output = ComplexOutput.from_json(json_data)
    elif data_type == 'literal':
        output = LiteralOutput.from_json(json_data)
    elif data_type == 'bbox':
        output = BoundingBoxOutput.from_json(json_data)
    else:
        raise InvalidParameterValue("Output type not recognized: {}".format(data_type))

    return output
