import json
import logging
import os
import pathlib
import pkgutil
import typing as T

import cfunits  # type: ignore
import click
import numpy as np  # type: ignore
import structlog  # type: ignore
import xarray as xr

LOGGER = structlog.get_logger()

CDM = json.loads(pkgutil.get_data(__name__, "cdm.json") or "")
CDM_ATTRS: T.List[str] = CDM.get("attrs", [])
CDM_COORDS: T.Dict[str, T.Dict[str, str]] = CDM.get("coords", {})
CDM_DATA_VARS: T.Dict[str, T.Dict[str, str]] = CDM.get("data_vars", {})

TIME_DTYPE_NAMES = {"datetime64[ns]", "timedelta64[ns]"}


def check_dataset_attrs(
    attrs: T.Dict[T.Hashable, T.Any], log: structlog.BoundLogger = LOGGER
) -> None:
    conventions = attrs.get("Conventions")
    if conventions is None:
        log.warning("missing required 'Conventions' global attribute")
    elif conventions not in ["CF-1.8", "CF-1.7", "CF-1.6"]:
        log.warning("invalid 'Conventions' value", conventions=conventions)

    for attr_name in CDM_ATTRS:
        if attr_name not in attrs:
            log.warning(f"missing recommended global attribute '{attr_name}'")


def get_definition(
    name: T.Hashable,
    attrs: T.Dict[T.Hashable, str],
    definitions: T.Dict[str, T.Dict[str, str]],
    log: structlog.BoundLogger = LOGGER,
) -> T.Dict[str, str]:
    if name in definitions:
        assert isinstance(name, str)
        return definitions[name]
    else:
        log.warning("unexpected name for variable")
        standard_name = attrs.get("standard_name")
        if standard_name is not None:
            log = log.bind(standard_name=standard_name)
            matching_variables = []
            for var_name, var_def in definitions.items():
                if var_def.get("standard_name") == standard_name:
                    matching_variables.append(var_name)
            if len(matching_variables) == 0:
                log.warning("'standard_name' attribute not valid")
            elif len(matching_variables) == 1:
                expected_name = matching_variables[0]
                log.warning("wrong name for variable", expected_name=expected_name)
                return definitions[expected_name]
            else:
                log.warning(
                    "variables with matching 'standard_name':",
                    matching_variables=matching_variables,
                )
    return {}


def check_variable_attrs(
    attrs: T.Dict[T.Hashable, T.Any],
    definition: T.Dict[str, str],
    log: structlog.BoundLogger = LOGGER,
) -> None:
    if "long_name" not in attrs:
        log.warning("missing recommended attribute 'long_name'")

    if "units" not in attrs:
        log.warning("missing recommended attribute 'units'")

    units = attrs.get("units")
    expected_units = definition.get("units")
    if expected_units is not None:
        log = log.bind(expected_units=expected_units)
        cf_units = cfunits.Units(units)
        if not cf_units.isvalid:
            log.warning("'units' attribute not valid", units=units)
        else:
            expected_cf_units = cfunits.Units(expected_units)
            log = log.bind(units=units, expected_units=expected_units)
            if not cf_units.equivalent(expected_cf_units):
                log.warning("'units' attribute not equivalent to the expected")
            elif not cf_units.equals(expected_cf_units):
                log.warning("'units' attribute not equal to the expected")

    standard_name = attrs.get("standard_name")
    expected_standard_name = definition.get("standard_name")
    if expected_standard_name is not None:
        log = log.bind(expected_standard_name=expected_standard_name)
        if standard_name is None:
            log.warning("missing expected attribute 'standard_name'")
        elif standard_name != expected_standard_name:
            log.warning(
                "'standard_name' attribute not valid", standard_name=standard_name
            )


def check_coordinate_attrs(
    name: T.Hashable,
    attrs: T.Dict[T.Hashable, T.Any],
    dtype_name: T.Optional[str] = None,
    log: structlog.BoundLogger = LOGGER,
) -> None:
    log = log.bind(coord_name=name)

    standard_name = attrs.get("standard_name")
    units = attrs.get("units")

    log = log.bind(standard_name=standard_name)

    definition = {}
    if name in CDM_COORDS:
        assert isinstance(name, str)
        definition = CDM_COORDS[name]
    elif standard_name is not None:
        for expected_name, coord_def in CDM_COORDS.items():
            if coord_def.get("standard_name") == standard_name:
                definition = coord_def
                log.error("wrong name for coordinate", expected_name=expected_name)

    if definition == {}:
        log.error("coordinate not found in CDM")

    expected_units = definition.get("units", "1")

    if "long_name" not in attrs:
        log.warning("missing recommended attribute 'long_name'")

    if dtype_name in TIME_DTYPE_NAMES:
        return

    if "units" not in attrs:
        log.error("missing required attribute 'units'")
    else:
        cf_units = cfunits.Units(units)
        if not cf_units.isvalid:
            log.error("'units' attribute not valid", units=units)
        else:
            expected_cf_units = cfunits.Units(expected_units)
            log = log.bind(units=units, expected_units=expected_units)
            if not cf_units.equals(expected_cf_units):
                log.error("'units' attribute not equal to the expected")


def check_coordinate_data(
    coord_name: T.Hashable,
    coord: xr.DataArray,
    increasing: bool = True,
    log: structlog.BoundLogger = LOGGER,
) -> None:
    log = log.bind(coord_name=coord_name)
    diffs = coord.diff(coord_name).values
    zero = 0
    if coord.dtype.name in TIME_DTYPE_NAMES:
        zero = np.timedelta64(0, "ns")
    if increasing:
        if (diffs <= zero).any():
            log.error("coordinate stored direction is not 'increasing'")
    else:
        if (diffs >= zero).any():
            log.error("coordinate stored direction is not 'decreasing'")


def check_variable_data(
    data_var: xr.DataArray, log: structlog.BoundLogger = LOGGER
) -> None:
    for dim in data_var.dims:
        if dim not in CDM_COORDS:
            log.warning(f"unknown coordinate '{dim}'")
        elif dim not in data_var.coords:
            log.error(f"dimension with no associated coordinate '{dim}'")
        else:
            assert isinstance(dim, str)
            coord_definition = CDM_COORDS[dim]
            stored_direction = coord_definition.get("stored_direction", "increasing")
            increasing = stored_direction == "increasing"
            check_coordinate_data(dim, data_var.coords[dim], increasing, log=log)


def check_variable(
    data_var_name: T.Hashable,
    data_var: xr.DataArray,
    log: structlog.BoundLogger = LOGGER,
) -> None:
    log.bind(data_var_name=data_var_name)
    definition = get_definition(data_var_name, data_var.attrs, CDM_DATA_VARS, log)
    check_variable_attrs(data_var.attrs, definition, log=log)
    check_variable_data(data_var, log=log)


def check_dataset(dataset: xr.Dataset, log: structlog.BoundLogger = LOGGER) -> None:
    data_vars = list(dataset.data_vars)
    if len(data_vars) > 1:
        log.error("file must have at most one variable", data_vars=data_vars)
    check_dataset_attrs(dataset.attrs)
    for data_var_name, data_var in dataset.data_vars.items():
        check_variable(data_var_name, data_var, log=log)
    for coord_name, coord in dataset.coords.items():
        check_coordinate_attrs(coord_name, coord.attrs, coord.dtype.name, log=log)


def open_netcdf_dataset(file_path: T.Union[str, "os.PathLike[str]"]) -> xr.Dataset:
    bare_dataset = xr.open_dataset(file_path, decode_cf=False)  # type: ignore
    return xr.decode_cf(bare_dataset, use_cftime=False)  # type: ignore


def check_file(
    file_path: T.Union[str, "os.PathLike[str]"], log: structlog.BoundLogger = LOGGER
) -> None:
    dataset = open_netcdf_dataset(file_path)
    check_dataset(dataset)


def cmor_tables_to_cdm(
    cmor_tables_dir: T.Union[str, "os.PathLike[str]"],
    cdm_path: T.Union[str, "os.PathLike[str]"],
) -> None:
    cmor_tables_dir = pathlib.Path(cmor_tables_dir)
    axis_entry: T.Dict[str, T.Dict[str, str]]
    with open(cmor_tables_dir / "CDS_coordinate.json") as fp:
        axis_entry = json.load(fp).get("axis_entry", {})

    cdm_coords: T.Dict[str, T.Any] = {}
    for coord in sorted(axis_entry.values(), key=lambda x: x["out_name"]):
        cdm_coord = {
            k: v for k, v in coord.items() if v and k in {"standard_name", "long_name"}
        }
        if coord.get("units", "") and "since" not in coord["units"]:
            cdm_coord["units"] = coord["units"]
        if coord.get("stored_direction", "") not in {"increasing", ""}:
            cdm_coord["stored_direction"] = coord["stored_direction"]
        cdm_coords[coord["out_name"]] = cdm_coord

    variable_entry: T.Dict[str, T.Dict[str, str]]
    with open(cmor_tables_dir / "CDS_variable.json") as fp:
        variable_entry = json.load(fp).get("variable_entry", {})

    cdm_data_vars = {}
    for coord in sorted(variable_entry.values(), key=lambda x: x["out_name"]):
        cdm_data_var = {
            k: v for k, v in coord.items() if v and k in {"standard_name", "long_name"}
        }
        if coord.get("units", "") and "since" not in coord["units"]:
            cdm_data_var["units"] = coord["units"]
        cdm_data_vars[coord["out_name"]] = cdm_data_var

    cdm = {
        "attrs": ["title", "history", "institution", "source", "comment", "references"],
        "coords": cdm_coords,
        "data_vars": cdm_data_vars,
    }
    with open(cdm_path, "w") as fp:
        json.dump(cdm, fp, separators=(",", ":"), indent=1)


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
def check_file_cli(file_path: str) -> None:
    logging.basicConfig(level=logging.INFO)
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())
    check_file(file_path)
