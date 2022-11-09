##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

import unittest
from pywps import Service
from pywps import get_ElementMakerForVersion
from pywps.tests import client_for, assert_response_accepted, assert_response_success

from pywps import configuration
from .processes import Greeter
from urllib.parse import urlparse

from time import sleep

VERSION = "1.0.0"

WPS, OWS = get_ElementMakerForVersion(VERSION)


class ExecuteTest(unittest.TestCase):

    def setUp(self) -> None:
        # Use fake async processing for this test
        self.process_mode = configuration.get_config_value('processing', 'mode')
        configuration.CONFIG.set('processing', 'mode', 'noasyncprocessing')

    def tearDown(self) -> None:
        # Restore default processing mode
        configuration.CONFIG.set('processing', 'mode', self.process_mode)

    def test_wps_status(self):
        client = client_for(Service(processes=[Greeter()]))
        request_doc = WPS.Execute(
            OWS.Identifier('greeter'),
            WPS.DataInputs(
                WPS.Input(
                    OWS.Identifier('name'),
                    WPS.Data(
                        WPS.LiteralData(
                            "SomeName"
                        )
                    )
                )
            ),
            WPS.ResponseForm(
              WPS.ResponseDocument(storeExecuteResponse='true', status='true')
            ),
            version="1.0.0"
        )
        resp = client.post_xml(doc=request_doc)
        assert_response_accepted(resp)

        url = resp.xml.xpath("//@statusLocation")[0]

        # Parse url because we do not have real server
        url = urlparse(url)
        resp = client.get(f'{url.path}?{url.query}')
        assert_response_success(resp)

