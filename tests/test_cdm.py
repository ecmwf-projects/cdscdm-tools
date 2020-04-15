import pathlib

import pytest
import structlog

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


def test_open_netcdf_dataset(sampledir):
    cdm.open_netcdf_dataset(sampledir / "cdm_simple.nc")

    with pytest.raises(OSError):
        cdm.open_netcdf_dataset(sampledir / "bad_wrong-file-format.nc")
