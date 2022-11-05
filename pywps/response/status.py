from collections import namedtuple
from werkzeug.wrappers import Response
import json
from pywps.inout.array_encode import ArrayEncoder
from pywps.app.basic import get_json_indent
from jinja2 import Environment, PackageLoader
import os
from pywps.translations import get_translation
from pywps import dblog
from . import RelEnvironment
from pywps.exceptions import NoApplicableCode


_WPS_STATUS = namedtuple('WPSStatus', ['UNKNOWN', 'ACCEPTED', 'STARTED', 'PAUSED', 'SUCCEEDED', 'FAILED'])
WPS_STATUS = _WPS_STATUS(0, 1, 2, 3, 4, 5)


class StatusResponse(Response):
    """
    Load status from the database and render it.
    """
    def __init__(self, uuid, mimetype):

        status = dblog.get_status_record(uuid)
        if status is None:
            raise NoApplicableCode("Invalid uuid for status request", code=500)

        template_env = RelEnvironment(
            loader=PackageLoader('pywps', 'templates'),
            trim_blocks=True, lstrip_blocks=True,
            autoescape=True,
        )
        template_env.globals.update(get_translation=get_translation)

        print(status.data)

        if mimetype == 'application/json':
            doc = json.dumps(self._render_json_response(status.data), cls=ArrayEncoder, indent=get_json_indent())
        else:
            template = template_env.get_template(status.data["version"] + '/execute/main.xml')
            doc = template.render(**status.data)
        super(StatusResponse, self).__init__(response=doc, mimetype=mimetype)

    @staticmethod
    def _render_json_response(jdoc):
        response = dict()
        response['status'] = jdoc['status']
        out = jdoc['outputs']
        d = {}
        for val in out:
            id = val.get('identifier')
            if id is None:
                continue
            type = val.get('type')
            key = 'data' if type == 'bbox' else 'data'
            if key in val:
                d[id] = val[key]
        response['outputs'] = d
        return response
