import confuse
from os import environ

# Try and simplify handling configuration values need for, e.g., compiling different versions of the runtimes
# under different operating systems, while allowing a user to 'easily' override defaults if necessary.
#
# Any platform independent configuration settings can go in 'config_default.yaml'
config = confuse.LazyConfig('mccodeantlr', __name__)

# use environment variables specified as 'MCCODEANTLR_XYZ' as configuration entries 'xyz'
config.set_env()


# Add platform specific values from the local config_platforms.yaml
def _platform_defaults():
    import platform
    import yaml
    from importlib.resources import files, as_file

    platforms_file = files(__name__).joinpath('platforms.yaml')
    if not platforms_file.is_file():
        raise RuntimeError(f"Can not locate platforms.yaml in module files (looking for {platforms_file}")

    with as_file(platforms_file) as file:
        with open(file, 'r', encoding='utf-8') as data:
            platform_configs = yaml.safe_load(data)

    system = platform.system()  # "Linux", "Darwin", "Windows", ...
    if system not in platform_configs:
        raise RuntimeError(f"Unknown system '{system}' for default configuration")

    return platform_configs[system]


def _common_defaults():
    import yaml
    from importlib.resources import files, as_file

    common_file = files(__name__).joinpath('config_default.yaml')
    if not common_file.is_file():
        raise RuntimeError(f"Can not locate config_default.yaml in module files (looking for {common_file})")
    with as_file(common_file) as file:
        with open(file, 'r', encoding='utf-8') as data:
            common_configs = yaml.safe_load(data)

    return common_configs


def registry_defaults(libc_registry, projects: list[str]):
    """Add values for @MCCODE_*@ expansion based on the in-use LIBC registry"""
    from datetime import datetime, timezone

    def version_macro():
        from packaging.version import Version, InvalidVersion
        try:
            v = Version(libc_registry.version)
            return (v.major * 100 + v.minor) * 1000 + v.micro
        except InvalidVersion:
            return 399999  # 3.99.999 to match McCode default (MCVERSION not set)

    configs = {project: {} for project in projects}
    for project in configs.values():
        project['string'] = str(libc_registry).replace('\n', '')
        project['version'] = libc_registry.version
        project['version_macro'] = version_macro()
        project['date'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Override any configurations in case this is called more than once with different information
    config.set(configs)


# By using the 'add' method, we set these as the *lowest* priority. Any user/system files will override:
config.add(_platform_defaults())
#
config.add(_common_defaults())

# Allow overriding with pseudo-standard environment variables:
for env in ('CC',):
    if env in environ:
        config[env.lower()] = environ[env]
