#

import logging
import time
import codecs
import datetime

## Monkey-patching parsimonious 0.8 to support Python 3.11

import sys
import inspect

# Check if we're running on Python 3.11 or later
if sys.version_info >= (3, 11):
    # Implement a getargspec function using getfullargspec for compatibility
    def getargspec(func):
        full_argspec = inspect.getfullargspec(func)
        args = full_argspec.args
        varargs = full_argspec.varargs
        varkw = full_argspec.varkw
        defaults = full_argspec.defaults
        return inspect.ArgSpec(args, varargs, varkw, defaults)

    # Monkey patch the inspect module
    inspect.getargspec = getargspec

## End of monkey-patching parsimonious


from web3 import Web3
from web3.eth import Eth
import eth_abi

from .wallet import Wallet
from .ApiCommunication import ApiCommunication, ComChainABI
from .ApiHandling import ApiHandling, Endpoint

logger = logging.getLogger(__name__)


NONE = {}


def decode_data(abi_types, data):
    unique = False
    if isinstance(abi_types, str):
        unique = True
        abi_types = [abi_types]
    if data.startswith("0x"):
        data = data[2:]

    if len(data) == 0:
        return None

    try:
        data_buffer = bytes.fromhex(data)
    except ValueError:
        raise ValueError("Invalid data provided: not a hex string")

    if len(data_buffer) % 32 != 0:
        raise ValueError("Invalid data provided: data length is not a multiple of 32")

    res = eth_abi.decode(abi_types, data_buffer)
    if unique:
        return res[0]
    return res




class WalletLocked(Exception): pass


class AddressableObject:

    def __init__(self, address):
        self.address = address[2:] if address.startswith("0x") else address


class Account(AddressableObject): pass
class Transaction(AddressableObject): pass
class Block(AddressableObject): pass


class Pyc3l:

    def __init__(self, endpoint=None):
        self._additional_nonce = 0

        self._current_block = 0

        self._endpoint_last_usage = None

        if endpoint:
            logger.info(f"endpoint: {endpoint} (fixed)")
            self._endpoint = Endpoint(endpoint)
            self._endpoint_resolver = None
        else:
            self._endpoint = None
            self._endpoint_resolver = ApiHandling()

    @property
    def endpoints(self):
        if self._endpoint_resolver is not None:
            return self._endpoint_resolver.endpoints
        return [self._endpoint]

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

    ## Blockchain information

    def getBlockNumber(self):
        return self.endpoint.api.post()

    def getTransactionBlock(self, transaction_hash):
        info = self.getTransactionInfo(transaction_hash)
        return info["transaction"]["blockNumber"]

    def getTransactionInfo(self, transaction_hash):
        data = {"hash": f"0x{transaction_hash}"}

        r = self.endpoint.api.post(data=data)
        ## XXXvlab: seems to need to be parsed twice (confirmed upon
        ## reading the code of the comchain API).
        if isinstance(r, str):
            import json

            r = json.loads(r)
        return r

    def getBlockInfo(self, block_number):
        """Get block transactions from block_number in hex without 0x in front"""
        idx = 0
        while True:
            try:
                yield self.endpoint.block.get(params={
                    "block": f"0x{block_number}",
                    "index": hex(idx),
                })
            except Exception as e:
                break
            idx += 1

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

    def read(self, fn, args, abi_return_type="int256"):
        data = {
            "ethCall": {
                "to": fn[0],  ## contract
                "data": fn[1] + "".join(
                    (v[2:] if v.startswith("0x") else v).zfill(64)
                    for v in args
                )
            }
        }
        try:
            result = self.endpoint.api.post(data=data)
        except Exception as e:
            logger.error(
                "Unexpected failure of ethCall " +
                f"contract: 0x{fn[0]}, fn: 0x{fn[1]}, args: {args!r}"
            )
            raise e
        if abi_return_type is None:
            return result
        return decode_data(abi_return_type, result)

    def get_element_in_list(self, map_fn, amount_fn, caller_address,
                            idx, dct, idx_min):
        if idx < idx_min:
            return dct
        data = self.read(map_fn, [caller_address, hex(idx)], None)
        amount = self.read(amount_fn, [caller_address, data]) / 100.0

        address = "0x" + data[-40:]
        dct[address] = amount
        return self.get_element_in_list(
            map_fn, amount_fn,
            caller_address, idx - 1, dct, idx_min
        )

    ## Blockchain transaction

    def send_transaction(
            self,
            fn,
            data,
            account,
            ciphered_message_from="",
            ciphered_message_to="",
    ):
        tr_infos = self.getTrInfos(account.address)
        gas_price = int(tr_infos["gasprice"], 0)
        gas_price_gwei = Web3.fromWei(gas_price, "gwei")
        nonce = int(tr_infos["nonce"], 0)
        logger.info(f"Gas price: {gas_price!r} wei ({gas_price_gwei} gwei), Nonce: {nonce!r}")
        transaction = {
            "to": fn[0],
            "value": 0,
            # "gas": 2500000,
            "gas": 5000000,
            "gasPrice": gas_price,
            "nonce": self.update_nonce(nonce),
            "data": fn[1] + data,
            "from": account.address,
        }

        signed = Eth.account.signTransaction(transaction, account.privateKey)
        str_version = (
            "0x" + str(codecs.getencoder("hex_codec")(signed.rawTransaction)[0])[2:-1]
        )
        raw_tx = {"rawtx": str_version}

        if ciphered_message_from != "":
            raw_tx["memo_from"] = ciphered_message_from

        if ciphered_message_to != "":
            raw_tx["memo_to"] = ciphered_message_to

        return self.endpoint.api.post(data=raw_tx)

    def update_nonce(self, nonce):
        if not self.hasChangedBlock(do_reset=True):
            self._additional_nonce = self._additional_nonce + 1
            return nonce + self._additional_nonce
        else:
            self._additional_nonce = 0
            return nonce

    ## Sub-objects

    def Currency(pyc3l_instance, name):
        class Pyc3lCurrency(ApiCommunication):

            def Account(pyc3l_currency, address):

                class Pyc3lCurrencyAccount(Account):

                    def __getattr__(self, label):
                        label = label[0].upper() + label[1:]
                        if label.startswith("getAccount"):
                            method = getattr(pyc3l_currency, label, NONE)
                            if method is not NONE:
                                return lambda: method(self.address)
                        method = getattr(pyc3l_currency, f"getAccount{label}", NONE)
                        if method is NONE:
                            method = getattr(pyc3l_instance, f"getAccount{label}", NONE)
                        if method is not NONE:
                            return method(self.address)
                        if label.endswith("s"):
                            method = getattr(pyc3l_currency, f"get{label[:-1]}List", NONE)
                            if method is not NONE:
                                return method(self.address)
                        raise AttributeError(label)

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
                if not hasattr(self, "_data"):
                    self._data = pyc3l_instance.getTransactionInfo(self.address)
                return self._data

            @property
            def is_cc_transaction(self):
                return "status" in self.data

            @property
            def block(self):
                return self.data["transaction"]["blockNumber"]

            @property
            def received_at(self):
                if not self.is_cc_transaction:
                    return False
                res = int(self.data["time"])
                return datetime.datetime.utcfromtimestamp(res)

            @property
            def currency(self):
                res = self.data.get("currency")
                if res is None:
                    return None
                return pyc3l_instance.Currency(res)

            @property
            def input_hex(self):
                return self.data["transaction"]["input"]

            @property
            def abi_fn(self):
                abi_fn_hex = self.input_hex[2:10]
                if not self.currency:
                    abi_rev_fns = ComChainABI._rev_transaction_functions
                    return (
                        f"[{self.data['transaction']['to'][2:8]}..]",
                        abi_rev_fns.get(abi_fn_hex, abi_fn_hex) 
                    )
                abi_rev_fns =  self.currency.comchain.abi_rev_transaction_functions
                key = (self.data["transaction"]["to"][2:].lower(), abi_fn_hex)
                if key not in abi_rev_fns:
                    abi_rev_fns = ComChainABI._rev_transaction_functions
                    return (
                        f"[{self.data['transaction']['to'][2:8]}..]",
                        abi_rev_fns.get(abi_fn_hex, abi_fn_hex) 
                    )
                contract_idx = [c.lower() for c in self.currency.contracts].index(
                    self.data["transaction"]["to"]
                )
                assert contract_idx is not None
                return (
                    f"{self.currency.symbol}.{contract_idx + 1}",
                    abi_rev_fns[key]
                )

            @property
            def first_sibling_transaction_time(self):
                if not self.is_cc_transaction:
                    return False
                ## XXXvlab: depending on the API endpoint used, it can be
                ## a dict or the direct value.
                res = self.data["receivedat"]
                if isinstance(res, dict):
                    res = int(res["value"])
                else:
                    res = int(res)
                return datetime.datetime.utcfromtimestamp(res)

            @property
            def cost_gas(self):
                return int(self.data["transaction"]["gas"], 16)

            @property
            def gas_price(self):
                return int(self.data["transaction"]["gasPrice"], 16)

            @property
            def cost_wei(self):
                return self.cost_gas * self.gas_price

            @property
            def cost_eth(self):
                return Web3.fromWei(self.cost_wei, 'ether')

            @property
            def cost_gwei(self):
                return Web3.fromWei(self.cost_wei, 'gwei')

            @property
            def pending(self):
                if not self.is_cc_transaction:
                    return False
                if self.block is None:
                    assert self.data["block"] is None and self.data["status"] == 1
                else:
                    assert self.data["block"] == int(self.block, 16) and self.data["status"] == 0
                return self.block is None

        return Pyc3lTransaction(address)

    def Block(pyc3l_instance, address):

        class Pyc3lBlock(Block):

            @property
            def transactions(self):
                for transaction in pyc3l_instance.getBlockInfo(self.address):
                    yield pyc3l_instance.Transaction(transaction["hash"])

        return Pyc3lBlock(address)