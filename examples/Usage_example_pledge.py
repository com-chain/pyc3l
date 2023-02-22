from pyc3l.LocalAccountOpener import LocalAccountOpener
from pyc3l.ApiHandling import ApiHandling
from pyc3l.ApiCommunication import ApiCommunication

# Load the API
api_handling = ApiHandling()


# refresh the node list
api_handling.updateNodeRepo()



account_opener = LocalAccountOpener()
server, admin_account = account_opener.openAccountInteractively('open admin account',account_file='')

address_test_lock = '0xE00000000000000000000000000000000000000E'


#load the high level functions
api_com = ApiCommunication(api_handling, server)

status = api_com.getAccountStatus(address_test_lock)
print( 'Account '+address_test_lock+' is currently actif = ' + str(status))
print('Balance = '+str(api_com.getAccountGlobalBalance(address_test_lock)))


res, r = api_com.lockUnlockAccount(admin_account, address_test_lock, lock=False)
print(res)
print(r.text)
print("")

res, r = api_com.pledgeAccount(admin_account, address_test_lock, 0.01)
print(res)
print(r.text)
print("")

res, r = api_com.lockUnlockAccount(admin_account, address_test_lock, lock=True)
print(res)
print(r.text)
print("")
