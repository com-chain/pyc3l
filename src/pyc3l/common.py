import os

def init_cache_dirs():
    """Create the cache directory if it doesn't exist and returns it's path."""

    if os.environ.get("PYC3L_CACHE_DIR"):
        PYC3L_CACHE_DIR = os.environ.get("PYC3L_CACHE_DIR")
    else:
        if os.geteuid() == 0:
            PYC3L_CACHE_DIR = "/var/cache/pyc3l"
        else:
            PYC3L_CACHE_DIR = os.path.expanduser("~/.cache/pyc3l")

    if not os.path.exists(PYC3L_CACHE_DIR):
        os.makedirs(PYC3L_CACHE_DIR)
    return PYC3L_CACHE_DIR
