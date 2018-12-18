import os

import jinja2

from . import util

templates = os.path.join(os.path.dirname(__file__), 'templates')
loader = jinja2.FileSystemLoader(templates)
environ = jinja2.Environment(loader=loader)
environ.globals['util'] = util
