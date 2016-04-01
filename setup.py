#!/usr/bin/env python

from distutils.core import setup
import filers

setup(name='Filers',
      version=str(filers.__version__),
      description='Media tools',
      author='Matthew Einhorn',
      author_email='moiein2000@gmail.com',
      url='https://cpl.cornell.edu/',
      license='MIT',
      packages=['filers'])
