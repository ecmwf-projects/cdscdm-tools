import pathlib

import pytest

from cdstoolbox import cdm


@pytest.fixture()
def sampledir():
    return pathlib.Path(__file__).parent


def test_open_netcdf_dataset(sampledir):
    cdm.open_netcdf_dataset(sampledir / "cdm_simple.nc")

    with pytest.raises(OSError):
        cdm.open_netcdf_dataset(sampledir / "bad_wrong-file-format.nc")
