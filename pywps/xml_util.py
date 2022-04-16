import base64

from lxml import etree as _etree
import re
from io import BytesIO

PARSER = _etree.XMLParser(
    resolve_entities=False,
)

tostring = _etree.tostring


def fromstring(text):
    return _etree.fromstring(text, parser=PARSER)


def parse(source):
    return _etree.parse(source, parser=PARSER)


def escape_for_xml(s):
    # order matter
    s = re.sub("&", "&amp;", s)
    s = re.sub(">", "&gt;", s)
    s = re.sub("<", "&lt;", s)
    return s


def unescape_from_xml(s):
    # order matter
    s = re.sub("&lt;", "<", s)
    s = re.sub("&gt;", ">", s)
    s = re.sub("&amp;", "&", s)
    return s


def cleanup_xml_string_for_xml(s, encoding):
    data_doc = _etree.parse(BytesIO(s.encode(encoding or "utf-8")))
    return _etree.tostring(data_doc, pretty_print=True).decode('utf-8')
