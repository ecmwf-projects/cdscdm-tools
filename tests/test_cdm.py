import pathlib

import pytest
import structlog
import xarray as xr

from cdstoolbox import cdm


@pytest.fixture(name="log_output")
def fixture_log_output():
    return structlog.testing.LogCapture()


@pytest.fixture(autouse=True)
def fixture_configure_structlog(log_output):
    structlog.configure(processors=[log_output])


@pytest.fixture()
def sampledir():
    return pathlib.Path(__file__).parent


def test_check_dataset_attrs(log_output):
    cdm.check_dataset_attrs({})
    assert len(log_output.entries) == 7
    assert "Conventions" in log_output.entries[0]["event"]
    assert "title" in log_output.entries[1]["event"]

    global_attrs = {
        "Conventions": "CF-1.8",
        "title": "Test data",
        "history": "test data",
        "institution": "B-Open",
        "source": "B-Open",
        "comment": "No comment",
        "references": "No reference",
    }
    cdm.check_dataset_attrs({**global_attrs, "Conventions": "0.1"})
    assert len(log_output.entries) == 8
    assert "Conventions" in log_output.entries[7]["event"]

    cdm.check_dataset_attrs(global_attrs)
    assert len(log_output.entries) == 8

    assert all(e["log_level"] == "warning" for e in log_output.entries)


def test_check_variable_attrs(log_output):
    cdm.check_variable_attrs({})
    assert len(log_output.entries) == 2
    assert "long_name" in log_output.entries[0]["event"]
    assert "units" in log_output.entries[1]["event"]

    cdm.check_variable_attrs({"standard_name": "*", "long_name": "*", "units": "*"})
    assert len(log_output.entries) == 3
    assert "units" in log_output.entries[2]["event"]

    tas_attrs = {
        "standard_name": "air_temperature",
        "long_name": "air temperature",
        "units": "K",
    }
    cdm.check_variable_attrs(tas_attrs)
    assert len(log_output.entries) == 3

    cdm.check_variable_attrs({**tas_attrs, "units": "m"})
    assert len(log_output.entries) == 4
    assert "units" in log_output.entries[3]["event"]

    cdm.check_variable_attrs({**tas_attrs, "units": "°C"})
    assert len(log_output.entries) == 5
    assert "units" in log_output.entries[4]["event"]

    cdm.check_variable_attrs({**tas_attrs, "standard_name": "*"})
    assert len(log_output.entries) == 5

    assert all(e["log_level"] == "warning" for e in log_output.entries)


def test_check_coordinate_data(log_output):
    data = xr.Dataset(coords={"lat": [0, 90, 180], "plev": [1000, 800, 500]})

    cdm.check_coordinate_data("lat", data.coords["lat"])
    assert len(log_output.entries) == 0

    cdm.check_coordinate_data("plev", data.coords["plev"])
    assert len(log_output.entries) == 1

    cdm.check_coordinate_data("lat", data.coords["lat"], False)
    assert len(log_output.entries) == 2

    cdm.check_coordinate_data("plev", data.coords["plev"], False)
    assert len(log_output.entries) == 2


def test_check_variable_data(log_output):
    data = xr.DataArray([[0]], coords={"lat": [1], "lon": [2]}, dims=("lat", "lon"))
    cdm.check_variable_data(data)
    assert len(log_output.entries) == 0

    cdm.check_variable_data(data.rename(lat="lat1"))
    assert len(log_output.entries) == 1
    assert "lat1" in log_output.entries[0]["event"]
    assert log_output.entries[0]["log_level"] == "warning"

    cdm.check_variable_data(data.drop_vars("lat"))
    assert len(log_output.entries) == 2
    assert "lat" in log_output.entries[1]["event"]
    assert log_output.entries[1]["log_level"] == "error"


def test_open_netcdf_dataset(sampledir):
    cdm.open_netcdf_dataset(sampledir / "cdm_grid_simple.nc")
    cdm.open_netcdf_dataset(sampledir / "bad_two-physical-variables.nc")

    with pytest.raises(OSError):
        cdm.open_netcdf_dataset(sampledir / "bad_wrong-file-format.nc")
