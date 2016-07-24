#!/usr/bin/env python
from setuptools import setup, find_packages
import filers

with open('README.rst') as fh:
    long_description = fh.read()

setup(
    name='Filers',
    version=filers.__version__,
    author='Matthew Einhorn',
    author_email='moiein2000@gmail.com',
    url='http://matham.github.io/filers/',
    license='MIT',
    description='Video recording software.',
    long_description=long_description,
    classifiers=['License :: OSI Approved :: MIT License',
                 'Topic :: Scientific/Engineering',
                 'Topic :: System :: Hardware',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 3.3',
                 'Programming Language :: Python :: 3.4',
                 'Programming Language :: Python :: 3.5',
                 'Operating System :: Microsoft :: Windows',
                 'Intended Audience :: Developers'],
    packages=find_packages(),
    install_requires=['pybarst', 'pyflycap2', 'ffpyplayer', 'cplcom', 'kivy',
                      'psutil', 'six'],
    package_data={'filers': ['data/*', '*.kv']},
    entry_points={'console_scripts': ['filers=filers.main:run_app']},
)
