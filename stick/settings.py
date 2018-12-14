from .repository import Repository


class Settings(object):
    def __init__(self, bucket, prefix, profile, skip_existing, sign, sign_with, identity):
        self.bucket = bucket
        self.prefix = prefix
        self.profile = profile
        self.skip_existing = skip_existing
        self.sign = sign
        self.sign_with = sign_with
        self.identity = identity

    def create_repository(self):
        repo = Repository(self.bucket, self.prefix, self.profile)
        return repo
