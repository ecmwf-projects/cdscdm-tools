#!/bin/bash

set -e

export PYTHONPATH="./tests"

python -c 'import test_cdm; test_cdm.save_sample_files()'

mkdir -p tmp && cd tmp

cd cds-cmor-tables || (git clone https://git.ecmwf.int/scm/cst/cds-cmor-tables.git && cd cds-cmor-tables)

git reset --hard && git checkout $1 && git pull

cd ../..

cdscdm-cmor-to-cdm ./tmp/cds-cmor-tables/Tables > ./cdstoolbox/cdm.json
