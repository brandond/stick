from .repository import Repository


class Settings(object):
    def __init__(self, bucket, baseurl, prefix, profile=None, skip_existing=True, sign=False, sign_with='gpg', identity=None):
        self.bucket = bucket
        self.baseurl = baseurl
        self.prefix = prefix
        self.profile = profile
        self.skip_existing = skip_existing
        self.sign = sign
        self.sign_with = sign_with
        self.identity = identity

    def create_repository(self):
        repo = Repository(self.bucket, self.baseurl, self.prefix, self.profile)
        return repo
