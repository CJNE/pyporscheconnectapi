#!/usr/bin/env python
"""Python package description."""

from pathlib import Path

from setuptools import setup

setup(
    name="pyporscheconnectapi",
    version="0.2.2",
    author="Johan Isaksson",
    author_email="johan@generatorhallen.se",
    description="Python library and CLI for communicating with Porsche Connect API.",
    long_description=Path.open("README.md").read(),
    long_description_content_type="text/markdown",
    include_package_data=True,
    url="https://github.com/cjne/pyporscheconnectapi",
    license="MIT",
    packages=["pyporscheconnectapi"],
    python_requires=">=3.10",
    install_requires=["httpx<1", "BeautifulSoup4", "rich"],
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
