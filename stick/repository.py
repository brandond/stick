import boto3
import json
import io
import os
import logging

from botocore.exceptions import ClientError
from twine.package import PackageFile
from twine.exceptions import InvalidDistribution
from backports import tempfile
from .project import Project
from .j2 import environ
from .util import client_config

logger = logging.getLogger(__name__)


class Repository(object):
    def __init__(self, bucket, prefix, profile):
        self.bucket = bucket
        self.prefix = prefix
        self.client = boto3.Session(profile_name=profile).client('s3', config=client_config)
        self._project_cache = {}

        if not self.prefix.endswith('/'):
            self.prefix += '/'

    def get_url(self):
        url = 'https://{0}.s3.amazonaws.com/{1}'.format(self.bucket, self.prefix)
        return url

    def reindex(self, projects):
        """Rebuild html index and json metadata for projects in the repository"""
        all_projects = self._get_projects()
        if not projects:
            projects = all_projects[:]

        for safe_name in projects:
            try:
                project = Project(safe_name, self)
                for package, metadata in self._get_packages(safe_name):
                    try:
                        version = package.metadata.version
                        project.add_package(package, metadata['LastModified'])
                        self._put_json(safe_name, project, version)
                        self._put_release(safe_name, project, version)
                    except Exception:
                        logger.error('Failed to add package {0}'.format(package.basefilename), exc_info=True)

                if len(project.manifest):
                    self._project_cache[safe_name] = project
                    self._put_manifest(safe_name, project)
                    self._put_json(safe_name, project)
                    self._put_index(safe_name, project)
                else:
                    try:
                        all_projects.remove(safe_name)
                    except ValueError:
                        logger.warn('Project {0} not found'.format(safe_name))
            except Exception:
                logger.error('Failed to reindex {}'.format(safe_name), exc_info=True)

        self._update_repository_index(all_projects)

    def upload(self, package):
        """Upload a single package"""
        safe_name = package.safe_name
        version = package.metadata.version
        project = self._get_project(safe_name)

        project.add_package(package)

        self._put_package(safe_name, package)
        self._put_manifest(safe_name, project)
        self._put_json(safe_name, project, version)
        self._put_release(safe_name, project, version)
        self._put_json(safe_name, project)
        self._put_index(safe_name, project)

    def package_is_uploaded(self, package, bypass_cache=False):
        """Test to see if a given package has already been uploaded"""
        safe_name = package.safe_name
        project = self._get_project(safe_name, bypass_cache)

        for package_info in project.get_manifest():
            if package_info['filename'] == package.basefilename:
                return True

        return False

    def update_index(self):
        """Update the top-level project index"""
        projects = self._get_projects()
        for safe_name in projects[:]:
            if safe_name not in self._project_cache and not self._head_manifest(safe_name):
                projects.remove(safe_name)
        self._update_repository_index(projects)

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

    def _head_manifest(self, safe_name):
        """See if a manifest exists for this project"""
        json_key = '{0}{1}/manifest.json'.format(self.prefix, safe_name)
        logger.info('Checking {0}'.format(json_key))
        try:
            return self.client.head_object(Bucket=self.bucket, Key=json_key)
        except ClientError as e:
            if e.response['Error']['Code'] in ['403', '404']:
                return None
            else:
                raise e

    def _get_manifest(self, safe_name):
        """Download and load the project manifest JSON"""
        json_key = '{0}{1}/manifest.json'.format(self.prefix, safe_name)
        logger.info('Downloading {0}'.format(json_key))
        with io.BytesIO() as data:
            self.client.download_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key)
            data.seek(0, 0)
            return json.load(io.TextIOWrapper(data))

    def _put_manifest(self, safe_name, project):
        """Dump and upload the project manifest JSON"""
        json_key = '{0}{1}/manifest.json'.format(self.prefix, safe_name)
        logger.info('Uploading {0}'.format(json_key))
        with io.BytesIO() as data:
            json.dump(project.get_manifest(), data)
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key, ExtraArgs={'ContentType': 'application/json; charset=utf-8'})

    def _put_json(self, safe_name, project, version=None):
        """Regenerate and upload the project or release-level index JSON"""
        version_prefix = '' if version is None else '/{0}'.format(version)
        json_key = '{0}{1}{2}/json'.format(self.prefix, safe_name, version_prefix)
        logger.info('Uploading {0}'.format(json_key))
        with io.BytesIO() as data:
            json.dump(project.get_metadata(version), data)
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key, ExtraArgs={'ContentType': 'application/json; charset=utf-8'})

    def _put_index(self, safe_name, project):
        """Regenerate and upload the project-level index HTML"""
        index_key = '{0}{1}/'.format(self.prefix, safe_name)
        logger.info('Uploading {0}'.format(index_key))
        template = environ.get_template('index.html.j2')
        with io.BytesIO() as data:
            data.write(template.render(project=project).encode())
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=index_key, ExtraArgs={'ContentType': 'text/html; charset=utf-8'})

    def _put_release(self, safe_name, project, version):
        """Regenerate and upload the release-level index HTML"""
        release_key = '{0}{1}/{2}/'.format(self.prefix, safe_name, version)
        logger.info('Uploading {0}'.format(release_key))
        template = environ.get_template('release.html.j2')
        with io.BytesIO() as data:
            data.write(template.render(project=project, version=version).encode())
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=release_key, ExtraArgs={'ContentType': 'text/html; charset=utf-8'})

    def _get_projects(self):
        projects = []
        logger.info('Looking for projects in {}'.format(self.prefix))
        for page in self.client.get_paginator('list_objects').paginate(Bucket=self.bucket, Prefix=self.prefix, Delimiter='/'):
            projects += [p['Prefix'][len(self.prefix):-1] for p in page.get('CommonPrefixes', [])]
        return projects

    def _update_repository_index(self, projects):
        """Regenerate and upload the repository-level index HTML"""
        logger.info('Uploading {0}'.format(self.prefix))
        template = environ.get_template('repository_index.html.j2')
        with io.BytesIO() as data:
            data.write(template.render(repository=self, projects=projects).encode())
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=self.prefix, ExtraArgs={'ContentType': 'text/html; charset=utf-8'})

    def _put_package(self, safe_name, package):
        """Upload a single package to S3"""
        package_key = '{0}{1}/{2}'.format(self.prefix, safe_name, package.basefilename)
        logger.info('Uploading {0}'.format(package_key))
        with open(package.filename, 'rb') as data:
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=package_key, ExtraArgs={'ContentType': 'application/octet-stream'})

    def _get_packages(self, safe_name):
        """Yield (PackageFile, metadata) for each package in the project"""
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
                            package = PackageFile.from_filename(filename, '')
                            yield (package, item)
                        except InvalidDistribution as e:
                            logger.warn('Skipping {0}: {1}'.format(item['Key'], e))
                        except ClientError:
                            logger.error('Failed to download {0}'.format(item['Key']), exc_info=True)
