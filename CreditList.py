#!/usr/local/bin/python
# coding: utf-8

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
csv_file = ''
## Columns in the CSV file
address_column='Address'
amount_column='Montant'
message_column='Message'

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
                           amount_column='Montant', message_column='Message'):

    add_ind = header.index(address_column)
    ammount_ind = header.index(amount_column)
    message_ind = header.index(message_column)
    


    prepared_transactions=[]
    total=0
    for row in data:
        prepared_transactions.append({'add':row[add_ind],'amount':float(row[ammount_ind]),'message':row[message_ind]})
        total+=prepared_transactions[-1]['amount']

    return prepared_transactions, total

def getCsvFile(csv_file):
    if len(csv_file)==0:
            return filedialog.askopenfilename(title = 'Choose a CSV File')
    else:
        return csv_file



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
print('INFO: Load the API.')
api_handling = ApiHandling()

# refresh the node list
print('INFO: refresh the node list.')
api_handling.updateNodeRepo()

account_opener = LocalAccountOpener()
server, sender_account = account_opener.openAccountInteractively('Select Admin Wallet',account_file=account_file, password=password)

#load the high level functions
print('INFO: load the high level functions.')
api_com = ApiCommunication(api_handling, server)


print('INFO: Check the provided account to have admin role.')
api_com.checkAdmin(sender_account.address)
Sender_status = api_com.getAccountStatus(sender_account.address)

if Sender_status!=1:
    print("Error: The Admin Wallet is locked!")
    sys.exit()


        

################################################################################
##     (3) Check target accounts are available
################################################################################

print('INFO: Check the targets accounts are not locked.')
for tran in prepared_transactions:
    target_address = tran['add']
    
    target_status = api_com.getAccountStatus(target_address)
    if target_status!=1:
        print("Warning: The Target Wallet with address "+target_address+"is locked and will be skipped")
        tran['unlocked']=0
    else:
        tran['unlocked']=1
           
if not input('Ready to send the nantissement on '+server+': do you want to proceed? (y/n)')=='y':
    sys.exit()
    
################################################################################
##     (4) Execute transactions
################################################################################
transaction_hash={}
for tran in prepared_transactions:
    if tran['unlocked']==1:
        res, r = api_com.pledgeAccount(sender_account, tran['add'], tran['amount'], message_to=tran['message']) 
        transaction_hash[res]=tran['add']
        print("Transaction Nant sent to "+tran['add'] + ' ('+str(tran['amount'])+'LEM) with message "'+tran['message']+'" Transaction Hash='+ res)
        
        time.sleep( 30 ) # Delay for not overloading the BlockChain
    
    else :
        print("Transaction to "+tran['add'] + " skipped")

print("All transaction have been send, bye!")

################################################################################
##     (5) Wait for confirmation
################################################################################
#
#while len(transaction_hash)>0:
#    hash_to_test = list(transaction_hash.keys())[0] 
#    if api_com.getTransactionBLock(hash_to_test)!=None:
#        print("Transaction to "+transaction_hash[hash_to_test] + " has been mined")
#    else:
#        time.sleep( 15 ) 

#print("All transaction have been mined, bye!")

