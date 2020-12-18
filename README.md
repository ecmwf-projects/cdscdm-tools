# cdstoolbox

Remote API to the Climate Data Store Toolbox

# Develop

First time setup:
```
git clone https://github.com/bopen/cdstoolbox
cd cdstoolbox
conda env create -n CDSTOOLBOX -f environment.in.yml
conda activate CDSTOOLBOX
pip install -e .
```

New shell setup:
```
cd cdstoolbox
conda activate CDSTOOLBOX
conda env update -f environment.in.yml
```

Usage:
```
cdscdm-check-file myfile.nc
```
