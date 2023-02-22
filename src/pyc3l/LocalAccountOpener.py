from eth_account import Account
import getpass

import tkinter as tk
from tkinter import filedialog
import json

class LocalAccountOpener:

    def __init__(self):
        #setup tk
        self.root = tk.Tk()
        self.root.withdraw()

    # load account from file and password
    def openAccountInteractively(self, dialog_title, account_file='', password=''):
        if len(account_file)==0:
            account_file = filedialog.askopenfilename(title = dialog_title)
        file_admin = open(account_file, 'r') 
        keyfile = file_admin.read()   
        acc_object = json.loads(keyfile)
        print('INFO >ComChain::LocalAccountOpener > Opening file:')
        print(account_file)
        print('')
        print('INFO >ComChain::LocalAccountOpener > This file contains a wallet with address:')
        print('INFO >ComChain::LocalAccountOpener > 0x'+acc_object['address'])
        print('INFO >ComChain::LocalAccountOpener > and associated with server:')
        print('INFO >ComChain::LocalAccountOpener > ' + acc_object['server']['name'])
        print('')
        if len(password) ==0:
            password = getpass.getpass()

        account_admin = Account.privateKeyToAccount(Account.decrypt(keyfile, password))
      
        print('INFO >ComChain::LocalAccountOpener > Account '+account_admin.address+" opened.")
        return acc_object['server']['name'], account_admin
