import json
import logging
import pathlib
import pkgutil

import cfunits
import click
import numpy as np
import structlog
import xarray as xr

LOGGER = structlog.get_logger()

CDM = json.loads(pkgutil.get_data(__name__, "cdm.json"))
CDM_ATTRS = CDM["attrs"]
CDM_COORDS = CDM["coords"]
CDM_DATA_VARS = CDM["data_vars"]

TIME_DTYPE_NAMES = {"datetime64[ns]", "timedelta64[ns]"}


def check_dataset_attrs(attrs, log=LOGGER):
    conventions = attrs.get("Conventions")
    if conventions is None:
        log.warning("missing required 'Conventions' global attribute")
    elif conventions not in ["CF-1.8", "CF-1.7", "CF-1.6"]:
        log.warning("invalid 'Conventions' value", conventions=conventions)

    for attr_name in CDM_ATTRS:
        if attr_name not in attrs:
            log.warning(f"missing recommended global attribute '{attr_name}'")


def check_variable_attrs(name, attrs, log=LOGGER):
    standard_name = attrs.get("standard_name")
    units = attrs.get("units")

    log = log.bind(standard_name=standard_name)

    definition = {}
    if name in CDM_DATA_VARS:
        definition = CDM_DATA_VARS[name]
    elif standard_name is not None:
        for expected_name, coord_def in CDM_DATA_VARS.items():
            if coord_def.get("standard_name") == standard_name:
                definition = coord_def
                log.error("wrong name for coordinate", expected_name=expected_name)

    expected_units = definition.get("units")

    if "long_name" not in attrs:
        log.warning("missing recommended attribute 'long_name'")

    if "units" not in attrs:
        log.warning("missing recommended attribute 'units'")
    else:
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


def check_coordinate_attrs(name, attrs, dtype_name=None, log=LOGGER):
    log = log.bind(coord_name=name)

    standard_name = attrs.get("standard_name")
    units = attrs.get("units")

    log = log.bind(standard_name=standard_name)

    definition = {}
    if name in CDM_COORDS:
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


def check_coordinate_data(coord_name, coord, increasing=True, log=LOGGER):
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


def check_variable_data(data_var, log=LOGGER):
    for dim in data_var.dims:
        if dim not in CDM_COORDS:
            log.warning(f"unknown coordinate '{dim}'")
        elif dim not in data_var.coords:
            log.error(f"dimension with no associated coordinate '{dim}'")
        else:
            coord_definition = CDM_COORDS.get(dim, {})
            stored_direction = coord_definition.get("stored_direction", "increasing")
            increasing = stored_direction == "increasing"
            check_coordinate_data(dim, data_var.coords[dim], increasing, log=log)


def open_netcdf_dataset(file_path):
    bare_dataset = xr.open_dataset(file_path, engine="netcdf4", decode_cf=False)
    return xr.decode_cf(bare_dataset, use_cftime=False)


def check_variable(data_var_name, data_var, log=LOGGER):
    log.bind(data_var_name=data_var_name)
    check_variable_attrs(data_var_name, data_var.attrs, log=log)
    check_variable_data(data_var, log=log)


def check_dataset(dataset, log=LOGGER):
    data_vars = list(dataset.data_vars)
    if len(data_vars) > 1:
        log.error("file must have at most one variable", data_vars=data_vars)
    check_dataset_attrs(dataset.attrs)
    for data_var_name, data_var in dataset.data_vars.items():
        check_variable(data_var_name, data_var, log=log)
    for coord_name, coord in dataset.coords.items():
        check_coordinate_attrs(coord_name, coord.attrs, coord.dtype.name, log=log)


def check_file(file_path, log=LOGGER):
    dataset = open_netcdf_dataset(file_path)
    check_dataset(dataset)


def cmor_tables_to_cdm(cmor_tables_dir, cdm_path):
    cmor_tables_dir = pathlib.Path(cmor_tables_dir)
    with open(cmor_tables_dir / "CDS_coordinate.json") as fp:
        axis_entry = json.load(fp).get("axis_entry", {})

    cdm_coords = {}
    for coord in sorted(axis_entry.values(), key=lambda x: x["out_name"]):
        cdm_coord = {k: v for k, v in coord.items() if v and k in {"standard_name", "long_name"}}
        if coord.get("units", "") and 'since' not in coord["units"]:
            cdm_coord["units"] = coord["units"]
        if coord.get("stored_direction", "") not in {"increasing", ""}:
            cdm_coord["stored_direction"] = coord["stored_direction"]
        cdm_coords[coord["out_name"]] = cdm_coord

    with open(cmor_tables_dir / "CDS_variable.json") as fp:
        variable_entry = json.load(fp).get("variable_entry", {})

    cdm_data_vars = {}
    for coord in sorted(variable_entry.values(), key=lambda x: x["out_name"]):
        cdm_data_var = {k: v for k, v in coord.items() if v and k in {"standard_name", "long_name"}}
        if coord.get("units", "") and 'since' not in coord["units"]:
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
def check_file_cli(file_path):
    logging.basicConfig(level=logging.INFO)
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())
    check_file(file_path)
