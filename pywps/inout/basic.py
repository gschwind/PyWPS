##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################
import io
import json
import sys
from pathlib import PurePath

from pywps.inout.formats import Supported_Formats
from pywps.inout.types import Translations
from pywps.inout.storage import new_storage, get_storage_instance

from io import StringIO
import os
from io import open
import shutil
import requests
import tempfile
import logging
import pywps.configuration as config

from pywps.validator.mode import MODE

from pywps.exceptions import NoApplicableCode, InvalidParameterValue, FileSizeExceeded, \
    FileURLNotSupported
from urllib.parse import urlparse
import base64
from collections import namedtuple
from copy import deepcopy
from io import BytesIO
import humanize

import weakref


_SOURCE_TYPE = namedtuple('SOURCE_TYPE', 'MEMORY, FILE, STREAM, DATA, URL')
SOURCE_TYPE = _SOURCE_TYPE(0, 1, 2, 3, 4)

LOGGER = logging.getLogger("PYWPS")


def _is_textfile(filename):
    try:
        # use python-magic if available
        import magic
        is_text = 'text/' in magic.from_file(filename, mime=True)
    except ImportError:
        # read the first part of the file to check for a binary indicator.
        # This method won't detect all binary files.
        blocksize = 512
        fh = open(filename, 'rb')
        is_text = b'\x00' not in fh.read(blocksize)
        fh.close()
    return is_text


class NoneIOHandler(object):
    """Base class for implementation of IOHandler internal"""

    prop = None

    def __init__(self, ref):
        self._ref = weakref.ref(ref)

    @property
    def file(self):
        """Return filename."""
        return None

    @property
    def data(self):
        """Read file and return content."""
        return None

    @property
    def base64(self):
        """Return base64 encoding of data."""
        return None

    @property
    def stream(self):
        """Return stream object."""
        return None

    @property
    def mem(self):
        """Return memory object."""
        return None

    @property
    def url(self):
        """Return url to file."""
        return None

    @property
    def size(self):
        """Length of the linked content in octets."""
        return None

    @property
    def post_data(self):
        raise NotImplementedError

    # Will raise an error if used on invalid object
    @post_data.setter
    def post_data(self, value):
        raise NotImplementedError

    @property
    def storage(self):
        return None


class IOHandler(object):
    """Base IO handling class that handle multple IO types

    This class is created with NoneIOHandler that have no data
    inside. To initialise data you can set the `file`, `url`, `data` or
    `stream` attribute. If reset one of this attribute old data are lost and
    replaced by the new one.

    :param workdir: working directory, to save temporal file objects in.
    :param mode: ``MODE`` validation mode.


    `file` : str
      Filename on the local disk.
    `url` : str
      Link to an online resource.
    `stream` : FileIO
      A readable object.
    `data` : object
      A native python object (integer, string, float, etc)
    `base64` : str
      A base 64 encoding of the data.

    >>> # setting up
    >>> import os
    >>> from io import RawIOBase
    >>> from io import FileIO
    >>>
    >>> ioh_file = IOHandler(workdir=tmp)
    >>> assert isinstance(ioh_file, IOHandler)
    >>>
    >>> # Create test file input
    >>> fileobj = open(os.path.join(tmp, 'myfile.txt'), 'w')
    >>> fileobj.write('ASDF ASFADSF ASF ASF ASDF ASFASF')
    >>> fileobj.close()
    >>>
    >>> # testing file object on input
    >>> ioh_file.file = fileobj.name
    >>> assert ioh_file.file == fileobj.name
    >>> assert isinstance(ioh_file.stream, RawIOBase)
    >>> # skipped assert isinstance(ioh_file.memory_object, POSH)
    >>>
    >>> # testing stream object on input
    >>> ioh_stream = IOHandler(workdir=tmp)
    >>> assert ioh_stream.workdir == tmp
    >>> ioh_stream.stream = FileIO(fileobj.name,'r')
    >>> assert open(ioh_stream.file).read() == ioh_file.stream.read()
    >>> assert isinstance(ioh_stream.stream, RawIOBase)
    """

    def __init__(self, spec, workdir=None, mode=MODE.NONE):
        self._iohandler = NoneIOHandler(self)

        # Read only
        self._spec = spec
        self._storage = None

        # Internal defaults for class and subclass properties.
        self._workdir = None

        # Set public defaults
        self.workdir = workdir
        self.valid_mode = mode

        # TODO: Clarify intent
        self.as_reference = False
        self.inpt = {}
        self.uuid = None  # request identifier
        self.data_set = False

    def _check_valid(self):
        """Validate this input using given validator
        """
        _valid = self._spec.validate(self, self.valid_mode)
        if not _valid:
            self.data_set = False
            raise InvalidParameterValue('Input data not valid using '
                                        'mode {}'.format(self.valid_mode))
        self.data_set = True

    @property
    def workdir(self):
        return self._workdir

    @workdir.setter
    def workdir(self, path):
        """Set working temporary directory for files to be stored in."""

        if path is not None:
            if not os.path.exists(path):
                os.makedirs(path)

        self._workdir = path

    @property
    def validator(self):
        return self._spec.validator

    @property
    def spec(self):
        return self._spec

    @property
    def source_type(self):
        """Return the source type."""
        # For backward compatibility only. source_type checks could be replaced by `isinstance`.
        return getattr(SOURCE_TYPE, self.prop.upper())

    def _set_default_value(self, value=None, value_type=None):
        """Set default value based on input data type."""
        value = value or getattr(self, '_default')
        value_type = value_type or getattr(self, '_default_type')

        if value:
            # only set default when a value is optional
            if self.min_occurs == 0:
                if value_type == SOURCE_TYPE.DATA:
                    self.data = value
                elif value_type == SOURCE_TYPE.MEMORY:
                    raise NotImplementedError
                elif value_type == SOURCE_TYPE.FILE:
                    self.file = value
                elif value_type == SOURCE_TYPE.STREAM:
                    self.stream = value
                elif value_type == SOURCE_TYPE.URL:
                    self.url = value
            else:
                # when a value is requried the default value will be ignored
                LOGGER.warning(
                    "The given default value will not be used"
                    " because is is required to provide a value.")

    def _build_file_name(self, href=''):
        """Return a file name for the local system."""
        url_path = urlparse(href).path or ''
        file_name = os.path.basename(url_path).strip() or 'input'
        (prefix, suffix) = os.path.splitext(file_name)
        suffix = suffix or self.extension
        if prefix and suffix:
            file_name = prefix + suffix
        input_file_name = os.path.join(self.workdir, file_name)

        # build tempfile in case of duplicates
        if os.path.exists(input_file_name):
            input_file_name = tempfile.mkstemp(
                suffix=suffix, prefix=prefix + '_',
                dir=self.workdir)[1]
        else:
            open(file_name, "w")

        return input_file_name

    @property
    def extension(self):
        """Return the file extension for the data format, if set."""
        if getattr(self, 'data_format', None):
            return self.data_format.extension
        else:
            return ''

    def clone(self):
        """Create copy of yourself
        """
        return deepcopy(self)

    @property
    def base64(self):
        """Return raw data
        WARNING: may be bytes or str"""
        return self._iohandler.base64

    @property
    def size(self):
        """Return object size in bytes.
        """
        return self._iohandler.size

    @property
    def file(self):
        """Return a file name"""
        return self._iohandler.file

    @file.setter
    def file(self, value):
        #import traceback
        #print("="*80)
        print(f"Create FileHandler {value}")
        #traceback.print_stack(file=sys.stdout)
        #print("="*80)
        self._iohandler = FileHandler(value, self)
        self._check_valid()

    @property
    def data(self):
        """Return raw data
        WARNING: may be bytes or str"""
        return self._iohandler.data

    def data_as_json(self):
        # applies json.loads if needed
        data = self._iohandler.data
        if data and not isinstance(self._iohandler, DataHandler) and self.extension in ['.geojson', 'json']:
            data = json.loads(data)
            self.data = data  # switch to a DataHandler
        return data

    @data.setter
    def data(self, value):
        print(f"Create DataHandler {value}")
        self._iohandler = DataHandler(value, self)
        self._check_valid()

    @property
    def stream(self):
        """Return stream of data
        WARNING: may be FileIO or StringIO"""
        return self._iohandler.stream

    @stream.setter
    def stream(self, value):
        print(f"Create StreamHandler {value}")
        self._iohandler = StreamHandler(value, self)
        self._check_valid()

    @property
    def url(self):
        """Return the url of data"""
        return self._iohandler.url

    @url.setter
    def url(self, value):
        print(f"Create URlHandler {value}")
        self._iohandler = UrlHandler(value, self)
        self._check_valid()

    # FIXME: post_data is only related to url, this should be initialize with url setter
    @property
    def post_data(self):
        return self._iohandler.post_data

    # Will raise an arror if used on invalid object
    @post_data.setter
    def post_data(self, value):
        self._iohandler.post_data = value

    @property
    def prop(self):
        return self._iohandler.prop

    # Give to the data store an url
    def export(self):
        return self._iohandler.storage.export(self.identifier + self.data_format.extension, self.data_format.mime_type)


class FileHandler(NoneIOHandler):
    prop = 'file'

    def __init__(self, value, ref):
        self._ref = weakref.ref(ref)
        self._data = None
        self._stream = None
        self._storage = None
        self._file = os.path.abspath(value)

    @property
    def file(self):
        """Return filename."""
        return self._file

    @property
    def data(self):
        """Read file and return content."""
        if self._data is None:
            openmode = self._openmode(self._ref())
            kwargs = {} if 'b' in openmode else {'encoding': 'utf8'}
            with open(self.file, mode=openmode, **kwargs) as fh:
                self._data = fh.read()
        return self._data

    @property
    def base64(self):
        """Return base64 encoding of data."""
        data = self.data.encode() if not isinstance(self.data, bytes) else self.data
        return base64.b64encode(data)

    @property
    def stream(self):
        """Return stream object."""
        from io import FileIO
        if self._stream and not self._stream.closed:
            self._stream.close()

        self._stream = FileIO(self.file, mode='r', closefd=True)
        return self._stream

    @property
    def url(self):
        """Return url to file."""
        result = PurePath(self.file).as_uri()
        return result

    # Ensure the storage of handled data to be able to expose it to with url
    @property
    def storage(self):
        print(f"Try store {self.identifier}")

        if self._storage is not None:
            return self._storage

        self._storage = new_storage()

        # Copy data to the storage
        with self.stream as fi:
            # TODO: sanitise self.stream to always provide a binary stream.
            encoding = None
            if isinstance(fi, io.StringIO):
                encoding = "utf-8"
            with self._storage.open("w", encoding) as fo:
                s = fi.read(4096)
                while len(s) > 0:
                    fo.write(s)
                    s = fi.read(4096)
                    # TODO: For now the __exit__ is not implemented properly

        return self._storage

    @property
    def size(self):
        """Length of the linked content in octets."""
        return os.stat(self.file).st_size

    def _openmode(self, base, data=None):
        openmode = 'r'
        # in Python 3 we need to open binary files in binary mode.
        checked = False
        if hasattr(base, 'data_format'):
            if base.data_format.encoding == 'base64':
                # binary, when the data is to be encoded to base64
                openmode += 'b'
                checked = True
            elif 'text/' in base.data_format.mime_type:
                # not binary, when mime_type is 'text/'
                checked = True
        # when we can't guess it from the mime_type, we need to check the file.
        # mimetypes like application/xml and application/json are text files too.
        if not checked and not _is_textfile(self.file):
            openmode += 'b'
        return openmode


class DataHandler(FileHandler):
    prop = 'data'

    def __init__(self, value, ref):
        self._ref = weakref.ref(ref)
        self._file = None
        self._stream = None
        self._data = value

    def _openmode(self, data=None):
        openmode = 'w'
        if isinstance(data, bytes):
            # on Python 3 open the file in binary mode if the source is
            # bytes, which happens when the data was base64-decoded
            openmode += 'b'
        return openmode

    @property
    def data(self):
        """Return data."""
        return self._data

    @property
    def file(self):
        """Return file name storing the data.

        Requesting the file attributes writes the data to a temporary file on disk.
        """
        if self._file is None:
            self._file = self._ref()._build_file_name()
            print(f"YYYY Create File {self._file}")
            openmode = self._openmode(self.data)
            kwargs = {} if 'b' in openmode else {'encoding': 'utf8'}
            with open(self._file, openmode, **kwargs) as fh:
                if isinstance(self.data, (bytes, str)):
                    fh.write(self.data)
                else:
                    json.dump(self.data, fh)

        return self._file

    @property
    def stream(self):
        """Return a stream representation of the data."""
        if isinstance(self.data, bytes):
            return BytesIO(self.data)
        else:
            return StringIO(str(self.data))


class StreamHandler(DataHandler):
    prop = 'stream'

    def __init__(self, value, ref):
        self._ref = weakref.ref(ref)
        self._file = None
        self._data = None
        self._stream = value

    @property
    def stream(self):
        """Return the stream."""
        return self._stream

    @property
    def data(self):
        """Return the data from the stream."""
        if self._data is None:
            self._data = self.stream.read()
        return self._data


class UrlHandler(FileHandler):
    prop = 'url'

    def __init__(self, value, ref):
        self._ref = weakref.ref(ref)
        self._file = None
        self._data = None
        self._stream = None
        self._url = value
        self._post_data = None

    @property
    def url(self):
        """Return the URL."""
        return self._url

    @property
    def file(self):
        """Downloads URL and return file pointer.
        Checks if size is allowed before download.
        """
        if self._file is not None:
            return self._file

        self._file = self._ref()._build_file_name(href=self.url)

        max_byte_size = self.max_size()

        # Create request
        try:
            reference_file = self._openurl(self.url, self.post_data)
            data_size = reference_file.headers.get('Content-Length', 0)
        except Exception as e:
            raise NoApplicableCode('File reference error: {}'.format(e))

        error_message = 'File size for input "{}" exceeded. Maximum allowed: {}'.format(
            self._ref().inpt.get('identifier', '?'), humanize.naturalsize(max_byte_size))

        if int(max_byte_size) > 0:
            if int(data_size) > int(max_byte_size):
                raise FileSizeExceeded(error_message)

        try:
            with open(self._file, 'wb') as f:
                data_size = 0
                for chunk in reference_file.iter_content(chunk_size=1024):
                    data_size += len(chunk)
                    if int(max_byte_size) > 0:
                        if int(data_size) > int(max_byte_size):
                            raise FileSizeExceeded(error_message)
                    f.write(chunk)
        except FileSizeExceeded:
            raise
        except Exception as e:
            raise NoApplicableCode(e)

        return self._file

    @property
    def post_data(self):
        return self._post_data

    @post_data.setter
    def post_data(self, value):
        self._post_data = value

    @property
    def size(self):
        """Get content-length of URL without download"""
        req = self._openurl(self.url)
        if req.ok:
            size = int(req.headers.get('content-length', '0'))
        else:
            size = 0
        return size

    @staticmethod
    def _openurl(href, data=None):
        """Open given href.
        """
        LOGGER.debug('Fetching URL {}'.format(href))
        if data is not None:
            req = requests.post(url=href, data=data, stream=True)
        else:
            req = requests.get(url=href, stream=True)

        return req

    @staticmethod
    def max_size():
        """Calculates maximal size for input file based on configuration
        and units.

        :return: maximum file size in bytes
        """
        ms = config.get_config_value('server', 'maxsingleinputsize')
        byte_size = config.get_size_mb(ms) * 1024**2
        return byte_size


# class SimpleHandler(IOHandler):
#     """Data handler for Literal In- and Outputs
#
#     >>> class Int_type(object):
#     ...     @staticmethod
#     ...     def convert(value): return int(value)
#     >>>
#     >>> class MyValidator(object):
#     ...     @staticmethod
#     ...     def validate(inpt): return 0 < inpt.data < 3
#     >>>
#     >>> inpt = SimpleHandler(data_type = Int_type)
#     >>> inpt.validator = MyValidator
#     >>>
#     >>> inpt.data = 1
#     >>> inpt.validator.validate(inpt)
#     True
#     >>> inpt.data = 5
#     >>> inpt.validator.validate(inpt)
#     False
#     """
#
#     def __init__(self, workdir=None, data_type=None, mode=MODE.NONE):
#         IOHandler.__init__(self, workdir=workdir, mode=mode)
#         if data_type not in LITERAL_DATA_TYPES:
#             raise ValueError('data_type {} not in {}'.format(data_type, LITERAL_DATA_TYPES))
#         self.data_type = data_type
#
#     @IOHandler.data.setter
#     def data(self, value):
#         """Set data value. Inputs are converted into target format.
#         """
#         if self.data_type and value is not None:
#             value = convert(self.data_type, value)
#
#         IOHandler.data.fset(self, value)


