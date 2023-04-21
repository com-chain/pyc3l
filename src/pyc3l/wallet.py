import json
import logging

from eth_account import Account


logger = logging.getLogger(__name__)


class Wallet(object):

    def __init__(self, wallet):
        logger.info(
            "Load wallet with address 0x%s on server %r",
            wallet["address"],
            wallet["server"]["name"],
        )
        self._wallet = wallet
        self._account = None

    @classmethod
    def from_file(cls, filename):
        logger.info("Opening file %r", filename)
        return cls(json.load(open(filename)))

    @classmethod
    def from_json(cls, json_string):
        logger.info("Parsing JSON (size: %s)", len(json_string))
        return cls(json.loads(json_string))

    def unlock(self, password):
        self._account = Account.privateKeyToAccount(
            Account.decrypt(self._wallet, password)
        )

    @property
    def address(self):
        return self._wallet["address"]



