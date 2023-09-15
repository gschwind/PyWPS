##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

"""Unit tests for dblog
"""

import unittest

import sys
from pywps import configuration
from pywps.dblog import get_session
from pywps.dblog import ProcessInstance
from pywps.dblog import RequestInstance
from pywps import WPS_STATUS

# Define special cleanup, within the test environnement, because 
# fake request will not behave as real environnement request.
def cleanup_crashed_process():
    # TODO: implement other platform
    if sys.platform != "linux":
        return

    session = get_session()
    stored_query = session.query(RequestInstance.uuid)
    running_cur = (
        session.query(ProcessInstance)
        .filter(ProcessInstance.status.in_([WPS_STATUS.STARTED, WPS_STATUS.PAUSED]))
        .filter(~ProcessInstance.uuid.in_(stored_query))
    )

    failed = []
    running = [(p.uuid, p.pid) for p in running_cur]
    for uuid, pid in running:
        failed.append(uuid)

    for uuid in failed:
        store_status(uuid, WPS_STATUS.FAILED, "Process crashed", 100)

    session.close()

class DBLogTest(unittest.TestCase):
    """DBGLog test cases"""

    def setUp(self):

        self.database = configuration.get_config_value('logging', 'database')

    def test_0_dblog(self):
        """Test pywps.formats.Format class
        """
        session = get_session()
        self.assertTrue(session)

    def test_db_content(self):
        session = get_session()
        # Call cleanup, because we acces to database directly, that should
        # not happen in regular code.
        cleanup_crashed_process()

        null_time_end = session.query(ProcessInstance).filter(ProcessInstance.time_end == None)
        self.assertEqual(null_time_end.count(), 0,
                         'There are no unfinished processes loged')

        null_status = session.query(ProcessInstance).filter(ProcessInstance.status == None)
        self.assertEqual(null_status.count(), 0,
                         'There are no processes without status loged')

        null_percent = session.query(ProcessInstance).filter(ProcessInstance.percent_done == None)
        self.assertEqual(null_percent.count(), 0,
                         'There are no processes without percent loged')

        null_percent = session.query(ProcessInstance).filter(ProcessInstance.percent_done < 100)
        self.assertEqual(null_percent.count(), 0,
                         'There are no unfinished processes')

def load_tests(loader=None, tests=None, pattern=None):
    """Load local tests
    """
    if not loader:
        loader = unittest.TestLoader()
    suite_list = [
        loader.loadTestsFromTestCase(DBLogTest)
    ]
    return unittest.TestSuite(suite_list)
