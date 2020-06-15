# cdstoolbox
Remote API to the Climate Data Store Toolbox

# Develop

First time setup:
```
git clone https://github.com/bopen/cdstoolbox
cd cdstoolbox
conda env create -f environment.yml
conda activate cdstoolbox-env
pip install -e .
```

New shell setup:
```
cd cdstoolbox
conda activate cdstoolbox-env
conda env update -f environment.yml
```

Usage:
```
cdscdm-check-file myfile.nc
```
