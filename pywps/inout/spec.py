# -*- coding: utf-8 -*-
##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

import logging
from collections import deque
from . import inputs
from pywps.exceptions import (StorageNotSupported, OperationNotSupported,
                              MissingParameterValue, FileURLNotSupported,
                              ServerBusy, NoApplicableCode,
                              InvalidParameterValue)
from pywps.validator.base import emptyvalidator
from pywps.validator import get_validator
from pywps.validator.literalvalidator import (validate_value,
                                              validate_anyvalue,
                                              validate_allowed_values,
                                              validate_values_reference)
from pywps.translations import lower_case_dict
from pywps.inout.literaltypes import (LITERAL_DATA_TYPES, convert,
                                      make_allowedvalues, is_anyvalue,
                                      is_values_reference)
from pywps.validator.mode import MODE
from collections import namedtuple
from pywps import OGCUNIT

_SOURCE_TYPE = namedtuple('SOURCE_TYPE', 'MEMORY, FILE, STREAM, DATA, URL')
SOURCE_TYPE = _SOURCE_TYPE(0, 1, 2, 3, 4)

LOGGER = logging.getLogger("PYWPS")

class UOM(object):
    """
    :param uom: unit of measure
    """

    def __init__(self, uom='', reference=None):
        self.uom = uom
        self.reference = reference

        if self.reference is None:
            self.reference = OGCUNIT[self.uom]

    @property
    def json(self):
        return {"reference": self.reference,
                "uom": self.uom}

    def __eq__(self, other):
        return self.uom == other.uom


class BasicIO:
    """Store common data needed for the description of WPS inputs parameters
    or outputs parameters. Developers note: Should never handle actual data.

    :param str identifier: The name of this input.
    :param str title: Title of the input
    :param str abstract: Input abstract
    :param list keywords: Keywords that characterize this input.
    :param int min_occurs: minimum occurence
    :param int max_occurs: maximum occurence
    :param list metadata: List of metadata advertised by this process. They
                     should be :class:`pywps.app.Common.Metadata` objects.
    :param dict[str,dict[str,str]] translations: The first key is the RFC 4646 language code,
        and the nested mapping contains translated strings accessible by a string property.
        e.g. {"fr-CA": {"title": "Mon titre", "abstract": "Une description"}}
    """

    def __init__(self, identifier, title=None, abstract=None, keywords=None,
                 min_occurs=1, max_occurs=1, metadata=None, translations=None,
                 validator=None, validate_mode=MODE.NONE):
        self.identifier = identifier
        self.title = title
        self.abstract = abstract
        self.keywords = keywords
        self.min_occurs = int(min_occurs) if min_occurs is not None else 0
        self.max_occurs = int(max_occurs) if max_occurs is not None else None
        self.metadata = metadata if metadata is not None else []
        self.translations = lower_case_dict(translations)
        self.validator = validator
        self.validate_mode = validate_mode

    def as_json(self):
        return {
            'identifier': self.identifier,
            'title': self.title,
            'abstract': self.abstract,
            'keywords': self.keywords,
            'min_occurs': self.min_occurs,
            'max_occurs': self.max_occurs,
            'metadata': self.metadata,
            'translations': self.translations,
            'validate_mode': self.validate_mode
            # FIXME: cannot store self.validator
        }

    @property
    def json(self):
        """Serialize for DescribeProcess
        """
        return self.as_json()

    # Default validation
    def validate(self, io, validate_mode):
        if self.validator is not None:
            return self.validator(io, validate_mode)
        return True



class BasicLiteral(BasicIO):
    """Basic literal Input/Output class
    """

    def __init__(self, *args, data_type='string', uoms=None, mode=None, **kwargs):
        assert data_type in LITERAL_DATA_TYPES

        super().__init__(*args, **kwargs)

        self.data_type = data_type
        # list of uoms
        self.uoms = []
        # current uom
        self._uom = None

        # list of uoms
        self.uoms = []
        # add all uoms (upcasting to UOM)
        if uoms is not None:
            for uom in uoms:
                if not isinstance(uom, UOM):
                    uom = UOM(uom)
                self.uoms.append(uom)

        if len(self.uoms)>0:
            # default/current uom
            self.uom = self.uoms[0]

    @property
    def uom(self):
        return self._uom

    @uom.setter
    def uom(self, uom):
        if uom is not None:
            self._uom = uom

    def as_json(self):
        data = super().as_json()
        data['data_type'] = self.data_type

        if self.uoms:
            data["uoms"] = [uom.json for uom in self.uoms]
        return data


class BasicComplex(BasicIO):
    """Basic complex input/output class

    """

    def __init__(self, *args, data_format=None, supported_formats=None, **kwargs):
        super().__init__(*args, **kwargs)

        self._data_format = data_format
        self._supported_formats = ()
        if supported_formats:
            self.supported_formats = supported_formats

        if data_format:
            self.data_format = data_format
        elif self.supported_formats:
            # not an empty list, set the default/current format to the first
            self.data_format = supported_formats[0]

    def as_json(self):
        data = super().as_json()
        data.update({
            'type': 'complex',
            'data_format': self.data_format.json,
            'supported_formats': [frmt.json for frmt in self.supported_formats]
        })
        return data

    def get_format(self, mime_type):
        """
        :param mime_type: given mimetype
        :return: Format
        """

        for frmt in self.supported_formats:
            if frmt.mime_type == mime_type:
                return frmt
        else:
            return None

    def validate(self, io, validate_mode):
        """Return the proper validator for given data_format
        """
        if self.validator is not None:
            return self.validator(io, validate_mode)

        if self.data_format is None:
            return True
        else:
            return self.data_format.validate(io, validate_mode)


    @property
    def supported_formats(self):
        return self._supported_formats

    @supported_formats.setter
    def supported_formats(self, supported_formats):
        """Setter of supported formats
        """

        def set_format_validator(supported_format):
            if not supported_format.validate or \
               supported_format.validate == emptyvalidator:
                supported_format.validate =\
                    get_validator(supported_format.mime_type)
            return supported_format

        self._supported_formats = tuple(map(set_format_validator, supported_formats))

    @property
    def data_format(self):
        return self._data_format

    @data_format.setter
    def data_format(self, data_format):
        """self data_format setter
        """
        if self._is_supported(data_format):
            self._data_format = data_format
            if not data_format.validate or data_format.validate == emptyvalidator:
                data_format.validate = get_validator(data_format.mime_type)
        else:
            raise InvalidParameterValue("Requested format {}, {}, {} not supported".format(
                                        data_format.mime_type,
                                        data_format.encoding,
                                        data_format.schema),
                                        'mimeType')

    def _is_supported(self, data_format):

        if self.supported_formats:
            for frmt in self.supported_formats:
                if frmt.same_as(data_format):
                    return True

        return False


class BasicBoundingBox(BasicIO):
    """Basic BoundingBox input/output class
    """

    def __init__(self, *args, crss=None, dimensions=2, mode=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.crss = crss or ['epsg:4326']
        self.dimensions = dimensions

    def as_json(self):
        data = super().as_json()
        data.update({
            'type': 'bbox',
            'bbox': self.data,
            'crss': self.crss,
            'dimensions': self.dimensions
        })
        return data




class LiteralInput(BasicLiteral):
    """LiteralInput input abstract class
    """

    def __init__(self, *args, allowed_values=None,
                 default=None, default_type=SOURCE_TYPE.DATA, **kwargs):

        BasicLiteral.__init__(self, *args, **kwargs)

        if default_type != SOURCE_TYPE.DATA:
            raise InvalidParameterValue("Source types other than data are not supported.")

        self.any_value = False
        self.values_reference = None
        self.allowed_values = []

        if allowed_values:
            if not isinstance(allowed_values, (tuple, list)):
                allowed_values = [allowed_values]
            self.any_value = any(is_anyvalue(a) for a in allowed_values)
            for value in allowed_values:
                if is_values_reference(value):
                    self.values_reference = value
                    break
            self.allowed_values = make_allowedvalues(allowed_values)

        self._default = default
        self._default_type = default_type

    def as_json(self):
        data = super().as_json()
        data.update({
            'type': 'literal',
            'allowed_values': [value.json for value in self.allowed_values],
            'any_value': self.any_value
        })

        if self._default is not None:
            data['data'] = str(self._default)

        return data

    def validate(self, io, validate_mode):
        """Get validator for any value as well as allowed_values
        :rtype: function
        """

        # Custom validator
        if self.validator is not None:
            return self.validator(io, validate_mode)

        if self.any_value:
            return validate_anyvalue(io, validate_mode)
        elif self.values_reference:
            return validate_values_reference(io, validate_mode)
        elif self.allowed_values:
            return validate_allowed_values(io, validate_mode)
        else:
            return validate_value(io, validate_mode)

    def create(self, request_inputs):
        if request_inputs is None:
            # TODO: default values or exception
            ...

        o = deque(maxlen=self.max_occurs)
        for i in request_inputs:
            o.append(inputs.LiteralInput(self, i))
        if len(o) < self.min_occurs:
            description = "At least {} inputs are required. You provided {}.".format(
                self.min_occurs, len(o))
            raise MissingParameterValue(description, locator=self.identifier)
        return o


class LiteralOutput(BasicLiteral):
    """Basic LiteralOutput class
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # Explicit call to parent
    def as_json(self):
        return super().as_json()


class BoundingBoxInput(BasicBoundingBox):
    """Basic Bounding box input abstract class
    """

    def __init__(self, *args, default=None, default_type=SOURCE_TYPE.DATA, **kwargs):
        super().__init__(*args, **kwargs)

        if default_type != SOURCE_TYPE.DATA:
            raise InvalidParameterValue("Source types other than data are not supported.")

        self._default = default
        self._default_type = default_type

        # TODO: use to build default value in inputs.BoundingBoxInput
        # self._set_default_value(default, default_type)

    def create(self, json):
        return inputs.BoundingBoxInput(self, json)

        outinputs = deque(maxlen=self.max_occurs)

        for inpt in inputs:
            newinpt = source.clone()
            newinpt.data = inpt.get('data')
            LOGGER.debug(f'newinpt bbox data={newinpt.data}')
            newinpt.crs = inpt.get('crs')
            newinpt.dimensions = inpt.get('dimensions')
            outinputs.append(newinpt)

        if len(outinputs) < source.min_occurs:
            description = "At least {} inputs are required. You provided {}.".format(
                source.min_occurs,
                len(outinputs),
            )
            raise MissingParameterValue(description=description, locator=source.identifier)

        return outinputs


class BoundingBoxOutput(BasicBoundingBox):
    """Basic BoundingBox output class
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ComplexInput(BasicComplex):
    """
    Store specification of ComplexInput [Public API]

    :param str identifier: The name of this input.
    :param str title: Title of the input
    :param pywps.inout.formats.Format supported_formats: List of supported
                                                          formats
    :param pywps.inout.formats.Format data_format: default data format
    :param str abstract: Input abstract
    :param list keywords: Keywords that characterize this input.
    :param str workdir: working directory, to save temporary file objects in.
    :param list metadata: TODO
    :param int min_occurs: minimum occurrence
    :param int max_occurs: maximum occurrence
    :param pywps.validator.mode.MODE mode: validation mode (none to strict)
    :param dict[str,dict[str,str]] translations: The first key is the RFC 4646 language code,
        and the nested mapping contains translated strings accessible by a string property.
        e.g. {"fr-CA": {"title": "Mon titre", "abstract": "Une description"}}

    >>> ci = ComplexInput()
    >>> ci.validator = 1
    >>> ci.validator
    1
    """

    def __init__(self, *args, default=None, default_type=SOURCE_TYPE.DATA, **kwargs):
        super().__init__(*args, **kwargs)

        self._default = default
        self._default_type = default_type

    @staticmethod
    def _validate_file_input(href):
        href = href or ''
        parsed_url = urlparse(href)
        if parsed_url.scheme != 'file':
            raise FileURLNotSupported('Invalid URL scheme')
        file_path = parsed_url.path
        if not file_path:
            raise FileURLNotSupported('Invalid URL path')
        file_path = os.path.abspath(file_path)
        # build allowed paths list
        inputpaths = config.get_config_value('server', 'allowedinputpaths')
        allowed_paths = [os.path.abspath(p.strip()) for p in inputpaths.split(os.pathsep) if p.strip()]
        for allowed_path in allowed_paths:
            if file_path.startswith(allowed_path):
                LOGGER.debug("Accepted file url as input.")
                return
        raise FileURLNotSupported()

    def create(self, request_inputs):
        if request_inputs is None:
            # TODO: create default values
            ...

        o = deque(maxlen=self.max_occurs)
        for i in request_inputs:
            o.append(inputs.ComplexInput(self, i))

        if len(o) < self.min_occurs:
            description = "At least {} inputs are required. You provided {}.".format(
                self.min_occurs,
                len(o),
            )
            raise MissingParameterValue(description=description, locator=self.identifier)
        return o


class ComplexOutput(BasicComplex):
    """Complex output abstract class

    >>> # temporary configuration
    >>> import ConfigParser
    >>> from pywps.storage import *
    >>> config = ConfigParser.RawConfigParser()
    >>> config.add_section('FileStorage')
    >>> config.set('FileStorage', 'target', './')
    >>> config.add_section('server')
    >>> config.set('server', 'outputurl', 'http://foo/bar/filestorage')
    >>>
    >>> # create temporary file
    >>> tiff_file = open('file.tiff', 'w')
    >>> tiff_file.write("AA")
    >>> tiff_file.close()
    >>>
    >>> co = ComplexOutput()
    >>> co.file ='file.tiff'
    >>> fs = FileStorage(config)
    >>> co.storage = fs
    >>>
    >>> url = co.url # get url, data are stored
    >>>
    >>> co.stream.read() # get data - nothing is stored
    'AA'
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

