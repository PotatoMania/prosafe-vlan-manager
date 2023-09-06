import traceback

import click


@click.group()
def cli():
    pass


@cli.command()
@click.option('--config', help='path to your configuration file')
@click.option('--nobackup', is_flag=True, flag_value=True, default=False, help="skip configuration backup")
@click.option('--norestore', is_flag=True, flag_value=True, default=False, help="skip configuration restore on failure")
def apply(config: str, nobackup: bool, norestore: bool):
    raise NotImplementedError()
