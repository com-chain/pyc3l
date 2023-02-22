from eth_account import Account
import getpass

import tkinter as tk
from tkinter import filedialog
import json
import logging

logger = logging.getLogger(__name__)


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
        logger.info('Opening file %r', account_file)
        logger.info('  File contains wallet with address 0x%s', acc_object['address'])
        logger.info('  File contains wallet with address 0x%s on server %r',
                    acc_object['address'],
                    acc_object['server']['name'])
        if len(password) ==0:
            password = getpass.getpass()

        account_admin = Account.privateKeyToAccount(Account.decrypt(keyfile, password))
      
        logger.info("Account %s opened.", account_admin.address)
        return acc_object['server']['name'], account_admin
