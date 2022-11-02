##################################################################
# Copyright 2018 Open Source Geospatial Foundation and others    #
# licensed under MIT, Please consult LICENSE.txt for details     #
##################################################################

"""Test process
"""

import unittest

from pywps import Process
from pywps.app.Common import Metadata
from pywps.inout import LiteralInput
from pywps.inout import BoundingBoxInput
from pywps.inout import ComplexInput
from pywps.inout import FORMATS
from pywps.translations import get_translation


class DoNothing(Process):
    def __init__(self):
        super(DoNothing, self).__init__(
            self.donothing,
            "process",
            title="Process",
            abstract="Process description",
            inputs=[LiteralInput("length", title="Length"),
                    BoundingBoxInput("bbox", title="BBox", crss=[]),
                    ComplexInput("vector", title="Vector", supported_formats=[FORMATS.GML])],
            outputs=[],
            metadata=[Metadata('process metadata 1', 'http://example.org/1'),
                      Metadata('process metadata 2', 'http://example.org/2')],
            translations={"fr-CA": {"title": "Processus", "abstract": "Une description"}}
        )

    @staticmethod
    def donothing(request, response):
        pass


class ProcessTestCase(unittest.TestCase):

    def setUp(self):
        self.process = DoNothing()

    def test_get_input_title(self):
        """Test returning the proper input title"""

        inputs = {
            input.identifier: input.title for input in self.process.inputs
        }
        self.assertEqual("Length", inputs['length'])
        self.assertEqual("BBox", inputs["bbox"])
        self.assertEqual("Vector", inputs["vector"])

    def test_get_translations(self):
        title_fr = get_translation(self.process, "title", "fr-CA")
        assert title_fr == "Processus"
        abstract_fr = get_translation(self.process, "abstract", "fr-CA")
        assert abstract_fr == "Une description"
        identifier = get_translation(self.process, "identifier", "fr-CA")
        assert identifier == self.process.identifier

    def test_json_export_for_decribe_template(self):
        # Check if json output has required attribute to apply decribe process template
        o = self.process.json

        self.assertTrue('identifier' in o)
        self.assertTrue('title' in o)
        self.assertTrue('abstract' in o)
        self.assertTrue('translations' in o)
        self.assertTrue('inputs' in o)
        self.assertTrue('outputs' in o)
        self.assertTrue('version' in o)
        self.assertTrue('store_supported' in o)
        self.assertTrue('status_supported' in o)

        self.assertIsInstance(o['inputs'], list)
        self.assertIsInstance(o['outputs'], list)


def load_tests(loader=None, tests=None, pattern=None):
    """Load local tests
    """
    if not loader:
        loader = unittest.TestLoader()
    suite_list = [
        loader.loadTestsFromTestCase(ProcessTestCase)
    ]
    return unittest.TestSuite(suite_list)
