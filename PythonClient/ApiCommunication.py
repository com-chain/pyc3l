from .ApiHandling import ApiHandling 
from .CryptoAsim import EncryptMessage, DecryptMessage 
import requests 
import json
from eth_account import Account
from web3 import Web3
from web3.eth import Eth
import codecs

class objectview(object):
    def __init__(self, d):
        self.__dict__ = d

class ApiCommunication:

    def __init__(self, api_handler, server):
        self._api_handler=api_handler
        self._server = server
        self._contract_1, self._contract_2 = self._api_handler.getServerContract(self._server)
        self._end_point = self._api_handler.getApiEndpoint()
        self._current_block=''
        self._additional_nonce=0
        
        self.KEYSTORE = "/keys.php"
        
        # Functions
        # Consultation
        self.ACCOUNT_TYPE = "0xba99af70"
        self.ACCOUNT_STATUS = "0x61242bdd"
        self.ACCOUNT_IS_OWNER = "0x2f54bf6e"

        self.ACCOUNT_CM_LIMIT_M = "0xcc885a65"
        self.ACCOUNT_CM_LIMIT_P = "0xae7143d6"

        self.GLOBAL_BALANCE ='0x70a08231'
        self.NANT_BALANCE ='0xae261aba'
        self.CM_BALANCE ='0xbbc72a17'

        # Transaction
        self.ACCOUNT_PARAM = "0x848b2592"

        self.PLEDGE = "0x6c343eef"
        
        # On contract 2
        self.NANT_TRANSFERT = "0xa5f7c148"
        self.CM_TRANSFERT = "0x60ca9c4c"

    def encodeNumber(self, number):
        if number<0:
            return hex(16**64+number)[2:].zfill(64)
        else:
            return str(hex(number))[2:].zfill(64)
            
            
    def decodeNumber(self, hexnumber):
        res = 0;
        if hexnumber[0].lower()=='f' or (hexnumber[0:2]=='0x' and hexnumber[3].lower()=='f'):
            res = -16**64
            
        if (hexnumber[0:2]!='0x'):
            hexnumber='0x'+hexnumber

        return int(hexnumber,0)+res
        
        
    def encodeAddressForTransaction(self, address):
        full_address = address
        if full_address.startswith('0x'):
            full_address = full_address[2:]
        if len(full_address)!=40:
            
            raise Exception('Missformed wallet address: '+address)
        return full_address.zfill(64)  
         
    def buildInfoData(self, function, address):
        if address.startswith('0x'):
            address=address[2:]
        if not function.startswith('0x'):
            function='0x'+function
        return function + address.zfill(64)
        
        
    def callNumericInfo(self, api, contract, function, address, divider=100.):
        data =  {'ethCall[data]':self.buildInfoData(function,address), 
            'ethCall[to]':contract}
        r = requests.post(url = api, data = data)
        if r.status_code!=200: 
            raise Exception("Error while contacting the API("+api+"):"+str(r.status_code))
        response_parsed = json.loads(r.text)
        if not response_parsed['error']:
            return self.decodeNumber(response_parsed['data'])/divider
        else:
            return -1
            
    def resetApis(self, api_end_point="", use_new=False):

        # get the endpoint 
        if len(api_end_point)!=0:
            self._end_point = api_end_point;
        elif use_new:
            self._end_point = self._api_handler.getApiEndpoint()
            
    
    def getBlockNumber(self):
        r = requests.post(url = self._end_point)
        if r.status_code!=200: 
            raise Exception("Error while contacting the API("+ self._end_point+"):"+str(r.status_code))
        return r.text
        
    def getTransactionBLock(self, transaction_hash, api_end_point=""):
        if len(api_end_point)!=0:
            self._end_point = api_end_point;
             
        data = {'hash':transaction_hash}
        
        r = requests.post(url = self._end_point, data = data)
        response_parsed = json.loads(r.text)
        return response_parsed['transaction']['blockNumber']
        
                
          
    def getNumericalInfo(self, address_to_check, function, api_end_point="",divider=100., contract_id=1):
        self.resetApis(api_end_point=api_end_point, use_new=False)
        if contract_id==2:
            contract = self._contract_2
        else:
            contract = self._contract_1
            
        return self.callNumericInfo(self._end_point, contract, function, address_to_check, divider)  
        

        
    def getTrInfos(self, address, api_end_point=""):
        if len(api_end_point)!=0:
            self._end_point = api_end_point;
             
        data = {'txdata':address}
        
        r = requests.post(url = self._end_point, data = data)
        response_parsed = json.loads(r.text)
        return response_parsed['data']
        
       
        
    def checkAdmin(self, admin_address):
        if not self.getAccountIsValidAdmin(admin_address):
            raise Exception("The provided Admin Account with address "+admin_address+" is not an active admin on server "+self._server + " (" + self._contract_1+")")
        
        if not self.getAccountHasEnoughGas(admin_address):
            raise Exception("The provided Admin Account with address "+admin_address+" has not enough gas.")

    def hasChangedBlock(self,do_reset=False, endpoint=''):
        new_current_block = self._api_handler.getCurrentBlock(endpoint)
        res = new_current_block != self._current_block
        if (do_reset):
            self._current_block = new_current_block
        return res; 
        
    def registerCurrentBlock(self,  endpoint=''):
        self.hasChangedBlock(do_reset=True, endpoint=endpoint)
            
    def updateNonce(self, nonce):
        if not self.hasChangedBlock(do_reset=True):
            self._additional_nonce= self._additional_nonce + 1
            return nonce+self._additional_nonce
        else:
            self._additional_nonce = 0
            return nonce 

    def sendTransaction(self, data, admin_account, ciphered_message_from="", ciphered_message_to="", contract_id=1):
        tr_infos = self.getTrInfos(admin_account.address)

        if contract_id==2:
            contract = self._contract_2
        else:
            contract = self._contract_1

        transaction = {
            'to': contract,
            'value': 0,
            'gas': 5000000,
            'gasPrice':  int(tr_infos['gasprice'],0),
            'nonce': self.updateNonce(int(tr_infos['nonce'],0)),
            'data':data,
            'from':admin_account.address
        }
    
        signed = Eth.account.signTransaction(transaction, admin_account.privateKey)
        str_version = '0x'+str(codecs.getencoder('hex_codec')(signed.rawTransaction)[0])[2:-1]
        raw_tx = {'rawtx': str_version}
        
        if ciphered_message_from!="":
            raw_tx["memo_from"] = ciphered_message_from
            
        if ciphered_message_to!="":
            raw_tx["memo_to"] = ciphered_message_to
        
        r = requests.post(url = self._end_point, data = raw_tx)
        if r.status_code!=200: 
            raise Exception("Error while contacting the API:"+str(r.status_code))
        response_parsed = json.loads(r.text)
        return response_parsed['data'], r
        
        
    ############################### messages with transaction handling
    def getMessageKeys(self, address, with_private):
        query_string = '?addr=' + address
        if with_private:
           query_string = query_string + "&private=1" 
        
        url = self._end_point[:-len(self._api_handler.api_url)] +  self.KEYSTORE + query_string
        r = requests.get(url = url)
        if r.status_code!=200: 
            raise Exception("Error while contacting the API:"+str(r.status_code))
        response_parsed = json.loads(r.text) 
        return response_parsed, r
        
        
    def encryptTransactionMessage(self, plain_text, **kwargs ): # if public_message_key is present use it if not get the key from the address
        if "public_message_key" in kwargs:
            public_message_key = kwargs["public_message_key"]
        elif "address" in kwargs:
            response,r = self.getMessageKeys(kwargs["address"], False)
            if not "public_message_key" in response:
                print("WARNIN : No message key for account " + kwargs["address"])
                return "",""
            public_message_key = response["public_message_key"]
        else:
            raise ValueError("public_message_key or address agrgument must be present")
            
        ciphered = EncryptMessage(public_message_key, plain_text)
        return ciphered, public_message_key
        
        
    def decrypteTransactionMessage(self, ciphered, **kwargs ): # if private_message_key is present use it if not get the key from the address and private_key
        if "private_message_key" in kwargs:
            private_message_key = kwargs["private_message_key"]
        elif "address" in kwargs and "private_key" in kwargs:
            response,r = self.getMessageKeys(kwargs["address"], True)
            if not "private_message_key" in response:
                print("WARNIN : No message key for account " + kwargs["address"])
                return "",""
            private_message_key = DecryptMessage(kwargs["private_key"], response["private_message_key"])
           
        else:
            raise ValueError("private_message_key or ( address and private_key ) agrgument must be present")
            
        plain_text = DecryptMessage(private_message_key, ciphered)
        return plain_text, private_message_key
    
    ############################### High level Functions    
        
    def getAccountType(self, address_to_check, api_end_point="" ):
        return int(self.getNumericalInfo(address_to_check, self.ACCOUNT_TYPE, api_end_point=api_end_point, divider=1, contract_id=1))

    def getAccountStatus(self, address_to_check, api_end_point=""):
        return int(self.getNumericalInfo(address_to_check, self.ACCOUNT_STATUS, api_end_point=api_end_point, divider=1, contract_id=1))

    def getAccountIsValidAdmin(self, address_to_check, api_end_point=""):
        return self.getAccountType(address_to_check, api_end_point=api_end_point)==2 and self.getAccountStatus(address_to_check, api_end_point=api_end_point)==1

    def getAccountIsOwner(self, address_to_check, api_end_point=""):
        return int(self.getNumericalInfo(address_to_check, self.ACCOUNT_IS_OWNER, api_end_point=api_end_point, divider=1, contract_id=1))

    def getAccountHasEnoughGas(self, address_to_check, api_end_point="", min_gas=5000000):
        return int(self.getTrInfos(address_to_check, api_end_point)['balance'])>min_gas


    def getAccountGlobalBalance(self, address_to_check, api_end_point=""):
        return self.getNumericalInfo(address_to_check, self.GLOBAL_BALANCE, api_end_point=api_end_point, divider=100., contract_id=1)

    def getAccountNantBalance(self, address_to_check, api_end_point=""):
        return self.getNumericalInfo(address_to_check, self.NANT_BALANCE, api_end_point=api_end_point, divider=100., contract_id=1)

    def getAccountCMBalance(self, address_to_check, api_end_point=""):
        return self.getNumericalInfo(address_to_check, self.CM_BALANCE, api_end_point=api_end_point, divider=100., contract_id=1)

    def getAccountCMLimitMaximum(self, address_to_check, api_end_point=""):
        return self.getNumericalInfo(address_to_check, self.ACCOUNT_CM_LIMIT_P, api_end_point=api_end_point, divider=100., contract_id=1)

    def getAccountCMLimitMinimum(self, address_to_check, api_end_point=""):
        return self.getNumericalInfo(address_to_check, self.ACCOUNT_CM_LIMIT_M, api_end_point=api_end_point, divider=100., contract_id=1)
        
          
    ############################### High level Transactions
    def transfertNant(self, sender_account, dest_address, amount,  **kwargs): #server="", message_from="", message_to=""):
        """Transfert Nantissed current Currency (server) from the sender to the destination wallet

        Parameters:
        sender_account (eth_account import::Account): An account with enough balance on the current server. Will sign the transaction
        dest_address (string): The public address of the wallet to be credited (0x12345... format)
        amount (double): amount (in the current Currency) to be transfered from the sender wallet to the destination wallet
       
       """
        # setup the endpoint
        server = ""
        if "server" in kwargs:
            server = kwargs["server"]

        self.resetApis(use_new=True)
        
        
        # prepare messages
        if "message_from" in kwargs and kwargs["message_from"]!="":
            
            ciphered_message_from, public_key = self.encryptTransactionMessage(kwargs["message_from"], address=sender_account.address)
        else:
            ciphered_message_from = "" 
             
        if "message_to" in kwargs and kwargs["message_to"]!="":
            ciphered_message_to, public_key = self.encryptTransactionMessage(kwargs["message_to"], address=dest_address)
        else:
            ciphered_message_to = ""    
        
         # Get sender wallet infos
        status = self.getAccountStatus(sender_account.address)
        if status==0:
            raise Exception("The sender wallet " + sender_account.address+ " is locked on server "+self._server + " (" + self._contract_1+") and therefore cannot initiate a transfer.")
            
        balance = self.getAccountNantBalance(sender_account.address) 
        if balance<amount:
             raise Exception("The sender wallet " + sender_account.address+ " has an insuficient Nant balance on server "+self._server + " (" + self._contract_1+") to complete this transfer.")
        
        # Get destination wallet infos
        status = self.getAccountStatus(dest_address)
        if status==0:
            raise Exception("The destination wallet " + dest_address+ " is locked on server "+self._server + " (" + self._contract_++") and therefore cannot recieve a transfer.")
        
        # Prepare data    
        amount_cent = int(100*amount)
        data = self.encodeAddressForTransaction(dest_address)
        data += self.encodeNumber(amount_cent)

        # send transaction
        print("INFO >ComChain::ApiCommunication > Transferring "+str(amount)+" nantissed "+self._server + " from wallet "+sender_account.address+" to target wallet " + dest_address+ " on server "+self._server + " (" + self._contract_1+","+ self._contract_2+")")
        return self.sendTransaction(self.NANT_TRANSFERT + data, sender_account, ciphered_message_from, ciphered_message_to, 2)

    
    def transfertCM(self, sender_account, dest_address, amount,  **kwargs):# message_from="", message_to=""):
        """Transfert Mutual Credit current Currency (server) from the sender to the destination wallet

        Parameters:
        sender_account (eth_account import::Account): An account with enough balance on the current server. Will sign the transaction
        dest_address (string): The public address of the wallet to be credited (0x12345... format)
        amount (double): amount (in the current Currency) to be transfered from the sender wallet to the destination wallet
       
       """
        # setup the endpoint
        self.resetApis(use_new=True)

        # prepare messages
        if "message_from" in kwargs and kwargs["message_from"]!="":
            ciphered_message_from, public_key = self.encryptTransactionMessage(kwargs["message_from"], address=sender_account.address)
        else:
            ciphered_message_from = "" 
             
        if "message_to" in kwargs and kwargs["message_to"]!="":
            ciphered_message_to, public_key = self.encryptTransactionMessage(kwargs["message_to"], address=dest_address)
        else:
            ciphered_message_to = ""    
        
        
        
         # Get sender wallet infos
        status = self.getAccountStatus(sender_account.address)
        if status==0:
            raise Exception("The sender wallet " + sender_account.address+ " is locked on server "+self._server + " (" + self._contract_1+") and therefore cannot initiate a transfer.")
            
        balance = self.getAccountCMBalance(sender_account.address) 
        if balance<amount:
             raise Exception("The sender wallet " + sender_account.address+ " has an insuficient CM balance on server "+self._server + " (" + self._contract_1+") to complete this transfer.")
        
        # Get destination wallet infos
        status = self.getAccountStatus(dest_address)
        if status==0:
            raise Exception("The destination wallet " + dest_address+ " is locked on server "+self._server + " (" + self._contract_1+") and therefore cannot recieve a transfer.")
        
        # Prepare data    
        amount_cent = int(100*amount)
        data = self.encodeAddressForTransaction(dest_address)
        data += self.encodeNumber(amount_cent)

        # send transaction
        print("INFO >ComChain::ApiCommunication > Transferring "+str(amount)+" mutual credit "+self._server + " from wallet "+sender_account.address+" to target wallet " + dest_address+ " on server "+self._server + " (" + self._contract_1+","+ self._contract_2+")")
        return self.sendTransaction(self.CM_TRANSFERT + data, sender_account, ciphered_message_from, ciphered_message_to, 2)
                                                                                 
 
    ############################### High level Admin restricted Transactions        
    def lockUnlockAccount(self, admin_account, address, lock=True):
        """Lock or unlock an Wallet on the current Currency (server)

        Parameters:
        admin_account (eth_account import::Account): An account with admin permission on the current server. Will sign the transaction
        address (string): The public address of the wallet to be locked/unlocked (0x12345... format)
        lock (bool): if True, lock the wallet, if False unlock it
       
       """
        # setup the endpoint
        self.resetApis(use_new=True)       

        # Check the admin
        self.checkAdmin(admin_account.address)

        # Get wallet infos
        status = self.getAccountStatus(address)
        
        if lock and status == 0:
            print("INFO >ComChain::ApiCommunication > The wallet " + address+ " is already locked")
            return "", objectview({"text":"N.A."}) 
        elif not lock and status == 1:
            print("INFO >ComChain::ApiCommunication > The wallet " + address+ " is already unlocked")
            return "", objectview({"text":"N.A."}) 
        else:
        
           # Get wallet infos
            acc_type = self.getAccountType(address)
            lim_m = self.getAccountCMLimitMinimum(address)
            lim_p = self.getAccountCMLimitMaximum(address)

            status = 1
            if lock:
                status=0
           
            # prepare the data
            data = self.encodeAddressForTransaction(address)
            data += self.encodeNumber(status) + self.encodeNumber(acc_type) + self.encodeNumber(int(lim_p*100)) + self.encodeNumber(int(lim_m*100))
            
            # send the transaction
            print("INFO >ComChain::ApiCommunication > Locking/unlocking the wallet " + address+ " on server "+self._server + " (" + self._contract_1+")")
            return self.sendTransaction(self.ACCOUNT_PARAM + data, admin_account)
                       
    def pledgeAccount(self, admin_account, address, amount):
        """Pledge a given amount to a Wallet on the current Currency (server)

        Parameters:
        admin_account (eth_account import::Account): An account with admin permission on the current server. Will sign the transaction
        address (string): The public address of the wallet to be pledged (0x12345... format)
        amount (double): amount (in the current Currency) to be pledged to the wallet
       
       """
        # setup the endpoint
        self.resetApis(use_new=True)
        
        # Check the admin
        self.checkAdmin(admin_account.address)

        # Get wallet infos
        status = self.getAccountStatus(address)
        if status==0:
            print("WARN >ComChain::ApiCommunication > The target wallet " + address+ " is locked on server "+self._server + " (" + self._contract_1+")")
        
        # Prepare data    
        amount_cent = int(100*amount)
        data = self.encodeAddressForTransaction(address)
        data += self.encodeNumber(amount_cent)

        # send transaction
        print("INFO >ComChain::ApiCommunication > Pledging "+str(amount)+" to target wallet " + address+ " on server "+self._server + " (" + self._contract_1+") through end-point " + self._end_point)
        return self.sendTransaction(self.PLEDGE + data, admin_account)
                     

