##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

"""List of know mimetypes"""

# List of known complex data formats
# you can use any other, but these are widely known and supported by popular
# software packages
# based on Web Processing Service Best Practices Discussion Paper, OGC 12-029
# http://opengeospatial.org/standards/wps

import mimetypes
from typing import Optional, Sequence, Union
from types import SimpleNamespace


class IterableSimpleNamespace(SimpleNamespace):
    def __init__(self, *args, **kw_args):
        super().__init__(*args, **kw_args)

    def __iter__(self):
        return iter(self.__dict__.values())

    def _asdict(self):
        return self.__dict__


class Format(object):
    """Input/output format specification

    Predefined Formats are stored in :class:`pywps.inout.formats.FORMATS`

    :param str mime_type: mimetype definition
    :param str schema: xml schema definition
    :param str encoding: base64 or not
    :param function validate: function, which will perform validation. e.g.
    :param number mode: validation mode
    :param str extension: file extension
    """

    def __init__(self, mime_type,
                 schema=None, encoding=None,
                 validate=None,
                 extension=None):
        """Constructor
        """

        self._mime_type = None
        self._encoding = None
        self._schema = None
        self._extension = None

        self.mime_type = mime_type
        self.encoding = encoding
        self.schema = schema
        self.validate = validate
        self.extension = extension

    @property
    def mime_type(self):
        """Get format mime type
        :rtype: String
        """

        return self._mime_type

    @mime_type.setter
    def mime_type(self, mime_type):
        """Set format mime type
        """
        try:
            # support Format('GML')
            frmt = getattr(FORMATS, mime_type)
            self._mime_type = frmt.mime_type
        except AttributeError:
            # if we don't have this as a shortcut, assume it's a real mime type
            self._mime_type = mime_type
        except NameError:
            # TODO: on init of FORMATS, FORMATS is not available. Clean up code!
            self._mime_type = mime_type

    @property
    def encoding(self):
        """Get format encoding
        :rtype: String
        """

        if self._encoding:
            return self._encoding
        else:
            return ''

    @encoding.setter
    def encoding(self, encoding):
        """Set format encoding
        """

        self._encoding = encoding

    @property
    def schema(self):
        """Get format schema
        :rtype: String
        """
        if self._schema:
            return self._schema
        else:
            return ''

    @schema.setter
    def schema(self, schema):
        """Set format schema
        """
        self._schema = schema

    @property
    def extension(self):
        """Get format extension
        :rtype: String
        """
        if self._extension:
            return self._extension
        else:
            return ''

    @extension.setter
    def extension(self, extension):
        """Set format extension
        """
        self._extension = extension

    def same_as(self, frmt):
        """Check input frmt, if it seems to be the same as self
        """
        if not isinstance(frmt, Format):
            return False
        return all([frmt.mime_type == self.mime_type,
                    frmt.encoding == self.encoding,
                    frmt.schema == self.schema])

    def __eq__(self, other):
        return self.same_as(other)

    @property
    def json(self):
        """Get format as json
        :rtype: dict
        """
        return {
            'mime_type': self.mime_type,
            'encoding': self.encoding,
            'schema': self.schema,
            'extension': self.extension
        }

    @json.setter
    def json(self, jsonin):
        """Set format from json
        :param jsonin:
        """

        self.mime_type = jsonin['mime_type']
        self.encoding = jsonin['encoding']
        self.schema = jsonin['schema']
        self.extension = jsonin['extension']


Supported_Formats = Optional[Sequence[Union[str, Format]]]


FORMATS = IterableSimpleNamespace(
    GEOJSON =  Format('application/geo+json', extension='.geojson'),
    JSON =     Format('application/json', extension='.json'),
    SHP =      Format('application/x-zipped-shp', extension='.zip', encoding='base64'),
    GML =      Format('application/gml+xml', extension='.gml'),
    GPX =      Format('application/gpx+xml', extension='.gpx'),
    METALINK = Format('application/metalink+xml; version=3.0', extension='.metalink', schema="metalink/3.0/metalink.xsd"),
    META4 =    Format('application/metalink+xml; version=4.0', extension='.meta4', schema="metalink/4.0/metalink4.xsd"),
    KML =      Format('application/vnd.google-earth.kml+xml', extension='.kml'),
    KMZ =      Format('application/vnd.google-earth.kmz', extension='.kmz', encoding='base64'),
    GEOTIFF =  Format('image/tiff; subtype=geotiff', extension='.tiff', encoding='base64'),
    WCS =      Format('application/x-ogc-wcs', extension='.xml'),
    WCS100 =   Format('application/x-ogc-wcs; version=1.0.0', extension='.xml'),
    WCS110 =   Format('application/x-ogc-wcs; version=1.1.0', extension='.xml'),
    WCS20 =    Format('application/x-ogc-wcs; version=2.0', extension='.xml'),
    WFS =      Format('application/x-ogc-wfs', extension='.xml'),
    WFS100 =   Format('application/x-ogc-wfs; version=1.0.0', extension='.xml'),
    WFS110 =   Format('application/x-ogc-wfs; version=1.1.0', extension='.xml'),
    WFS20 =    Format('application/x-ogc-wfs; version=2.0', extension='.xml'),
    WMS =      Format('application/x-ogc-wms', extension='.xml'),
    WMS130 =   Format('application/x-ogc-wms; version=1.3.0', extension='.xml'),
    WMS110 =   Format('application/x-ogc-wms; version=1.1.0', extension='.xml'),
    WMS100 =   Format('application/x-ogc-wms; version=1.0.0', extension='.xml'),
    TEXT =     Format('text/plain', extension='.txt'),
    DODS =     Format('application/x-ogc-dods', extension='.nc'),
    NETCDF =   Format('application/x-netcdf', extension='.nc', encoding='base64'),
    NCML =     Format('application/ncML+xml', extension='.ncml', schema="ncml/2.2/ncml-2.2.xsd"),
    LAZ =      Format('application/octet-stream', extension='.laz'),
    LAS =      Format('application/octet-stream', extension='.las'),
    ZIP =      Format('application/zip', extension='.zip', encoding='base64'),
    XML =      Format('application/xml', extension='.xml'),
    CSV =      Format('text/csv', extension='.csv'),
)


def _get_mimetypes():
    """Add FORMATS to system wide mimetypes
    """
    mimetypes.init()
    for pywps_format in FORMATS:
        mimetypes.add_type(pywps_format.mime_type, pywps_format.extension, True)


_get_mimetypes()


def get_format(frmt, validator=None):
    """Return Format instance based on given pywps.inout.FORMATS keyword
    """
    # TODO this should be probably removed, it's used only in tests

    outfrmt = None

    if frmt in FORMATS._asdict():
        outfrmt = FORMATS._asdict()[frmt]
        outfrmt.validate = validator
        return outfrmt
    else:
        return Format('None', validate=validator)
