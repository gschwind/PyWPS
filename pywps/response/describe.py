import json

from werkzeug.wrappers import Request
import pywps.configuration as config
from pywps.app.basic import make_response, select_response_mimetype, get_json_indent
from pywps.exceptions import NoApplicableCode
from pywps.exceptions import MissingParameterValue
from pywps.exceptions import InvalidParameterValue
from .basic import WPSResponse
from pywps import __version__
import os, sys
from pywps.translations import get_translation

from jinja2 import Environment, PackageLoader
from . import RelEnvironment
from werkzeug.wrappers import Response


class DescribeResponse(Response):

    def __init__(self, http_request, wps_request, service_processes: dict):

        # TODO: find better alternative
        self.template_env = RelEnvironment(
            loader=PackageLoader('pywps', 'templates'),
            trim_blocks=True, lstrip_blocks=True,
            autoescape=True,
        )
        self.template_env.globals.update(get_translation=get_translation)

        if not wps_request.identifiers:
            raise MissingParameterValue('Missing parameter value "identifier"', 'identifier')

        if "all" in wps_request.identifiers:
            processes = service_processes.values()
        else:
            processes = list()
            for i in wps_request.identifiers:
                if i in service_processes:
                    processes.append(service_processes[i])
                else:
                    raise InvalidParameterValue(f"Unknown process {i}")

        data = {
            'pywps_version': __version__,
            'processes': [p.json for p in processes],
            'language': wps_request.language
        }

        mimetype = select_response_mimetype(
            http_request.accept_mimetypes, wps_request.default_mimetype)
        if mimetype == 'application/json':
            doc = json.dumps(data, indent=get_json_indent())
        else:
            print(mimetype)
            template = self.template_env.get_template(wps_request.version + '/describe/main.xml')
            max_size = int(config.get_size_mb(config.get_config_value('server', 'maxsingleinputsize')))
            doc = template.render(max_size=max_size, **data)
        super(DescribeResponse, self).__init__(response=doc, mimetype=mimetype)
