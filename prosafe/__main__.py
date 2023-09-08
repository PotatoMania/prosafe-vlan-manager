import traceback
from pathlib import Path

import click

from .vlan_config import load_config
from .cli import RequiredIf


@click.group()
def cli():
    pass


@cli.command()
@click.option('--config', '-c', required=True, 
            type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
            help='Path to your configuration file.')
@click.option('--norestore', is_flag=True, flag_value=True, default=False, help="Skip restore on failure.")
@click.option('--savepath', cls=RequiredIf, required_if="norestore",
            type=click.Path(exists=True, file_okay=False, dir_okay=True, writable=True),
            help='If specified, save switch config backups to that folder.')
def apply(config: str, norestore: bool, savepath: str|None):
    click.echo("Loading config from %s ..." % config)
    cfgs = load_config(config)
    click.echo("Got %d switch(es)." % len(cfgs))
    
    if isinstance(savepath, str):
        savepath = savepath.rstrip('/')
        savepath = Path(savepath)
    
    for sw_name, sw_cfg in cfgs.items():
        click.echo("Processing switch '%s' ..." % sw_name)
        sw = sw_cfg.model.driver(sw_cfg.address, sw_cfg.password)
        backup_data: bytes|None = None

        with sw.logged_in():
            backup_data = sw.backup()
            if isinstance(savepath, Path):
                backup_file = savepath / f'{sw_name}.cfg'
                click.echo("Backup saved to %s" % backup_file)
                with open(backup_file, 'wb') as f:
                    f.write(backup_data)
            try:
                vlan_membership = sw_cfg.get_vlan_membership()
                pvids = sw_cfg.get_pvids()
                sw.apply_vlan_config(vlan_membership, pvids)
            except Exception as e:
                traceback.print_exception(e)
                click.echo("Error occurred! Check the printed exception!")
                if not norestore:
                    click.echo("Restoring switch(%s) configuration ..." % sw_name)
                    sw.restore(backup_data)
                break
        
    click.echo("All done!")

cli()