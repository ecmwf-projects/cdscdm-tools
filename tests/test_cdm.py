import json
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
CDM_LON_ATTRS: T.Dict[T.Hashable, str] = {
    "long_name": "lon",
    "standard_name": "longitude",
    "units": "degrees_east",
}
CDM_LAT_ATTRS: T.Dict[T.Hashable, str] = {
    "long_name": "lat",
    "standard_name": "latitude",
    "units": "degrees_north",
}

CDM_GRID_DATASET = xr.Dataset(
    {
        "tas": (
            ("time", "leadtime", "plev"),
            np.ones((3, 4, 2), dtype="float32"),
            {**CDM_TAS_ATTRS, "grid_mapping": "crs"},
        ),
        "crs": ((), 1, {"grid_mapping_name": "latitude_longitude"}),
    },
    coords={
        "plev": (
            "plev",
            np.arange(1000, 800 - 1, -200, dtype="float32"),
            CDM_PLEV_ATTRS,
        ),
        "time": (
            "time",
            pd.date_range("2020-01-01", periods=3),
            CDM_TIME_ATTRS,
            {"units": "seconds since 1970-01-01"},
        ),
        "leadtime": (
            "leadtime",
            pd.timedelta_range(0, freq="h", periods=4),
            {"long_name": "lead time", "standard_name": "forecast_period"},
            {"units": "hours"},
        ),
        "lon": ((), 12.5, CDM_LON_ATTRS),
        "lat": ((), 42.5, CDM_LAT_ATTRS),
    },
    attrs=CDM_DATASET_ATTRS,
)
CDM_OBS_DATASET = xr.Dataset(
    {"ta": (("obs",), np.ones(4, dtype="float32"), CDM_TAS_ATTRS)},
    coords={
        "obs": ("obs", np.arange(4), {"long_name": "observation", "units": "1"}),
        "lon": ("obs", -np.arange(4, dtype="float32"), CDM_LON_ATTRS),
        "lat": ("obs", -np.arange(4, dtype="float32"), CDM_LAT_ATTRS),
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

CMOR_DEFINITION = {
    "axis_entry": {
        "time": {
            "units": "seconds since 1970-1-1",
            "out_name": "time",
            "stored_direction": "decreasing",
            "standard_name": "time",
        },
        "leadtime": {"units": "hours", "out_name": "leadtime"},
    },
    "variable_entry": {"ta": {"units": "K", "out_name": "ta"}},
}


def save_sample_files() -> None:
    CDM_GRID_DATASET.to_netcdf(SAMPLEDIR / "cdm_grid.nc")
    CDM_OBS_DATASET.to_netcdf(SAMPLEDIR / "cdm_obs.nc")
    BAD_GRID_DATASET.to_netcdf(SAMPLEDIR / "bad_grid.nc")
    with open(SAMPLEDIR / "CDS_coordinate.json", "w") as fp:
        json.dump(CMOR_DEFINITION, fp)

    assert xr.open_dataset(SAMPLEDIR / "cdm_grid.nc").equals(CDM_GRID_DATASET)
    assert xr.open_dataset(SAMPLEDIR / "cdm_obs.nc").equals(CDM_OBS_DATASET)
    assert xr.open_dataset(SAMPLEDIR / "bad_grid.nc").equals(BAD_GRID_DATASET)


def test_sanitise_mapping(log_output: T.Any) -> None:
    assert cdm.sanitise_mapping({None: 1, "key": 2}) == {"None": 1, "key": 2}
    assert len(log_output.entries) == 1


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


def test_guess_definition(log_output: T.Any) -> None:
    res = cdm.guess_definition(CDM_TAS_ATTRS, {"tas": CDM_TAS_ATTRS})
    assert res == CDM_TAS_ATTRS
    assert len(log_output.entries) == 1
    assert "wrong name" in log_output.entries[0]["event"]

    res = cdm.guess_definition({}, {})
    assert res == {}
    assert len(log_output.entries) == 2
    assert "standard_name" in log_output.entries[1]["event"]

    res = cdm.guess_definition(CDM_TAS_ATTRS, {})
    assert res == {}
    assert len(log_output.entries) == 3
    assert "standard_name" in log_output.entries[2]["event"]

    definitions = {"tas": CDM_TAS_ATTRS, "ta": CDM_TAS_ATTRS, "time": CDM_TIME_ATTRS}
    res = cdm.guess_definition(CDM_TAS_ATTRS, definitions)
    assert res == {}
    assert len(log_output.entries) == 4
    assert "standard_name" in log_output.entries[3]["event"]


def test_check_variable_attrs(log_output: T.Any) -> None:
    cdm.check_variable_attrs(CDM_TAS_ATTRS, CDM_TAS_ATTRS)
    assert len(log_output.entries) == 0

    cdm.check_variable_attrs(CDM_TIME_ATTRS, CDM_TIME_ATTRS, dtype="datetime64[ns]")
    assert len(log_output.entries) == 0

    cdm.check_variable_attrs(CDM_TAS_ATTRS, {**CDM_TAS_ATTRS, "units": None})
    assert len(log_output.entries) == 0

    cdm.check_variable_attrs({}, {})
    assert len(log_output.entries) == 2
    assert "long_name" in log_output.entries[0]["event"]
    assert "units" in log_output.entries[1]["event"]

    attrs = {**CDM_TAS_ATTRS, "units": "*", "standard_name": None}
    cdm.check_variable_attrs(attrs, CDM_TAS_ATTRS)
    assert len(log_output.entries) == 4
    assert "units" in log_output.entries[2]["event"]
    assert "standard_name" in log_output.entries[3]["event"]

    attrs = {**CDM_TAS_ATTRS, "units": "m", "standard_name": "dummy"}
    cdm.check_variable_attrs(attrs, CDM_TAS_ATTRS)
    assert len(log_output.entries) == 6
    assert "units" in log_output.entries[4]["event"]
    assert "standard_name" in log_output.entries[5]["event"]

    cdm.check_variable_attrs(BAD_TA_ATTRS, CDM_TAS_ATTRS)
    assert len(log_output.entries) == 7
    assert "units" in log_output.entries[6]["event"]

    assert all(e["log_level"] == "warning" for e in log_output.entries)


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


def test_check_variable(log_output: T.Any) -> None:
    data = CDM_GRID_DATASET["tas"]

    cdm.check_variable("tas", data, cdm.CDM_DATA_VARS)
    assert len(log_output.entries) == 0

    cdm.check_variable("dummy", data, cdm.CDM_DATA_VARS)
    assert len(log_output.entries) == 2
    assert "unexpected name" in log_output.entries[0]["event"]
    assert "variables with" in log_output.entries[1]["event"]


def test_check_dataset_data_vars(log_output: T.Any) -> None:
    cdm.check_dataset_data_vars(CDM_GRID_DATASET.data_vars)
    assert len(log_output.entries) == 0

    cdm.check_dataset_data_vars(
        {**CDM_GRID_DATASET.data_vars, "ta": CDM_OBS_DATASET.data_vars["ta"]}
    )
    assert len(log_output.entries) == 1
    assert "at most one" in log_output.entries[0]["event"]


def test_check_coordinate_data(log_output: T.Any) -> None:
    coords = CDM_GRID_DATASET.coords

    cdm.check_coordinate_data("time", coords["time"])
    assert len(log_output.entries) == 0

    cdm.check_coordinate_data("plev", coords["plev"], False)
    assert len(log_output.entries) == 0

    cdm.check_coordinate_data("plev", coords["plev"])
    assert len(log_output.entries) == 1

    cdm.check_coordinate_data("time", coords["time"], False)
    assert len(log_output.entries) == 2


def test_check_dataset_coords(log_output: T.Any) -> None:
    coords = CDM_GRID_DATASET.coords

    cdm.check_dataset_coords(coords)
    assert len(log_output.entries) == 0


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
    assert len(log_output.entries) == 15


def test_open_cmor_tables() -> None:
    res = cdm.open_cmor_tables(SAMPLEDIR)

    assert res == [CMOR_DEFINITION, {}]


def test_cmor_to_cdm() -> None:
    expected_coords = {
        "time": {"stored_direction": "decreasing", "standard_name": "time"},
        "leadtime": {"units": "hours"},
    }
    expected_data_vars = {"ta": {"units": "K"}}

    res = cdm.cmor_to_cdm([CMOR_DEFINITION])

    assert list(res) == ["attrs", "coords", "data_vars"]
    assert res["coords"] == expected_coords
    assert res["data_vars"] == expected_data_vars
