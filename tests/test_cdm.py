import pathlib

import numpy as np
import pandas as pd
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


CDM_DATASET_ATTRS = {
    "Conventions": "CF-1.8",
    "title": "Test data",
    "history": "test data",
    "institution": "B-Open",
    "source": "B-Open",
    "comment": "No comment",
    "references": "No reference",
}
CDM_TAS_ATTRS = {
    "standard_name": "air_temperature",
    "long_name": "near-surface air temperature",
    "units": "K",
}
CDM_PLEV_ATTRS = {
    "standard_name": "air_pressure",
    "long_name": "pressure",
    "units": "Pa",
}
CDM_TIME_ATTRS = {"standard_name": "time", "long_name": "time"}
BAD_TA_ATTRS = {
    "standard_name": "air_temperature",
    "long_name": "temperature",
    "units": "Celsius",
}

CDM_GRID_SIMPLE = xr.Dataset(
    {
        "tas": (
            ("plev", "time", "leadtime"),
            np.ones((2, 3, 4), "float32"),
            CDM_TAS_ATTRS,
        )
    },
    coords={
        "plev": ("plev", np.arange(1000, 800 - 1, -200), CDM_PLEV_ATTRS),
        "time": ("time", pd.date_range("2020-01-01", periods=3), CDM_TIME_ATTRS),
        "leadtime": (
            "leadtime",
            pd.timedelta_range(0, freq="h", periods=4),
            {"long_name": "lead time"},
        ),
    },
    attrs=CDM_DATASET_ATTRS,
)


BAD_GRID_SIMPLE = xr.Dataset(
    {
        "tprate": (
            ("lon1", "time"),
            np.ones((2, 3), "float32"),
            {"units": "Not-availabe"},
        ),
        "tas": (("lon", "lat"), np.ones((2, 3), "float32"), CDM_TAS_ATTRS),
        "ta": (("lon", "lat"), np.ones((2, 3), "float32"), BAD_TA_ATTRS),
    },
    coords={
        "lon": ("lon", -np.arange(2) * 10),
        "lat": ("lat", np.arange(3) * 25.0, {"units": "degrees_north"}),
    },
    attrs={
        "title": "Test data",
        "history": "test data",
        "institution": "B-Open",
        "source": "B-Open",
        "comment": "No comment",
    },
)


def test_check_dataset_attrs(log_output):
    cdm.check_dataset_attrs(CDM_DATASET_ATTRS)
    assert len(log_output.entries) == 0

    cdm.check_dataset_attrs({})
    assert len(log_output.entries) == 7
    assert "Conventions" in log_output.entries[0]["event"]
    assert "title" in log_output.entries[1]["event"]

    cdm.check_dataset_attrs({**CDM_DATASET_ATTRS, "Conventions": "0.1"})
    assert len(log_output.entries) == 8
    assert "Conventions" in log_output.entries[7]["event"]

    assert all(e["log_level"] == "warning" for e in log_output.entries)


def test_check_variable_attrs(log_output):
    cdm.check_variable_attrs(CDM_TAS_ATTRS)
    assert len(log_output.entries) == 0

    cdm.check_variable_attrs({})
    assert len(log_output.entries) == 2
    assert "long_name" in log_output.entries[0]["event"]
    assert "units" in log_output.entries[1]["event"]

    cdm.check_variable_attrs({**CDM_TAS_ATTRS, "units": "*"})
    assert len(log_output.entries) == 3
    assert "units" in log_output.entries[2]["event"]

    cdm.check_variable_attrs({**CDM_TAS_ATTRS, "units": "m"})
    assert len(log_output.entries) == 4
    assert "units" in log_output.entries[3]["event"]

    cdm.check_variable_attrs(BAD_TA_ATTRS)
    assert len(log_output.entries) == 5
    assert "units" in log_output.entries[4]["event"]

    assert all(e["log_level"] == "warning" for e in log_output.entries)


def test_check_coordinate_attrs(log_output):
    cdm.check_coordinate_attrs("plev", CDM_PLEV_ATTRS)
    assert len(log_output.entries) == 0

    cdm.check_coordinate_attrs("ref_time", CDM_TIME_ATTRS, dtype_name="datetime64[ns]")
    assert len(log_output.entries) == 1
    assert "coordinate" in log_output.entries[0]["event"]

    cdm.check_coordinate_attrs("level", {})
    assert len(log_output.entries) == 4
    assert "CDM" in log_output.entries[1]["event"]
    assert "long_name" in log_output.entries[2]["event"]
    assert "units" in log_output.entries[3]["event"]

    cdm.check_coordinate_attrs("lat", {**CDM_PLEV_ATTRS, "units": "*"})
    assert len(log_output.entries) == 5
    assert "units" in log_output.entries[4]["event"]

    cdm.check_coordinate_attrs("lat", {**CDM_PLEV_ATTRS, "units": "m"})
    assert len(log_output.entries) == 6
    assert "units" in log_output.entries[5]["event"]


def test_check_coordinate_data(log_output):
    coords = CDM_GRID_SIMPLE

    cdm.check_coordinate_data("time", coords["time"])
    assert len(log_output.entries) == 0

    cdm.check_coordinate_data("plev", coords["plev"], False)
    assert len(log_output.entries) == 0

    cdm.check_coordinate_data("plev", coords["plev"])
    assert len(log_output.entries) == 1

    cdm.check_coordinate_data("time", coords["time"], False)
    assert len(log_output.entries) == 2


def test_check_variable_data(log_output):
    cdm.check_variable_data(CDM_GRID_SIMPLE)
    assert len(log_output.entries) == 0

    cdm.check_variable_data(CDM_GRID_SIMPLE.rename(time="time1"))
    assert len(log_output.entries) == 1
    assert "time1" in log_output.entries[0]["event"]
    assert log_output.entries[0]["log_level"] == "warning"

    cdm.check_variable_data(CDM_GRID_SIMPLE.drop_vars("plev"))
    assert len(log_output.entries) == 2
    assert "plev" in log_output.entries[1]["event"]
    assert log_output.entries[1]["log_level"] == "error"


def test_open_netcdf_dataset(sampledir):
    cdm.open_netcdf_dataset(sampledir / "cdm_grid_simple.nc")
    cdm.open_netcdf_dataset(sampledir / "bad_grid_simple.nc")

    with pytest.raises(OSError):
        cdm.open_netcdf_dataset(sampledir / "bad_wrong-file-format.nc")


def test_check_dataset(log_output):
    cdm.check_dataset(CDM_GRID_SIMPLE)
    assert len(log_output.entries) == 0

    cdm.check_dataset(BAD_GRID_SIMPLE)
    assert len(log_output.entries) == 13


def test_check_file(log_output, sampledir):
    cdm.check_file(sampledir / "cdm_grid_simple.nc")
    assert len(log_output.entries) == 0

    with pytest.raises(OSError):
        cdm.check_file(sampledir / "bad_wrong-file-format.nc")
