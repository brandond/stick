import boto3
import json
import io

from .project import Project


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

    def reindex(self):
        """Rebuild html index and json metadata for all projects in the repository"""
        raise NotImplementedError()

    def upload(self, package):
        """Upload a single package"""
        safe_name = package.safe_name
        project = self._get_project(safe_name)

        project.add_package(package)

        # TODO: Handle these as three multipart uploads that are completed when all parts have been successfully sent
        self._put_package(safe_name, package)
        self._put_manifest(safe_name, project.get_manifest())
        self._put_json(safe_name, project.get_metadata(package.version), package.version)
        self._put_json(safe_name, project.get_metadata())
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
            except Exception:
                project = Project(safe_name, self)

            self._project_cache[safe_name] = project

        return project

    def _get_manifest(self, safe_name):
        json_key = '{0}{1}/manifest.json'.format(self.prefix, safe_name)
        with io.BytesIO() as data:
            self.client.download_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key)
            data.seek(0, 0)
            return json.load(io.TextIOWrapper(data))

    def _put_manifest(self, safe_name, manifest):
        json_key = '{0}{1}/manifest.json'.format(self.prefix, safe_name)
        with io.BytesIO() as data:
            json.dump(manifest, io.TextIOWrapper(data))
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key, ExtraArgs={'ContentType': 'application/json'})

    def _put_json(self, project_metadata, safe_name, version=None):
        version = '' if version else '/{0}'.format(version)
        json_key = '{0}{1}{2}/json'.format(self.prefix, safe_name, version)
        with io.BytesIO() as data:
            json.dump(project_metadata, io.TextIOWrapper(data))
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=json_key, ExtraArgs={'ContentType': 'application/json'})

    def _put_index(self, safe_name, project):
        index_key = '{0}{1}/'.format(self.prefix, safe_name)
        with io.BytesIO as data:
            data.write('<!DOCTYPE html><html><head><title>Links for {0}</title></head><body>'.format(safe_name).encode())
            data.write('<h1>Links for {0}</h1>'.format(safe_name).encode())
            for version, packages in project.releases.items():
                for uploaded_package in packages:
                    data.write('<a href="{0}">{0}</a><br>'.format(uploaded_package['filename']).encode())
            data.write(b'</body></html>')
            data.seek(0, 0)
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=index_key, ExtraArgs={'ContentType': 'text/html'})

    def _put_package(self, safe_name, package):
        package_key = '{0}{1}/{2}'.format(self.prefix, safe_name, package.basefilename)
        with open(package.filename, 'rb') as data:
            self.client.upload_fileobj(Fileobj=data, Bucket=self.bucket, Key=package_key, ExtraArgs={'ContentType': 'application/octet-stream'})
