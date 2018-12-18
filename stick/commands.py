import logging
import os
import sys

import click
from twine.package import PackageFile

from . import util
from .settings import Settings


def _print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    logger.info('{} {}'.format(util.pkgname, util.version))
    ctx.exit()


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
@click.option('--prefix', help='Prefix within the S3 Bucket that repository objects are stored.', default='simple', show_default=True)
@click.option('--profile', help='Use a specific profile from your credential file to access S3.', default=None)
@click.option('--skip-existing/--no-skip-existing', help='Skip uploading file if it already exists.', default=True, show_default=True)
@click.option('--sign/--no-sign', help='Sign files prior to upload using GPG.', default=False, show_default=True)
@click.option('--sign-with', help='GPG program used to sign uploads.', default='gpg', show_default=True)
@click.option('--identity', help='GPG identity used to sign uploads.')
@click.argument('dist', nargs=-1, type=click.Path(exists=True, dir_okay=False, allow_dash=False))
def upload(dist, **kwargs):
    """Upload one or more files to the repository."""
    upload_settings = Settings(**kwargs)
    signatures = dict((os.path.basename(d), d) for d in dist if d.endswith('.asc'))
    uploads = [d for d in dist if not d.endswith('.asc')]
    repository = upload_settings.create_repository()

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
@click.option('--prefix', help='Prefix within the S3 Bucket that repository objects are stored.', default='simple', show_default=True)
@click.option('--profile', help='Use a specific profile from your credential file to access S3.', default=None)
@click.option('--project', help='Reindex a specific project. May be specified multiple times.  [default: all projects]', default=None, multiple=True)
def reindex(project, **kwargs):
    """Reindex all packages within the repository, ignoring any existing metadata."""
    upload_settings = Settings(**kwargs)
    repository = upload_settings.create_repository()

    logger.info('Reindexing {0}'.format(repository.get_url()))

    repository.reindex(project)
    repository.update_index()


@cli.command(context_settings={'max_content_width': 120})
@click.option('--bucket', help='S3 Bucket hosting the repository.', required=True)
@click.option('--prefix', help='Prefix within the S3 Bucket that repository objects are stored.', default='simple', show_default=True)
@click.option('--profile', help='Use a specific profile from your credential file to access S3.', default=None)
@click.option('--project', help='Check a specific project. May be specified multiple times.  [default: all projects]', default=None, multiple=True)
def check(project, **kwargs):
    """Check for missing or changed packages."""
    upload_settings = Settings(**kwargs)
    repository = upload_settings.create_repository()

    logger.info('Checking {0}'.format(repository.get_url()))

    repository.check(project)


logging.basicConfig(level='INFO', format='%(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    cli()
