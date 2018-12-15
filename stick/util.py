from pkg_resources import get_distribution

pkgname = __name__.split('.')[0]
version = get_distribution(pkgname).version
