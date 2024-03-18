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
                                                             "delegate", "transferOnBehalfOf",
                                                             "enable", "disable"]:
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
                ## XXXvlab: ``getTransactionInfo`` should not be on ``Currency`` objects,
                ## this shows why: here we have to create a dummy currency just to get
                ## access to the endpoint api mecanism.
                return pyc3l_instance.Currency("").getTransactionInfo(self.address)

            @property
            def block(self):
                ## XXXvlab: ``getTransactionBLock`` should not be on ``Currency`` objects,
                ## this shows why: here we have to create a dummy currency just to get
                ## access to the endpoint api mecanism.
                return pyc3l_instance.Currency("").getTransactionBLock(self.address)

            @property
            def pending(self):
                return self.block is None

        return Pyc3lTransaction(address)

