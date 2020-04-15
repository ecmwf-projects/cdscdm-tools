import logging

import cfunits
import click
import structlog
import xarray as xr


LOGGER = structlog.get_logger()

CDM_GLOBAL_ATTRIBUTES = [
    "title",
    "history",
    "institution",
    "source",
    "comment",
    "references",
]
CDM_VARIABLES = {
    "air_temperature": {"units": "K", "long_name": "temperature",},
}
CDM_COORDINATES = {
    "lon": {},
    "lat": {},
    "time": {},
    "obs": {},
    "plev": {"stored_direction": "decreasing"},
}


class CommonDataModelError(Exception):
    pass


def check_dataset_attrs(attrs, log=LOGGER):
    conventions = attrs.get("Conventions")
    if conventions is None:
        log.warning("missing required 'Conventions' global attribute")
    elif conventions not in ["CF-1.8", "CF-1,7", "CF-1.6"]:
        log.warning("invalid 'Conventions' value", conventions=conventions)

    for attr_name in CDM_GLOBAL_ATTRIBUTES:
        if attr_name not in attrs:
            log.warning(f"missing recommended global attribute '{attr_name}'")


def check_variable_attrs(attrs, log=LOGGER):
    standard_name = attrs.get("standard_name")
    units = attrs.get("units")

    expected_attrs = CDM_VARIABLES.get(standard_name, {})
    expected_units = expected_attrs.get("units")

    if standard_name is not None:
        log = log.bind(standard_name=standard_name)

    if "long_name" not in attrs:
        log.warning("missing recommended attribute 'long_name'")

    if "units" not in attrs:
        log.warning("missing recommended attribute 'units'")
    else:
        cf_units = cfunits.Units(units)
        if not cf_units.isvalid:
            log.warning("'units' attribute not valid", units=units)
        elif expected_units is not None:
            expected_cf_units = cfunits.Units(expected_units)
            log = log.bind(units=units, expected_units=expected_units)
            if not cf_units.equivalent(expected_cf_units):
                log.warning("'units' attribute not equivalent to the expected")
            elif not cf_units.equals(expected_cf_units):
                log.warning("'units' attribute not equal to the expected")


def check_coordinate_data(coord_name, coord, increasing=True, log=LOGGER):
    log = log.bind(coord_name=coord_name)
    diffs = coord.diff(coord_name).values
    if increasing:
        if (diffs <= 0).any():
            log.error("coordinate stored direction is not 'increasing'")
    else:
        if (diffs >= 0).any():
            log.error("coordinate stored direction is not 'decreasing'")


def check_variable_data(data_var, log=LOGGER):
    for dim in data_var.dims:
        if dim not in CDM_COORDINATES:
            log.warning(f"unknown coordinate '{dim}'")
        elif dim not in data_var.coords:
            log.error(f"dimension with no associated coordinate '{dim}'")
        else:
            coord_definition = CDM_COORDINATES.get(dim, {})
            stored_direction = coord_definition.get("stored_direction", "increasing")
            increasing = stored_direction == "increasing"
            check_coordinate_data(dim, data_var.coords[dim], increasing, log=log)


def check_variable(data_var, log=LOGGER):
    check_variable_attrs(data_var.attrs, log=log)
    check_variable_data(data_var, log=log)


def check_dataset(dataset, log=LOGGER):
    data_vars = list(dataset.data_vars)
    if len(data_vars) > 1:
        log.error("file must have at most one variable", data_vars=data_vars)
    check_dataset_attrs(dataset.attrs)
    for data_var_name, data_var in dataset.data_vars.items():
        check_variable(data_var, log=log.bind(data_var_name=data_var_name))


def open_netcdf_dataset(file_path):
    return xr.open_dataset(file_path, engine="netcdf4")


def check_file(file_path, log=LOGGER):
    try:
        dataset = open_netcdf_dataset(file_path)
    except OSError:
        raise CommonDataModelError("Cannot open file as netCDF4 data")
    check_dataset(dataset)


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
def check_file_cli(file_path):
    logging.basicConfig(level=logging.INFO)
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())
    check_file(file_path)
