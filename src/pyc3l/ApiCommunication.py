from web3.eth import Eth

import codecs
import logging

from .CryptoAsim import EncryptMessage, DecryptMessage
from .ApiHandling import ApiHandling, Endpoint, APIError

logger = logging.getLogger(__name__)


def encodeNumber(number):
    if number < 0:
        return hex(16**64 + number)[2:].zfill(64)
    else:
        return str(hex(number))[2:].zfill(64)


def decodeNumber(hexnumber):
    res = 0
    if hexnumber[0].lower() == "f" or (
        hexnumber[0:2] == "0x" and hexnumber[3].lower() == "f"
    ):
        res = -(16**64)

    if hexnumber[0:2] != "0x":
        hexnumber = "0x" + hexnumber

    return int(hexnumber, 0) + res


def encodeAddressForTransaction(address):
    full_address = address
    if full_address.startswith("0x"):
        full_address = full_address[2:]
    if len(full_address) != 40:

        raise Exception("Missformed wallet address: " + address)
    return full_address.zfill(64)


def buildInfoData(function, address):
    if address.startswith("0x"):
        address = address[2:]
    if not function.startswith("0x"):
        function = "0x" + function
    return function + address.zfill(64)


def callNumericInfo(endpoint, contract, function, address, divider=100.0):
    data = {
        "ethCall[data]": buildInfoData(function, address),
        "ethCall[to]": contract,
    }
    try:
        r = endpoint.api.post(data=data)
    except APIError:
        return -1
    return decodeNumber(r) / divider


class ApiCommunication:
    def __init__(self, currency_name, endpoint=None):
        self._currency_name = currency_name

        self._current_block = 0
        self._additional_nonce = 0
        self._metadata = None

        if endpoint:
            logger.info(f"endpoint: {endpoint} (fixed)")
            self._endpoint = Endpoint(endpoint)
            self._endpoint_resolver = None
        else:
            self._endpoint = None
            self._endpoint_resolver = ApiHandling()

        # Functions
        # Consultation
        self.ACCOUNT_TYPE = "0xba99af70"
        self.ACCOUNT_STATUS = "0x61242bdd"
        self.ACCOUNT_IS_OWNER = "0x2f54bf6e"

        self.ACCOUNT_CM_LIMIT_M = "0xcc885a65"
        self.ACCOUNT_CM_LIMIT_P = "0xae7143d6"

        self.GLOBAL_BALANCE = "0x70a08231"
        self.NANT_BALANCE = "0xae261aba"
        self.CM_BALANCE = "0xbbc72a17"

        # Transaction
        self.ACCOUNT_PARAM = "0x848b2592"

        self.PLEDGE = "0x6c343eef"

        # On contract 2
        self.NANT_TRANSFERT = "0xa5f7c148"
        self.CM_TRANSFERT = "0x60ca9c4c"

    @property
    def endpoint(self):
        if self._endpoint is None:
            self._endpoint = self._endpoint_resolver.endpoint
            logger.info(f"endpoint: {self._endpoint} (elected)")
        return self._endpoint

    @property
    def metadata(self):
        if self._metadata is None:
            ipfs_endpoint = (
                self._endpoint_resolver.ipfs_endpoint
                if self._endpoint_resolver
                else self.endpoint
            )
            self._metadata = ipfs_endpoint.currency_data(self._currency_name)
        return self._metadata

    @property
    def contracts(self):
        server = self.metadata["server"]
        return (
            server["contract_1"],
            server["contract_2"],
        )

    def getBlockNumber(self):
        return self.endpoint.api.post()

    def getTransactionBLock(self, transaction_hash):
        data = {"hash": transaction_hash}

        r = self.endpoint.api.post(data=data)
        ## XXXvlab: seems to need to be parsed twice (confirmed upon
        ## reading the code of the comchain API).
        if isinstance(r, str):
            import json

            r = json.loads(r)
        return r["transaction"]["blockNumber"]

    def getNumericalInfo(
        self, address_to_check, function, divider=100.0, contract_id=1
    ):
        if contract_id == 2:
            contract = self.contracts[1]
        else:
            contract = self.contracts[0]

        return callNumericInfo(
            self.endpoint, contract, function, address_to_check, divider
        )

    def getTrInfos(self, address):
        return self.endpoint.api.post(data={"txdata": address})

    def checkAdmin(self, admin_address):
        if not self.getAccountIsValidAdmin(admin_address):
            raise Exception(
                "The provided Admin Account with address "
                + admin_address
                + " is not an active admin on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ")"
            )

        if not self.getAccountHasEnoughGas(admin_address):
            raise Exception(
                "The provided Admin Account with address "
                + admin_address
                + " has not enough gas."
            )

    def hasChangedBlock(self, do_reset=False):
        new_current_block = self.getBlockNumber()
        res = new_current_block != self._current_block
        if do_reset:
            self._current_block = new_current_block
        return res

    def registerCurrentBlock(self):
        self.hasChangedBlock(do_reset=True)

    def updateNonce(self, nonce):
        if not self.hasChangedBlock(do_reset=True):
            self._additional_nonce = self._additional_nonce + 1
            return nonce + self._additional_nonce
        else:
            self._additional_nonce = 0
            return nonce

    def sendTransaction(
        self,
        data,
        admin_account,
        ciphered_message_from="",
        ciphered_message_to="",
        contract_id=1,
    ):
        tr_infos = self.getTrInfos(admin_account.address)

        if contract_id == 2:
            contract = self.contracts[1]
        else:
            contract = self.contracts[0]

        transaction = {
            "to": contract,
            "value": 0,
            "gas": 5000000,
            "gasPrice": int(tr_infos["gasprice"], 0),
            "nonce": self.updateNonce(int(tr_infos["nonce"], 0)),
            "data": data,
            "from": admin_account.address,
        }

        signed = Eth.account.signTransaction(transaction, admin_account.privateKey)
        str_version = (
            "0x" + str(codecs.getencoder("hex_codec")(signed.rawTransaction)[0])[2:-1]
        )
        raw_tx = {"rawtx": str_version}

        if ciphered_message_from != "":
            raw_tx["memo_from"] = ciphered_message_from

        if ciphered_message_to != "":
            raw_tx["memo_to"] = ciphered_message_to

        return self.endpoint.api.post(data=raw_tx)

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

    def getAccountType(self, address_to_check):
        return int(
            self.getNumericalInfo(
                address_to_check,
                self.ACCOUNT_TYPE,
                divider=1,
                contract_id=1,
            )
        )

    def getAccountStatus(self, address_to_check):
        return int(
            self.getNumericalInfo(
                address_to_check,
                self.ACCOUNT_STATUS,
                divider=1,
                contract_id=1,
            )
        )

    def getAccountIsValidAdmin(self, address_to_check):
        return (
            self.getAccountType(address_to_check) == 2
            and self.getAccountStatus(address_to_check) == 1
        )

    def getAccountIsOwner(self, address_to_check):
        return int(
            self.getNumericalInfo(
                address_to_check,
                self.ACCOUNT_IS_OWNER,
                divider=1,
                contract_id=1,
            )
        )

    def getAccountHasEnoughGas(self, address_to_check, min_gas=5000000):
        return int(self.getTrInfos(address_to_check)["balance"]) > min_gas

    def getAccountGlobalBalance(self, address_to_check):
        return self.getNumericalInfo(
            address_to_check,
            self.GLOBAL_BALANCE,
            divider=100.0,
            contract_id=1,
        )

    def getAccountNantBalance(self, address_to_check):
        return self.getNumericalInfo(
            address_to_check,
            self.NANT_BALANCE,
            divider=100.0,
            contract_id=1,
        )

    def getAccountCMBalance(self, address_to_check):
        return self.getNumericalInfo(
            address_to_check,
            self.CM_BALANCE,
            divider=100.0,
            contract_id=1,
        )

    def getAccountCMLimitMaximum(self, address_to_check):
        return self.getNumericalInfo(
            address_to_check,
            self.ACCOUNT_CM_LIMIT_P,
            divider=100.0,
            contract_id=1,
        )

    def getAccountCMLimitMinimum(self, address_to_check):
        return self.getNumericalInfo(
            address_to_check,
            self.ACCOUNT_CM_LIMIT_M,
            divider=100.0,
            contract_id=1,
        )

    ############################### High level Transactions
    def transfertNant(
        self, sender_account, dest_address, amount, **kwargs
    ):  # server="", message_from="", message_to=""):
        """Transfert Nantissed current Currency (server) from the sender to the destination wallet

        Parameters:
        sender_account (eth_account import::Account): An account with enough balance on the current server. Will sign the transaction
        dest_address (string): The public address of the wallet to be credited (0x12345... format)
        amount (double): amount (in the current Currency) to be transfered from the sender wallet to the destination wallet

        """

        # prepare messages
        if "message_from" in kwargs and kwargs["message_from"] != "":

            ciphered_message_from, public_key = self.encryptTransactionMessage(
                kwargs["message_from"], address=sender_account.address
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
        status = self.getAccountStatus(sender_account.address)
        if status == 0:
            raise Exception(
                "The sender wallet "
                + sender_account.address
                + " is locked on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ") and therefore cannot initiate a transfer."
            )

        balance = self.getAccountNantBalance(sender_account.address)
        if balance < amount:
            raise Exception(
                "The sender wallet "
                + sender_account.address
                + " has an insuficient Nant balance on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ") to complete this transfer."
            )

        # Get destination wallet infos
        status = self.getAccountStatus(dest_address)
        if status == 0:
            raise Exception(
                "The destination wallet "
                + dest_address
                + " is locked on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ") and therefore cannot receive a transfer."
            )

        # Prepare data
        amount_cent = int(100 * amount)
        data = encodeAddressForTransaction(dest_address)
        data += encodeNumber(amount_cent)

        # send transaction
        logger.info(
            "Transferring %s nantissed %s from wallet %s to target wallet %s on server %s",
            amount,
            self._currency_name,
            sender_account.address,
            dest_address,
            "%s(%s, %s)" % (self._currency_name, self.contracts[0], self.contracts[1]),
        )
        return self.sendTransaction(
            self.NANT_TRANSFERT + data,
            sender_account,
            ciphered_message_from,
            ciphered_message_to,
            2,
        )

    def transfertCM(
        self, sender_account, dest_address, amount, **kwargs
    ):  # message_from="", message_to=""):
        """Transfert Mutual Credit current Currency (server) from the sender to the destination wallet

        Parameters:
        sender_account (eth_account import::Account): An account with enough balance on the current server. Will sign the transaction
        dest_address (string): The public address of the wallet to be credited (0x12345... format)
        amount (double): amount (in the current Currency) to be transfered from the sender wallet to the destination wallet

        """
        # prepare messages
        if "message_from" in kwargs and kwargs["message_from"] != "":
            ciphered_message_from, public_key = self.encryptTransactionMessage(
                kwargs["message_from"], address=sender_account.address
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
        status = self.getAccountStatus(sender_account.address)
        if status == 0:
            raise Exception(
                "The sender wallet "
                + sender_account.address
                + " is locked on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ") and therefore cannot initiate a transfer."
            )

        balance = self.getAccountCMBalance(sender_account.address)
        if balance < amount:
            raise Exception(
                "The sender wallet "
                + sender_account.address
                + " has an insuficient CM balance on server "
                + self._currency_name
                + " ("
                + self.contracts[0]
                + ") to complete this transfer."
            )

        # Get destination wallet infos
        status = self.getAccountStatus(dest_address)
        if status == 0:
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
        amount_cent = int(100 * amount)
        data = encodeAddressForTransaction(dest_address)
        data += encodeNumber(amount_cent)

        # send transaction
        logger.info(
            "Transferring %s mutual credit %s from wallet %s to target wallet %s on server %s",
            amount,
            self._currency_name,
            sender_account.address,
            dest_address,
            "%s(%s, %s)" % (self._currency_name, self.contracts[0], self.contracts[1]),
        )

        return self.sendTransaction(
            self.CM_TRANSFERT + data,
            sender_account,
            ciphered_message_from,
            ciphered_message_to,
            2,
        )

    ############################### High level Admin restricted Transactions
    def lockUnlockAccount(self, admin_account, address, lock=True):
        """Lock or unlock an Wallet on the current Currency (server)

        Parameters:
        admin_account (eth_account import::Account): An account with admin permission on the current server. Will sign the transaction
        address (string): The public address of the wallet to be locked/unlocked (0x12345... format)
        lock (bool): if True, lock the wallet, if False unlock it

        """
        # Check the admin
        self.checkAdmin(admin_account.address)

        # Get wallet infos
        status = self.getAccountStatus(address)

        if lock and status == 0:
            logger.info("The wallet %s is already locked", address)
            return None
        elif not lock and status == 1:
            logger.info("The wallet %s is already unlocked", address)
            return None
        else:

            # Get wallet infos
            acc_type = self.getAccountType(address)
            lim_m = self.getAccountCMLimitMinimum(address)
            lim_p = self.getAccountCMLimitMaximum(address)

            status = 1
            if lock:
                status = 0

            # prepare the data
            data = encodeAddressForTransaction(address)
            data += (
                encodeNumber(status)
                + encodeNumber(acc_type)
                + encodeNumber(int(lim_p * 100))
                + encodeNumber(int(lim_m * 100))
            )

            # send the transaction
            logger.info(
                "Locking/unlocking the wallet %s on server %s (%s)",
                address,
                self._currency_name,
                self.contracts[0],
            )
            return self.sendTransaction(self.ACCOUNT_PARAM + data, admin_account)

    def pledgeAccount(self, admin_account, address, amount, **kwargs):  #  message_to
        """Pledge a given amount to a Wallet on the current Currency (server)

        Parameters:
        admin_account (eth_account import::Account): An account with admin permission on the current server. Will sign the transaction
        address (string): The public address of the wallet to be pledged (0x12345... format)
        amount (double): amount (in the current Currency) to be pledged to the wallet

        """
        # Check the admin
        self.checkAdmin(admin_account.address)

        # Get wallet infos
        status = self.getAccountStatus(address)
        if status == 0:
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
        amount_cent = int(100 * amount)
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
        return self.sendTransaction(
            self.PLEDGE + data, admin_account, "", ciphered_message_to
        )
