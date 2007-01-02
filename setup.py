from setuptools import setup, find_packages
from byteplay import __version__ as lib_version

setup(
       name = 'byteplay',
       version = lib_version,
       py_modules = ['byteplay'],
       zip_safe = True,
)
