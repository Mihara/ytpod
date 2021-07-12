# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='ytpod',
    version='0.2',
    py_modules=['ytpod'],
    dependency_links=['https://github.com/kurtmckee/feedparser@5.2.1#egg=feedparser'],
    install_requires=[
        'click >= 8.0',
        'feedgen',
        'feedparser',
        'youtube-dl',
        'beautifulsoup4',
        'requests',
        'pyinstaller'
    ],
    python_requires='>=3.6',
    entry_points='''
        [console_scripts]
        ytpod=ytpod:run
    ''',
)
