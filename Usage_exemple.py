from LocalAccountOpener import LocalAccountOpener
from ApiHandling import ApiHandling
from ApiCommunication import ApiCommunication

# Load the API
api_handling = ApiHandling()

# refresh the node list
api_handling.updateNodeRepo()



account_opener = LocalAccountOpener()
server, admin_account = account_opener.openAccountInteractively('open admin account',account_file='')

address_test_lock = '0x0000000000000000000000000000000000000000'


#load the high level functions
api_com = ApiCommunication(api_handling, server)

status = api_com.getAccountStatus(address_test_lock)
print( 'Account is currently actif = ' + str(status))
res, r = api_com.lockUnlockAccount(admin_account, address_test_lock, lock=(status==1))
print(res)
print(r)
print( 'Account is currently actif = ' + str(api_com.getAccountStatus(address_test_lock)))
