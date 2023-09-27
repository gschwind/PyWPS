##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

import logging
import os
from urllib.parse import urljoin
import uuid

from pywps import configuration as config
from pywps.exceptions import FileStorageError, NotEnoughStorage
from pywps.inout.basic import IOHandler
import pywps.dblog as db

from pywps.util import trim_directory_if_needed

from types import SimpleNamespace

from . import STORE_TYPE, CachedStorage
from .implementationbuilder import StorageImplementationBuilder

LOGGER = logging.getLogger('PYWPS')


class FileStorageBuilder(StorageImplementationBuilder):

    def build(self):
        file_path = config.get_config_value('file-storage', 'path')
        copy_function = config.get_config_value('server', 'storage_copy_function')
        return FileStorage(file_path, copy_function=copy_function)


def _build_output_name(output):
    (prefix, suffix) = os.path.splitext(output.file)
    if not suffix:
        suffix = output.data_format.extension
    _, file_name = os.path.split(prefix)
    output_name = file_name + suffix
    return output_name, suffix


class FileStorage(CachedStorage):
    """File storage implementation, stores data to file system

    >>> from configparser import ConfigParser
    >>> config = ConfigParser.RawConfigParser()
    >>> config.add_section('FileStorage')
    >>> config.set('FileStorage', 'target', './')
    >>> config.add_section('server')
    >>> config.set('server', 'outputurl', 'http://foo/bar/filestorage')
    >>>
    >>> store = FileStorage()
    >>>
    >>> class FakeOutput(object):
    ...     def __init__(self):
    ...         self.file = self._get_file()
    ...     def _get_file(self):
    ...         tiff_file = open('file.tiff', 'w')
    ...         tiff_file.close()
    ...         return 'file.tiff'
    >>> fake_out = FakeOutput()
    >>> (store_type, path, url) = store.store(fake_out)
    >>> store_type == STORE_TYPE.PATH
    True
    """

    def __init__(self, output_path, copy_function=None):
        """
        """
        CachedStorage.__init__(self)
        self.target = output_path
        self.copy_function = copy_function
        self.uuid = uuid.uuid1()

    def _do_store(self, output):
        """Copy output to final storage location.

        - Create output directory
        - Check available file space
        - Create output file name, taking care of possible duplicates
        - Copy / link output in work directory to output directory
        - Return store type, output path and output URL
        """
        import math
        import platform
        import tempfile
        import uuid

        src_file_name = output.file
        path, basename = os.path.split(src_file_name)

        os.makedirs(self.target, exist_ok=True)

        sz = os.path.getsize(src_file_name)

        min_size = config.get_size_value('file-storage', 'min_stored_size')
        max_size = config.get_size_value('file-storage', 'max_stored_size')

        trim_directory_if_needed(self.target, min_size * 1024 * 1024, max_size * 1024 * 1024, sz)

        # build output name
        _fd, full_output_name = tempfile.mkstemp(dir=self.target, prefix=f"{str(self.uuid)}_", suffix=f"_{basename}")

        LOGGER.info(f'Storing file output to {full_output_name} ({self.copy_function}).')
        try:
            self.copy(src_file_name, full_output_name, self.copy_function)
        except Exception:
            LOGGER.exception(f"Could not copy '{src_file_name}' to '{full_output_name}'.")
            raise FileStorageError("Could not copy output file.")

        url = self.url(full_output_name)
        LOGGER.info('File output URI: {}'.format(url))

        db.update_file_storage_record(SimpleNamespace(
            uuid=self.uuid,
            pretty_filename=basename,
            mimetype=output.data_format.mime_type,
            path=full_output_name
        ))

        return STORE_TYPE.PATH, basename, url

    @staticmethod
    def copy(src, dst, copy_function=None):
        """Copy file from source to destination using `copy_function`.

        Values of `copy_function` (default=`copy`):
        * copy: using `shutil.copy2`
        * move: using `shutil.move`
        * link: using `os.link`  (hardlink)
        """
        import shutil
        if copy_function == 'move':
            shutil.move(src, dst)
        elif copy_function == 'link':
            try:
                os.link(src, dst)
            except Exception:
                LOGGER.warning("Could not create hardlink. Fallback to copy.")
                FileStorage.copy(src, dst)
        else:
            shutil.copy2(src, dst)

    def write(self, data, destination, data_format=None):
        """Write data to self.target."""
        if not os.path.exists(os.path.dirname(self.target)):
            os.makedirs(self.target)

        full_output_name = os.path.join(self.target, destination)

        with open(full_output_name, "w") as file:
            file.write(data)

        return self.url(destination)

    def url(self, destination):
        base_url = config.get_config_value('server', 'url')
        return f"{base_url}/file?uuid={self.uuid}"

    def location(self, destination):
        return os.path.join(self.target, destination)
