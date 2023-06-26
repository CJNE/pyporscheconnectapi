#!/usr/bin/env python
from setuptools import setup


setup(
    name="pyporscheconnectapi",
    version="0.1.4",
    author="Johan Isaksson",
    author_email="johan@generatorhallen.se",
    description="Python library and CLI for communicating with Porsche Connect API.",
    long_description=open("README.md", 'r').read(),
    long_description_content_type='text/markdown',
    include_package_data=True,
    url="https://github.com/cjne/pyporscheconnectapi",
    license="MIT",
    packages=["pyporscheconnectapi"],
    python_requires=">=3.6",
    install_requires=["aiohttp<4","beautifulsoup4"],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Operating System :: OS Independent",
    ],
    setup_requires=("pytest-runner"),
    tests_require=(
        "asynctest",
        "pytest-cov",
        "pytest-asyncio",
        "pytest-trio",
        "pytest-tornasync",
    ),
)
