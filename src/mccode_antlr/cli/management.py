def config_dump(config):
    from yaml import dump, add_representer
    from collections import OrderedDict
    def represent(yaml_dumper, data):
        return yaml_dumper.represent_mapping('tag:yaml.org,2002:map', data.items())
    add_representer(OrderedDict, represent)
    return dump(config)


def config_list(regex):
    from pathlib import Path
    from mccode_antlr.config import config as c
    config_dir = Path(c.config_dir())
    d = {k: c[k].get() for k in list(c)}
    print(config_dump(d))


def config_get(key, verbose):
    from mccode_antlr.config import config as c
    if key:
        levels = key.split('.')
        depth = []
        for level in levels:
            if level in c:
                c = c[level]
                depth.append(level)
            elif verbose:
                print(f'Full key {key} not found in config.')
                print(f'  {level} not in {".".join(depth)}.{list(c)}')
                return
            else:
                return
    d = c.get()
    if key:
        d = {key: d}
    print(config_dump(d))


def _get_config_yaml(path: str | None = None):
    from pathlib import Path
    from yaml import safe_load
    from mccode_antlr.config import config

    config_file = Path(path or config.config_dir()) / 'config.yaml'
    if config_file.exists():
        with config_file.open('r') as f:
            return safe_load(f) or {}
    return {}


def _save_config_yaml(config_dict, path: str | None = None):
    from pathlib import Path
    from mccode_antlr.config import config

    config_file = Path(path or config.config_dir()) / 'config.yaml'
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with config_file.open('w') as f:
        f.write(config_dump(config_dict))


def config_set(key, value, path: str | None = None):
    """
    Set a configuration value both in the file and in memory.
    This function updates the existing configuration file to preserve
    other keys and only modify the specified key.
    """
    from mccode_antlr.config import config
    from pathlib import Path
    # Load existing file config if it exists
    existing_config = _get_config_yaml(path)

    # Navigate to the nested key and set the value
    levels = key.split('.')
    try:
        current = existing_config
        for level in levels[:-1]:
            if level not in current:
                current[level] = {}
            current = current[level]
        current[levels[-1]] = value
    except (KeyError, TypeError):
        print(f"Error setting key {key} in configuration.")
        return

    # Save the complete config
    _save_config_yaml(existing_config, path)

    # Also update the in-memory config if we're not modifying a different path
    if path is None or Path(path) == Path(config.config_dir()):
        try:
            c = config
            for level in levels[:-1]:
                c = c[level]
            c[levels[-1]] = value
        except (KeyError, TypeError):
            print(f"Error setting key {key} in in-memory configuration.")
            return


def config_unset(key, path: str | None = None):
    """
    Unset a configuration value both in the file and in memory.
    This function updates the existing configuration file to preserve
    other keys and only remove the specified key.
    """
    from mccode_antlr.config import config
    from pathlib import Path
    existing_config = _get_config_yaml(path)

    # Navigate to the nested key and delete it
    levels = key.split('.')
    current = existing_config
    try:
        for level in levels[:-1]:
            current = current[level]
        del current[levels[-1]]
    except (KeyError, TypeError):
        # Key doesn't exist in file config, that's okay
        pass

    # Save the complete config
    _save_config_yaml(existing_config, path)

    # Also update the in-memory config if we're not modifying a different path
    if path is None or Path(path) == Path(config.config_dir()):
        try:
            c = config
            for level in levels[:-1]:
                c = c[level]
            del c[levels[-1]]
        except (KeyError, TypeError):
            pass


def config_save(path: str | None = None, verbose: bool = False):
    from pathlib import Path
    from mccode_antlr.config import config as c
    config_dir = Path(path or c.config_dir())
    d = {k: c[k].get() for k in list(c)}
    config_file = config_dir.joinpath('config.yaml')
    with config_file.open('w') as file:
        file.write(config_dump(d))
    if verbose:
        print(f'Configuration written to {config_file}')


def add_config_management_parser(modes):
    parser = modes.add_parser(name='config', help='Manage the mccode-antlr configuration')
    actions = parser.add_subparsers(help='Action to perform', metavar='ACTION', required=True)
    l = actions.add_parser(name='list', help='print one or more configuration value to STDOUT')
    l.add_argument('regex', type=str, nargs='?', help='Select only keys matching this regular expression')
    l.set_defaults(action=config_list)

    g = actions.add_parser(name='get', help='Retrieve one configuration value')
    g.add_argument('key', type=str, nargs='?', help="'.' separated key (default full configuration)")
    g.add_argument('-v', '--verbose', action='store_true')
    g.set_defaults(action=config_get)

    s = actions.add_parser(name='set', help='Update or insert one configuration value')
    s.add_argument('key', type=str, default=None)
    s.add_argument('value', type=str, default=None)
    s.add_argument('path', type=str, nargs='?')
    s.set_defaults(action=config_set)

    u = actions.add_parser(name='unset', help='Remove one configuration value')
    u.add_argument('key', type=str, default=None)
    u.add_argument('path', type=str, nargs='?')
    u.set_defaults(action=config_unset)

    v = actions.add_parser(name='save', help='Create or update the configuration file')
    v.add_argument('path', type=str, nargs='?')
    v.add_argument('-v', '--verbose', action='store_true')
    v.set_defaults(action=config_save)
    return actions


def cache_path():
    from pooch import os_cache
    return os_cache(f'mccodeantlr')


def cache_remove(name, version, force):
    from shutil import rmtree
    path = cache_path()
    if name is not None:
        path = path.joinpath(name)
    if version is not None:
        path = path.joinpath(version)
    if not force:
        response = input(f'Remove {path} and all contents? [yN] ')
        if 'yes' == response.lower() or 'y' == response.lower():
            force = True
    if force:
        rmtree(path)


def cache_list(name, long):
    path = cache_path()
    if name is not None:
        path = path.joinpath(name)
    dirs = sorted([d for d in path.iterdir() if d.is_dir()], key=lambda x: x.name)
    dstr = '\n'.join(f'  {d if long else d.name}' for d in dirs)
    n = len(dirs)
    c = 'cache' if n == 1 else 'caches'
    print(f'{n} known {c} for {path.name}:\n{dstr}')


def add_cache_management_parser(modes):
    parser = modes.add_parser(name='cache', help='Manage the mccode-antlr cache')
    actions = parser.add_subparsers(help='Action to perform', metavar='ACTION', required=True)
    r = actions.add_parser(name='remove', help='Remove a named cache')
    r.add_argument('name', type=str, nargs='?', help='cache to remove [default all caches]')
    r.add_argument('version', type=str, nargs='?', help='version to remove [default all versions]')
    r.add_argument('-f', '--force', action='store_true')
    r.set_defaults(action=cache_remove)
    l = actions.add_parser(name='list', help='List named caches or the versions of one cache')
    l.add_argument('name', type=str, nargs='?')
    l.add_argument('-l', '--long', action='store_true')
    l.set_defaults(action=cache_list)
    return actions


def mccode_management_parser():
    """CLI interface to managing configuration and cache"""
    from argparse import ArgumentParser
    parser = ArgumentParser(prog="mccode-antlr",
                            description='Manage mccode-antlr')
    modes = parser.add_subparsers(title='mode', help='Mode')
    add_cache_management_parser(modes)
    add_config_management_parser(modes)
    return parser


def mccode_management():
    parser = mccode_management_parser()
    args = parser.parse_args()
    attrs = vars(args)  # convert from Namespace to dict
    action = attrs.pop('action')
    action(**attrs)


if __name__ == '__main__':
    mccode_management()