import requests

import json
from random import randrange
import datetime
import os.path
import logging
import tempfile
import os
import shutil
from contextlib import closing

logger = logging.getLogger(__name__)


class ApiHandling:
    def __init__(self, endpoint_file=None):
        """Constructor for this ApiHandling."""
        if not endpoint_file:
            home = os.path.expanduser("~")

            xdg_state_home = os.environ.get("XDG_STATE_HOME") or os.path.join(
                home, ".local", "state"
            )

            self.endpoint_file = os.path.join(
                xdg_state_home, "pyc3l", "current_endpoints.txt"
            )
        else:
            self.endpoint_file = endpoint_file
        self.default_endpoints = [
            "https://node-cc-001.cchosting.org",
            "https://node-001.cchosting.org",
            "https://node-002.cchosting.org",
            "https://node-003.cchosting.org",
            "https://node-004.cchosting.org",
        ]
        self.ipfs_config_url = (
            "/ipns/QmaAAZor2uLKnrzGCwyXTSwogJqmPjJgvpYgpmtz5XcSmR/configs/"
        )
        self.ipfs_node_list_url = "/ipns/QmcRWARTpuEf9E87cdA4FfjBkv7rKTJyfvsLFTzXsGATbL"
        self.api_url = "/api.php"
        self._endpoints = None

    @property
    def endpoints(self):
        if not self._endpoints:
            self._endpoints = self._read_endpoints()
        return self._endpoints

    def updateNodeRepo(self):
        endpoints = self.endpoints[:]
        while len(endpoints) > 0:
            index = randrange(len(endpoints))
            url = (
                endpoints[index]
                + self.ipfs_node_list_url
                + "?_="
                + str(datetime.datetime.now())
            )
            logger.info("getting node list from %r", url)
            try:
                r = requests.get(url)
            except:
                logger.warn("exception raised by %r", url)
                del endpoints[index]
                continue
            if r.status_code == 200:
                self._save_endpoints(r.json())
                return
            logger.warn("return status %d for %r", r.status_code, url)
        raise Exception(
            "Unable to find a valid ipfs node. Please check that you are online."
        )

    def getIPFSEndpoint(self):
        for nb_try in range(1, 21):
            index = randrange(len(self.endpoints))
            endpoint = self.endpoints[index]
            url = (
                endpoint
                + self.ipfs_config_url
                + "/ping.json?_="
                + str(datetime.datetime.now())
            )
            try:
                r = requests.get(url=url)
            except:
                logger.warn("Exception raised from %r", url)
                continue
            if r.status_code == 200:
                return endpoint
            else:
                logger.warn("status %d from %r", r.status_code, url)

        raise Exception("Unable to find a valid ipfs node after %d tries." % nb_try)

    def getCurrentBlock(self, endpoint=None):
        if not endpoint:
            endpoint = self.getApiEndpoint()
        r = requests.get(endpoint + "?_=" + str(datetime.datetime.now()))
        return r.text

    def getApiEndpoint(self):
        for nb_try in range(1, 21):
            index = randrange(len(self.endpoints))
            endpoint = self.endpoints[index]
            url = endpoint + self.api_url + "?_=" + str(datetime.datetime.now())
            try:
                r = requests.get(url)
            except:
                logger.warn("Exception raised by %r", url)
                continue
            if r.status_code == 200:
                logger.info("Selected endpoint: %r", endpoint)
                return endpoint + self.api_url
            logger.warn("status %s from %r", str(r.status_code), url)

        raise Exception("Unable to find a valid API endpoint after %d tries." % nb_try)

    def getServerContract(self, server_name):
        endpoint = self.getIPFSEndpoint()
        r = requests.get(
            url=endpoint
            + self.ipfs_config_url
            + "/"
            + server_name
            + ".json?"
            + str(datetime.datetime.now())
        )
        if r.status_code != 200:
            raise Exception("Unknown server " + server_name)
        server_data = r.json()["server"]

        return (
            server_data["contract_1"],
            server_data["contract_2"],
        )

    def _save_endpoints(self, endpoints):
        """Save endpoints in state file

        This implementation is atomic and thus race-condition free.

        """
        if set(self.endpoints) == set(endpoints):
            logger.info("Saved endpoint list is already up-to-date.")
            return
        f, tmp = tempfile.mkstemp()
        with closing(os.fdopen(f, "w")) as file:
            for line in endpoints:
                file.write(line + "\n")
        if not os.path.isfile(self.endpoint_file):
            logger.info("Create local endpoint file named %r.", self.endpoint_file)
            os.makedirs(os.path.dirname(self.endpoint_file), exist_ok=True)
        shutil.move(tmp, self.endpoint_file)  ## atomic
        self._endpoints = endpoints

    def _read_endpoints(self):
        if not os.path.isfile(self.endpoint_file):
            return self.default_endpoints
        with open(self.endpoint_file, "r") as file:
            lines = file.readlines()

        # remove the endline char
        for index in range(len(lines)):
            lines[index] = lines[index][:-1]

        return lines
