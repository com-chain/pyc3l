#

import logging
import time
import codecs
import datetime

## Monkey-patching parsimonious 0.8 to support Python 3.11

import sys
import inspect

from . import common

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

from . import store
from .wallet import Wallet
from .ApiCommunication import ApiCommunication, ComChainABI
from .ApiHandling import ApiHandling, Endpoint, APIErrorNoMessage
from .lib.dt import utc_ts_to_dt, utc_ts_to_local_iso, dt_to_local_iso

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
        self.address = address[2:] \
            if isinstance(address, str) and address.startswith("0x") else \
               address

class AddressableBridgeObject(AddressableObject):

    def __init__(self, address, data=None):
        super().__init__(address)
        if data is not None:
            self._data = data

    def __getattr__(self, label):
        if label.startswith("_"):
            raise AttributeError(label)

        if label in self._data:
            return self._data[label]
        raise AttributeError(label)

class Account(AddressableObject): pass
class Transaction(AddressableBridgeObject): pass
class BCTransaction(AddressableBridgeObject): pass
class Block(AddressableBridgeObject): pass

class Pyc3l:

    def __init__(self, endpoint=None, block_number=None):
        self._additional_nonce = 0

        self._current_block = 0
        self._target_block = block_number or "pending"

        self._endpoint_last_usage = None

        if endpoint:
            logger.info(f"endpoint: {endpoint} (fixed)")
            self._endpoint = Endpoint(endpoint) if isinstance(endpoint, str) else endpoint
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

    @property
    def contract_hex_to_currency(self):
        if not hasattr(self, "_contract_hex_to_currency"):
            res = self.ipfs_endpoint.config.get("list.json")
            _contract_hex_to_currency = {}
            for k, v in res.items():
                currency = self.Currency(v)
                for contract in currency.contracts:
                    contract_key = contract.lower()
                    if contract_key in _contract_hex_to_currency:
                        previous_currency = _contract_hex_to_currency[contract_key]
                        if previous_currency.symbol != currency.symbol:
                            raise Exception(
                                f"Two currencies ({currency.symbol}, {previous_currency.symbol}) "
                                f"share the same contract address: {contract_key}"
                            )
                        else:
                            continue
                    _contract_hex_to_currency[contract_key] = currency
            self._contract_hex_to_currency = _contract_hex_to_currency
        return self._contract_hex_to_currency

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

    def getBlockByNumber(self, nb):
        """Get block info given int nb"""
        try:
            return self.endpoint.block.get(params={"block": f"{hex(nb)}"})
        except APIErrorNoMessage:
            return None

    def getBlockByHash(self, hash):
        """Get block info given it's string hash (with 0x in front)"""
        try:
            return self.endpoint.block.get(params={"hash": hash})
        except APIErrorNoMessage:
            return None

    def getTrInfos(self, address):
        return self.endpoint.api.post(data={"txdata": address})

    def getTxPool(self):
        return self.endpoint.pool.get()

    def getAccountEthBalance(self, address):
        return self.endpoint.api.post(data={"balance": address})['balance']

    def getAccountTransactions(self, address, count=10, offset=0):
        transactions = self.endpoint.transactions.get(params={
            "addr": f"0x{address}",
            "count": count,
            "offset": offset,
        })
        ## XXXvlab: seems to need to be parsed twice (confirmed upon
        ## reading the code of the comchain API).
        import json
        return [json.loads(r) for r in transactions]

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
            "ethCallAt": {
                "to": fn[0],  ## contract
                "data": fn[1] + "".join(
                    (v[2:] if v.startswith("0x") else v).zfill(64)
                    for v in args
                )
            },
            "blockNb": self._target_block
        }
        try:
            result = self.endpoint.api.post(data=data)
        except Exception as e:
            logger.error(
                "Unexpected failure of ethCallAt " +
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

                class Pyc3lCurrencyAccount(pyc3l_instance.Account):

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

                    @property
                    def nonce_hex(self):
                        return pyc3l_instance.getTrInfos(self.address)["nonce"]

                    @property
                    def nonce_dec(self):
                        return int(self.nonce_hex, 16)

                    @property
                    def currency(self):
                        return pyc3l_currency

                    @property
                    def active(self):
                        return self.isActive

                    @property
                    def owner(self):
                        return self.isOwner

                    @property
                    def role(self):
                        return [
                            "personal",
                            "business",
                            "admin",
                            "pledge admin",
                            "property admin"
                        ][self.type]

                    @property
                    def eth_balance_wei(self):
                        return int(self.EthBalance)

                    @property
                    def eth_balance_gwei(self):
                        return Web3.fromWei(self.eth_balance_wei, "gwei")

                    @property
                    def eth_balance(self):
                        return Web3.fromWei(self.eth_balance_wei, "ether")

                    @property
                    def allowances(self):
                        return self.Allowances

                    @property
                    def requests(self):
                        return self.Requests

                    @property
                    def my_requests(self):
                        return self.MyRequests

                    @property
                    def delegations(self):
                        return self.Delegations

                    @property
                    def my_delegations(self):
                        return self.MyDelegations

                    @property
                    def accepted_requests(self):
                        return self.AcceptedRequests

                    @property
                    def rejected_requests(self):
                        return self.RejectedRequests

                return Pyc3lCurrencyAccount(address)

            @property
            def symbol(self):
                return self.metadata["server"]["currencies"]["CUR"]

            @property
            def name(self):
                return name

            @property
            def technicalAccounts(self):
                return self.metadata["server"]["technicalAccounts"]

        return Pyc3lCurrency(name, pyc3l_instance)

    @property
    def Account(pyc3l_instance):

        class Pyc3lAccount(Account):

            @property
            def transactions(self):
                batch_size = 15
                offset = 0
                while True:
                    txs = pyc3l_instance.getAccountTransactions(self.address, count=batch_size, offset=offset)
                    if not txs:
                        break
                    for tx in txs:
                        yield pyc3l_instance.Transaction(tx["hash"], data=tx)
                    offset += batch_size

        return Pyc3lAccount


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

    def Transaction(pyc3l_instance, *args, **kwargs):

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
            def bc_tx_data(self):
                if "transaction" not in self.data:
                    ## we don't have the bc transaction info
                    self.data["transaction"] = pyc3l_instance.getTransactionInfo(self.address)["transaction"]
                return self.data["transaction"]

            @property
            def input_hex(self):
                return self.data["transaction"]["input"]

            @property
            def received_at(self):
                if not self.is_cc_transaction:
                    return False
                res = int(self.data["time"])
                return utc_ts_to_dt(res)

            @property
            def currency(self):
                if "transaction" not in self.data and self.data.get("currency") is not None:
                    return pyc3l_instance.Currency(self.data["currency"])
                contract = self.bc_tx_data["to"].lower()
                if contract not in pyc3l_instance.contract_hex_to_currency and \
                   self.data.get("currency") is not None:
                    return pyc3l_instance.Currency(self.data["currency"])
                return pyc3l_instance.contract_hex_to_currency.get(contract)

            @property
            def block(self):
                if self.data["block"] is None:
                    return None
                return pyc3l_instance.BlockByNumber(int(self.data["block"]))

            @property
            def pending(self):
                if not self.is_cc_transaction:
                    return False
                if self.block is None:
                    assert self.data["status"] == 1
                else:
                    assert self.data["status"] == 0
                return self.block is None

            @property
            def bc_tx(self):
                if "transaction" not in self.data:
                    full_tx = pyc3l_instance.getTransactionInfo(self.address)
                    if full_tx is None:
                        raise Exception(f"Unexpected error: couldn't re-request transaction info of {self.address}")
                    return pyc3l_instance.BCTransaction(
                        self.address,
                        data=full_tx["transaction"]
                    )
                return pyc3l_instance.BCTransaction(
                    self.address,
                    data=self.data["transaction"]
                )

            @property
            def time(self):
                ts = self.time_ts
                if ts is None:
                    return None
                return utc_ts_to_dt(ts)

            @property
            def time_ts(self):
                if "time" in self.data:
                    return int(self.data["time"])
                return None

            @property
            def type(self):
                return self.data["type"].lower()

            @property
            def time_iso(self):
                dt = self.time
                if dt is None:
                    return None
                return dt_to_local_iso(dt)

        return Pyc3lTransaction(*args, **kwargs)

    def BCTransaction(pyc3l_instance, *args, **kwargs):

        class Pyc3lBCTransaction(Transaction):

            @property
            def data(self):
                if not hasattr(self, "_data"):
                    raise NotImplementedError("Not implemented")
                return self._data

            @property
            def bc_tx_data(self):
                return self.data

            @property
            def block_nb(self):
                return self.data["blockNumber"]

            @property
            def full_tx(self):
                try:
                    return pyc3l_instance.Transaction(
                        self.data["hash"],
                        data=pyc3l_instance.getTransactionInfo(self.address))
                except APIErrorNoMessage:
                    return None

            @property
            def currency(self):
                contract = self.data["to"]
                if contract is None:
                    return None
                contract = contract.lower()
                return pyc3l_instance.contract_hex_to_currency.get(contract)

            @property
            def input_hex(self):
                return self.data["input"]

            @property
            def fn(self):
                return self.input_hex[2:10]

            @property
            def gas_limit(self):
                return int(self.data["gas"], 16)

            @property
            def gas_price(self):
                return int(self.data["gasPrice"], 16)

            @property
            def gas_price_wei(self):
                return self.gas_price

            @property
            def gas_price_gwei(self):
                return Web3.fromWei(self.gas_price, 'gwei')

            @property
            def limit_cost_wei(self):
                return self.cost_gas * self.gas_price

            @property
            def limit_cost_eth(self):
                return Web3.fromWei(self.cost_wei, 'ether')

            @property
            def limit_cost_gwei(self):
                return Web3.fromWei(self.cost_wei, 'gwei')

            @property
            def block(self):
                if self.data["blockHash"] is None:
                    return None
                return pyc3l_instance.Block(
                    self.data["blockHash"],
                    pyc3l_instance.getBlockByHash(self.data["blockHash"])
                )

            @property
            def abi_fn(self):
                bc_tx_data = self.data
                if bc_tx_data["to"] is None:
                    return ("" , "loadContract")
                abi_fn_hex = bc_tx_data["input"][2:10]
                if not self.currency:
                    abi_rev_fns = ComChainABI._rev_transaction_functions
                    return (
                        f"[{bc_tx_data['to'][2:8]}‥]",
                        abi_rev_fns.get(abi_fn_hex, f'[{abi_fn_hex}‥]')
                    )
                abi_rev_fns =  self.currency.comchain.abi_rev_transaction_functions
                key = (bc_tx_data["to"][2:].lower(), abi_fn_hex)
                if key not in abi_rev_fns:
                    abi_rev_fns = ComChainABI._rev_transaction_functions
                    return (
                        f"<{bc_tx_data['to'][2:8]}‥>",
                        abi_rev_fns.get(abi_fn_hex, abi_fn_hex)
                    )
                contract_idx = [c.lower() for c in self.currency.contracts].index(
                    bc_tx_data["to"]
                )
                assert contract_idx is not None
                return (
                    f"{self.currency.symbol}-{contract_idx + 1}",
                    abi_rev_fns[key]
                )


        return Pyc3lBCTransaction(*args, **kwargs)

    def Block(pyc3l_instance, address, *args, **kwargs):

        class Pyc3lBlock(Block):

            @property
            def data(self):
                if not hasattr(self, "_data"):
                    self._data = pyc3l_instance.getBlockInfo(self.address)
                return self._data

            @property
            def hash(self):
                return self.address

            @property
            def number(self):
                return int(self.number_hex, 16)

            @property
            def number_hex(self):
                return self.data["number"]

            @property
            def collated_ts(self):
                return int(self.data["timestamp"], 16)

            @property
            def collated_dt(self):
                return utc_ts_to_dt(self.collated_ts)

            @property
            def collated_iso(self):
                return utc_ts_to_local_iso(self.collated_ts)

            @property
            def next(self):
                return pyc3l_instance.BlockByNumber(self.number + 1)

            @property
            def prev(self):
                if self.number == 0:
                    return None
                return pyc3l_instance.BlockByNumber(self.number - 1)

            @property
            def bc_txs(self):
                return [
                    pyc3l_instance.BCTransaction(tx["hash"], data=tx) for tx in self.data['transactions']
                ]

        return Pyc3lBlock(address, *args, **kwargs)

    def BlockByNumber(self, nb):
        block = self.Block(None)
        data = self.getBlockByNumber(nb)
        if data is None:
            data = {"number": hex(nb), "hash": "0x0"}
        block._data = data
        block.address = block._data["hash"]
        return block


__all__ = [
    Pyc3l,
    store
]
