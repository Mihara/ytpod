# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='ytpod',
    version='0.1',
    py_modules=['ytpod'],
    dependency_links=['https://github.com/kurtmckee/feedparser@5.2.1#egg=feedparser'],
    install_requires=[
        'click',
        'feedgen',
        'feedparser',
        'youtube-dl',
    ],
    entry_points='''
        [console_scripts]
        ytpod=ytpod:run
    ''',
)
