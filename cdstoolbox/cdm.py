import click
import structlog
import xarray as xr


LOGGER = structlog.get_logger()


class CommonDataModelError(Exception):
    pass


def check_variables(data_vars, log=LOGGER):
    if len(data_vars) > 1:
        log.critical(
            "dataset must have at most one physical variable", data_vars=list(data_vars)
        )


def check_coordinates(coords, log=LOGGER):
    pass


def check_dataset(dataset, log=LOGGER):
    check_variables(dataset.data_vars, log=log)
    check_coordinates(dataset.coords, log=log)


def open_netcdf_dataset(file_path):
    return xr.open_dataset(file_path, engine="netcdf4")


def check_file(file_path, log=LOGGER):
    log = log.bind(file_path=file_path)
    log.msg("start checking")
    try:
        dataset = open_netcdf_dataset(file_path)
    except OSError:
        raise CommonDataModelError("Cannot open file as netCDF4 data")
    check_dataset(dataset, log=log)
    log.msg("check completed")


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
def check_file_cli(file_path):
    check_file(file_path)
