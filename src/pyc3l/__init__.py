#

import logging
import time

from .wallet import Wallet
from .ApiCommunication import ApiCommunication
from .ApiHandling import ApiHandling, Endpoint

logger = logging.getLogger(__name__)


NONE = {}


class WalletLocked(Exception): pass


class AddressableObject:

    def __init__(self, address):
        self.address = address


class Account(AddressableObject): pass
class Transaction(AddressableObject): pass


class Pyc3l:

    def __init__(self, endpoint=None):
        self._endpoint_last_usage = None
        if endpoint:
            logger.info(f"endpoint: {endpoint} (fixed)")
            self._endpoint = Endpoint(endpoint)
            self._endpoint_resolver = None
        else:
            self._endpoint = None
            self._endpoint_resolver = ApiHandling()

    @property
    def endpoint(self):
        if self._endpoint_resolver is not None:
            now = time.time()
            if self._endpoint and now - self._endpoint_last_usage > 2 * 60:
                self._endpoint = None
                logger.info("Re-selection of an endpoint triggered")
            self._endpoint_last_usage = now
            if self._endpoint is None:
                self._endpoint = self._endpoint_resolver.endpoint
                logger.info(f"endpoint: {self._endpoint} (elected)")
        return self._endpoint

    @property
    def ipfs_endpoint(self):
        if self._endpoint_resolver is not None:
            return self._endpoint_resolver.ipfs_endpoint
        return self._endpoint


    ## Blockchain operation

    def getBlockNumber(self):
        return self.endpoint.api.post()

    def getTransactionBlock(self, transaction_hash):
        info = self.getTransactionInfo(transaction_hash)
        return info["transaction"]["blockNumber"]

    def getTransactionInfo(self, transaction_hash):
        data = {"hash": transaction_hash}

        r = self.endpoint.api.post(data=data)
        ## XXXvlab: seems to need to be parsed twice (confirmed upon
        ## reading the code of the comchain API).
        if isinstance(r, str):
            import json

            r = json.loads(r)
        return r

    ## XXXvlab: these only need endpoints, they should not be on currency
    def getTrInfos(self, address):
        return self.endpoint.api.post(data={"txdata": address})


    def getAccountEthBalance(self, address):
        return self.endpoint.api.post(data={"balance": address})['balance']

    def hasChangedBlock(self, do_reset=False):
        new_current_block = self.getBlockNumber()
        res = new_current_block != self._current_block
        if do_reset:
            self._current_block = new_current_block
        return res

    def registerCurrentBlock(self):
        self.hasChangedBlock(do_reset=True)


    ## Sub-objects

    def Currency(pyc3l_instance, name):
        class Pyc3lCurrency(ApiCommunication):

            def Account(pyc3l_currency, address):

                class Pyc3lCurrencyAccount(Account):

                    def __getattr__(self, label):
                        if label.startswith("getAccount"):
                            method = getattr(pyc3l_currency, label, NONE)
                            if method is not NONE:
                                return lambda: method(self.address)
                        method = getattr(pyc3l_currency, f"getAccount{label}", NONE)
                        if method is not NONE:
                            return method(self.address)
                        if label.endswith("s"):
                            method = getattr(pyc3l_currency, f"get{label[:-1]}List", NONE)
                            if method is not NONE:
                                return method(self.address)
                        raise AttributeError()

                return Pyc3lCurrencyAccount(address)

            @property
            def symbol(self):
                return self.metadata["server"]["currencies"]["CUR"]

        return Pyc3lCurrency(name, pyc3l_instance)

    @property
    def Wallet(pyc3l_instance):

        class Pyc3lWallet(Wallet):

            @property
            def currency(self):
                return pyc3l_instance.Currency(self._wallet["server"]["name"])

            @property
            def account(self):
                return self.currency.Account(self.address)

            def __getattr__(self, label):
                method = getattr(self.account, label, NONE)
                if method is not NONE:
                    return method
                if label.startswith("transfer") or label in ["lockUnlockAccount", "pledge",
                                                             "delegate", "transferOnBehalfOf"]:
                    if not self._account:
                        raise WalletLocked("Wallet is required to be unlocked")
                    method = getattr(self.currency, label, NONE)
                    if method is not NONE:
                        return lambda *args, **kwargs: method(self._account, *args, **kwargs)
                raise AttributeError(label)

        return Pyc3lWallet

    def Transaction(pyc3l_instance, address):

        class Pyc3lTransaction(Transaction):

            @property
            def data(self):
                return pyc3l_instance.getTransactionInfo(self.address)

            @property
            def block(self):
                return pyc3l_instance.getTransactionBlock(self.address)

            @property
            def pending(self):
                return self.block is None

        return Pyc3lTransaction(address)

