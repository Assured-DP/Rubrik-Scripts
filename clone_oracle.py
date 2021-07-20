## Clone Oracle DB from Rubrik to Target
## Paramaters
## rubrikclone.py <<SourceHost>> <<SourceDB>> <<TargetHost>> <<pfile>>
## sample:
## rubrikclone.py

import json
import requests
import urllib3
import syslog
import datetime
import sys
import time
import os

## Required to silence HTTPS certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

## Rubrik Connection Functions
def connectRubrik(hostname, username, password):
    global token
    session = requests.Session()
    session.verify = False
    sessurl = "https://"+hostname+"/api/v1/session"
    firstresponse = requests.request('POST', url=sessurl, auth=(username,password), verify=False)
    syslog.syslog(syslog.LOG_INFO, hostname+": Connection Status reponse "+str(firstresponse.status_code))
    firstjson = firstresponse.json()
    sessionBearer = "Bearer "+firstjson['token']
    sessionHeader = {'Authorization': sessionBearer, 'Content-Type': 'application/json'}
    session.headers = sessionHeader
    testurl = "https://"+hostname+"/api/v1/cluster/me"
    response = session.get(url=testurl)
    return session

def initMemory():
    if os.path.exists(memoryFile):
        diskmemory = json.load(open(memoryFile))
        diskmemory['sourceHost'] = sys.argv[1]
        diskmemory['sourceDB'] = sys.argv[2]
        diskmemory['targetHost'] = sys.argv[3]
        diskmemory['customPfile'] = sys.argv[4]
        return diskmemory
    else:
        syslog.syslog(syslog.LOG_INFO, "Establishing memory: "+str(memoryFile))
        memory = {
            "sourceHost": "",
            "sourceDB": "",
            "targetHost": "",
            "customPfile":"",
            "lastTime": "",
            "recoveryPoint": 0,
            "snapId": ""
            }
        with open(memoryFile, 'w') as dmpit:
            json.dump(memory, dmpit, indent=4)
        return memory

def manageMemory(memory):
    with open(memoryFile, 'w') as dmpit:
         syslog.syslog(syslog.LOG_INFO, "Writing memory file: "+str(memoryFile))
         json.dump(memory, dmpit, indent=4)
         return memory

def getOracleHost(name):
    url = "https://"+rubrikTarget+"/api/internal/oracle/host?name="+name
    response = rubriksession.get(url=url)
    responsejson = response.json()
    resultcount = len(responsejson['data'])
    if resultcount == 0:
        syslog.syslog(syslog.LOG_INFO, name+" resulted in 0 matches")
        sys.exit("No Host Match for "+name)
    if resultcount == 1:
        syslog.syslog(syslog.LOG_INFO, name+" resulted in 1 match: "+responsejson['data'][0]['name'])
        result = responsejson['data'][0]
    if resultcount > 1:
        syslog.syslog(syslog.LOG_INFO, name+" resulted in "+str(resultcount)+" matches")
        matchlist = []
        for match in responsejson['data']:
            matchlist.append(match['name'])
        syslog.syslog(syslog.LOG_INFO, name+" matches: "+str(matchlist))
        sys.exit("Too many matches for "+name)
    if result['status'] != "Connected":
        syslog.syslog(syslog.LOG_INFO, name+" currently disconnected. Check Rubrik Backup Service and retry")
        sys.exit(name+" currently disconnected from Rubrik. Exiting")
    return result['id']

def getOracleDB(name):
    url = "https://"+rubrikTarget+"/api/internal/oracle/db?name="+name+"&is_relic=false&include_backup_task_info=false"
    response = rubriksession.get(url=url)
    responsejson = response.json()
    resultcount = len(responsejson['data'])
    filteredDbList = []
    for result in responsejson['data']:
        if result['standaloneHostId'] == database['source']['hostId']:
            filteredDbList.append(result)
    resultcount = len(filteredDbList)
    if resultcount == 0:
        syslog.syslog(syslog.LOG_INFO, name+" DB resulted in 0 matches")
        sys.exit("No DB Match for "+name)
    if resultcount == 1:
        syslog.syslog(syslog.LOG_INFO, name+" DB resulted in 1 match: "+responsejson['data'][0]['name']+" on host: "+myMemory['sourceHost'])
        result = filteredDbList[0]['id']
    if resultcount > 1:
        syslog.syslog(syslog.LOG_INFO, name+" DB matches multiple databases: "+str(filteredDbList))
        sys.exit("Too many DB matches for "+name)
    return result

def converttoms(timestring):
    endTime = datetime.datetime.strptime(timestring, "%Y-%m-%dT%H:%M:%S.%fZ").strftime('%s.%f')
    endTime = int(float(endTime)*1000)
    syslog.syslog(syslog.LOG_INFO, "Converted "+timestring+" to "+str(endTime))
    return endTime

def getRecoveryPoint():
    global myMemory
    url = "https://"+rubrikTarget+"/api/internal/oracle/db/"+database['source']['sourceDbId']+"/recoverable_range"
    response = rubriksession.get(url=url)
    responsejson = response.json()
    latest = responsejson['data'][len(responsejson['data'])-1]
    database['source']['snapid'] = latest['dbSnapshotSummaries'][len(latest['dbSnapshotSummaries'])-1]['id']
    syslog.syslog(syslog.LOG_INFO, myMemory['sourceDB']+" latest recovery point: "+latest['endTime'])
    thisTime = datetime.datetime.strptime(latest['endTime'], "%Y-%m-%dT%H:%M:%S.%fZ")
    if len(myMemory['lastTime'])>0:
        syslog.syslog(syslog.LOG_INFO, "Previous Restore in Memory, setting to: "+str(myMemory['lastTime']))
        lastTime = datetime.datetime.strptime(myMemory['lastTime'], "%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        syslog.syslog(syslog.LOG_INFO, "No Previous Restore in Memory, setting to: "+latest['endTime'])
        lastTime = thisTime
        myMemory['lastTime'] = latest['endTime']
    offset = thisTime - datetime.timedelta(hours=-24)
    syslog.syslog(syslog.LOG_INFO, "Offest detected as "+str(offset)+" hours")
    if lastTime > offset:
        myMemory['lastTime'] = latest['endTime']
    recoverypoint = converttoms(myMemory['lastTime'])
    myMemory['snapId'] = database['source']['snapid']
    return recoverypoint

def runExport():
    url = "https://"+rubrikTarget+"/api/internal/oracle/db/"+database['source']['sourceDbId']+"/export"
    payload = {
        "recoveryPoint": {
        "snapshotId": myMemory['snapId']
            },
        "targetOracleHostOrRacId": database['target']['hostId'],
        "customPfilePath": myMemory['customPfile']
        }
    syslog.syslog(syslog.LOG_INFO, "Payload sent: "+str(payload))
    response = rubriksession.post(url=url, json=payload)
    syslog.syslog(syslog.LOG_INFO, "Status Response: "+str(response.status_code))
    syslog.syslog(syslog.LOG_INFO, "Status Data: "+str(response.text))
    exporttask = response.json()
    #sample = "EXPORT_ORACLE_SNAPSHOT_b299f9be-da85-42c6-9e7f-93652ec678f9_de914856-88c4-4d20-9049-1a4cff17efb6:::0"
    #return sample
    return exporttask['id']

def monitorExport(exporttask):
    url = "https://"+rubrikTarget+"/api/internal/oracle/request/"+exporttask
    inProcess = True
    while inProcess:
        response = rubriksession.get(url=url)
        responsejson = response.json()
        if responsejson['status'] == "RUNNING":
            syslog.syslog(syslog.LOG_INFO, "Export Running: "+str(responsejson['progress']))
            time.sleep(4)
        if responsejson['status'] == "SUCCEEDED":
            syslog.syslog(syslog.LOG_INFO, "Export Succeeded, closing with exit 0")
            inProcess = False
            sys.exit(0)
        if responsejson['status'] == "FAILED":
            syslog.syslog(syslog.LOG_INFO, "Export Failed")
            syslog.syslog(syslog.LOG_ERR, "Failure: "+responsejson['error']['message'])
            inProcess = False
            sys.exit(1)

## Main Body
## Global Variables
user = "TempOracle"
password = "<<PASSWORD>"

memoryFile = "./.rubrikMemory.json"
syslog.syslog(syslog.LOG_INFO, "Checking for history at path: "+str(memoryFile))

if not (os.path.exists(sys.argv[4])):
    syslog.syslog(syslog.LOG_ERR, "Failure for custom pfile path, check proper path: "+sys.argv[4] )
    sys.exit(1)

diskmemory = initMemory()
myMemory = initMemory()
database = {
    "source" : {},
    "target" : {}
    }

rubrikTarget = "TARGETIPORHOST"

#print(myMemory)
#print(diskmemory)

## Update Memory with Paramaters
syslog.syslog(syslog.LOG_INFO, "Recording Parameters: "+str(memoryFile))
myMemory = manageMemory(myMemory)
syslog.syslog(syslog.LOG_INFO, "Memory Recorded: "+str(myMemory))

## Establish Rubrik Connection
syslog.syslog(syslog.LOG_INFO, "Connecting to Rubrik: "+str(rubrikTarget))
rubriksession = connectRubrik(rubrikTarget, user, password )

## Establish Rubrik ID information
# SourceHost
syslog.syslog(syslog.LOG_INFO, "Searching for Oracle Host "+myMemory['sourceHost'])
database['source']['hostId'] = getOracleHost(myMemory['sourceHost'])
syslog.syslog(syslog.LOG_INFO, myMemory['sourceHost']+" discovered as "+database['source']['hostId'])

# TargetHost
syslog.syslog(syslog.LOG_INFO, "Searching for Oracle Host "+myMemory['targetHost'])
database['target']['hostId'] = getOracleHost(myMemory['targetHost'])
syslog.syslog(syslog.LOG_INFO, myMemory['targetHost']+" discovered as "+database['target']['hostId'])

# SourceDB
syslog.syslog(syslog.LOG_INFO, "Searching for Oracle DB "+myMemory['sourceDB'])
database['source']['sourceDbId'] = getOracleDB(myMemory['sourceDB'])
syslog.syslog(syslog.LOG_INFO, myMemory['sourceDB']+" identified as "+database['source']['sourceDbId'])

## Find Latest Snapshot Time
if myMemory['snapId'] == "":
    myMemory['recoveryPoint'] = getRecoveryPoint()
myMemory = manageMemory(myMemory)
syslog.syslog(syslog.LOG_INFO, str(myMemory['recoveryPoint'])+" set as recovery point")

## Execute the Export
exportTask = runExport()

## Monitor Export
monitorExport(exportTask)
