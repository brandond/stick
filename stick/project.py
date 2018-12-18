from collections import OrderedDict, defaultdict
from datetime import datetime
from os.path import getsize

from packaging.version import parse

RELEASE_FIELDS = [
    'comment_text', 'digests', 'filename', 'has_sig', 'packagetype',
    'python_version', 'requires_python', 'size', 'upload_time']
INFO_FIELDS = [
    'author', 'author_email', 'classifiers', 'description',
    'description_content_type', 'home_page', 'keywords', 'license',
    'maintainer', 'maintainer_email', 'name', 'platform', 'project_urls',
    'requires_dist', 'requires_python', 'summary', 'version']
URL_FIELDS = [
    'comment_text', 'digests', 'filename', 'has_sig', 'md5_digest',
    'packagetype', 'python_version', 'requires_python', 'size', 'upload_time']


class Project(object):
    def __init__(self, safe_name, repository, manifest=[]):
        self.safe_name = safe_name
        self.repository = repository
        self.manifest = manifest
        self.releases = defaultdict(list)
        self._rebuild_releases()

    def get_manifest(self):
        return self.manifest

    def get_metadata(self, version=None):
        return OrderedDict([
            ('info', self.get_info(version)),
            ('last_serial', -1),
            ('releases', self.get_releases()),
            ('urls', self.get_urls(version)),
            ])

    def get_releases(self):
        return OrderedDict((str(v), [self._make_release(p) for p in self.releases[v]]) for v in sorted(self.releases.keys()))

    def get_info(self, version=None):
        version = parse(version) if version else max(self.releases.keys())
        return self._make_info(self.releases[version][0])

    def get_urls(self, version=None):
        version = parse(version) if version else max(self.releases.keys())
        return [self._make_url(p) for p in self.releases[version]]

    def add_package(self, package, upload_time=None, etag=None):
        if upload_time is None:
            upload_time = datetime.utcnow()
        package_info = {
            'author': package.metadata.author,
            'author_email': package.metadata.author_email,
            'classifiers': package.metadata.classifiers,
            'comment_text': package.comment,
            'description': package.metadata.description,
            'description_content_type': package.metadata.description_content_type,
            'digests': {
                'md5': package.md5_digest,
                'sha256': package.sha2_digest,
                },
            'etag': etag,
            'filename': package.basefilename,
            'has_sig': package.gpg_signature is not None,
            'home_page': package.metadata.home_page,
            'keywords': package.metadata.keywords,
            'license': package.metadata.license,
            'maintainer': package.metadata.maintainer,
            'maintainer_email': package.metadata.maintainer_email,
            'md5_digest': package.md5_digest,
            'name': package.metadata.name,
            'packagetype': package.filetype,
            'platform': package.metadata.platforms[0],
            'project_urls': package.metadata.project_urls,
            'python_version': package.python_version,
            'requires_dist': package.metadata.requires_dist,
            'requires_python': package.metadata.requires_python,
            'size': getsize(package.filename),
            'summary': package.metadata.summary,
            'upload_time': upload_time.strftime('%Y-%m-%dT%H:%m:%S'),
            'version': package.metadata.version,
             }

        self.manifest = [p for p in self.manifest if p['filename'] != package_info['filename']]
        self.manifest.append(package_info)
        self._rebuild_releases()

    def _rebuild_releases(self):
        self.releases.clear()
        for package_info in self.manifest:
            version = parse(package_info['version'])
            self.releases[version].append(package_info)

        for package_list in self.releases.values():
            package_list[:] = sorted(package_list, key=lambda p: (p['packagetype'], p['filename']))

    def _make_release(self, package_info):
        release = OrderedDict((k, package_info[k]) for k in RELEASE_FIELDS)
        release['downloads'] = -1
        release['url'] = self._get_package_url(package_info)
        return release

    def _make_info(self, package_info):
        info = OrderedDict((k, '' if package_info[k] is None else package_info[k]) for k in INFO_FIELDS)
        info['bugtrack_url'] = None
        info['docs_url'] = None
        info['downloads'] = {'last_day': -1, 'last_month': -1, 'last_week': -1}
        info['package_url'] = self._get_package_url(package_info, None)
        info['platform'] = '' if info['platform'] == 'UNKNOWN' else info['platform']
        info['project_url'] = info['package_url']
        info['project_urls'] = {'Homepage': info['home_page']} if not info['project_urls'] else dict(info['project_urls'])
        info['release_url'] = self._get_package_url(package_info, 'version', '/')
        return info

    def _make_url(self, package_info):
        url = OrderedDict((k, package_info[k]) for k in URL_FIELDS)
        url['md5_digest'] = package_info['digests']['md5']
        url['url'] = self._get_package_url(package_info)
        return url

    def _get_package_url(self, package_info, key='filename', term=''):
        url = '{0}{1}/'.format(self.repository.get_url(), self.safe_name)
        if key in package_info:
            url += '{0}{1}'.format(package_info[key], term)
        return url.replace('+', '%2B')
