# -*- coding: utf-8 -*-

"""
Where is the setup.py documented *sensibly*, anyway?
"""

from setuptools import setup

setup(
    name="ytpod",
    version="0.3",
    py_modules=["ytpod"],
    install_requires=[
        "click >= 8.0",
        "feedgen",
        "feedparser >= 5.2.1",
        "beautifulsoup4",
        "requests[socks]",
        "mediafile",
        "arrow",
    ],
    extras_require={"binary": ["shiv"]},
    python_requires=">=3.8",
    entry_points={"console_scripts": ["ytpod=ytpod:run"]},
)
