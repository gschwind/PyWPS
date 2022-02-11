#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pywps

#from pywps.app.WPSResponse import STATUS
from pywps.exceptions import NoApplicableCode
import logging

LOG = logging.getLogger('PYWPS')

class Process(pywps.Process):
 """Main process class"""

 # Describe process
 def __init__(self):
  """Process initialization"""
  inputs = [
   pywps.LiteralInput(identifier = "param0", title = "Param0 title",
                      min_occurs = 1, max_occurs = 10, data_type = 'string'),
   pywps.LiteralInput(identifier = "param1", title = "Param1 title",
                      min_occurs = 1, max_occurs = 1, data_type = 'string'),
   pywps.LiteralInput(identifier = "param2", title = "Param2 title",
                      min_occurs = 1, max_occurs = 1, data_type = 'string'),
   pywps.LiteralInput(identifier = "param3", title = "Param3 title",
                      min_occurs = 0, max_occurs = 1, data_type = 'string'),
   pywps.LiteralInput(identifier = "param4", title = "Param4 title",
                      min_occurs = 1, max_occurs = 1, data_type = 'string')
  ]

  outputs = [
   pywps.ComplexOutput(identifier="result",
      title="Output buffer file", supported_formats=[
     pywps.Format("application/json")
    ])
  ]

  super().__init__(
   self._handler,
   identifier="dummy",
   version='1.0',
   title="Dummy title",
   store_supported="true",
   status_supported="true",
   inputs=inputs,
   outputs=outputs,
   abstract="Dummy abstrat")

 # Execute process
 def _handler(self, request, response):
  try:
   # read inputs from PyWPS
   p0 = request.inputs['param0'][0].data
   p1 = request.inputs['param1'][0].data
   p2 = request.inputs['param2'][0].data
   p3 = request.inputs['param3'][0].data
   out_file_mime = response.outputs['result'].data_format.mime_type
   LOG.debug(f"{self.identifier}: {p0}")
   LOG.debug(f"{self.identifier}: {p1}")
   LOG.debug(f"{self.identifier}: {p2}")
   LOG.debug(f"{self.identifier}: {p3}")
   LOG.debug(f"{self.identifier}: mimetype = %s", out_file_mime)
   LOG.debug(self.workdir)
   LOG.debug(response.outputs['result'].file)

   # note: the output file name is unique as the current folder is a tmp folder created by PyWPS.
   outfilename = os.path.join(self.workdir, "result.json")
   time.sleep(30)
   with open(outfilename, "w") as f:
    f.write("dummy data\n")
   if not os.path.exists(outfilename):
    raise Exception("Output file was not generated")
   response.outputs['result'].file = outfilename
  except:
   raise

import pywps.server
from pywps.app.Service import Service

processes = [ Process() ]

_service = Service(processes, ['pywps.cfg'])

server = pywps.server.WPSServer("127.0.0.1", 8080, _service)
server.serve_forever()

