stick
=====
[![PyPI version](https://badge.fury.io/py/stick.svg)](https://badge.fury.io/py/stick)
[![Build Status](https://travis-ci.com/brandond/stick.svg?branch=master)](https://travis-ci.com/brandond/stick)

Stick is a utility for publishing Python packages to PyPI-compatible indexes hosted on S3.
Its syntax and functionality are inspired by [twine](https://pypi.org/project/twine/).

_Stick your package in a bucket!_

Getting Started
---------------

1. **Install stick:**

   ```sh
   pip install stick
   ```

2. **Build your package:**

    ```sh
    python my-package/setup.py sdist bdist_wheel
    ```

3. **Upload package artifacts to your S3 repository:**

    ```sh
    stick upload --bucket my-bucket-name --prefix simple my-package/dist/*
    ```

4. **Tell pip to use your S3 repository's index:**

    *configuration file:*
    ```sh
    test -d $HOME/.pip/ || mkdir $HOME/.pip/
    cat <<EOF >> $HOME/.pip/pip.conf
    [global]
    extra-index-url =
        https://my-bucket-name.s3.amazonaws.com/simple/
    EOF
    ```

    *environment variable:*
    ```sh
    export PIP_EXTRA_INDEX_URL=https://my-bucket-name.s3.amazonaws.com/simple/
    ```

    *command line option:*
    ```sh
    pip install my-package --extra-index-url=https://my-bucket-name.s3.amazonaws.com/simple/
    ```

Usage
-----

#### Upload

```
Usage: stick upload [OPTIONS] [DIST]...

  Upload one or more files to the repository.

Positional Arguments:
  dist                  The distribution files to upload to the repository (package index).
                        Usually dist/* . May additionally contain a .asc file to include an
                        existing signature with the file upload.

Options:
  --bucket TEXT       S3 Bucket hosting the repository.  [required]
  --baseurl TEXT      Use an alternate base URL, instead of the S3 Bucket address.
  --prefix TEXT       Prefix within the S3 Bucket that repository objects are stored.  [default: simple]
  --profile TEXT      Use a specific profile from your credential file to access S3.
  --skip-existing / --no-skip-existing
                      Skip uploading file if it already exists.  [default: True]
  --sign / --no-sign  Sign files prior to upload using GPG.  [default: False]
  --sign-with TEXT    GPG program used to sign uploads.  [default: gpg]
  --identity TEXT     GPG identity used to sign uploads.
  --help              Show this message and exit.
```

#### Check

```
Usage: stick check [OPTIONS]

  Check for missing or changed packages.

Options:
  --bucket TEXT   S3 Bucket hosting the repository.  [required]
  --baseurl TEXT  Use an alternate base URL, instead of the S3 Bucket address.
  --prefix TEXT   Prefix within the S3 Bucket that repository objects are stored.  [default: simple]
  --profile TEXT  Use a specific profile from your credential file to access S3.
  --project TEXT  Check a specific project. May be specified multiple times.  [default: all projects]
  --help          Show this message and exit.
```

#### Reindex

_**Note:** Reindexing is not normally necessary unless files have been manually added or removed from the bucket.
Reindexing will read all packages from the repository in order to extract packaging metadata._

```
Usage: stick reindex [OPTIONS]

  Reindex all packages within the repository, ignoring any existing metadata.

Options:
  --bucket TEXT   S3 Bucket hosting the repository.  [required]
  --baseurl TEXT  Use an alternate base URL, instead of the S3 Bucket address.
  --prefix TEXT   Prefix within the S3 Bucket that repository objects are stored.  [default: simple]
  --profile TEXT  Use a specific profile from your credential file to access S3.
  --project TEXT  Reindex a specific project. May be specified multiple times.  [default: all projects]
  --help          Show this message and exit.
```

Features
--------

The indexes created by Stick are intended to be compatible with both the [pypi-legacy PEP 503 API](https://www.python.org/dev/peps/pep-0503/),
as well as the new [Warehouse JSON APIs](https://warehouse.readthedocs.io/api-reference/json/).

**File Structure**

* `<prefix>/`  - PEP 503 Simple HTML-based project index for this repository
* `<prefix>/<project_name>/`  - PEP 503 Simple HTML-based package index for this project
* `<prefix>/<project_name>/json`  - Warehouse JSON metadata for the latest version of this project
* `<prefix>/<project_name>/manifest.json`  - Stick internal cache of package metadata
* `<prefix>/<project_name>/<version>/`  - PyPI legacy style project version info page
* `<prefix>/<project_name>/<version>/json`  - Warehouse JSON metadata for a specific version of this project
* `<prefix>/<project_name>/<project_name>-<version>.tar.gz`  - Package artifact (sdist)
* `<prefix>/<project_name>/<project_name>-<version>-py2.py3-none-any.whl`  - Package artifact (wheel)

**Package Manifest**

Stick maintains a flattened list of package metadata for each project in `manifest.json`. This manifest is used to rebuild the HTML index and
JSON metadata when a new package is added to the repository. If objects are manually added or removed from the bucket, you must reindex the
repository in order to reflect the changes.

**Project Manifest**

Stick does not maintain a top-level project list. Whenever a package is uploaded or the repository reindexed, Stick checks all prefixes under
the top-level prefix for a `manifest.json`. Any prefix containing such key is displayed in the project list.

**Base URL Override**

You may use the `--baseurl` option to specify an alternate base URL for links generated in the HTML indexes or JSON metadata. You can use this
with CloudFront, S3 Access Points, or S3 CNAME DNS aliases. Note: The URL should include a trailing slash.
