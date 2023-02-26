import requests

import random
import datetime
import os.path
import logging
import tempfile
import os
import shutil
import traceback

from contextlib import closing

logger = logging.getLogger(__name__)


class ApiHandling:

    IPFS_CONFIG_PATH = "/ipns/QmaAAZor2uLKnrzGCwyXTSwogJqmPjJgvpYgpmtz5XcSmR/configs/"
    IPFS_NODE_LIST_PATH = "/ipns/QmcRWARTpuEf9E87cdA4FfjBkv7rKTJyfvsLFTzXsGATbL"
    API_PATH = "/api.php"
    DEFAULT_ENDPOINTS = [
        "https://node-cc-001.cchosting.org",
        "https://node-001.cchosting.org",
        "https://node-002.cchosting.org",
        "https://node-003.cchosting.org",
        "https://node-004.cchosting.org",
    ]

    def __init__(self, endpoint_file=None):
        """Constructor for this ApiHandling."""
        self._store = (
            SimpleFileStore(endpoint_file)
            if endpoint_file
            else StateFileStore("pyc3l", "endpoints.txt")
        )
        self._endpoints = None  ## cache and lazy loading

    @property
    def endpoints(self):
        if not self._endpoints:
            self._endpoints = set(self.load() or self.DEFAULT_ENDPOINTS[:])
        return self._endpoints

    def updateNodeRepo(self):
        for endpoint in random.sample(list(self.endpoints), k=len(self.endpoints)):
            logger.debug("try to get endpoint list from %r", endpoint)
            r = self.request(f"{endpoint}{self.IPFS_NODE_LIST_PATH}")
            if r is False:
                continue

            logger.info("getting endpoint list from %r", endpoint)
            new_endpoints = set(e[:-1] if e[-1] == "/" else e for e in r.json())
            if self.endpoints == new_endpoints:
                logger.info("saved endpoint list is already up-to-date.")
            else:
                removed = self.endpoints - new_endpoints
                added = new_endpoints - self.endpoints
                msg = "\n".join(
                    ["  - %s" % e for e in removed] + ["  + %s" % e for e in added]
                )
                logger.info("Updating endpoint list:\n%s", msg)

                logger.info("saved endpoint list is already up-to-date.")
                self.save(new_endpoints)
                self._endpoints = new_endpoints
            return
        raise Exception(
            "Unable to find a valid ipfs node. Please check that you are online."
        )

    def getIPFSEndpoint(self):
        for nb_try in range(1, 21):
            endpoint = random.choice(list(self.endpoints))
            if self.request(f"{endpoint}{self.IPFS_CONFIG_PATH}/ping.json"):
                return endpoint

        raise Exception("Unable to find a valid ipfs node after %d tries." % nb_try)

    def getCurrentBlock(self, endpoint=None):
        if not endpoint:
            endpoint = self.getApiEndpoint()
        r = requests.get(endpoint + "?_=" + str(datetime.datetime.now()))
        return r.text

    def getApiEndpoint(self):
        for nb_try in range(1, 21):
            endpoint = random.choice(list(self.endpoints))
            url = f"{endpoint}{self.API_PATH}"
            if self.request(url):
                logger.info("Selected endpoint: %r", endpoint)
                return url

        raise Exception("Unable to find a valid API endpoint after %d tries." % nb_try)

    def getServerContract(self, currency):
        endpoint = self.getIPFSEndpoint()
        now = str(datetime.datetime.now())
        url = f"{endpoint}{self.IPFS_CONFIG_PATH}/{currency}.json?{now}"
        r = requests.get(url)
        if r.status_code != 200:
            raise Exception("Unknown currency " + currency)
        server_data = r.json()["server"]

        return (
            server_data["contract_1"],
            server_data["contract_2"],
        )

    def request(self, url):
        now = str(datetime.datetime.now())
        url = f"{url}?_={now}"
        logger.debug("request to %r", url)
        try:
            r = requests.get(url)
        except Exception:
            logger.warn("Exception raised by %r:\n%s", url, format_last_exception())
            return False
        if r.status_code != 200:
            logger.warn("status %s from %r", str(r.status_code), url)
            return False
        return r

    def save(self, endpoints):
        self._store.save("\n".join(endpoints))

    def load(self):
        saved_data = self._store.load()
        if saved_data is None:
            return []
        return [e[:-1] if e[-1] == "/" else e for e in saved_data.split("\n")]


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

    def load(self):
        if not os.path.isfile(self._filename):
            return None
        with open(self._filename, "r") as file:
            return file.read()


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
