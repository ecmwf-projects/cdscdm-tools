import json
import logging
import os
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
CDM_ANCILLARY_VARS: T.Set[str] = {"crs"}
TIME_DTYPE_NAMES = {"datetime64[ns]", "timedelta64[ns]"}


def sanitise_mapping(
    mapping: T.Mapping[T.Hashable, T.Any], log: structlog.BoundLogger = LOGGER
) -> T.Dict[str, T.Any]:
    clean = {}
    for key, value in mapping.items():
        if isinstance(key, str):
            clean[key] = value
        else:
            key_repr = repr(key)
            log.warning("non-string key", key=key_repr)
            clean[key_repr] = value
    return clean


def check_dataset_attrs(
    dataset_attrs: T.Mapping[T.Hashable, T.Any], log: structlog.BoundLogger = LOGGER
) -> None:
    attrs = sanitise_mapping(dataset_attrs, log)
    conventions = attrs.get("Conventions")
    if conventions is None:
        log.warning("missing required 'Conventions' global attribute")
    elif conventions not in {"CF-1.8", "CF-1.7", "CF-1.6"}:
        log.warning("invalid 'Conventions' value", conventions=conventions)

    for attr_name in CDM_ATTRS:
        if attr_name not in attrs:
            log.warning(f"missing recommended global attribute '{attr_name}'")


def guess_definition(
    attrs: T.Dict[str, str],
    definitions: T.Dict[str, T.Dict[str, str]],
    log: structlog.BoundLogger = LOGGER,
) -> T.Dict[str, str]:
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
    else:
        log.warning("missing recommended attribute 'standard_name'")
    return {}


def check_variable_attrs(
    variable_attrs: T.Mapping[T.Hashable, T.Any],
    definition: T.Dict[str, str],
    dtype: T.Optional[str] = None,
    log: structlog.BoundLogger = LOGGER,
) -> None:
    attrs = sanitise_mapping(variable_attrs, log)

    if "long_name" not in attrs:
        log.warning("missing recommended attribute 'long_name'")
    if "units" not in attrs:
        if dtype not in TIME_DTYPE_NAMES:
            log.warning("missing recommended attribute 'units'")
    else:
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


def check_variable_data(
    data_var: xr.DataArray, log: structlog.BoundLogger = LOGGER
) -> None:
    for dim in data_var.dims:
        if dim not in CDM_COORDS:
            log.warning(f"unknown dimension '{dim}'")
        elif dim not in data_var.coords:
            log.error(f"dimension with no associated coordinate '{dim}'")


def check_variable(
    data_var_name: str,
    data_var: xr.DataArray,
    definitions: T.Dict[str, T.Dict[str, str]],
    log: structlog.BoundLogger = LOGGER,
) -> None:
    attrs = sanitise_mapping(data_var.attrs, log)
    if data_var_name in definitions:
        definition = definitions[data_var_name]
    else:
        log.warning("unexpected name for variable")
        definition = guess_definition(attrs, definitions, log)
    check_variable_attrs(data_var.attrs, definition, dtype=data_var.dtype.name, log=log)
    check_variable_data(data_var, log=log)
    if data_var.dims == (data_var_name,):
        increasing = definition.get("stored_direction", "increasing") == "increasing"
        check_coordinate_data(data_var_name, data_var, increasing, log)


def check_dataset_data_vars(
    dataset_data_vars: T.Mapping[T.Hashable, xr.DataArray],
    log: structlog.BoundLogger = LOGGER,
) -> T.Tuple[T.Dict[str, xr.DataArray], T.Dict[str, xr.DataArray]]:
    data_vars = sanitise_mapping(dataset_data_vars, log=log)
    payload_vars = {}
    ancillary_vars = {}
    for name, var in data_vars.items():
        if name in CDM_ANCILLARY_VARS:
            ancillary_vars[name] = var
        else:
            payload_vars[name] = var
    if len(payload_vars) > 1:
        log.error(
            "file must have at most one non-auxiliary variable",
            data_vars=list(payload_vars),
        )
    for data_var_name, data_var in payload_vars.items():
        log = log.bind(data_var_name=data_var_name)
        check_variable(data_var_name, data_var, CDM_DATA_VARS, log=log)
    return payload_vars, ancillary_vars


def check_coordinate_data(
    coord_name: T.Hashable,
    coord: xr.DataArray,
    increasing: bool = True,
    log: structlog.BoundLogger = LOGGER,
) -> None:
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


def check_dataset_coords(
    dataset_coords: T.Mapping[T.Hashable, T.Any], log: structlog.BoundLogger = LOGGER
) -> None:
    coords = sanitise_mapping(dataset_coords, log=log)
    for coord_name, coord in coords.items():
        log = log.bind(coord_name=coord_name)
        check_variable(coord_name, coord, CDM_COORDS, log=log)


def open_netcdf_dataset(file_path: T.Union[str, "os.PathLike[str]"]) -> xr.Dataset:
    bare_dataset = xr.open_dataset(file_path, decode_cf=False)  # type: ignore
    return xr.decode_cf(bare_dataset, use_cftime=False)  # type: ignore


def check_dataset(dataset: xr.Dataset, log: structlog.BoundLogger = LOGGER) -> None:
    check_dataset_attrs(dataset.attrs, log=log)
    check_dataset_coords(dataset.coords, log=log)
    check_dataset_data_vars(dataset.data_vars, log=log)


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
def check_file_cli(file_path: str) -> None:
    logging.basicConfig(level=logging.INFO)
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())
    dataset = open_netcdf_dataset(file_path)
    check_dataset(dataset)
