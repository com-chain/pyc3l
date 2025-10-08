# -*- coding: utf-8 -*-

from kids.cache import cache

import os
import pickle
import fcntl
import time

from contextlib import contextmanager

from .common import init_cache_dirs


def dirty(method):
    """Decorator to mark DirtyDict as dirty on mutation methods."""
    def wrapper(self, *args, **kwargs):
        self._dirty = True
        return method(self, *args, **kwargs)
    return wrapper


class DirtyDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dirty = False

    @dirty
    def __setitem__(self, key, value):
        super().__setitem__(key, value)

    @dirty
    def __delitem__(self, key):
        super().__delitem__(key)

    @dirty
    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)

    @dirty
    def clear(self):
        super().clear()

    @dirty
    def pop(self, key, default=None):
        return super().pop(key, default)

    @dirty
    def popitem(self):
        return super().popitem()

    def setdefault(self, key, default=None):
        if key not in self:
            self._dirty = True
        return super().setdefault(key, default)

    def is_dirty(self):
        return self._dirty


@contextmanager
def locked_pickle_cache(path):
    # Open the file in read/write mode, create if not exists.
    try:
        f = open(path, 'r+b')
    except FileNotFoundError:
        f = open(path, 'w+b')
    with f:
        # Lock the file exclusively.
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            data = pickle.load(f)
            if not isinstance(data, dict):
                data = {}
        except (EOFError, pickle.UnpicklingError):
            data = {}
        cache = DirtyDict(data)
        yield cache
        # Save only if modified.
        if cache.is_dirty():
            f.seek(0)
            pickle.dump(dict(cache), f)
            f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)


@cache
class PersistentTTLCache(object):
    """Dict like key/value store that persists to disk.

    Only implements get/set/del methods.

    """

    def __init__(self, label, ttl):
        self.path = init_cache_dirs() + f"/pttl/{label}.pkl"
        dname = os.path.dirname(self.path)
        if not os.path.exists(dname):
            os.makedirs(dname)

        self.ttl = ttl

    def __getitem__(self, key):

        with locked_pickle_cache(self.path) as cache:
            ttl, value = cache[key]
            if (ttl is not None) and (time.time() - ttl > self.ttl):
                del cache[key]
                raise KeyError(key)
            return value

    def __setitem__(self, key, value):
        with locked_pickle_cache(self.path) as cache:
            cache[key] = (time.time(), value)

SUPPORTED_DECORATOR = {
    property: lambda f: f.fget,
    classmethod: lambda f: f.__func__,
    staticmethod: lambda f: f.__func__,
}

def qualname(func):
    """Returns the qualified name of a function or method, handling decorators."""
    for call_wrapper, unwrap in SUPPORTED_DECORATOR.items():
        if isinstance(func, call_wrapper):
            func = unwrap(func)
            break
    return func.__module__ + "." + func.__qualname__


def pcache(*cargs, **ckwargs):

    if "ttl" in ckwargs:
        ttl = ckwargs.pop("ttl")

    def wrapper(fn):
        object_name = qualname(fn)
        cache_store = PersistentTTLCache(object_name, ttl=ttl)
        return cache(use=cache_store, *cargs, **ckwargs)(fn)
    return wrapper
