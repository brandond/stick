from pkg_resources import get_distribution
from botocore.client import Config

pkgname = __name__.split('.')[0]
version = get_distribution(pkgname).version
client_config = Config(user_agent_extra='{0}/{1}'.format(pkgname, version))
