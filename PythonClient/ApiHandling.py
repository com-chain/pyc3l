import requests 
import json
from random import randrange
import datetime
import os.path

class ApiHandling:
    def __init__(self, endpoint_file="Current_Ednpoints.txt"):
        ''' Constructor for this ApiHandling. '''
        self.endpoint_file = endpoint_file
        self.default_enpoints = ['https://node-001.cchosting.org', 'https://node-002.cchosting.org']
        self.ipfs_config_url = '/ipns/QmaAAZor2uLKnrzGCwyXTSwogJqmPjJgvpYgpmtz5XcSmR/configs/'
        self.ipfs_node_list_url = '/ipns/Qmb2paHChFzvU9fnDtAvmpbEcwyKfpKjaHc67j4GCmWLZv'
        self.api_url = '/api.php'
        
    def initNodeRepoHandling(self):
        if not os.path.isfile(self.endpoint_file):
            print("INFO >ComChain::ApiHandling > Create Local repo file named " + self.endpoint_file)
            
        with open(self.endpoint_file, "w") as file:
                for line in self.default_enpoints:
                    file.write(line + "\n") 
                    
    def getNodeRepo(self):
        self.initNodeRepoHandling()

        with open(self.endpoint_file, "r") as file:
            lines = file.readlines()
            
        # remove the endline char    
        for index in range(len(lines)) :
            lines[index]=lines[index][:-1]
            
        return lines
        
    def updateNodeRepo(self):
        current_list = self.getNodeRepo()
        found=False
        while len(current_list)>0:
            index = randrange(len(current_list))
            url = current_list[index]+self.ipfs_node_list_url+'?_='+str(datetime.datetime.now())
            print("INFO >ComChain::ApiHandling > Getting node list from  :"+url)
            try:
                r = requests.get(url = url)
                if r.status_code!=200: 
                    print('WARN >ComChain::ApiHandling > '+url+' return status '+str(r.status_code))
                    continue
                else:
                    found=True
                    response_parsed = json.loads(r.text)
                    with open(self.endpoint_file, "w") as file:
                        for line in response_parsed:
                            file.write(line+ "\n") 
                    break
            except: 
                print('WARN >ComChain::ApiHandling > '+url+' rises an exception')
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
                r = requests.get(url = end_point_list[index]+self.ipfs_config_url+'/ping.json?_='+str(datetime.datetime.now()))
                if r.status_code==200:
                    found=True
                    return end_point_list[index]
                else:
                    print('WARN >ComChain::ApiHandling > ' + end_point_list[index]+self.ipfs_config_url+'/ping.json return status '+str(r.status_code))
            except :
                print('WARN >ComChain::ApiHandling > ' + end_point_list[index]+self.ipfs_config_url+'/ping.json throw error') 
           
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
                r = requests.get(url = end_point_list[index]+self.api_url+'?_='+str(datetime.datetime.now()))
                if r.status_code==200:
                    found=True
                    return end_point_list[index]+self.api_url
                else:
                    print('WARN >ComChain::ApiHandling > ' + end_point_list[index]+self.api_url+' return status '+str(r.status_code))
            except :
                print('WARN >ComChain::ApiHandling > ' + end_point_list[index]+self.api_url+' throw error') 
                
        if not found:
            raise Exception("Unable to find a valid api endpoint after "+str(nb_try)+" Try.")             
                
                
    def getServerContract(self, server_name):
        end_point_url = self.getIPFSEndpoint()
        r = requests.get(url = end_point_url+self.ipfs_config_url+'/'+server_name+'.json?'+str(datetime.datetime.now()))
        if r.status_code!=200: 
            raise Exception("Unknow server "+server_name)
        response_parsed = json.loads(r.text)
        return response_parsed['server']['contract_1']                         
