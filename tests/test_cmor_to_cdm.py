import json
import pathlib
import typing as T

import pytest
import structlog  # type: ignore

from cdstoolbox import cmor_to_cdm


@pytest.fixture(name="log_output")
def fixture_log_output() -> T.Any:
    return structlog.testing.LogCapture()


@pytest.fixture(autouse=True)
def fixture_configure_structlog(log_output: T.Any) -> None:
    structlog.configure(processors=[log_output])


SAMPLEDIR = pathlib.Path(__file__).parent


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
    with open(SAMPLEDIR / "CDS_coordinate.json", "w") as fp:
        json.dump(CMOR_DEFINITION, fp)


def test_open_cmor_tables() -> None:
    res = cmor_to_cdm.open_cmor_tables(SAMPLEDIR)

    assert res == [CMOR_DEFINITION, {}]


def test_cmor_to_cdm() -> None:
    expected_coords = {
        "time": {"stored_direction": "decreasing", "standard_name": "time"},
        "leadtime": {"units": "hours"},
    }
    expected_data_vars = {"ta": {"units": "K"}}

    res = cmor_to_cdm.cmor_to_cdm([CMOR_DEFINITION])

    assert list(res) == ["attrs", "coords", "data_vars"]
    assert res["coords"] == expected_coords
    assert res["data_vars"] == expected_data_vars
