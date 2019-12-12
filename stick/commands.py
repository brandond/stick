import logging
import os
import sys

import boto3
import click
from twine.package import PackageFile

from . import util
from .settings import Settings

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


def _print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    logger.info('{} {}'.format(util.pkgname, util.version))
    ctx.exit()


def _check_url(ctx, param, value):
    try:
        url = urlparse.urlparse(value)
    except ValueError:
        raise click.BadParameter('you must provide a valid URL')

    if not url.netloc:
        raise click.BadParameter('you must provide an absolute URL')

    if url.scheme not in ('http', 'https'):
        raise click.BadParameter('you must provide an HTTP or HTTPS URL')

    if not url.path.endswith('/'):
        url = url._replace(path=url.path + '/')
        click.echo(message='Trailing slash missing from baseurl; baseurl has been set to {}'.format(url.geturl()), err=True)

    return url.geturl()


def _check_prefix(ctx, param, value):
    if not value.endswith('/'):
        value += '/'
        click.echo(message='Trailing slash missing from prefix; prefix has been set to {}'.format(value))

    return value


def _check_profile(ctx, param, value):
    try:
        boto3.Session(profile_name=value).client('sts', config=util.client_config).get_caller_identity()
    except Exception as e:
        raise click.BadParameter('{}'.format(e), param_hint=param)

    return value


@click.group()
@click.option(
    '--version',
    is_flag=True,
    callback=_print_version,
    expose_value=False,
    is_eager=True,
    help='Show current tool version.'
)
def cli():
    pass


@cli.command(context_settings={'max_content_width': 120, 'ignore_unknown_options': True})
@click.option('--bucket', help='S3 Bucket hosting the repository.', required=True)
@click.option('--baseurl', help='Use an alternate base URL, instead of the S3 Bucket address.', default=None, callback=_check_url)
@click.option('--prefix', help='Prefix within the S3 Bucket that repository objects are stored.', default='simple', show_default=True, callback=_check_prefix)
@click.option('--profile', help='Use a specific profile from your credential file to access S3.', default=None)
@click.option('--skip-existing/--no-skip-existing', help='Skip uploading file if it already exists.', default=True, show_default=True)
@click.option('--sign/--no-sign', help='Sign files prior to upload using GPG.', default=False, show_default=True)
@click.option('--sign-with', help='GPG program used to sign uploads.', default='gpg', show_default=True)
@click.option('--identity', help='GPG identity used to sign uploads.')
@click.argument('dist', nargs=-1, type=click.Path(exists=True, dir_okay=False, allow_dash=False))
@click.pass_context
def upload(ctx, dist, **kwargs):
    """Upload one or more files to the repository."""
    _check_profile(ctx, 'profile', kwargs['profile'])
    upload_settings = Settings(**kwargs)
    repository = upload_settings.create_repository()
    signatures = dict((os.path.basename(d), d) for d in dist if d.endswith('.asc'))
    uploads = [d for d in dist if not d.endswith('.asc')]

    logger.info('Uploading distributions to {0}'.format(repository.get_url()))

    uploaded = 0
    for filename in uploads:
        package = PackageFile.from_filename(filename, '')
        skip_message = 'Skipping {0} because it appears to already exist'.format(package.basefilename)

        if upload_settings.skip_existing and repository.package_is_uploaded(package):
            logger.info(skip_message)
            continue

        signed_name = package.signed_basefilename
        if signed_name in signatures:
            package.add_gpg_signature(signatures[signed_name], signed_name)
        elif upload_settings.sign:
            package.sign(upload_settings.sign_with, upload_settings.identity)

        repository.upload(package)
        uploaded += 1

    if uploaded:
        repository.update_index()


@cli.command(context_settings={'max_content_width': 120})
@click.option('--bucket', help='S3 Bucket hosting the repository.', required=True)
@click.option('--baseurl', help='Use an alternate base URL, instead of the S3 Bucket address.', default=None, callback=_check_url)
@click.option('--prefix', help='Prefix within the S3 Bucket that repository objects are stored.', default='simple', show_default=True, callback=_check_prefix)
@click.option('--profile', help='Use a specific profile from your credential file to access S3.', default=None)
@click.option('--project', help='Reindex a specific project. May be specified multiple times.  [default: all projects]', default=None, multiple=True)
@click.pass_context
def reindex(ctx, project, **kwargs):
    """Reindex all packages within the repository, ignoring any existing metadata."""
    _check_profile(ctx, 'profile', kwargs['profile'])
    upload_settings = Settings(**kwargs)
    repository = upload_settings.create_repository()

    logger.info('Reindexing {0}'.format(repository.get_url()))

    repository.reindex(project)
    repository.update_index()


@cli.command(context_settings={'max_content_width': 120})
@click.option('--bucket', help='S3 Bucket hosting the repository.', required=True)
@click.option('--baseurl', help='Use an alternate base URL, instead of the S3 Bucket address.', default=None, callback=_check_url)
@click.option('--prefix', help='Prefix within the S3 Bucket that repository objects are stored.', default='simple', show_default=True, callback=_check_prefix)
@click.option('--profile', help='Use a specific profile from your credential file to access S3.', default=None)
@click.option('--project', help='Check a specific project. May be specified multiple times.  [default: all projects]', default=None, multiple=True)
@click.pass_context
def check(ctx, project, **kwargs):
    """Check for missing or changed packages."""
    _check_profile(ctx, 'profile', kwargs['profile'])
    upload_settings = Settings(**kwargs)
    repository = upload_settings.create_repository()

    logger.info('Checking {0}'.format(repository.get_url()))

    repository.check(project)


logging.basicConfig(level='INFO', format='%(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    cli()
