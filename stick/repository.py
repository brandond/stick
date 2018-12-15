import boto3
import json
import io
import os
import logging

from botocore.exceptions import ClientError
from twine.package import PackageFile
from backports import tempfile
from .project import Project

logger = logging.getLogger(__name__)


class Repository(object):
    def __init__(self, bucket, prefix, profile):
        self.bucket = bucket
        self.prefix = prefix
        self.client = boto3.Session(profile_name=profile).client('s3')
        self._project_cache = {}

        if not self.prefix.endswith('/'):
            self.prefix += '/'

    def get_url(self):
        url = 'https://{0}.s3.amazonaws.com/{1}'.format(self.bucket, self.prefix)
        return url

    def reindex(self, projects):
        """Rebuild html index and json metadata for projects in the repository"""
        if not projects:
            projects = self._update_repository_index()

        for safe_name in projects:
            try:
                project = Project(safe_name, self)
                for package, metadata in self._get_packages(safe_name):
                    version = package.metadata.version
                    project.add_package(package, metadata['LastModified'])
                    self._put_json(safe_name, project, version)
                    self._put_release(safe_name, project, version)
                    os.unlink(package.filename)
                self._put_manifest(safe_name, project)
                self._put_json(safe_name, project)
                self._put_index(safe_name, project)
            except Exception:
                logger.error('Failed to reindex {}'.format(safe_name), exc_info=True)

    def update_index(self):
        """Update the top-level project index"""
        self._update_repository_index()

    def upload(self, package):
        """Upload a single package"""
        safe_name = package.safe_name
        version = package.metadata.version
        project = self._get_project(safe_name)

        project.add_package(package)

        self._put_package(safe_name, package)
        self._put_manifest(safe_name, project)
        self._put_json(safe_name, project, version)
        self._put_json(safe_name, project)
        self._put_release(safe_name, project, version)
        self._put_index(safe_name, project)

    def package_is_uploaded(self, package, bypass_cache=False):
        """Test to see if a given package has already been uploaded"""
        safe_name = package.safe_name
        project = self._get_project(safe_name, bypass_cache)

        for package_info in project.get_manifest():
            if package_info['filename'] == package.basefilename:
                return True

        return False

    def _get_project(self, safe_name, bypass_cache=False):
        project = None
        if not bypass_cache:
            project = self._project_cache.get(safe_name)

        if project is None:
            try:
                manifest = self._get_manifest(safe_name)
                project = Project(safe_name, self, manifest)
            except ClientError as e:
                if e.response['Error']['Code'] in ['403', '404']:
                    logger.debug('No existing manifest for {0}'.format(safe_name))
                else:
                    logger.error('Failed to download manifest for {0}'.format(safe_name), exc_info=True)
                project = Project(safe_name, self)

            self._project_cache[safe_name] = project

        return project

    def _get_manifest(self, safe_name):
        json_key = '{0}{1}/manifest.json'.format(self.prefix, safe_name)
        logger.info('Downloading {0}'.format(json_key))
        with io.BytesIO() as data:
            self.client.download_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key)
            data.seek(0, 0)
            return json.load(io.TextIOWrapper(data))

    def _put_manifest(self, safe_name, project):
        json_key = '{0}{1}/manifest.json'.format(self.prefix, safe_name)
        logger.info('Uploading {0}'.format(json_key))
        with io.BytesIO() as data:
            json.dump(project.get_manifest(), data)
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key, ExtraArgs={'ContentType': 'application/json'})

    def _put_json(self, safe_name, project, version=None):
        version_prefix = '' if version is None else '/{0}'.format(version)
        json_key = '{0}{1}{2}/json'.format(self.prefix, safe_name, version_prefix)
        logger.info('Uploading {0}'.format(json_key))
        with io.BytesIO() as data:
            json.dump(project.get_metadata(version), data)
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key, ExtraArgs={'ContentType': 'application/json'})

    def _put_index(self, safe_name, project):
        index_key = '{0}{1}/'.format(self.prefix, safe_name)
        releases = project.get_releases()
        logger.info('Uploading {0}'.format(index_key))
        with io.BytesIO() as data:
            data.write('<!DOCTYPE html><html><head><title>Links for {0}</title></head><body>'.format(safe_name).encode())
            data.write('<h1>Links for {0}</h1>'.format(safe_name).encode())
            for version in sorted(releases.keys()):
                for uploaded_package in releases[version]:
                    uploaded_package['has_sig'] = str(uploaded_package['has_sig']).lower()
                    if uploaded_package['requires_python'] is None:
                        uploaded_package['requires_python'] = ''
                    data.write('<a href="{url}#sha256={digests[sha256]}" data-gpg-sig="{has_sig}" data-requires-python="{requires_python}">{filename}</a><br>'.format(
                        **uploaded_package).encode())
            data.write(b'</body></html>')
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=index_key, ExtraArgs={'ContentType': 'text/html'})

    def _put_release(self, safe_name, project, version):
        release_key = '{0}{1}/{2}/'.format(self.prefix, safe_name, version)
        project_info = project.get_info(version)
        logger.info('Uploading {0}'.format(release_key))
        with io.BytesIO() as data:
            data.write('<!DOCTYPE html><html><head><title>{0}</title></head><body>'.format(safe_name).encode())
            data.write('<h1>{0}=={1}</h1>'.format(safe_name, version).encode())
            for key in ['summary', 'author', 'author_email', 'requires_python']:
                data.write('<b>{0}:</b> {1}<br>'.format(key, project_info[key]).encode())
            data.write(b'<br>')
            for url in project.get_urls(version):
                url['has_sig'] = str(url['has_sig']).lower()
                if url['requires_python'] is None:
                    url['requires_python'] = ''
                data.write('<a href="{url}#sha256={digests[sha256]}" data-gpg-sig="{has_sig}" data-requires-python="{requires_python}">{filename}</a><br>'.format(
                    **url).encode())
            data.write(b'</body></html>')
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=release_key, ExtraArgs={'ContentType': 'text/html'})

    def _put_package(self, safe_name, package):
        package_key = '{0}{1}/{2}'.format(self.prefix, safe_name, package.basefilename)
        logger.info('Uploading {0}'.format(package_key))
        with open(package.filename, 'rb') as data:
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=package_key, ExtraArgs={'ContentType': 'application/octet-stream'})

    def _update_repository_index(self):
        projects = []
        logger.info('Looking for projects in {}'.format(self.prefix))
        for page in self.client.get_paginator('list_objects').paginate(Bucket=self.bucket, Prefix=self.prefix, Delimiter='/'):
            projects += [p['Prefix'][len(self.prefix):-1] for p in page.get('CommonPrefixes', [])]

        logger.info('Uploading {0}'.format(self.prefix))
        with io.BytesIO() as data:
            data.write(b'<!DOCTYPE html><html><head><title>Simple Index</title></head><body>')
            for project in projects:
                data.write('<a href="{0}{1}/">{1}</a><br>'.format(self.get_url(), project).encode())
            data.write(b'</body></html>')
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=self.prefix, ExtraArgs={'ContentType': 'text/html'})

        return projects

    def _get_packages(self, safe_name):
        prefix = '{0}{1}/'.format(self.prefix, safe_name)
        logger.info('Looking for packages in {}'.format(prefix))
        with tempfile.TemporaryDirectory() as temp_dir:
            for page in self.client.get_paginator('list_objects').paginate(Bucket=self.bucket, Prefix=prefix, Delimiter='/'):
                for item in page.get('Contents', []):
                    key = item['Key'].replace(prefix, '', 1)
                    if not (key == '' or key.endswith('json') or key.endswith('.asc')):
                        try:
                            filename = os.path.join(temp_dir, key)
                            logger.info('Downloading {0}'.format(item['Key']))
                            self.client.download_file(Bucket=self.bucket, Key=item['Key'], Filename=filename)
                            try:
                                self.client.head_object(Bucket=self.bucket, Key=item['Key'] + '.asc')
                                logger.info('Downloading {0} (signature)'.format(Key=item['Key'] + '.asc'))
                                self.client.download_file(Bucket=self.bucket, Key=item['Key'] + '.asc', Filename=filename + '.asc')
                            except ClientError as e:
                                if e.response['Error']['Code'] in ['403', '404']:
                                    logger.debug('No GPG signature for {0}'.format(item['Key']))
                                else:
                                    raise e
                            yield (PackageFile.from_filename(filename, ''), item)
                        except ClientError:
                            logger.error('Failed to download {0}'.format(item['Key']), exc_info=True)
