from PythonClient.LocalAccountOpener import LocalAccountOpener
from PythonClient.ApiHandling import ApiHandling
from PythonClient.ApiCommunication import ApiCommunication
import sys
import csv
import time
import tkinter as tk  #python3 only
from tkinter import filedialog

###############################################################################
## Parametrization
###############################################################################
## CSV File containing the transactions (if '' a file selector is open)
csv_file = 'List_payement.csv'
## Columns in the CSV file
address_column='Address'
amount_column='Montant'
message_to='Libellé envoyé'
message_from='Libellé gardé'

## .dat File containing the wallet sending the funds (if '' a file selector is open)
account_file=''
## password for unlocking the wallet (if '' the password is asked on the command line)
password=''

###############################################################################

def readCSV(file_path):
    header=[]
    data=[]

    with open(file_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        length=0
        for row in csv_reader:

            if line_count == 0:
                length=len(row)
                header=[item.replace('"','').strip() for item in row]
            else:
                if len(row)>length:
                    new_row=[]
                    in_str=False
                    for item in row:

                        if not in_str:
                            new_row.append(item)
                            if item.count('"')==1:
                                in_str=True
                        else:
                            new_row[-1]= new_row[-1] + ','+item
                            if item.count('"')==1:
                                    in_str=False
                    row=new_row

                row = [item.replace('"','').strip() for item in row]
                data.append(row)
            line_count += 1
    return header, data
    
def prepareTransactionData(header, data, address_column='Address',
                           amount_column='Montant',
                           message_to='Libellé envoyé',
                           message_from='Libellé gardé'):

    add_ind = header.index(address_column)
    ammount_ind = header.index(amount_column)
    m_to_ind = header.index(message_to)
    m_from_ind = header.index(message_from)


    prepared_transactions=[]
    total=0
    for row in data:
        prepared_transactions.append({'add':row[add_ind],'amount':float(row[ammount_ind]),'m_to':row[m_to_ind],'m_from':row[m_from_ind]})
        total+=prepared_transactions[-1]['amount']

    return prepared_transactions, total

def getCsvFile(csv_file):
    if len(csv_file)==0:
            tk().withdraw()
            return filedialog.askopenfilename(title = 'Choose a CSV File')



################################################################################
##     (1) CSV file handling
################################################################################
csv_file = getCsvFile(csv_file)
header, data=readCSV(csv_file)
prepared_transactions, total = prepareTransactionData(header, data)

print('The file "'+csv_file+'" has been read.')
print('It contains '+str(len(prepared_transactions))+' transaction(s) for a total of '+str(total))

if not input('Continue to the execution (y/n)')=='y':
    sys.exit()
    
    
################################################################################
##     (2) Load the account and check funds availability
################################################################################

# Load the API
api_handling = ApiHandling()

# refresh the node list
api_handling.updateNodeRepo()

account_opener = LocalAccountOpener()
server, sender_account = account_opener.openAccountInteractively('Select Sender Wallet',account_file=account_file, password=password)

#load the high level functions
api_com = ApiCommunication(api_handling, server)

CM_balance=api_com.getAccountCMBalance(sender_account.address)
CM_limit=api_com.getAccountCMLimitMinimum(sender_account.address)
Nant_balance = api_com.getAccountNantBalance(sender_account.address)
Sender_status = api_com.getAccountStatus(sender_account.address)

if Sender_status==1:
    print("Error: The Sender Wallet is locked!")
    sys.exit()

use_cm=False
use_negative_cm=False
use_nant=False
use_mix=False

if total<=CM_balance:
    use_cm=True
elif total<=Nant_balance:
    use_nant=True
elif total<=CM_balance-CM_limit:
    print("Warning: The Mutual credit balance of the Sender Wallet will be negative.")
    use_negative_cm=True
else:
    print("Warning: Not enough fund for unsplited transactions")
    if total>CM_balance+CM_balance-CM_limit:
        print("Error: The Sender Wallet is underfunded: This batch of payment="+str(total)+" Nant balance="+str(Nant_balance)+" CM balance="+str(CM_balance)+" CM Limit="+str(CM_limit))
        sys.exit()
    else:
        use_mix=True
        

################################################################################
##     (3) Check target accounts are available
################################################################################

total_cm=0
total_nant=0
for tran in prepared_transactions:
    target_address = tran['add']
    target_amount = tran['amount']
    
    target_status = api_com.getAccountStatus(target_address)
    if target_status!=1:
         print("Warning: The Target Wallet with address "+target_address+"is locked and will be skipped")
    else:
        tran['unlocked']=1
        if use_nant:
            total_nant+=target_amount
            tran['type']='N'
        else:
            CM_target_balance=api_com.getAccountCMBalance(target_address)
            CM_target_limit=api_com.getAccountCMLimitMaximum(target_address)
            tran['canCM'] = target_amount+CM_target_balance<CM_target_limit
            if  tran['canCM']:
                total_cm+=target_amount
                tran['type']='CM'
            else:
                total_nant+=target_amount
                tran['type']='N'
                print("Warning: The Target Wallet with address "+target_address+" cannot accept "+str(target_amount)+ "in mutual credit (will try the nant.)")

if  total_nant>Nant_balance or  total_cm>CM_balance-CM_limit:
    print("Error: Due to constraint on the target amount the splitting ("+str(total_nant)+"Nant + "+str(total_cm)+"CM) is not compatible with the available funds")
    sys.exit()          
    
if not input('Ready to send the payments: do you want to proceed? (y/n)')=='y':
    sys.exit()
    
################################################################################
##     (4) Execute transactions
################################################################################
transaction_hash=[]
for tran in prepared_transactions:
    if tran['unlocked']==1 and tran['type']=='N':
        res, r = api_com.transfertNant(sender_account, tran['add'], tran['amount'], message_from=tran['m_from'], message_to=tran['m_to'])
        transaction_hash[res]=tran['add']
        print("Transaction Nant sent to "+tran['add'])
        time.sleep( 15 ) # Delay for not overloading the BlockChain
    elif  tran['unlocked']==1 and tran['type']=='CM':
        res, r = api_com.transfertCM(sender_account, tran['add'], tran['amount'], message_from=tran['m_from'], message_to=tran['m_to'])
        transaction_hash[res]=tran['add']
        print("Transaction CM sent to "+tran['add'])
        time.sleep( 15 ) # Delay for not overloading the BlockChain
    else :
        print("Transaction to "+tran['add'] + " skipped")

################################################################################
##     (5) Wait for confirmation
################################################################################

while len(transaction_hash)>0:
    hash_to_test = list(transaction_hash.keys())[0] 
    if api_com.getTransactionBLock(hash_to_test)!=None:
        print("Transaction to "+transaction_hash[hash_to_test] + " has been mined")
    else:
        time.sleep( 15 ) 

print("All transaction have been mined, bye!")

