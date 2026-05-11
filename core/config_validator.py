"""
Simorgh - Config validation
"""


class ConfigError(Exception):
    pass


DEFAULTS = {
    "listen_host": "127.0.0.1",
    "listen_port": 1080,
    "max_connections": 200,
    "connection_timeout": 30,
    "auth": {
        "enabled": False,
        "username": "",
        "password": "",
    },
    "fragment": {
        "enabled": True,
        "min_size": 10,
        "max_size": 40,
        "delay_min": 0.01,
        "delay_max": 0.05,
        "randomize_order": False,
    },
    "logging": {
        "level": "INFO",
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (non-destructive)."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def validate_and_fill(config: dict) -> dict:
    """Merge user config with defaults and validate critical fields."""
    config = deep_merge(DEFAULTS, config)

    # Port range
    port = config.get("listen_port")
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise ConfigError(f"listen_port must be an integer between 1-65535, got: {port!r}")

    # Auth validation
    auth = config.get("auth", {})
    if auth.get("enabled"):
        if not auth.get("username") or not auth.get("password"):
            raise ConfigError("auth.enabled is true but username/password are missing")

    # Fragment validation
    frag = config.get("fragment", {})
    if frag.get("min_size", 1) < 1:
        raise ConfigError("fragment.min_size must be >= 1")
    if frag.get("max_size", 1) < frag.get("min_size", 1):
        raise ConfigError("fragment.max_size must be >= fragment.min_size")
    if frag.get("delay_min", 0) < 0:
        raise ConfigError("fragment.delay_min must be >= 0")
    if frag.get("delay_max", 0) < frag.get("delay_min", 0):
        raise ConfigError("fragment.delay_max must be >= fragment.delay_min")

    # Max connections
    max_conn = config.get("max_connections", 200)
    if not isinstance(max_conn, int) or max_conn < 1:
        raise ConfigError("max_connections must be a positive integer")

    return config
