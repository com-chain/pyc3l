import requests 
import json
from random import randrange
import datetime
import os.path
import logging
import tempfile
import os
import shutil
from contextlib import closing

logger = logging.getLogger(__name__)


class ApiHandling:

    def __init__(self, endpoint_file=None):
        ''' Constructor for this ApiHandling. '''
        if not endpoint_file:
            home = os.path.expanduser('~')

            xdg_state_home = os.environ.get('XDG_STATE_HOME') or \
                os.path.join(home, '.local', 'state')

            self.endpoint_file = os.path.join(
                xdg_state_home, "pyc3l", "current_endpoints.txt")
        else:
            self.endpoint_file = endpoint_file
        self.default_enpoints = ['https://node-cc-001.cchosting.org', 'https://node-001.cchosting.org', 'https://node-002.cchosting.org', 'https://node-003.cchosting.org', 'https://node-004.cchosting.org']
        self.ipfs_config_url = '/ipns/QmaAAZor2uLKnrzGCwyXTSwogJqmPjJgvpYgpmtz5XcSmR/configs/'
        self.ipfs_node_list_url = '/ipns/QmcRWARTpuEf9E87cdA4FfjBkv7rKTJyfvsLFTzXsGATbL'
        self.api_url = '/api.php'


    def getNodeRepo(self):
        if not os.path.isfile(self.endpoint_file):
            return self.default_enpoints
        return self.read_endpoints()
        
    def updateNodeRepo(self):
        current_list = self.getNodeRepo()
        found=False
        while len(current_list)>0:
            index = randrange(len(current_list))
            url = current_list[index]+self.ipfs_node_list_url+'?_='+str(datetime.datetime.now())
            logger.info("Getting node list from %r", url)
            try:
                r = requests.get(url = url)
                if r.status_code!=200: 
                    logger.warn('return status %d for %r', r.status_code, url)
                    continue
                else:
                    found=True
                    self.save_endpoints(json.loads(r.text))

                    break
            except: 
                logger.warn('exception raised by %r', url)
                del current_list[index]
        if not found:
            raise Exception("Unable to find a valid ipfs node. Please check that you are online.") 

    def getIPFSEndpoint(self):
        end_point_list = self.getNodeRepo();
        nb_try=0
        found = False
        while nb_try<20:
            nb_try+=1
            index = randrange(len(end_point_list))
            try:
                url = end_point_list[index]+self.ipfs_config_url+'/ping.json?_='+str(datetime.datetime.now())
                r = requests.get(url=url)
                if r.status_code==200:
                    found=True
                    return end_point_list[index]
                else:
                    logger.warn('status %d from %r', r.status_code, url)
            except :
                logger.warn('Exception raised from %r', url)
           
        if not found:
            raise Exception("Unable to find a valid ipfs node after "+str(nb_try)+" Try.")   
            
    def getCurrentBlock(self, endpoint=''):
        if len(endpoint)==0:
            endpoint = self.getApiEndpoint()
        r = requests.get(url = endpoint+'?_='+str(datetime.datetime.now()))
        return r.text
              
    def getApiEndpoint(self):
        end_point_list = self.getNodeRepo();
        nb_try=0
        found = False
        while nb_try<20:
            nb_try+=1
            index = randrange(len(end_point_list))
            try:
                url = end_point_list[index]+self.api_url+'?_='+str(datetime.datetime.now())
                r = requests.get(url=url)
                if r.status_code==200:
                    found=True
                    logger.info('Selected end-point: %r', end_point_list[index])
                    return end_point_list[index]+self.api_url
                else:
                    logger.warn('status %s from %r', str(r.status_code), url)
            except:
                logger.warn('Exception raised by %r', url)
                
        if not found:
            raise Exception("Unable to find a valid api endpoint after "+str(nb_try)+" Try.")             
                
                
    def getServerContract(self, server_name):
        end_point_url = self.getIPFSEndpoint()
        r = requests.get(url = end_point_url+self.ipfs_config_url+'/'+server_name+'.json?'+str(datetime.datetime.now()))
        if r.status_code!=200: 
            raise Exception("Unknow server "+server_name)
        response_parsed = json.loads(r.text)
        return response_parsed['server']['contract_1'], response_parsed['server']['contract_2']                         

    def save_endpoints(self, endpoints):
        """Save endpoints in state file

        This implementation is atomic and thus race-condition free.

        """
        if set(self.read_endpoints()) == set(endpoints):
            logger.info("Saved endpoint list is already up-to-date.")
            return
        f, tmp = tempfile.mkstemp()
        with closing(os.fdopen(f, "w")) as file:
            for line in endpoints:
                file.write(line + "\n")
        if not os.path.isfile(self.endpoint_file):
            logger.info("Create local endpoint file named %r.", self.endpoint_file)
            os.makedirs(
                os.path.dirname(self.endpoint_file),
                exist_ok=True
            )
        shutil.move(tmp, self.endpoint_file)  ## atomic

    def read_endpoints(self):
        with open(self.endpoint_file, "r") as file:
            lines = file.readlines()

        # remove the endline char
        for index in range(len(lines)) :
            lines[index]=lines[index][:-1]

        return lines
