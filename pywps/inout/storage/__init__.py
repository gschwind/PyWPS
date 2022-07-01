##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################
import base64
import io
import logging
import os
import uuid

import pywps.configuration
import pywps.dblog

LOGGER = logging.getLogger('PYWPS')


class STORE_TYPE:
    PATH = 0
    S3 = 1
# TODO: cover with tests


# Allow to store, create and convert storage
_storage_type_registry = {}


# register the given class as storage
def register_storage_type(cls):
    global _storage_type_registry
    _storage_type_registry[cls.__name__] = cls
    return cls


# Return a fresh storage of given typename or the default one
def new_storage(type=None):
    global _storage_type_registry
    if type is None:
        return _storage_type_registry["DatabaseStorage"]()
    else:
        return _storage_type_registry[type]()


# Return a Storage that handle the given uuid or None if not found.
def get_store_instance(uuid):
    global _storage_type_registry
    store_instance_record = pywps.dblog.get_store_instance(uuid)
    if store_instance_record:
        return _storage_type_registry[store_instance_record.type](
            uuid=store_instance_record.uuid,
            pettry_filename=store_instance_record.pretty_filename,
            mimetype=store_instance_record.mimetype,
            json=store_instance_record.data
        )
    return None


class StorageAbstract(object):
    """Data storage abstract class
    """

    def __init__(self, **kwargs):

        if "uuid" in kwargs:
            self._uuid = uuid.UUID(kwargs["uuid"])
            self._pretty_filename = kwargs.get("pretty_filename", None)
            self._mimetype = kwargs.get("mimetype", None)
            self.json = kwargs.get("json", {})
        else:
            # Given uuid to the store
            self._uuid = uuid.uuid1()

            # Will be set only when export is made
            self._pretty_filename = None
            self._mimetype = None

    def open(self, mode = "r", encoding = None):
        """
        Return file object like handler
        """
        raise NotImplementedError

    def export(self, pretty_filename, mimetype):
        """
        Export this file to be available from web
        """
        self._uuid = uuid.uuid1()
        self._pretty_filename = pretty_filename
        self._mimetype = mimetype

        pywps.dblog.update_store_instance(self)
        return self.url

    def unexport(self):
        self.export(None, None)

    @property
    def uuid(self):
        return self._uuid

    @property
    def pretty_filename(self):
        return self._pretty_filename

    @property
    def mimetype(self):
        return self._mimetype


    @property
    def url(self):
        """Build and return the exported url"""
        base_url = pywps.configuration.get_config_value('server', 'url')
        return f"{base_url}?service=files&uuid={self.uuid}"

    # Used to permanently store the file
    @property
    def json(self):
        raise NotImplementedError

    # Used to recreate the store from the database
    @json.setter
    def json(self, value):
        raise NotImplementedError


class DatabaseStorageByteHandler(io.BytesIO):
    def __init__(self, ds, initial_bytes = b''):
        super(DatabaseStorageByteHandler, self).__init__(initial_bytes)
        self._ds = ds

    def flush(self):
        super(DatabaseStorageByteHandler, self).flush()
        self._ds.store(self.getvalue())

    # Override close
    def close(self):
        self._ds.store(self.getvalue())
        super(DatabaseStorageByteHandler, self).close()

    def __exit__(self, *args, **kwargs):
        self._ds.store(self.getvalue())
        super(DatabaseStorageByteHandler, self).__exit__(*args, **kwargs)


class DatabaseStorageStringHandler(io.StringIO):
    def __init__(self, ds, encoding, initial_value=""):
        super(DatabaseStorageStringHandler, self).__init__(initial_value)
        self._ds = ds
        self._encoding = encoding

    def flush(self):
        super(DatabaseStorageStringHandler, self).flush()
        self._ds.store(self.getvalue().encode(self._encoding))

    # Override close
    def close(self):
        self._ds.store(self.getvalue().encode(self._encoding))
        super(DatabaseStorageStringHandler, self).close()

    def __exit__(self, *args, **kwargs):
        self._ds.store(self.getvalue().encode(self._encoding))
        super(DatabaseStorageStringHandler, self).__exit__(*args, **kwargs)

@register_storage_type
class DatabaseStorage(StorageAbstract):
    """Database storage will put data in base64 within the database
    """

    def __init__(self, **kwargs):
        self._data = b''
        super().__init__(**kwargs)

    def open(self, mode, encoding=None):
        if encoding is None:
            if mode == "w":
                return DatabaseStorageByteHandler(self)
            else:
                return DatabaseStorageByteHandler(self, self._data)
        else:
            if mode == "w":
                return DatabaseStorageStringHandler(self, encoding)
            else:
                return DatabaseStorageStringHandler(self, encoding, self._data.decode(encoding))

    def store(self, bytes):
        self._data = bytes
        pywps.dblog.update_store_instance(self)

    @property
    def json(self):
        return base64.b64encode(self._data).decode("utf-8")

    @json.setter
    def json(self, value):
        self._data = base64.b64decode(value.encode("utf-8"))
