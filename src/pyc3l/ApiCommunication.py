import logging
import inspect
import re
from typing import NewType


from .CryptoAsim import EncryptMessage, DecryptMessage


logger = logging.getLogger(__name__)


class AddressMeta(type):
    _pattern = re.compile(r"^(0x)?[a-fA-F0-9]{40}$")

    def __instancecheck__(cls, instance):
        return isinstance(instance, str) and cls._pattern.fullmatch(instance) is not None

class Address(str, metaclass=AddressMeta):
    pass

Uint256 = NewType('Uint256', int)
Amount = NewType('Amount', Uint256)
Bool = NewType('Bool', Uint256)
Bytes = NewType('Bytes', bytes)



def encodeNumber(number):
    if number < 0:
        return hex(16**64 + number)[2:].zfill(64)
    else:
        return str(hex(number))[2:].zfill(64)


def encodeAddressForTransaction(address):
    full_address = address
    if full_address.startswith("0x"):
        full_address = full_address[2:]
    if len(full_address) != 40:

        raise Exception("Missformed wallet address: " + address)
    return full_address.zfill(64)


class MetaABI(type):

    def __new__(cls, name, bases, dct):
        new_cls = super().__new__(cls, name, bases, dct)
        if name == "ABI":
            return new_cls
        new_cls._read_functions = dict(filter(
            lambda x: x[1] is not None, [
                (key, fn.__annotations__.get("return"))
                for key, fn in dct.items()
                if callable(fn) and hasattr(fn, "__annotations__")
            ]))
        new_cls._transaction_functions = dict([
            (key, fn.__doc__)
            for key, fn in dct.items()
            if callable(fn) and hasattr(fn, "__annotations__") and
            fn.__annotations__.get("return") is None
        ])
        new_cls._rev_transaction_functions = dict([
            (fn_hex, key)
            for key, fn_hex in new_cls._transaction_functions.items()
        ])
        return new_cls

    
class ABI(metaclass=MetaABI):
    """Abstract Base Class for ABI classes"""


class ComChainABI(ABI):

    def amountPledged() -> Amount: "18160ddd"

    def accountType(account: Address) -> Uint256: "ba99af70"
    def accountIsActive(account: Address) -> Bool: "61242bdd"
    def accountIsOwner(account: Address) -> Bool: "2f54bf6e"
    def accountCmLimitMax(account: Address) -> Amount: "cc885a65"
    def accountCmLimitMin(account: Address) -> Amount: "ae7143d6"
    def accountGlobalBalance(account: Address) -> Amount: "70a08231"
    def accountNantBalance(account: Address) -> Amount: "ae261aba"
    def accountCmBalance(account: Address) -> Amount: "bbc72a17"

    def setAccountParam(
            address: Address,
            status: Uint256,
            accountType: Uint256,
            limitP: Amount,
            limitM: Amount): "848b2592"
    def pledge(address: Address, amount: Amount): "6c343eef"
    def delegate(address: Address, amount: Amount): "75741c79"

    def nantTransfer(dest: Address, amount: int): "a5f7c148-1"
    def cmTransfer(dest: Address, amount: int): "60ca9c4c-1"
    def transferNantOnBehalf(src: Address, to: Address, amount: int): "1b6b1ee5-1"

    def accountAllowances(account: Address) -> list[Amount]: "aa7adb3d-1,b545b11f-1,dd62ed3e-1"
    def accountRequests(account: Address) -> list[Amount]: "debb9d28-1,726d0a28-1,3537d3fa-1"
    def accountMyRequests(account: Address) -> list[Amount]: "418d0fd4-1,0becf93f-1,09a15e43-1"
    def accountDelegations(account: Address) -> list[Amount]: "58fb5218-1,ca40edf1-1,046d3307-1"
    def accountMyDelegations(account: Address) -> list[Amount]: "7737784d-1,49bce08d-1,f24111d2-1"
    def accountAcceptedRequests(account: Address) -> list[Amount]: "8d768f84-1,59a1921a-1,958cde37-1"
    def accountRejectedRequests(account: Address) -> list[Amount]: "20cde8fa-1,9aa9366e-1,eac9dd4d-1"


class Contract:

    def __init__(self, pyc3l, abi, contracts):
        self._pyc3l = pyc3l
        self._abi = abi
        self._contracts = contracts


    CONVERSIONS = {
        Uint256: lambda x: int(x),
        Amount: lambda x: x / 100.0,
        Bool: lambda x: bool(x),
    }

    @property
    def abi_rev_transaction_functions(self):
        """Dictionary of transaction functions in the ABI

        Key is a tuple (contract, fn_hex), value is the name of the function

        """
        if not hasattr(self, "_abi_rev_transaction_functions"):
            res = dict([
                (self._get_contract_fn_hexs(key)[0], key)
                for key in self._abi._transaction_functions.keys()
            ])
            self._abi_rev_transaction_functions = {
                (contract[2:].lower(), fn_hex[2:]): key
                for (contract, fn_hex), key in res.items()
            }
        return self._abi_rev_transaction_functions

    def _get_contract_fn_hexs(self, fn_name):
        fn_def = getattr(self._abi, fn_name, None)
        if fn_def is None:
            raise AttributeError(f"Function {fn_name!r} not found in ABI")
        fn_hexs = fn_def.__doc__.split(",")
        parsed_fn_hexs = []
        for fn_hex in fn_hexs:
            hex_parts = fn_hex.split("-", 1)
            if not re.match("^[0-9a-f]{8}$", hex_parts[0]):
                raise ValueError(
                    f"Invalid hex data provided ({hex_parts[0]!r}) for {fn_name!r} function"
                )

            contract = self._contracts[0 if len(hex_parts) == 1 else int(hex_parts[1])]
            fn_hex = f"0x{hex_parts[0]}"
            parsed_fn_hexs.append((contract, fn_hex))
        return parsed_fn_hexs

    def __getattr__(self, label):
        if not label.startswith("get"):
            raise AttributeError(label)

        key = label[3:]
        key = key[0].lower() + key[1:]

        return_type = self._abi._read_functions.get(key)
        if not return_type:
            raise AttributeError(
                f"Comchain read function {key!r} not found in ABI"
            )
        parsed_fn_hexs = self._get_contract_fn_hexs(key)

        if getattr(return_type, "__origin__", None) is list:
            try:
                count_fn, map_fn, amount_fn  = parsed_fn_hexs
            except ValueError:
                raise ValueError(
                    f"Invalid list function {key} docstring: {doc!r}, "
                    "please provide count, map, amount hex functions separated by commas"
                )
            def get_list_function(address, idx_min=0, idx_max=0):
                count = self._pyc3l.read(count_fn, [address])
                return self._pyc3l.get_element_in_list(
                    map_fn,
                    amount_fn,
                    address,
                    min(count - 1, idx_max),
                    {},
                    idx_min
                )

            return get_list_function

        fn = getattr(self._abi, key)

        def _method(*args):
            ## check args follow argspec from fn
            sig = inspect.getfullargspec(fn)
            if len(args) != len(sig.args):
                raise TypeError(
                    f"{key}() missing {len(sig.args) - 1 - len(args)} required positional arguments"
                )
            for arg, sig_arg in zip(args, sig.args):
                if not isinstance(arg, sig.annotations[sig_arg]):
                    raise TypeError(
                        f"{key}() argument must be of type {sig.annotations[sig_arg]}"
                    )
            value = self._pyc3l.read(parsed_fn_hexs[0], args)
            return self.CONVERSIONS[return_type](value)
        return _method


class ApiCommunication:

    def __init__(self, currency_name, pyc3l, abi=ComChainABI):
        self._currency_name = currency_name

        self._current_block = 0
        self._metadata = None
        self._pyc3l = pyc3l

        self._comchain = None
        self._abi = abi

    @property
    def comchain(self):
        if self._comchain is None:
            self._comchain = Contract(
                self._pyc3l,
                self._abi,
                self.contracts
            )
        return self._comchain

    @property
    def endpoint(self):
        return self._pyc3l.endpoint

    @property
    def ipfs_endpoint(self):
        return self._pyc3l.ipfs_endpoint

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = self._pyc3l.ipfs_endpoint.config.get(f"{self._currency_name}.json")
        return self._metadata

    @property
    def contracts(self):
        server = self.metadata["server"]
        return (
            server["contract_1"],
            server["contract_2"],
        )

    def checkAdmin(self, address):
        if not self.getAccountIsValidAdmin(address):
            raise Exception(
                f"The provided account {address} is not an "
                f"active admin on f{self._currency_name}"
                f" ({self.contracts[0]})"
            )

        if not self.getAccountHasEnoughGas(address):
            raise Exception(
                f"The provided account {address} has not enough gas."
            )



    ############################### messages with transaction handling
    def getMessageKeys(self, address, with_private):
        params = {"addr": address}
        if with_private:
            params["private"] = 1
        return self.endpoint.keys.get(params=params)

    def encryptTransactionMessage(self, plain_text, **kwargs):
        # if public_message_key is present use it if not get the key from the address
        if "public_message_key" in kwargs:
            public_message_key = kwargs["public_message_key"]
        elif "address" in kwargs:
            response = self.getMessageKeys(kwargs["address"], False)
            if "public_message_key" not in response:
                logger.warn("No message key for account %s", kwargs["address"])
                return "", ""
            public_message_key = response["public_message_key"]
        else:
            raise ValueError("public_message_key or address agrgument must be present")

        ciphered = EncryptMessage(public_message_key, plain_text)
        return ciphered, public_message_key

    def decryptTransactionMessage(self, ciphered, **kwargs):
        # if private_message_key is present use it if not get the key from the address and private_key
        if "private_message_key" in kwargs:
            private_message_key = kwargs["private_message_key"]
        elif "address" in kwargs and "private_key" in kwargs:
            response, r = self.getMessageKeys(kwargs["address"], True)
            if "private_message_key" not in response:
                logger.warn("No message key for account %s", kwargs["address"])
                return "", ""
            private_message_key = DecryptMessage(
                kwargs["private_key"], response["private_message_key"]
            )

        else:
            raise ValueError(
                "private_message_key or ( address and private_key ) agrgument must be present"
            )

        plain_text = DecryptMessage(private_message_key, ciphered)
        return plain_text, private_message_key

    ############################### High level Functions

    def getAccountIsValidAdmin(self, address):
        return (
            self.getAccountType(address) == 2
            and self.getAccountIsActive(address) == True
        )

    def getAccountHasEnoughGas(self, address, min_gas=5000000):
        return int(self._pyc3l.getTrInfos(address)["balance"]) > min_gas

    ############################### High level Transactions
    def transferNant(self, account, dest_address, amount, **kwargs):
        # message_from="", message_to=""):
        """Transfer Nantissed current Currency (server) from the sender to the destination wallet

        Parameters:
        account (eth_account import::Account): An account with enough balance on the current server. Will sign the transaction
        dest_address (string): The public address of the wallet to be credited (0x12345... format)
        amount (double): amount (in the current Currency) to be transfered from the sender wallet to the destination wallet

        """

        # prepare messages
        if "message_from" in kwargs and kwargs["message_from"] != "":

            ciphered_message_from, public_key = self.encryptTransactionMessage(
                kwargs["message_from"], address=account.address
            )
        else:
            ciphered_message_from = ""

        if "message_to" in kwargs and kwargs["message_to"] != "":
            ciphered_message_to, public_key = self.encryptTransactionMessage(
                kwargs["message_to"], address=dest_address
            )
        else:
            ciphered_message_to = ""

        # Get sender wallet infos
        if not self.getAccountIsActive(account.address):
            raise Exception(
                f"The sender wallet {account.address} is locked "
                f"on {self._currency_name} ({self.contracts[0]}) "
                "and therefore cannot initiate a transfer."
            )

        balance = self.getAccountNantBalance(account.address)
        if balance < amount:
            raise Exception(
                f"The sender wallet {account.address} has an "
                f"insufficient Nant balance on {self._currency_name} "
                f"({self.contracts[0]}) to complete this transfer."
            )

        # Get destination wallet infos
        if not self.getAccountIsActive(dest_address):
            raise Exception(
                f"The destination wallet {dest_address} is locked on "
                f"{self._currency_name}  ({self.contracts[0]}) and "
                "therefore cannot receive a transfer."
            )

        # Prepare data
        amount_cent = round(100 * amount)
        data = encodeAddressForTransaction(dest_address)
        data += encodeNumber(amount_cent)

        # send transaction
        logger.info(
            "Transferring %s nantissed %s from wallet %s to target wallet %s on server %s",
            amount,
            self._currency_name,
            account.address,
            dest_address,
            "%s(%s, %s)" % (self._currency_name, self.contracts[0], self.contracts[1]),
        )
        return self._pyc3l.send_transaction(
            self.comchain._get_contract_fn_hexs("nantTransfer")[0],
            data,
            account,
            ciphered_message_from,
            ciphered_message_to,
        )

    def transferCM(self, account, dest_address, amount, **kwargs):
        # message_from="", message_to=""):
        """Transfer Mutual Credit current Currency (server) from the sender to the destination wallet

        Parameters:
        account (eth_account import::Account): An account with enough balance on the current server. Will sign the transaction
        dest_address (string): The public address of the wallet to be credited (0x12345... format)
        amount (double): amount (in the current Currency) to be transfered from the sender wallet to the destination wallet

        """
        # prepare messages
        if "message_from" in kwargs and kwargs["message_from"] != "":
            ciphered_message_from, public_key = self.encryptTransactionMessage(
                kwargs["message_from"], address=account.address
            )
        else:
            ciphered_message_from = ""

        if "message_to" in kwargs and kwargs["message_to"] != "":
            ciphered_message_to, public_key = self.encryptTransactionMessage(
                kwargs["message_to"], address=dest_address
            )
        else:
            ciphered_message_to = ""

        # Get sender wallet infos
        if not self.getAccountIsActive(account.address):
            raise Exception(
                "The sender wallet "
                + account.address
                + " is locked on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ") and therefore cannot initiate a transfer."
            )

        balance = self.getAccountCMBalance(account.address)
        if balance < amount:
            raise Exception(
                "The sender wallet "
                + account.address
                + " has an insuficient CM balance on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ") to complete this transfer."
            )

        # Get destination wallet infos
        if not self.getAccountIsActive(dest_address):
            raise Exception(
                "The destination wallet "
                + dest_address
                + " is locked on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ") and therefore cannot recieve a transfer."
            )

        # Prepare data
        amount_cent = round(100 * amount)
        data = encodeAddressForTransaction(dest_address)
        data += encodeNumber(amount_cent)

        # send transaction
        logger.info(
            "Transferring %s mutual credit %s from wallet %s to target wallet %s on server %s",
            amount,
            self._currency_name,
            account.address,
            dest_address,
            "%s(%s, %s)" % (self._currency_name, self.contracts[0], self.contracts[1]),
        )

        return self._pyc3l.send_transaction(
            self.comchain._get_contract_fn_hexs("cmTransfer")[0],
            data,
            account,
            ciphered_message_from,
            ciphered_message_to,
        )

    ############################### High level Admin restricted Transactions
    def enable(self, account, address):
        return self._lockUnlockAccount(account, address, lock=False)

    def disable(self, account, address):
        return self._lockUnlockAccount(account, address, lock=True)

    def _lockUnlockAccount(self, account, address, lock=True):
        """Lock or unlock an Wallet on the current Currency (server)

        Parameters:
        account (eth_account import::Account): An account with admin permission on the current server. Will sign the transaction
        address (string): The public address of the wallet to be locked/unlocked (0x12345... format)
        lock (bool): if True, lock the wallet, if False unlock it

        """
        # Check the admin
        self.checkAdmin(account.address)

        # Get wallet infos
        status = self.getAccountIsActive(address)

        if lock and not status:
            logger.info("The wallet %s is already locked", address)
            return None
        if not lock and status:
            logger.info("The wallet %s is already unlocked", address)
            return None

        # Get wallet infos
        acc_type = self.getAccountType(address)
        lim_m = self.getAccountCmLimitMin(address)
        lim_p = self.getAccountCmLimitMax(address)

        status = 1
        if lock:
            status = 0

        # prepare the data
        data = encodeAddressForTransaction(address)
        data += (
            encodeNumber(status)
            + encodeNumber(acc_type)
            + encodeNumber(round(lim_p * 100))
            + encodeNumber(round(lim_m * 100))
        )

        # send the transaction
        logger.info(
            "%s the wallet %s on server %s (%s)",
            "Locking" if lock else "Unlocking",
            address,
            self._currency_name,
            self.contracts[0],
        )
        return self._pyc3l.send_transaction(
            self.comchain._get_contract_fn_hexs("setAccountParam")[0],
            data, account)

    def pledge(self, account, address, amount, **kwargs):
        """Pledge a given amount to a Wallet on the current Currency (server)

        Parameters:
        account (eth_account import::Account): An account with admin permission on the current server. Will sign the transaction
        address (string): The public address of the wallet to be pledged (0x12345... format)
        amount (double): amount (in the current Currency) to be pledged to the wallet

        """
        # Check the admin
        self.checkAdmin(account.address)

        # Get wallet infos
        if not self.getAccountIsActive(address):
            logger.warn(
                "The target wallet %s is locked on server %s (%s)",
                address,
                self._currency_name,
                self.contracts[0],
            )

        # encode message if any
        if "message_to" in kwargs and kwargs["message_to"] != "":
            ciphered_message_to, public_key = self.encryptTransactionMessage(
                kwargs["message_to"], address=address
            )
        else:
            ciphered_message_to = ""

        # Prepare data
        amount_cent = round(100 * amount)
        data = encodeAddressForTransaction(address)
        data += encodeNumber(amount_cent)

        # send transaction
        logger.info(
            "Pledging %s to target wallet %s on server %s (%s) through end-point %s",
            amount,
            address,
            self._currency_name,
            self.contracts[0],
            self.endpoint,
        )
        return self._pyc3l.send_transaction(
            self.comchain._get_contract_fn_hexs("pledge")[0],
            data, account, "", ciphered_message_to
        )

    def delegate(self, account, address, amount):
        """Delegate a given amount of own money to an address

        Parameters:
        account: The account issuing the delegation
        address (string): The public address of the wallet to receive delegeation (0x12345... format)
        amount (double): amount (in the current Currency) to be delegated

        """

        # Prepare data
        amount_cent = round(100 * amount)
        data = encodeAddressForTransaction(address)
        data += encodeNumber(amount_cent)

        # send transaction
        logger.info(
            "Delegating %s to target wallet %s on server %s (%s) through end-point %s",
            amount,
            address,
            self._currency_name,
            self.contracts[0],
            self.endpoint,
        )
        return self._pyc3l.send_transaction(
            self.comchain._get_contract_fn_hexs("delegate")[0],
            data, account)

    def transferOnBehalfOf(self, account, address_from, address_to, amount, **kwargs):
        """Transfer amount money from address_from to address_to

        Note, this requires a delegation to be set up previously

        Parameters:
        account: The account issuing the order
        address_from (string): The address of the wallet to take money (0x12345... format)
        address_to (string): The address of the wallet to send money (0x12345... format)
        amount (double): amount (in the current Currency) to be transfered

        """

        # Prepare data
        data = encodeAddressForTransaction(address_from)
        data += encodeAddressForTransaction(address_to)
        data += encodeNumber(round(100 * amount))

        # prepare messages
        if "message_from" in kwargs and kwargs["message_from"] != "":
            ciphered_message_from, public_key = self.encryptTransactionMessage(
                kwargs["message_from"], address=address_from
            )
        else:
            ciphered_message_from = ""

        if "message_to" in kwargs and kwargs["message_to"] != "":
            ciphered_message_to, public_key = self.encryptTransactionMessage(
                kwargs["message_to"], address=address_to
            )
        else:
            ciphered_message_to = ""

        # send transaction
        logger.info(
            "Ask Transfer from %s to %s of %s",
            address_from,
            address_to,
            amount,
        )
        return self._pyc3l.send_transaction(
            self.comchain._get_contract_fn_hexs("transferNantOnBehalf")[0],
            data,
            account,
            ciphered_message_from,
            ciphered_message_to,
        )

    def __getattr__(self, label):
        return getattr(self.comchain, label)

