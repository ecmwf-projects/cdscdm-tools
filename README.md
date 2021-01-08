# cdscdm-tools

Remote API to the Climate Data Store Toolbox

# Develop

First time setup:
```
git clone https://github.com/bopen/cdscdm-tools
cd cdscdm-tools
conda env create -n CDSCDM-TOOLS -f environment.in.yml
conda activate CDSCDM-TOOLS
pip install -e .
```

New shell setup:
```
cd cdscdm-tools
conda activate CDSCDM-TOOLS
conda env update -f environment.in.yml
```

Usage:
```
cdscdm-check-file myfile.nc
```
