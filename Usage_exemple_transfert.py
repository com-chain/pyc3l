from PythonClient.LocalAccountOpener import LocalAccountOpener
from PythonClient.ApiHandling import ApiHandling
from PythonClient.ApiCommunication import ApiCommunication

# Load the API
api_handling = ApiHandling()

# refresh the node list
api_handling.updateNodeRepo()


account_opener = LocalAccountOpener()
server, sender_account = account_opener.openAccountInteractively('open sender account',account_file='')

target_address = '0xE00000000000000000000000000000000000000E'


#load the high level functions
api_com = ApiCommunication(api_handling, server)


print('The sender wallet '+sender_account.address+', on server '+server+' has a balance of = '+str(api_com.getAccountGlobalBalance(sender_account.address)))


res, r = api_com.transfertNant(sender_account, target_address, 0.01, message_from="test", message_to="test")
print(res)
print(r.text)
print("")


