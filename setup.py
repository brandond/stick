# -*- coding: utf-8 -*-
from os import chdir
from os.path import abspath, dirname

from setuptools import find_packages, setup

chdir(dirname(abspath(__file__)))

version = {}

with open('README.rst') as f:
    readme = f.read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    author='Brandon Davidson',
    author_email='brad@oatmail.org',
    classifiers=[
        'Development Status :: 4 - Beta',
        "Intended Audience :: Developers",
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Topic :: System :: Archiving :: Packaging',
    ],
    description="Collection of utilities for publishing Python packages to PyPI-compatible indexes hosted on S3.",
    entry_points={
        'console_scripts': ['stick=stick.commands:cli']
    },
    extras_require={
        'dev': [
            'setuptools-version-command',
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    long_description=readme,
    name='stick',
    packages=find_packages(exclude=('docs')),
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*",
    url='https://github.com/brandond/stick',
    version_command=('git describe --tags --dirty', 'pep440-git-full'),
)
