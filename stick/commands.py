import os
import click
from twine.package import PackageFile
from .settings import Settings


@click.group()
def cli():
    pass


@cli.command(context_settings={'ignore_unknown_options': True})
@click.option('--bucket', required=True)
@click.option('--prefix')
@click.option('--profile')
@click.option('--skip-existing/--no-skip-existing', default=True)
@click.option('--sign/--no-sign', default=False)
@click.option('--sign-with')
@click.option('--identity')
@click.argument('dist', nargs=-1, type=click.Path(exists=True, dir_okay=False, allow_dash=False))
def upload(dist, **kwargs):
    upload_settings = Settings(**kwargs)
    signatures = dict((os.path.basename(d), d) for d in dist if d.endswith('.asc'))
    uploads = [d for d in dist if not d.endswith('.asc')]
    repository = upload_settings.create_repository()

    click.echo('Uploading distributions to {0}'.format(repository.get_url()))

    for filename in uploads:
        package = PackageFile.from_filename(filename, '')
        skip_message = 'Skipping {0} because it appears to already exist'.format(package.basefilename)

        if upload_settings.skip_existing and repository.package_is_uploaded(package):
            click.echo(skip_message)
            continue

        signed_name = package.signed_basefilename
        if signed_name in signatures:
            package.add_gpg_signature(signatures[signed_name], signed_name)
        elif upload_settings.sign:
            package.sign(upload_settings.sign_with, upload_settings.identity)

        repository.upload(package)


if __name__ == '__main__':
    cli()
