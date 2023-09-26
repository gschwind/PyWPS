##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

"""
Implementation of logging for PyWPS-4
"""

import datetime
import logging
import os
import sys
import json
import time

from types import SimpleNamespace
from multiprocessing import Lock

import sqlalchemy
from sqlalchemy import Integer, LargeBinary, Unicode
from sqlalchemy.orm import sessionmaker, mapped_column, DeclarativeBase, Mapped
from sqlalchemy.pool import NullPool, StaticPool

from pywps import configuration
from pywps.exceptions import NoApplicableCode

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

from pywps.response.status import WPS_STATUS

from types import SimpleNamespace as ns

LOGGER = logging.getLogger('PYWPS')
_SESSION_MAKER_DATABASE = None
_SESSION_MAKER = None

_tableprefix = configuration.get_config_value('logging', 'prefix')
_schema = configuration.get_config_value('logging', 'schema')


from sqlalchemy.types import TypeDecorator


def TemplateIntEnum(cls: type):
    """Create appropriate class to handle the enum.IntEnum by sqlalchemy"""
    class TemapleMetaIntEnum(TypeDecorator):
        """Convert Python IntEnum to Integer and the opposite"""

        impl = Integer

        cache_ok = True

        def process_bind_param(self, value, dialect):
            return value.value

        def process_result_value(self, value, dialect):
            return cls(value)

    return TemapleMetaIntEnum


WPS_STATUS_TYPE = TemplateIntEnum(WPS_STATUS)


class JSON_BINARY(TypeDecorator):
    impl = LargeBinary

    cache_ok = True

    def process_bind_param(self, value, dialect):
        return json.dumps(value).encode("utf-8")

    def process_result_value(self, value, dialect):
        return json.loads(value.decode("utf-8"))


class Base(DeclarativeBase):
    type_annotation_map = {
        str: Unicode,
        WPS_STATUS: WPS_STATUS_TYPE
    }
    pass


lock = Lock()


class SessionManager:
    """Implement ref counted session, and close session automaticaly

    This SessionManager allow to call all dblog function recursively

    Usage:

    >>> with current_session as session:
    ...     [...]
    ...     pass

    Nested with statement will reuse the session and only one session.close()
    will be issued and it will be issued in any case, even on return or
    exception within 'with' statement
    """
    def __init__(self):
        self._session = None
        self._handler_count = 0

    def __enter__(self):
        self._handler_count += 1
        if self._session is None:
            self._session = get_session()
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._handler_count -= 1
        if self._handler_count <= 0:
            self._session.close()
            self._session = None
        return False


current_session = SessionManager()


class ProcessInstance(Base):
    __tablename__ = '{}requests'.format(_tableprefix)

    uuid: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    pid: Mapped[int] = mapped_column(nullable=False)
    operation: Mapped[str] = mapped_column(nullable=False)
    version: Mapped[str] = mapped_column(nullable=False)
    time_start: Mapped[datetime.datetime] = mapped_column(nullable=False)
    time_end: Mapped[datetime.datetime] = mapped_column(nullable=True)
    identifier: Mapped[str] = mapped_column(nullable=True)
    message: Mapped[str] = mapped_column(nullable=True)
    percent_done: Mapped[float] = mapped_column(nullable=True)
    status: Mapped[WPS_STATUS] = mapped_column(nullable=False, insert_default=WPS_STATUS.UNKNOWN)

    def __repr__(self):
        return f"<ProcessInstance id={self.uuid} pid={self.pid} operation={self.operation}" \
               f"status={self.status.name} percent_done={self.percent_done}>"


class RequestInstance(Base):
    __tablename__ = '{}stored_requests'.format(_tableprefix)

    uuid: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    request: Mapped[bytes] = mapped_column(JSON_BINARY, nullable=False)


class FileStorageRecord(Base):
    __tablename__ = '{}file_storage_records'.format(_tableprefix)

    uuid: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    pretty_filename: Mapped[str] = mapped_column(nullable=True)
    mimetype: Mapped[str] = mapped_column(nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(nullable=False)


class StatusRecord(Base):
    __tablename__ = '{}status_records'.format(_tableprefix)

    # Process uuid
    uuid: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    # Time stamp for creation time
    timestamp: Mapped[datetime.datetime] = mapped_column(nullable=False)
    # json data used in template
    data: Mapped[bytes] = mapped_column(JSON_BINARY, nullable=False)


def log_request(uuid, request):
    """Write OGC WPS request (only the necessary parts) to database logging
    system
    """

    pid = os.getpid()
    operation = request.operation
    version = request.version
    time_start = datetime.datetime.now()
    identifier = _get_identifier(request)

    with current_session as session:
        request = ProcessInstance(
            uuid=str(uuid), pid=pid, operation=operation, version=version,
            time_start=time_start, identifier=identifier)
        session.add(request)
        session.commit()
    # NoApplicableCode("Could commit to database: {}".format(e.message))


def get_process_counts():
    """Returns running and stored process counts and
    """

    with current_session as session:
        stored_query = session.query(RequestInstance.uuid)
        running_count = (
            session.query(ProcessInstance)
            .filter(ProcessInstance.percent_done < 100)
            .filter(ProcessInstance.percent_done > -1)
            .filter(~ProcessInstance.uuid.in_(stored_query))
            .count()
        )
        stored_count = stored_query.count()
        return running_count, stored_count


def pop_first_stored():
    """Gets the first stored process and delete it from the stored_requests table
    """
    with current_session as session:
        request = session.query(RequestInstance).first()

        if request:
            delete_count = session.query(RequestInstance).filter_by(uuid=request.uuid).delete()
            if delete_count == 0:
                LOGGER.debug("Another thread or process took the same stored request")
                request = None

            session.commit()
        return request


def store_status(uuid, wps_status, message=None, status_percentage=None):
    """Writes response to database
    """
    with current_session as session:
        requests = session.query(ProcessInstance).filter_by(uuid=str(uuid))
        if requests.count():
            request = requests.one()
            request.time_end = datetime.datetime.now()
            request.message = str(message)
            request.percent_done = status_percentage
            request.status = wps_status
            session.commit()


def update_file_storage_record(store_instance):
    """Update or create a file store instance"""
    with current_session as session:
        r = session.query(FileStorageRecord).filter_by(uuid=str(store_instance.uuid))
        if r.count() > 0:
            store_instance_record = r.one()
            store_instance_record.pretty_filename = store_instance.pretty_filename
            store_instance_record.mimetype = store_instance.mimetype
            store_instance_record.path = store_instance.path
        else:
            store_instance_record = FileStorageRecord(
                uuid=str(store_instance.uuid),
                timestamp=datetime.datetime.now(),
                pretty_filename=store_instance.pretty_filename,
                mimetype=store_instance.mimetype,
                path=store_instance.path
            )
            session.add(store_instance_record)
        session.commit()


def get_file_storage_record(uuid):
    """Get file store from uuid"""
    with current_session as session:
        r = session.query(FileStorageRecord).filter_by(uuid=str(uuid))
        if r.count() < 1:
            return None
        store_instance_record = r.one()
        # Copy store_instance_record content to unlink data from session
        # TODO: get dynamic list of attributes
        attrs = ["uuid", "timestamp", "pretty_filename", "mimetype", "path"]
        store_instance_record = ns(**{k: getattr(store_instance_record, k) for k in attrs})
        return store_instance_record


# Update or create a store instance
def update_status_record(uuid, data):
    with current_session as session:
        r = session.query(StatusRecord).filter_by(uuid=str(uuid))
        if r.count():
            status_record = r.one()
            status_record.timestamp = datetime.datetime.now()
            status_record.data = data
        else:
            status_record = StatusRecord(
                uuid=str(uuid),
                timestamp=datetime.datetime.now(),
                data=data
            )
            session.add(status_record)
        session.commit()


def force_failed_status(uuid):
    with current_session as session:
        r = session.query(StatusRecord).filter_by(uuid=str(uuid))
        if r.count() < 1:
            return
        status_record = r.one()
        data = status_record.data
        data['status'] = {
            "status": "failed",
            "time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime()),
            "message": "Process has crashed"
        }
        status_record.timestamp = datetime.datetime.now()
        status_record.data = data
        session.commit()


# Get store instance data from uuid
def get_status_record(uuid):
    with current_session as session:
        if sys.platform == "linux":
            # Check if the current process is fail
            r = session.query(ProcessInstance).filter_by(uuid=str(uuid))
            # If no process instance is found then there is no status records
            if r.count() < 1:
                return None
            process_record = r.one()
            if process_record.status not in {WPS_STATUS.FAILED, WPS_STATUS.SUCCEEDED}:
                if not os.path.exists(os.path.join("/proc", str(process_record.pid))):
                    store_status(process_record.uuid, WPS_STATUS.FAILED, "Process crashed", 100)
                    force_failed_status(process_record.uuid)

        r = session.query(StatusRecord).filter_by(uuid=str(uuid))
        if r.count() < 1:
            return None
        status_record = r.one()
        # Ensure new item to avoid change in database
        # FIXME: There is a better solution ?
        attrs = ["uuid", "timestamp", "data"]
        status_record = SimpleNamespace(**{k: getattr(status_record, k) for k in attrs})
        status_record.data = status_record.data
        return status_record


def update_pid(uuid, pid):
    """Update actual pid for the uuid processing
    """
    with current_session as session:
        requests = session.query(ProcessInstance).filter_by(uuid=str(uuid))
        if requests.count():
            request = requests.one()
            request.pid = pid
            session.commit()


def cleanup_crashed_process():
    # TODO: implement other platform
    if sys.platform != "linux":
        return

    with current_session as session:
        stored_query = session.query(RequestInstance.uuid)
        running_cur = (
            session.query(ProcessInstance)
            .filter(ProcessInstance.status.in_([WPS_STATUS.STARTED, WPS_STATUS.PAUSED]))
            .filter(~ProcessInstance.uuid.in_(stored_query))
        )

        failed = []
        running = [(p.uuid, p.pid) for p in running_cur]
        for uuid, pid in running:
            # No process with this pid, the process has crashed
            if not os.path.exists(os.path.join("/proc", str(pid))):
                failed.append(uuid)
                continue

            # If we can't read the environ, that mean the process belong another user
            # which mean that this is not our process, thus our process has crashed
            # this not work because root is the user for the apache
            # if not os.access(os.path.join("/proc", str(pid), "environ"), os.R_OK):
            #     failed.append(uuid)
            #     continue
            pass

        for uuid in failed:
            store_status(uuid, WPS_STATUS.FAILED, "Process crashed", 100)


def _get_identifier(request):
    """Get operation identifier
    """

    if request.operation == 'execute':
        return request.identifier
    elif request.operation == 'describeprocess':
        if request.identifiers:
            return ','.join(request.identifiers)
        else:
            return None
    else:
        return None


def get_session():
    """Get Connection for database
    """
    LOGGER.debug('Initializing database connection')
    global _SESSION_MAKER, _SESSION_MAKER_DATABASE

    database = configuration.get_config_value('logging', 'database')

    # Check if database has changed, and clear session maker if needed
    if _SESSION_MAKER_DATABASE != database:
        _SESSION_MAKER_DATABASE = None
        _SESSION_MAKER = None

    if _SESSION_MAKER:
        return _SESSION_MAKER()

    with lock:
        echo = True
        level = configuration.get_config_value('logging', 'level')
        level_name = logging.getLevelName(level)
        if isinstance(level_name, int) and level_name >= logging.INFO:
            echo = False
        try:
            if ":memory:" in database:
                engine = sqlalchemy.create_engine(database,
                                                  echo=echo,
                                                  connect_args={'check_same_thread': False},
                                                  poolclass=StaticPool)
            elif database.startswith("sqlite"):
                engine = sqlalchemy.create_engine(database,
                                                  echo=echo,
                                                  connect_args={'check_same_thread': False},
                                                  poolclass=NullPool)
            else:
                engine = sqlalchemy.create_engine(database, echo=echo, poolclass=NullPool)
        except sqlalchemy.exc.SQLAlchemyError as e:
            raise NoApplicableCode("Could not connect to database: {}".format(e.message))

        Session = sessionmaker(bind=engine)
        ProcessInstance.metadata.create_all(engine)
        RequestInstance.metadata.create_all(engine)
        StatusRecord.metadata.create_all(engine)
        FileStorageRecord.metadata.create_all(engine)

        _SESSION_MAKER_DATABASE = database
        _SESSION_MAKER = Session

    return _SESSION_MAKER()


def store_process(uuid, request):
    """Save given request under given UUID for later usage
    """

    with current_session as session:
        request_json = request.json
        # the BLOB type requires bytes on Python 3
        request_json = request_json.encode('utf-8')
        request = RequestInstance(uuid=str(uuid), request=request_json)
        session.add(request)
        session.commit()
