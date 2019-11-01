from ApiHandling import ApiHandling 
import requests 
import json
from eth_account import Account
from web3 import Web3
from web3.eth import Eth
import codecs


class ApiCommunication:

    def __init__(self, api_handler, server):
        self._api_handler=api_handler
        self._server = server
        self._contract = self._api_handler.getServerContract(self._server)
        self._end_point = self._api_handler.getApiEndpoint()
        
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
        
        
    def buildInfoData(self, function, address):
        if address.startswith('0x'):
            address=address[2:]
        if function.startswith('0x'):
            function=function[2:]
        return '0x'+function+address.zfill(72-len(function))
        
        
    def callNumericInfo(self, api, contract, function, address, divider=100.):
        data =  {'ethCall[data]':self.buildInfoData(function,address), 
            'ethCall[to]':contract}
        r = requests.post(url = api, data = data)
        if r.status_code!=200: 
            raise Exception("Error while contacting the API:"+str(r.status_code))
        response_parsed = json.loads(r.text)
        if not response_parsed['error']:
            return self.decodeNumber(response_parsed['data'])/divider
        else:
            return -1
        
    def getNumericalInfo(self, address_to_check, function, api_end_point="", server="", contract="", divider=100.):
        if len(api_end_point)!=0:
            self._end_point = api_end_point;
            
        if len(server)>0:
            self._server = server 
            self._contract = self._api_handler.getServerContract(self._server)
        
        if len(contract)>0:
            self._contract =contract
        
        return self.callNumericInfo(self._end_point, self._contract, function, address_to_check, divider)  
        
        
    def getTrInfos(self, address, api_end_point=""):
        if len(api_end_point)!=0:
            self._end_point = api_end_point; 
        data = {'txdata':address}
        
        r = requests.post(url = self._end_point, data = data)
        response_parsed = json.loads(r.text)
        return response_parsed['data']
        
    ############################### High level Functions    
        
    def getAccountType(self, address_to_check, api_end_point="", server="", contract=""):
        return int(self.getNumericalInfo(address_to_check, self.ACCOUNT_TYPE, api_end_point=api_end_point, server=server, contract=contract, divider=1))

    def getAccountStatus(self, address_to_check, api_end_point="", server="", contract=""):
        return int(self.getNumericalInfo(address_to_check, self.ACCOUNT_STATUS, api_end_point=api_end_point, server=server, contract=contract, divider=1))

    def getAccountIsValidAdmin(self, address_to_check, api_end_point="", server="", contract=""):
        return self.getAccountType(address_to_check, api_end_point=api_end_point, server=server, contract=contract)==2 and self.getAccountStatus(address_to_check, api_end_point=api_end_point, server=server, contract=contract)==1

    def getAccountIsOwner(self, address_to_check, api_end_point="", server="", contract=""):
        return int(self.getNumericalInfo(address_to_check, self.ACCOUNT_IS_OWNER, api_end_point=api_end_point, server=server, contract=contract, divider=1))

    def getAccountHasEnoughGas(self, address_to_check, api_end_point="", min_gas=5000000):
        return int(self.getTrInfos(address_to_check, api_end_point)['balance'])>min_gas


    def getAccountGlobalBalance(self, address_to_check, api_end_point="", server="", contract=""):
        return self.getNumericalInfo(address_to_check, self.GLOBAL_BALANCE, api_end_point=api_end_point, server=server, contract=contract)

    def getAccountNantBalance(self, address_to_check, api_end_point="", server="", contract=""):
        return self.getNumericalInfo(address_to_check, self.NANT_BALANCE, api_end_point=api_end_point, server=server, contract=contract)

    def getAccountCMBalance(self, address_to_check, api_end_point="", server="", contract=""):
        return self.getNumericalInfo(address_to_check, self.CM_BALANCE, api_end_point=api_end_point, server=server, contract=contract)

    def getAccountCMLimitMaximum(self, address_to_check, api_end_point="", server="", contract=""):
        return self.getNumericalInfo(address_to_check, self.ACCOUNT_CM_LIMIT_P, api_end_point=api_end_point, server=server, contract=contract)

    def getAccountCMLimitMinimum(self, address_to_check, api_end_point="", server="", contract=""):
        return self.getNumericalInfo(address_to_check, self.ACCOUNT_CM_LIMIT_M, api_end_point=api_end_point, server=server, contract=contract)
        
          
    ############################### High level Transactions     
    def lockUnlockAccount(self, admin_account, address, lock=True, server="", contract=""):
        # get the contract
        if len(server)>0:
            self._server = server
            self._contract = self._api_handler.getServerContract(self._server)
        
        if len(contract)>0:
            self._contract = contract
            
        # get the endpoint 
        self._end_point = self._api_handler.getApiEndpoint()
        

        # Check the admin
        if not self.getAccountIsValidAdmin(admin_account.address):
            raise Exception("The provided Admin Account with address "+admin_account.address+" is not an active admin on server "+self._server + " (" + self._contract+")")
        
        if not self.getAccountHasEnoughGas(admin_account.address):
            raise Exception("The provided Admin Account with address "+admin_account.address+" has not enough gas.")


        # Get wallet infos
        status = self.getAccountStatus(address)
        
        if lock and status == 0:
            print("INFO >ComChain::ApiCommunication > The wallet " + address+ " is already locked")
        elif not lock and status == 1:
            print("INFO >ComChain::ApiCommunication > The wallet " + address+ " is already unlocked")
        else:
            acc_type = self.getAccountType(address)
            lim_m = self.getAccountCMLimitMinimum(address)
            lim_p = self.getAccountCMLimitMaximum(address)

            status = 1
            if lock:
                status=0
            data = address
            if data.startswith('0x'):
                data = data[2:]
            data += self.encodeNumber(status) + self.encodeNumber(acc_type) + self.encodeNumber(int(lim_p*100)) + self.encodeNumber(int(lim_m*100))
            
            tr_infos = self.getTrInfos(admin_account.address)
            
            transaction = {
                
                'to': contract,
                'value': 0,
                'gas': 5000000,
                'gasPrice':  int(tr_infos['gasprice'],0),
                'nonce': int(tr_infos['nonce'],0),
                'data':self.ACCOUNT_PARAM + data,
                'from':admin_account.address

            }
            signed = Eth.account.signTransaction(transaction, admin_account.privateKey)
            str_version = '0x'+str(codecs.getencoder('hex_codec')(signed.rawTransaction)[0])[2:-1]
            raw_tx = {'rawtx': str_version}
            print("INFO >ComChain::ApiCommunication > Locking/unlocking the wallet " + address+ " on server "+self._server + " (" + self._contract+")")
            r = requests.post(url = self._end_point, data = raw_tx)
            if r.status_code!=200: 
                raise Exception("Error while contacting the API:"+str(r.status_code))
            response_parsed = json.loads(r.text)
            return response_parsed['data'], r
                       
    def pledgeAccount(self, admin_account, address, amount, unlock_if_locked=False, server="", contract=""):
         # get the contract

        if len(server)>0:
            self._server = server
            self._contract = self._api_handler.getServerContract(self._server)
        
        if len(contract)>0:
            self._contract = contract
            
        # get the endpoint 
        self._end_point = self._api_handler.getApiEndpoint()
        
        
        # Check the admin
        if not self.getAccountIsValidAdmin(admin_account.address):
            raise Exception("The provided Admin Account with address "+admin_account.address+" is not an active admin on server "+self._server + " (" + self._contract+")")
        
        if not self.getAccountHasEnoughGas(admin_account.address):
            raise Exception("The provided Admin Account with address "+admin_account.address+" has not enough gas.")


        # Get wallet infos
        status = self.getAccountStatus(address)
        
        if status==0:
            print("WARN >ComChain::ApiCommunication > The target wallet " + address+ " is locked on server "+self._server + " (" + self._contract+")")
            if unlock_if_locked:
                print("INFO >ComChain::ApiCommunication > Unlocking the target wallet " + address+ ".")
                lockUnlockAccount(admin_account, address, lock=False)
            else:
                raise Exception("A locked account cannot be pledged")
        print("INFO >ComChain::ApiCommunication > Pledging "+amount+" to target wallet " + address+ " on server "+self._server + " (" + self._contract+")")
        amount_cent = int(100*amount)
        data = address
        if data.startswith('0x'):
            data = data[2:]
        data += self.encodeNumber(amount_cent)

        tr_infos = self.getTrInfos(self._end_point, admin_account.address)

        transaction = {

            'to': contract,
            'value': 0,
            'gas': 5000000,
            'gasPrice':  int(tr_infos['gasprice'],0),
            'nonce': int(tr_infos['nonce'],0),
            'data':self.PLEDGE + data,
            'from':admin_account.address

        }
        signed = Eth.account.signTransaction(transaction, admin_account.privateKey)
        str_version = '0x'+str(codecs.getencoder('hex_codec')(signed.rawTransaction)[0])[2:-1]
        raw_tx = {'rawtx': str_version}
        r = requests.post(url = api_end_point, data = raw_tx)
        if r.status_code!=200: 
            raise Exception("Error while contacting the API:"+str(r.status_code))
        response_parsed = json.loads(r.text)
        return response_parsed['data'], r
                               
