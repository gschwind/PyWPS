##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

"""
Implementation of logging for PyWPS-4
"""

import logging
import sys

from pywps import configuration
from pywps.exceptions import NoApplicableCode
import sqlite3
import datetime
import pickle
import json
import os
from multiprocessing import Lock
from filelock import FileLock

import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, VARCHAR, Float, DateTime, LargeBinary
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool


LOGGER = logging.getLogger('PYWPS')
_SESSION_MAKER = None

_tableprefix = configuration.get_config_value('logging', 'prefix')
_schema = configuration.get_config_value('logging', 'schema')

Base = declarative_base()

# Use custom lock scheme for the database because there is no unified database lock mechanism
_db_lock = None


class ProcessInstance(Base):
    __tablename__ = '{}requests'.format(_tableprefix)

    uuid = Column(VARCHAR(255), primary_key=True, nullable=False)
    pid = Column(Integer, nullable=False)
    operation = Column(VARCHAR(30), nullable=False)
    version = Column(VARCHAR(5), nullable=False)
    time_start = Column(DateTime(), nullable=False)
    time_end = Column(DateTime(), nullable=True)
    identifier = Column(VARCHAR(255), nullable=True)
    message = Column(String, nullable=True)
    percent_done = Column(Float, nullable=True)
    status = Column(Integer, nullable=True)


class RequestInstance(Base):
    __tablename__ = '{}stored_requests'.format(_tableprefix)

    uuid = Column(VARCHAR(255), primary_key=True, nullable=False)
    request = Column(LargeBinary, nullable=False)


def log_request(uuid, request):
    """Write OGC WPS request (only the necessary parts) to database logging
    system
    """

    pid = os.getpid()
    operation = request.operation
    version = request.version
    time_start = datetime.datetime.now()
    identifier = _get_identifier(request)

    session = get_session()
    request = ProcessInstance(
        uuid=str(uuid), pid=pid, operation=operation, version=version,
        time_start=time_start, identifier=identifier)

    session.add(request)
    session.commit()
    session.close()
    # NoApplicableCode("Could commit to database: {}".format(e.message))


def get_process_counts():
    """Returns running and stored process counts and
    """

    session = get_session()
    stored_query = session.query(RequestInstance.uuid)
    running_count = (
        session.query(ProcessInstance)
        .filter(ProcessInstance.percent_done < 100)
        .filter(ProcessInstance.percent_done > -1)
        .filter(~ProcessInstance.uuid.in_(stored_query))
        .count()
    )
    stored_count = stored_query.count()
    session.close()
    return running_count, stored_count


def pop_first_stored():
    """Gets the first stored process and delete it from the stored_requests table
    """
    session = get_session()

    with get_lock():
        request = session.query(RequestInstance).first()

        if request:
            delete_count = session.query(RequestInstance).filter_by(uuid=request.uuid).delete()
            if delete_count == 0:
                LOGGER.debug("Another thread or process took the same stored request")
                request = None

            session.commit()
        session.close()
    return request


def store_status(uuid, wps_status, message=None, status_percentage=None):
    """Writes response to database
    """
    session = get_session()

    requests = session.query(ProcessInstance).filter_by(uuid=str(uuid))
    if requests.count():
        request = requests.one()
        request.time_end = datetime.datetime.now()
        request.message = str(message)
        request.percent_done = status_percentage
        request.status = wps_status
        session.commit()
    session.close()


def update_pid(uuid, pid):
    """Update actual pid for the uuid processing
    """
    session = get_session()

    requests = session.query(ProcessInstance).filter_by(uuid=str(uuid))
    if requests.count():
        request = requests.one()
        request.pid = pid
        session.commit()
    session.close()


def cleanup_crashed_process():
    # TODO: implement other platform
    if sys.platform != "linux":
        return

    session = get_session()

    stored_query = session.query(RequestInstance.uuid)
    running_cur = (
        session.query(ProcessInstance)
        .filter(ProcessInstance.percent_done < 100)
        .filter(ProcessInstance.percent_done > -1)
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

    for uuid in failed:
        # Using WPS_STATUS.FAILED does not work because of recursive import
        store_status(uuid, 5, "Process crashed", 100)

    session.close()


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


def get_lock():
    global _db_lock
    if _db_lock is None:
        filelock_name = configuration.get_config_value('logging', 'database_filelock')
        if filelock_name == 'none':
            _db_lock = Lock()
        else:
            _db_lock = FileLock(filelock_name)
    return _db_lock


def get_session():
    """Get Connection for database
    """
    LOGGER.debug('Initializing database connection')
    global _SESSION_MAKER

    if _SESSION_MAKER:
        return _SESSION_MAKER()

    with get_lock():
        database = configuration.get_config_value('logging', 'database')
        echo = configuration.get_config_value('logging', 'database_echo') == 'true'
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

        _SESSION_MAKER = Session

    return _SESSION_MAKER()


def store_process(request):
    """Save given request under given UUID for later usage
    """

    session = get_session()
    request_json = request.json
    # the BLOB type requires bytes on Python 3
    request_json = request_json.encode('utf-8')
    request = RequestInstance(uuid=str(request.uuid), request=request_json)
    session.add(request)
    session.commit()
    session.close()
