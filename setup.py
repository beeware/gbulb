#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name='gbulb',
    version='0.6.0',
    description='GLib event loop for tulip (PEP 3156)',
    author='Nathan Hoad',
    author_email='nathan@getoffmalawn.com',
    license='Apache 2.0',
    url='http://github.com/nathan-hoad/gbulb',
    packages=['gbulb'],
    long_description="""Gbulb is a python library that implements a PEP 3156 interface for the GLib main event loop. It is designed to be used together with the tulip reference implementation.""",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires='>3.5'
)
