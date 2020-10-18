#!/usr/bin/env python

#from distutils.core import setup
from setuptools import setup

packge_name = "mpgameserver"
description = "Python Multiplayer Game Server"
long_description = """A Python 3.8+ UDP Client and Server for building multiplayer games with a focus on security and ease of use."""

# https://pypi.org/classifiers/
classifiers = [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Operating System :: MacOS :: MacOS X',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: POSIX',
    'License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)',
    'Programming Language :: Python :: 3.8',

]

keywords = ['PYGAME', 'MULTIPLAYER', 'UDP', 'SERVER']

# copied from requirements.txt
install_requires=[
  'cryptography>=3.0',
  'pygame>=2.0.0.dev10',
  'pillow>=7.2.0',
  'twisted>=20.3.0',
]

version = "0.1.1"
url = 'https://github.com/nsetzer/mpgameserver'
download_url = "%s/archive/%s.tar.gz" % (url, version)

entry_points = {
  "console_scripts": [
    "mpcli=mpgameserver.__main__:main",
  ]
}
setup(name=packge_name,
      version=version,
      description=description,
      author='Nick Setzer',
      author_email='nsetzer@users.noreply.github.com',
      url=url,
      download_url=download_url,
      packages=[packge_name],
      long_description=long_description,
      keywords=keywords,
      classifiers=classifiers,
      install_requires=install_requires,
      entry_points=entry_points
     )