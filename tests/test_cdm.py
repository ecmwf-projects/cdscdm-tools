import pathlib
import typing as T

import numpy as np  # type: ignore
import pandas as pd  # type: ignore
import pytest
import structlog  # type: ignore
import xarray as xr

from cdstoolbox import cdm


@pytest.fixture(name="log_output")
def fixture_log_output() -> T.Any:
    return structlog.testing.LogCapture()


@pytest.fixture(autouse=True)
def fixture_configure_structlog(log_output: T.Any) -> None:
    structlog.configure(processors=[log_output])


SAMPLEDIR = pathlib.Path(__file__).parent


CDM_DATASET_ATTRS: T.Dict[T.Hashable, str] = {
    "Conventions": "CF-1.8",
    "title": "Test data",
    "history": "test data",
    "institution": "B-Open",
    "source": "B-Open",
    "comment": "No comment",
    "references": "No reference",
}
CDM_TAS_ATTRS: T.Dict[T.Hashable, str] = {
    "standard_name": "air_temperature",
    "long_name": "near-surface air temperature",
    "units": "K",
}
CDM_PLEV_ATTRS: T.Dict[T.Hashable, str] = {
    "standard_name": "air_pressure",
    "long_name": "pressure",
    "units": "Pa",
}
CDM_TIME_ATTRS: T.Dict[T.Hashable, str] = {"standard_name": "time", "long_name": "time"}

CDM_GRID_DATASET = xr.Dataset(
    {"tas": (("plev", "time", "leadtime"), np.ones((2, 3, 4)), CDM_TAS_ATTRS,)},
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
CDM_OBS_DATASET = xr.Dataset(
    {"ta": (("obs",), np.ones(4, dtype="float32"), CDM_TAS_ATTRS)},
    coords={
        "obs": ("obs", np.arange(4), {"long_name": "observation", "units": "1"}),
        "lon": ("obs", -np.arange(4), {"long_name": "lon", "units": "degrees_east"},),
        "lat": ("obs", -np.arange(4), {"long_name": "lat", "units": "degrees_north"},),
    },
    attrs=CDM_DATASET_ATTRS,
)

BAD_TA_ATTRS: T.Dict[T.Hashable, str] = {
    "standard_name": "air_temperature",
    "long_name": "temperature",
    "units": "Celsius",
}
BAD_GRID_DATASET = xr.Dataset(
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


def save_sample_files() -> None:
    CDM_GRID_DATASET.to_netcdf(SAMPLEDIR / "cdm_grid.nc")
    CDM_OBS_DATASET.to_netcdf(SAMPLEDIR / "cdm_obs.nc")
    BAD_GRID_DATASET.to_netcdf(SAMPLEDIR / "bad_grid.nc")


def test_check_dataset_attrs(log_output: T.Any) -> None:
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


def test_get_definition(log_output: T.Any) -> None:
    res = cdm.get_definition("tas", {}, {"tas": CDM_TAS_ATTRS})
    assert res == CDM_TAS_ATTRS

    res = cdm.get_definition("dummy", CDM_TAS_ATTRS, {"tas": CDM_TAS_ATTRS})
    assert res == CDM_TAS_ATTRS
    assert len(log_output.entries) == 2
    assert "unexpected name for variable" in log_output.entries[0]["event"]
    assert "wrong name" in log_output.entries[1]["event"]

    res = cdm.get_definition("dummy", {}, {})
    assert res == {}
    assert len(log_output.entries) == 3
    assert "unexpected name for variable" in log_output.entries[2]["event"]

    res = cdm.get_definition("tas", CDM_TAS_ATTRS, {})
    assert res == {}
    assert len(log_output.entries) == 5
    assert "unexpected name for variable" in log_output.entries[3]["event"]
    assert "standard_name" in log_output.entries[4]["event"]

    definitions = {"tas": CDM_TAS_ATTRS, "ta": CDM_TAS_ATTRS, "time": CDM_TIME_ATTRS}
    res = cdm.get_definition("dummy", CDM_TAS_ATTRS, definitions)
    assert res == {}
    assert len(log_output.entries) == 7
    assert "unexpected name for variable" in log_output.entries[5]["event"]
    assert "standard_name" in log_output.entries[6]["event"]


def test_check_variable_attrs(log_output: T.Any) -> None:
    cdm.check_variable_attrs(CDM_TAS_ATTRS, CDM_TAS_ATTRS)
    assert len(log_output.entries) == 0

    cdm.check_variable_attrs({}, {})
    assert len(log_output.entries) == 2
    assert "long_name" in log_output.entries[0]["event"]
    assert "units" in log_output.entries[1]["event"]

    cdm.check_variable_attrs({**CDM_TAS_ATTRS, "units": "*"}, CDM_TAS_ATTRS)
    assert len(log_output.entries) == 3
    assert "units" in log_output.entries[2]["event"]

    cdm.check_variable_attrs({**CDM_TAS_ATTRS, "units": "m"}, CDM_TAS_ATTRS)
    assert len(log_output.entries) == 4
    assert "units" in log_output.entries[3]["event"]

    cdm.check_variable_attrs(BAD_TA_ATTRS, CDM_TAS_ATTRS)
    assert len(log_output.entries) == 5
    assert "units" in log_output.entries[4]["event"]

    assert all(e["log_level"] == "warning" for e in log_output.entries)


def test_check_coordinate_attrs(log_output: T.Any) -> None:
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


def test_check_coordinate_data(log_output: T.Any) -> None:
    coords = CDM_GRID_DATASET

    cdm.check_coordinate_data("time", coords["time"])
    assert len(log_output.entries) == 0

    cdm.check_coordinate_data("plev", coords["plev"], False)
    assert len(log_output.entries) == 0

    cdm.check_coordinate_data("plev", coords["plev"])
    assert len(log_output.entries) == 1

    cdm.check_coordinate_data("time", coords["time"], False)
    assert len(log_output.entries) == 2


def test_check_variable_data(log_output: T.Any) -> None:
    data = CDM_GRID_DATASET["tas"]

    cdm.check_variable_data(data)
    assert len(log_output.entries) == 0

    cdm.check_variable_data(data.rename(time="time1"))
    assert len(log_output.entries) == 1
    assert "time1" in log_output.entries[0]["event"]
    assert log_output.entries[0]["log_level"] == "warning"

    cdm.check_variable_data(data.drop_vars("plev"))
    assert len(log_output.entries) == 2
    assert "plev" in log_output.entries[1]["event"]
    assert log_output.entries[1]["log_level"] == "error"


def test_open_netcdf_dataset() -> None:
    cdm.open_netcdf_dataset(SAMPLEDIR / "cdm_grid.nc")

    with pytest.raises(OSError):
        cdm.open_netcdf_dataset(SAMPLEDIR / "bad_wrong-file-format.nc")


def test_check_dataset(log_output: T.Any) -> None:
    cdm.check_dataset(CDM_GRID_DATASET)
    assert len(log_output.entries) == 0

    cdm.check_dataset(CDM_OBS_DATASET)
    assert len(log_output.entries) == 0

    cdm.check_dataset(BAD_GRID_DATASET)
    assert len(log_output.entries) == 14


def test_check_file(log_output: T.Any) -> None:
    cdm.check_file(SAMPLEDIR / "cdm_grid.nc")
    assert len(log_output.entries) == 0

    with pytest.raises(OSError):
        cdm.check_file(SAMPLEDIR / "bad_wrong-file-format.nc")
