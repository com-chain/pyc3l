import requests

import random
import datetime
import os.path
import logging
import tempfile
import os
import shutil
import traceback
import time
import itertools

from contextlib import closing


from .pcache import pcache

logger = logging.getLogger(__name__)


class HTTPError(Exception): pass

class APIError(Exception): pass

class APIErrorNoMessage(APIError): pass


def urlencode_prepare_dict(dct):
    """Flattens nested dict to support urlencode

    Non nested dicts are unchanged:
    
    >>> urlencode_prepare_dict({"a": 1})
    {'a': 1}

    But nested dicts will be flatten to be encoded in URL
    or ``application/x-www-form-urlencode`` POST bodies:

    >>> urlencode_prepare_dict({"a": {"b": 1}})
    {'a[b]': 1}

    >>> urlencode_prepare_dict({"a": {"b": 1}, "c": 2})
    {'a[b]': 1, 'c': 2}

    """
    def flatten_dict(d, parent_key=""):
        nd = {}
        for k, v in d.items():
            new_key = f"{parent_key}[{k}]" if parent_key else k
            if isinstance(v, dict):
                nd.update(flatten_dict(v, new_key))
            else:
                nd[new_key] = v
        return nd

    return flatten_dict(dct)


class BaseEndpoint(object):
    """Simple request shortcut

    This object keeps the base url of an endpoint and allows
    to call `requests` by specifying only the `path` part:

    Let's setup the mock to see how it calls `requests`:

        >>> import minimock
        >>> minimock.mock('requests.get')
        >>> minimock.mock('requests.post')

    Instantiate by specifying the base url:

        >>> e = BaseEndpoint('http://example.com')
        >>> e.get('/path', 1, 2, foo="bar")
        Called requests.get('http://example.com/path', 1, 2, foo='bar')
        >>> e.post('/path', 1, 2, foo="bar")
        Called requests.post('http://example.com/path', 1, 2, foo='bar')

    We can see that positional arguments and keyword arguments are
    correctly sent to `requests.*` methods.

        >>> minimock.restore()

    """

    def __init__(self, url):
        self._url = url

    def __getattr__(self, label):
        if label not in ["get", "post"]:
            raise AttributeError()

        def r(*args, **kwargs):
            if len(args):
                args = list(args)
                args[0] = f"{self._url}{args[0]}"
            else:
                args = [f"{self._url}"]
            logger.debug("Request %s %s %r" % (
                label.upper(),
                args[0],
                kwargs
            ))
            if "data" in kwargs:
                kwargs["data"] = urlencode_prepare_dict(kwargs["data"])
            res = getattr(requests, label)(*args, **kwargs)
            logger.debug("  Response [%s]: %d bytes" % (
                res.status_code,
                len(res.text),
            ))
            if res.status_code != 200:
                raise HTTPError("%s %s ERROR (%s)" % (
                    label.upper(),
                    args[0],
                    res.status_code
                    ))
            try:
                data = res.json()
            except Exception:
                raise Exception("%s %s ERROR (Not JSON data)" % (
                    label.upper(),
                    self._url,
                ))

            if not isinstance(data, dict):
                return data

            if data.get("error", False):
                data_msg = f" (data: {data.get('data')})" if data['data'] else ""
                if data['msg']:
                    raise APIError(f"API Call failed with message: {data['msg']}{data_msg}")
                raise APIErrorNoMessage(f"API Call failed without message: JSON: {data}")
            if "data" in data:
                return data["data"]
            return data

        return r


class TTLCacheBaseEndpoint(BaseEndpoint):
    def __init__(self, url, ttl=60):
        super(TTLCacheBaseEndpoint, self).__init__(url)
        self._ttl = ttl

    def __getattr__(self, label):
        if label in ["get", "post"]:
            return pcache(ttl=self._ttl)(super(TTLCacheBaseEndpoint, self).__getattr__(label))
        return super(TTLCacheBaseEndpoint, self).__getattr__(label)


class Endpoint(BaseEndpoint):

    URLS = {
        "api": "/api.php",
        "pool": "/pool.php",
        "config": ("/ipns/QmaAAZor2uLKnrzGCwyXTSwogJqmPjJgvpYgpmtz5XcSmR/configs/", 3*60*60 ),   ## 3 hours
        "endpoint_list": ("/ipns/QmcRWARTpuEf9E87cdA4FfjBkv7rKTJyfvsLFTzXsGATbL", 24*60*60 * 7), ## 7 days
        "keys": "/keys.php",
        "transactions": "/trnslist.php",
        "lost_transactions": "/lost_trn.php",
        "block": "/block.php",
    }

    def __init__(self, url):
        self._url = url

    def __getattr__(self, label):
        if label in ["get", "post"]:
            return super(Endpoint, self).__getattr__(label)
        if label in self.URLS.keys():
            if isinstance(self.URLS[label], tuple):
                path, ttl = self.URLS[label]
                return TTLCacheBaseEndpoint(f"{self._url}{path}", ttl)
            else:
                path = self.URLS[label]
                return BaseEndpoint(f"{self._url}{path}")
        raise AttributeError()

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._url!r}>"

    def __str__(self):
        return self._url

    def __hash__(self):
        return hash(self._url)

    def __eq__(self, value):
        return isinstance(value, Endpoint) and self._url == value._url


def random_picker(elts):
    """Iterator giving endless random pick in given set of elts

    Don't forget to set the seed if you expect to give you a different
    set after recreating the iterator.

    """
    while True:
        yield random.choice(elts)


def first(elts, predicate):
    return next(filter(predicate, elts))


def first_pick(elts, predicate, max_retries=20):
    return first(
        itertools.islice(elts, 0, max_retries),
        predicate,
    )


class ApiHandling(object):

    DEFAULT_ENDPOINTS = [
        "https://node-cc-001.cchosting.org",
        "https://node-001.cchosting.org",
        "https://node-002.cchosting.org",
        "https://node-003.cchosting.org",
        "https://node-004.cchosting.org",
    ]
    UPDATE_INTERVAL = 60 * 15  ## in sec

    def __init__(self, endpoint_file=None, max_retries=20):
        self._store = (
            SimpleFileStore(endpoint_file)
            if endpoint_file
            else StateFileStore("pyc3l", "endpoints.txt")
        )
        self._mtime = 0  ## cache and lazy loading
        self._max_retries = max_retries
        self._endpoints = None

    @property
    def endpoints(self):
        if not self._endpoints:
            self._endpoints, self._mtime = self._load()
        if self._endpoints is None:
            self._endpoints = set(Endpoint(e) for e in self.DEFAULT_ENDPOINTS)
        if time.time() - self._mtime < self.UPDATE_INTERVAL:
            return self._endpoints

        logger.info("endpoint list is obsolete, requesting update of list")
        if not self._update(force=True):
            logger.warn("endpoint list update failed, keeping old list")

        return self._endpoints

    def _update(self, force=False):
        logger.info("updating endpoint list")
        ## Avoid to use self.endpoints for recursivity reasons
        endpoints = (
            self._endpoints
            or self._load()[0]
            or set(Endpoint(e) for e in self.DEFAULT_ENDPOINTS)
        )
        for endpoint in random.sample(list(endpoints), k=len(endpoints)):
            logger.debug("  Try to get endpoint list from %r", endpoint)
            r = self._safe_req(endpoint.endpoint_list.get)
            if r is not False:
                break

        if r is False:
            logger.error("Failed to get new endpoint list.")
            return False

        logger.info("  Got endpoint list from %r", endpoint)
        new_endpoints = set(Endpoint(e[:-1] if e[-1] == "/" else e) for e in r)
        modified = endpoints != new_endpoints
        if not force and not modified:
            logger.info("saved endpoint list is already up-to-date.")
            return

        if modified:
            removed = endpoints - new_endpoints
            added = new_endpoints - endpoints
            msg = "\n".join(
                sorted(["  - %s" % e for e in removed] + ["  + %s" % e for e in added])
            )
            logger.info("  Updating endpoint list:\n%s", msg)
        else:
            logger.info("  Update endpoint last modification time.")

        self._save(new_endpoints)
        return True

    def _first_pick_endpoints(self, predicate, max_retries):
        random.seed(time.time())
        endpoint = first_pick(random_picker(list(self.endpoints)), predicate, max_retries)
        if endpoint:
            return endpoint
        raise Exception(
            f"No endpoint found able to fullfill predicate after {max_retries} retries."
        )

    @property
    def ipfs_endpoint(self):
        return self._first_pick_endpoints(
            lambda e: self._safe_req(e.config.get, "ping.json") is not False, self._max_retries
        )

    @property
    def endpoint(self):
        return self._first_pick_endpoints(
            lambda e: self._safe_req(e.api.get), self._max_retries
        )

    def _safe_req(self, method, path=""):
        try:
            r = method(f"{path}?_={datetime.datetime.now()}")
        except Exception as e:
            logger.warn("request raised exception: %s", e)
            return False
        return r

    def _save(self, endpoints):
        self._store.save("\n".join(["%s" % e for e in endpoints]))
        self._endpoints = endpoints
        self._mtime = time.time()

    def _load(self):
        saved_data, last_mtime = self._store.load(with_mtime=True)
        if saved_data is None:
            return set(), last_mtime
        endpoints = set(
            Endpoint(e[:-1] if e[-1] == "/" else e)
            for e in saved_data.strip().split("\n")
        )
        logger.info(
            "read local list of endpoint: %d endpoints, last mtime: %s",
            len(endpoints),
            datetime.datetime.utcfromtimestamp(last_mtime).isoformat(),
        )
        return (
            endpoints,
            last_mtime,
        )


class SimpleFileStore:
    """Manage saving and loading text data in file

    The class constructor takes a filename as input, which represents
    the name of the file where data will be saved.

        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     store = SimpleFileStore(f"{tmpdir}/data.txt")
        ...     store.save("Hello, World!")
        ...     store.load()
        'Hello, World!'

    Take care of creating directory if not existent.

        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     store = SimpleFileStore(f"{tmpdir}/a/b/c/data.txt")
        ...     store.save("Hello, World!")
        ...     store.load()
        'Hello, World!'

    Creation of the directory happens on save only.

        >>> import os
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     store = SimpleFileStore(f"{tmpdir}/data.txt")
        ...     os.path.isfile(f"{tmpdir}/data.txt")
        False

    Load will return ``None`` if file is not existent (nothing was never saved).

        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     store = SimpleFileStore(f"{tmpdir}/a/b/c/data.txt")
        ...     store.load() is None
        True

    Ensure atomicity by using a temporary file and use move (atomic)
    to replace the target file. This also ensure that only fully
    written file will be saved.

    - This class is best used for small to medium-sized files since it
      reads and writes the entire file into memory at once.

    - The class assumes that the file will contain text data. If
      binary data needs to be saved, the file should be opened in
      binary mode.

    """

    def __init__(self, filename):
        self._filename = filename

    def save(self, content):
        """Save endpoints in file"""
        f, tmp = tempfile.mkstemp()
        with closing(os.fdopen(f, "w")) as file:
            file.write(content)
        if not os.path.isfile(self._filename):
            logger.info("Create local endpoint file named %r.", self._filename)
            os.makedirs(os.path.dirname(self._filename), exist_ok=True)
        shutil.move(tmp, self._filename)  ## atomic

    def load(self, with_mtime=False):
        if not os.path.isfile(self._filename):
            return (None, 0) if with_mtime else None
        with open(self._filename, "r") as file:
            data = file.read()
        return (data, os.path.getmtime(self._filename)) if with_mtime else data


class StateFileStore(SimpleFileStore):
    """Manage saving and loading data in file in state directory

     It will use XDG_STATE_HOME environment variable if available

         >>> import tempfile, os
         >>> with tempfile.TemporaryDirectory() as tmpdir:
         ...     os.environ["XDG_STATE_HOME"] = tmpdir
         ...     store = StateFileStore("bar", "foo")
         ...     store._filename == f"{tmpdir}/bar/foo"
         True

     Otherwise will fallback on ``~/.local/state/{group}/{name}``

         >>> with tempfile.TemporaryDirectory() as tmpdir:
         ...     del os.environ["XDG_STATE_HOME"]
         ...     os.environ["HOME"] = tmpdir
         ...     store = StateFileStore("bar", "foo")
         ...     store._filename == f"{tmpdir}/.local/state/bar/foo"
         True

    It'll get all the features of SimpleFileStore:

         >>> import tempfile
         >>> with tempfile.TemporaryDirectory() as tmpdir:
         ...     os.environ["XDG_STATE_HOME"] = tmpdir
         ...     store = StateFileStore("bar", "data.txt")
         ...     assert not os.path.isfile(store._filename)  ## doesn't exist yet
         ...     store.save("Hello, World!")
         ...     assert os.path.isfile(store._filename)      ## created
         ...     store.load()
         'Hello, World!'


    """

    def __init__(self, group, name):
        xdg_state_home = os.environ.get("XDG_STATE_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "state"
        )

        super(StateFileStore, self).__init__(os.path.join(xdg_state_home, group, name))


def format_last_exception(prefix="  | "):
    """Format the last exception for display it in tests.

    This allows to raise custom exception, without loosing the context of what
    caused the problem in the first place:

    >>> def f():
    ...     raise Exception("Something terrible happened")
    >>> try:  ## doctest: +ELLIPSIS
    ...     f()
    ... except Exception:
    ...     formated_exception = format_last_exception()
    ...     raise ValueError('Oups, an error occured:\\n%s' % formated_exception)
    Traceback (most recent call last):
    ...
    ValueError: Oups, an error occured:
      | Traceback (most recent call last):
    ...
      | Exception: Something terrible happened

    """

    return "\n".join(
        str(prefix + line) for line in traceback.format_exc().strip().split("\n")
    )
