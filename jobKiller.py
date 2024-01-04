# Python 3.6+ Required
# Rubrik Job Killer

import json
import requests
import urllib3
import getpass
import logging
import syslog
import datetime
import time
import os
from urllib import parse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def generateToken(target, username, password):
    thesession = requests.Session()
    thesession.verify = False
    baseurl = "https://"+target+"/api/"
    url = baseurl+"internal/session"
    payload = {"initParams":{}}
    response = thesession.post(url=url, auth=(username, password), json=payload)
    responseJson = response.json()
    #print("")
    #print(responseJson)
    if "token" in responseJson['session']:
        finalToken = responseJson['session']['token']
    else:
        #print(response.json())
        attemptId = response.json()['mfaResponse']['attemptId']
        code = input("Enter TOTP Code: ")
        data = {
            "initParams":{}, 
            "mfaParams":{ 
                "attemptId":attemptId,
                "challengeSetId":"N/A",
                "challengeId":"rubrik-totp-auth",
                "credValue":code
                }
            }
        challengeResponse = thesession.post(url=url, timeout=120, json=data, auth=(username,password))
        finalToken = challengeResponse.json()['session']['token']
    return finalToken

def connectRubrik(dripaddress,username,password):
    drrbksess = requests.Session()
    drrbksess.verify = False
    baseurl = "https://"+dripaddress+"/api/"
    drsessurl = baseurl + "v1/session"
    drtoken = generateToken(dripaddress, username, password)
    drbearer = "Bearer " + drtoken
    drheader = {'Authorization': drbearer}
    drrbksess.headers = drheader
    testurl = baseurl + "v1/cluster/me"
    drtestconnect = drrbksess.get(url=testurl)
    drtestresponse = drtestconnect.status_code
    drtestjson = drtestconnect.json()
    return drrbksess, drbearer;
    
def generateFilterPayload():
    payload = {}
    if currentFilters['limit'] > 0:
        payload['limit'] = currentFilters['limit']
    if len(currentFilters['job_type']) > 2:
        payload['job_type'] = currentFilters['job_type']
    if len(currentFilters['object_type']) > 2:
        payload['object_type'] = currentFilters['object_type']
    if len(currentFilters['object_name']) > 2:
        payload['object_name'] = currentFilters['object_name']
    if len(currentFilters['node_name']) > 2:
        payload['node_name'] = currentFilters['node_name']
    if len(currentFilters['job_state']) > 2:
        payload['job_state'] = currentFilters['job_state']
    if currentFilters['is_first_full']:
        payload['is_first_full'] = True
    if currentFilters['include_log_jobs']:
        payload['include_log_jobs'] = True
    return payload

def updateJobData():
    url = basedrurl+"v1/job_monitoring"
    payload = generateFilterPayload()
    print("")
    print("Collecting Job Data...")
    response = drsession.get(url=url, params=payload)
    allJobData['latestPull'] = response.json()['jobMonitoringInfoList']
    print(json.dumps(response.json(), indent=4))

def displayJobs():
    print("")
    print("nothing really to show here yet")

#### Main Body
passone = "one"
passtwo = "two"

# Collect User Information and connect to Rubrik
os.system('clear')
drclusterip = input("Enter Rubrik DR Cluster IP or Hostname: ")
drusername = input("Enter Rubrik DR username []: ")
while passone != passtwo:
    passone = getpass.getpass('Enter Rubrik Password: ')
    passtwo = getpass.getpass('Re-Enter Rubrik Password: ')
    if passone != passtwo:
        print("Passwords do not match")
drpassword = passone
passone = "blank"
passtwo = "blank"
basedrurl = "https://"+drclusterip+"/api/"
urlclusterid = basedrurl+"v1/cluster/me"
urlvmcall = basedrurl+"v1/vmware/vm"
print(" ")
print("Connecting to DR Rubrik at "+basedrurl)
drsession, globaltoken = connectRubrik(drclusterip,drusername,drpassword)
response = drsession.get(url=urlclusterid)
if response.status_code == 200:
    clusterjson = response.json()
    drlocalid = clusterjson['id']
    urlclustername = basedrurl+"internal/cluster/"+clusterjson['id']+"/name"
    clsnameresponse = drsession.get(url=urlclustername)
    print(" ")
    print("Connected to "+clsnameresponse.text)
else:
    print("Failed to connect")
    print("Response: "+str(response))
    print(response.text)
    exit()

#### Main Menu
allJobData = {}
currentFilters = {
    "limit" : 25,
    "job_type" : "",
    "include_log_jobs" : False,
    "is_first_full": False,
    "object_type": "",
    "object_name": "",
    "node_name": "",
    "job_state": "Active"
    }

menuLoop = True
while menuLoop:
    print("-----------------")
    print(" ")
    print("Current Filters:")
    print(json.dumps(currentFilters, indent=4))
    print("Job Options: ")
    print("1) Display jobs matching current filters")
    print("2) Change filters")
    print("X) Quit Program")
    menuOption = input("Enter Selection: ")
    if menuOption == "1":
        updateJobData()
        displayJobs()
    elif menuOption == "2":
        changeTheFilters()
    elif menuOption.lower() == "x":
        menuLoop = False
    else:
        print("Invalid Entry")
