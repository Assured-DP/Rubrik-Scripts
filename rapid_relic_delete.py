#!/bin/python
## Relic management Script
## (C) Andrew Eva - Assured Data Protection

# Modules
import json
import requests
import urllib3
import getpass
import logging
import datetime
import os
import threading
import syslog
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def recordAnswer(userinput, answerreference):
    global answerjson
    if userinput =="":
        return answerjson[answerreference]
    else:
        answerjson[answerreference] = userinput
        answerjson = manageAnswerFile(answerjson)
        return userinput

def manageAnswerFile(answerfile):
    answerpath = '/tmp/.tempfile.json'
    if os.path.exists(answerpath):
        loadedanswers = json.load(open(answerpath))
        if loadedanswers == answerfile:
            return answerfile
        else:
            with open(answerpath, 'w') as dmpfile:
                json.dump(answerfile, dmpfile)
            return answerfile
    else:
        answerfile = establishAnswers()
        with open(answerpath, 'w') as dmpfile:
            json.dump(answerfile, dmpfile)
    return answerfile

def connectRubrik(dripaddress,username,password):
    global localprimaryclusterid
    #tempsess = requests.Session()
    #tempsess.verify = False
    drrbksess = requests.Session()
    drrbksess.verify = False
    baseurl = "https://"+dripaddress+"/api/"
    #tempsess.auth = (username, password)
    drsessurl = baseurl + "v1/session"
    #print "Generating Token"
    drtokenresponse = requests.request('POST', url=drsessurl, auth=(username,password), verify=False)
    #print "Token Reponse: "+str(drtokenresponse)
    drtokenjson = drtokenresponse.json()
    drtoken = drtokenjson['token']
    drbearer = "Bearer " + drtoken
    drheader = {'Authorization': drbearer}
    #print "Header Assembled: "+str(drheader)
    drrbksess.headers = drheader
    testurl = baseurl + "v1/cluster/me"
    drtestconnect = drrbksess.get(url=testurl)
    drtestresponse = drtestconnect.status_code
    drtestjson = drtestconnect.json()
    localprimaryclusterid = drtestjson['id']
    #print "Token Auth Test: "+str(drtestresponse)
    return drrbksess, drbearer;    

def applyFilters(source, **filters):
    current = source.copy()
    output = []
    for obj in current:
        add = True
        for key, value in filters.items():
            if add:
                if value in obj['key']:
                    add = True
                else:
                    add = False
        if add:
            output.append(obj.copy())
    return output

def genericFilter(obj,key,value):
    if value.casefold() in obj[key].casefold():
        return True
    else:
        return False

def displayList(thelist):
    print("=======================================================================================================================================")
    tbltemplatea = "{0:25}| {1:25} | {2:20} | {3:15} "
    print(tbltemplatea.format("Object Name","Type","Status","Snapcount"))
    print("---------------------------------------------------------------------------------------------------------------------------------------")
    for obj in thelist:
        print(tbltemplatea.format(obj['name'][0:25],obj['objectType'],obj['unmanagedStatus'],str(obj['snapshotCount'])))
    
def menu(listsize, currentlist):
    print(str(listsize)+" Filtered objects, choose Option: ")
    print("(N)ame Filter")
    print("(S)tatus Filter")
    print("(T)ype Filter")
    print("(C)lear Filters")
    print("(P)rint list")
    print("e(X)it")
    option = input("Selection: ")
    if option.lower() == "p":
        displayList(currentlist)
        return currentlist.copy()
    if option.lower() == "n":
        print("")
        namefilter = input("Enter Name to Filter with: ")
        reducedlist = []
        reducedlist.append([d for d in filteredlist if genericFilter(d,"name",namefilter)])
        return reducedlist.copy()
        #print(json.dumps(reducedlist,indent=4))
    if option.lower() == "c":
        reducedlist = objlist['data'].copy()
        listsize = len(reducedlist)
        return reducedlist.copy()
    if option.lower() == "x":
        quit()
    if option.lower() == "s":
        print("")
        namefilter = input("Enter STatus to Filter with (Protected, ReplicatedRelic, Relic, Unprotected): ")
        reducedlist = []
        reducedlist.append([d for d in currentlist if genericFilter(d,"unmanagedStatus",namefilter)])
        return reducedlist.copy()
        

########################## MAIN BODY ##################################
maxThreadCount = 10
passone = "one"
passtwo = "two"
completed = [0]
bootedvmlist = []
localprimaryclusterid = ""
relicdatabase = {
    "clusters": []
    }

# Setup Answer File
answerpath = '/tmp/.tempfile.json'
answerjson = { 
    "rubrikip": "a", 
    "rubrikuser": "b"
    }
    
if os.path.exists(answerpath):
    answerjson = json.load(open(answerpath))
else:
    with open(answerpath, 'w') as dmpfile:
        json.dump(answerjson, dmpfile)

# Collect User Information
os.system('clear')
clusterip = input("Enter Rubrik Cluster IP or Hostname [{0}]: ".format(answerjson['rubrikip']))
clusterip = recordAnswer(clusterip, "rubrikip")
username = input("Enter Rubrik username [{0}]: ".format(answerjson['rubrikuser']))
username = recordAnswer(username, "rubrikuser")
while passone != passtwo:
    passone = getpass.getpass('Enter Rubrik Password: ')
    passtwo = getpass.getpass('Re-Enter Rubrik Password: ')
    if passone != passtwo:
        print("Passwords do not match")
password = passone
passone = "blank"
passtwo = "blank"
baseurl = "https://"+clusterip+"/api/"
urlclusterid = baseurl+"v1/cluster/me"
urlvmcall = baseurl+"v1/vmware/vm"
print(" ")

# Connect to DR Rubrik
print("Connecting to Rubrik at "+baseurl)
rubrik, globaltoken = connectRubrik(clusterip,username,password)
response = rubrik.get(url=urlclusterid)
if response.status_code == 200:
    clusterjson = response.json()
    localid = clusterjson['id']
    urlclustername = baseurl+"internal/cluster/"+clusterjson['id']+"/name"
    clsnameresponse = rubrik.get(url=urlclustername)
    print(" ")
    print("Connected to "+clsnameresponse.text)
else:
    print("Failed to connect")
    print("Response: "+str(response))
    print(response.text)
    exit()   

# Collect Unmanaged Objects
url = baseurl+"v1/unmanaged_object"
print("Loading Object List...")
response = rubrik.get(url=url)
objlist = response.json()

print("Loaded "+str(len(objlist['data']))+" Objects")
filteredlist = objlist['data'].copy()

samesame = True
while samesame:
    filteredlist = menu(len(filteredlist),filteredlist)
    print(filteredlist)
    