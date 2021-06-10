## Python 3.6 Unprotect and Reassign Script
## Author Andrew Eva - Assured Data Protection
## 
## Purpose:
## VDI Images automatically created by Nutanix AHV Frame need to be excluded from backup
##
## Challenges:
## There are some persistent images that need to be protected so they need to be differentiated from the auto discovered virtual machines
## Any backup images that have been automatically created need to be purged, but false-positives need to be held for 3 days
##
## Persistent Image String Exampled:
## frame-instance-prod-v12345-s1234567
##
## Source File Sample:
## { 
##     "rubrikuser" = "admin"
##     "rubrikpassword" : "DifficultPassword"
##     "rubrikhost" : "127.0.0.1"
##     "matchstring" : "frame-instance-prod-v\d{5}-s\d{7}"
##     "retentionsla" : "Bronze"
## }
##
##  Paramater       | Description
##  =====================================================
##  -h, --help      | Display Help
##  -f, --file      | Use Configuration File
##  -u, --user      | Rubrik User [required]
##  -p, --password  | Rubrik Password [optional]
##  -t, --target    | Rubrik Hostname or IP Address in IPv4
##  -s, --sla       | Target SLA for Retention
##  -r, --regex     | Regex to match for Virtual Machines
##  -n, --noop      | Display results but make no changes
##  ====
##  Please view https://github.com/Assured-DP/Rubrik-Scripts for complete notes
##  Script is created and maintained by Assured Data Protection without warranty to be free of defects
##  Use at your own risk

import json
import urllib3
import requests
import re
import datetime
import syslog
import sys
import getopt
import os

## Global Variables
class allparams():
    rubrikuser = ""
    rubrikpassword = ""
    rubrikhost = "" ## Hostname or IP Address
    matchstring = 'frame-instance-prod-v\d{5}-s\d{7}'
    retentionsla = "ShortHold"
    sourcefile = './unprotectsettings.conf'
    verbose = True
    noop = False

myClusterData = {}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

## Functions
def testConnection(rubrikSession, baseurl):
    testurl = baseurl+'v1/cluster/me'
    testresp = 503
    try:
        testcall = rubrikSession.get(url=testurl)
        testresp = testcall.status_code
    except:
        testresp = 503
    if testresp == 200:
        myClusterData = testcall.json()
        print(json.dumps(myClusterData, indent=4))
        myClusterData['versmajor'] = int(myClusterData['version'][0])
        myClusterData['versminor'] = int(myClusterData['version'][2])
        myClusterData['versfix'] = int(myClusterData['version'][4])
    syslog.syslog(syslog.LOG_INFO, 'Testresponse '+str(testresp))
    return testresp

def connectRubrik(ipaddress,username,password):
    session = requests.Session()
    session.verify = False
    baseurl = "https://"+ipaddress+"/api/"
    drsessurl = baseurl + "v1/session"
    tokenresponse = requests.request('POST', url=drsessurl, auth=(username,password), verify=False)
    try:
        tokenjson = tokenresponse.json()
    except:
        statusLog("ERROR", "Unable to login to rubrik at "+ipaddress+" with user "+username)
        quit()
    token = tokenjson['token']
    bearer = "Bearer " + token
    header = {'Authorization': bearer}
    session.headers = header
    testresponse = testConnection(session,baseurl)
    if testresponse == 200:
        statusLog("INFO","Successful Connnection with Rubrik: "+ipaddress)
    else:
        statusLog("ERROR","Rubrik connection at "+ipaddress+" failed with response: "+str(testresponse))
        quit()
    return session, token;

def statusLog(severity,message):
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    print(timestamp+" "+severity+": "+message)
    if severity == "ERROR":
        syslog.syslog(syslog.LOG_ERR, message)
        return
    if severity == "DEBUG":
        syslog.syslog(syslog.LOG_DEBUG, message)
        return
    if severity == "WARNING":
        syslog.syslog(syslog.LOG_WARNING, message)
        return
    syslog.syslog(syslog.LOG_INFO, message)

def showhelp():
    print("Please review help text below")
    print("Paramaters and Options:")
    optiontemplate = "{0:15} | {1:35}"
    print(optiontemplate.format("Paramater","Description"))
    print("=====================================================")
    print(optiontemplate.format("-h, --help","Display Help"))
    print(optiontemplate.format("-f, --file","Use Configuration File"))
    print(optiontemplate.format("-u, --user","Rubrik User [required]"))
    print(optiontemplate.format("-p, --password","Rubrik Password [optional]"))
    print(optiontemplate.format("-t, --target","Rubrik Hostname or IP Address in IPv4"))
    print(optiontemplate.format("-s, --sla","Target SLA for Retention"))
    print(optiontemplate.format("-r, --regex","Regex to match for Virtual Machines"))
    print(optiontemplate.format("-n, --noop","Display results but perform no actions"))
    print("====")
    print("Please view https://github.com/Assured-DP/Rubrik-Scripts for complete notes")
    print("Script is created and maintained by Assured Data Protection without warranty to be free of defects")
    print("Use at your own risk")

def loadFile(path):
    filedata = {}
    if os.path.exists(path):
        try:
            filedata = json.load(open(path))
        except ValueError as borked:
            statusLog("ERROR","Attempt to load "+path+" failed: "+str(borked))
            quit()
        allparams.rubrikuser = filedata['rubrikuser']
        allparams.rubrikpassword = filedata['rubrikpassword']
        allparams.rubrikhost = filedata['rubrikhost']
        allparams.matchstring = filedata['matchstring']
        allparams.retentionsla = filedata['retentionsla']
        allparams.verbose = filedata['verbose']
        allparams.noop = filedata['noop']
        
def processArguments(parameters):
    if len(parameters) == 0:
        showhelp()
        quit()
    try:
        opts, parameters = getopt.getopt(parameters,"f:u:p:t:h:s:r:n:",["file=","user=","password=","target=","sla=","regex="])
    except getopt.GetoptError as err:
        print("Invalid Parameter")
        print(err)
        showhelp()
        quit(2)
    for opt, arg in opts:
        print(str(opt)+" is "+str(arg))
        if opt in ("-h","--help"):
            showhelp()
            quit()
        elif opt in ("-f","--file"):
            statusLog("INFO","Input File "+arg+" specified, ignoring other params")
            loadFile(arg)
            return
        elif opt in ("-u","--user"):
            allparams.rubrikuser = arg
        elif opt in ("-p","--password"):
            allparams.rubrikpassword = arg
        elif opt in ("-t","--target"):
            allparams.rubrikhost = arg
        elif opt in ("-s","--sla"):
            allparams.retentionsla = arg
        elif opt in ("-r","--regex"):
            allparams.matchstring = arg
        elif opt in ("-n","--noop"):
            allparams.noop = arg
        
def getAllVMs(session):
    statusLog("INFO","Discovering all non-relic local virtual machines")
    url = "https://"+allparams.rubrikhost+"/api/v1/vmware/vm?primary_cluster_id=local&is_relic=false"
    response = session.get(url=url)
    allvms = []
    if response.status_code == 200:
        responsejson = response.json()
        statusLog("INFO","Discovered "+str(len(responsejson['data']))+" local VMWare VMs")
        for vm in responsejson['data']:
            allvms.append(vm)
    else:
        statusLog("ERROR","Get VMware VMs call failed with status code: "+str(response.status_code))
    url = "https://"+allparams.rubrikhost+"/api/internal/nutanix/vm?primary_cluster_id=local&is_relic=false"
    response = session.get(url=url)
    if response.status_code == 200:
        responsejson = response.json()
        statusLog("INFO","Discovered "+str(len(responsejson['data']))+" local AHV VMs")
        for vm in responsejson['data']:
            allvms.append(vm)
    else:
        statusLog("ERROR","Get AHV VMs call failed with status code: "+str(response.status_code))
    url = "https://"+allparams.rubrikhost+"/api/internal/hyperv/vm?primary_cluster_id=local&is_relic=false"
    response = session.get(url=url)
    if response.status_code == 200:
        responsejson = response.json()
        statusLog("INFO","Discovered "+str(len(responsejson['data']))+" local HyperV VMs")
        for vm in responsejson['data']:
            allvms.append(vm)
    else:
        statusLog("ERROR","Get HyperV VMs call failed with status code: "+str(response.status_code))
    return allvms

def applyFilters(allvms):
    pattern = re.compile(allparams.matchstring)
    matched = []
    for vm in allvms:
        if pattern.match(vm['name']):
            if allparams.verbose:
                statusLog("INFO","Matched "+vm['name']+" to RegEx: "+allparams.matchstring)
            if vm['slaAssignment'] == "Direct":
                if allparams.verbose:
                    statusLog("INFO",vm['name']+" has a Direct SLA of "+vm['configuredSlaDomainName']+": skipping")
            else:
                if allparams.verbose:
                    statusLog("INFO",vm['name']+" has an effective SLA of "+vm['effectiveSlaDomainName'])
                matched.append(vm)
    return matched

def getSlaId(name):
    url = "https://"+allparams.rubrikhost+"/api/v2/sla_domain?primary_cluster_id=local&name="+name
    response = rubrik.get(url=url)
    if response.status_code == 200:
        responsejson = response.json()
        if responsejson['total'] > 1:
            statusLog("WARNING","Found "+str(response['total'])+" matching Local SLAs named "+name+". Attempting case matching")
            for sla in responsejson['data']:
                if sla['name'] == name:
                    statusLog("INFO","Case matched to SLA with ID "+sla['id']+". Proceeding.")
                    return sla
            statusLog("WARNING","No Case match found. Defaulting to first found SLA with ID: "+responsejson['data'][0]['id'])
            return responsejson['data'][0]
        elif responsejson['total'] == 1:    
            statusLog("INFO","Retrieved SLA ID "+responsejson['data'][0]['id']+" for SLA "+name)
            return responsejson['data'][0]
        else:
            statusLog("ERROR","No SLA found with name "+name+". Script exiting")
            quit()
    else:
        statusLog("ERROR","Failed to retrieve SLA ID on local cluster for "+name)
        quit()

def removeProtection(vmlist):
    removelist = []
    for vm in vmlist:
        removelist.append(vm['id'])
    bodyjson = {
        "managedIds": removelist,
        "existingSnapshotRetention": "KeepForever"
        }
    unprotecturl = "https://"+allparams.rubrikhost+"/api/internal/sla_domain/UNPROTECTED/assign"
    statusLog("INFO","Changing "+str(len(vmlist))+" virtual machines to UNPROTECTED with Keep Forever")
    if not allparams.noop:
        response = rubrik.post(url=unprotecturl, json=bodyjson)
    else:
        response = "No Op Triggered"
    if response.status_code == 204:
        statusLog("INFO","Successfully assigned protection")
    else:
        statusLog("ERROR","Request to remove SLAs has failed with error: "+str(response.status_code))
    statusLog("INFO","Retreiving SLA ID")
    sla = getSlaId(allparams.retentionsla)
    statusLog("INFO","Retreiving any relics for reassigned VMs")
    for vm in vmlist:
        url = "https://"+allparams.rubrikhost+"/api/internal/unmanaged_object/"+vm['id']+"/snapshot"
        response = rubrik.get(url=url)
        if response.status_code == 200:
            thejson = response.json()
            if thejson['total'] == 0:
                if allparams.verbose:
                    statusLog("INFO","No unmanaged snapshots for "+vm['name'])
            else:
                ondemandcount = 0
                snaplist = []
                for snap in thejson['data']:
                    if snap['unmanagedSnapshotType'] == "OnDemand":
                        ondemandcount = ondemandcount + 1
                    else:
                        if snap['retentionSlaDomainId'] == sla['id']:
                            continue
                        else:
                            statusLog("WARNING",vm['name']+": Unmanaged snapshot "+snap['id']+" from "+snap['date']+" reassigned to "+sla['name'])
                            snaplist.append(snap)
                if len(snaplist) > 0:
                    reassignurl = "https://"+allparams.rubrikhost+"/api/internal/unmanaged_object/snapshot/assign_sla"
                    body = {
                        "slaDomainId": sla['id'],
                        "snapshotIds": snaplist
                        }
                    statusLog("INFO","Bulk reassignment for "+vm['name']+" running")
                    if not allparams.noop:
                        response = rubrik.post(url=reassignurl, json=body)
                    else:
                        response = "No Op Triggered"
                    if response.status_code == 204:
                        statusLog("INFO","Bulk reassignment for "+vm['name']+" completed successfully")
                    else:
                        statusLog("ERROR","Bulk reassignment failed with status: "+str(response.status_code))
                        
        
    

## Main Body
processArguments(sys.argv[1:])
rubrik, rubriktoken = connectRubrik(allparams.rubrikhost, allparams.rubrikuser, allparams.rubrikpassword)

vmlist = getAllVMs(rubrik)

filteredvms = applyFilters(vmlist)
if len(filteredvms) == 0:
    statusLog("INFO","Nothing to reassign. Script Exiting")
else:
    removeProtection(filteredvms)