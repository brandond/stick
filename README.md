stick
=====
[![PyPI version](https://badge.fury.io/py/stick.svg)](https://badge.fury.io/py/stick)
[![Build Status](https://travis-ci.org/brandond/stick.svg?branch=master)](https://travis-ci.org/brandond/stick)

Stick is a utility for publishing Python packages to PyPI-compatible indexes hosted on S3. Stick your project in a bucket!

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

4. **Tell pip to use your S3 repository:**

    ```sh
    test -d $HOME/.pip/ || mkdir $HOME/.pip/
    cat <<EOF >> $HOME/.pip/pip.conf
    [global]
    extra-index-url =
        https://my-bucket-name.s3.amazonaws.com/simple/
    EOF
    ```

    - or -
    ```sh
    export PIP_EXTRA_INDEX_URL=https://my-bucket-name.s3.amazonaws.com/simple/
    ```

Usage
-----

Upload one or more packages to a repository:

```
Usage: stick upload [OPTIONS] [DIST]...

Positional Arguments:
  dist                  The distribution files to upload to the repository
                        (package index). Usually dist/* . May additionally
                        contain a .asc file to include an existing signature
                        with the file upload.

Options:
  --bucket TEXT         S3 Bucket hosting the repository  [required]
  --prefix TEXT         Prefix within the S3 Bucket that repository objects will be created  [default: simple]
  --profile TEXT        Use a specific profile from your credential file
  --skip-existing / --no-skip-existing
                        Continue uploading files if one already exists  [default: False]
  --sign / --no-sign    Sign files to upload using GPG  [default: False]
  --sign-with TEXT      GPG program used to sign uploads  [default: gpg]
  --identity TEXT       GPG identity used to sign files
  --help                Show this message and exit
```

Reindex the repository:

```
Usage: stick reindex [OPTIONS]

Options:
  --bucket TEXT         S3 Bucket hosting the repository  [required]
  --prefix TEXT         Prefix within the S3 Bucket that repository objects will be created  [default: simple]
  --profile TEXT        Use a specific profile from your credential file
  --help                Show this message and exit
```

