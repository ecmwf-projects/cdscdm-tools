#!/usr/bin/env python
#
# Copyright 2017-2020 European Centre for Medium-Range Weather Forecasts (ECMWF).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import os
import re

import setuptools  # type: ignore


def read(path: str) -> str:
    file_path = os.path.join(os.path.dirname(__file__), *path.split("/"))
    return io.open(file_path, encoding="utf-8").read()


# single-sourcing the package version using method 1 of:
#   https://packaging.python.org/guides/single-sourcing-package-version/
def parse_version_from(path: str) -> str:
    version_file = read(path)
    version_match = re.search(r'^version = "(.*)"', version_file, re.M)
    if version_match is None or len(version_match.groups()) > 1:
        raise ValueError("couldn't parse version")
    return version_match.group(1)


setuptools.setup(
    name="cdscdm-tools",
    version=parse_version_from("cdscdm_tools/__init__.py"),
    description="Remote API to the Climate Data Store Toolbox",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="European Centre for Medium-Range Weather Forecasts (ECMWF)",
    author_email="software.support@ecmwf.int",
    license="Apache License Version 2.0",
    url="https://github.com/bopen/cdscdm-tools",
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=["cfunits", "click", "netcdf4", "structlog", "xarray"],
    python_requires=">=3.6",
    zip_safe=True,
    keywords="GRIB netCDF xarray",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "cdscdm-check-file=cdscdm_tools.cdm:check_file_cli",
            "cdscdm-cmor-to-cdm=cdscdm_tools.cmor_to_cdm:cmor_to_cdm_cli",
        ]
    },
)
