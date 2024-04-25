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
import rubrikSDK

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
# Walkthrough the New Answer Process
def recordAnswer(userinput, answerreference):
    global answerjson
    if userinput =="":
        return answerjson[answerreference]
    else:
        answerjson[answerreference] = userinput
        answerjson = manageAnswerFile(answerjson)
        return userinput

def manageAnswerFile(answerfile):
    homepath = str(os.path.expanduser('~')) 
    answerpath = homepath+'/.runbookntanswerfile.json'
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
    #drtokenresponse = requests.request('POST', url=drsessurl, auth=(username,password), verify=False)
    #print "Token Reponse: "+str(drtokenresponse)
    #drtokenjson = drtokenresponse.json()
    drtoken = rubrikSDK.connectCluster(dripaddress, password=password, username=username)
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

def grabReplicaClusters():
    url = baseurl+"internal/replication/source"
    response = rubrik.get(url=url)
    replicadata = response.json()
    relicdatabase['clusters'] = replicadata['data']
    relicdatabase['total'] = replicadata['total']
    
def addStoredAmounts():
    url = baseurl+"internal/stats/total_replication_storage"
    response = rubrik.get(url=url)
    storedinfo = response.json()
    for datapoint in storedinfo['remoteVmStorageOnPremise']:
        for cluster in relicdatabase['clusters']:
            if datapoint['remoteClusterUuid'] == cluster['sourceClusterUuid']:
                cluster['relicindex']['replicaspace'] = datapoint['totalStorage']

def humanReadable(inBytes):
    for unit in ['', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']:
        if abs(inBytes) < 1024:
            return "%3.1f%s" % (inBytes, unit)
        inBytes /= 1024.0
    return "%.1f%s" % (inBytes, 'ZB')

def displayReplication(filtertext):
    os.system('clear')
    print("=======================================================================================================================================")
    tbltemplatea = "{0:25}| {1:36} | {2:20} | {3:>7} | {4:>9} | {5:>13} | {6:>11} |"
    print(tbltemplatea.format("Cluster Name","UUID","Index Status","Objects","Snapcount","Replica Space","Relic Space"))
    print("---------------------------------------------------------------------------------------------------------------------------------------")
    count = 1
    for cluster in relicdatabase['clusters']:
        if not(filtertext in cluster['sourceClusterName']):
            count += 1
            continue
        if cluster['relicindex']['indexstatus'] == "Queued":
            prefix = "* "+str(count)+") "
        else:
            prefix = str(count)+") "
        print(tbltemplatea.format(prefix+cluster['sourceClusterName'],cluster['sourceClusterUuid'],cluster['relicindex']['indexstatus'],cluster['relicindex'][ 'objectcount'],cluster['relicindex']['snapcount'],str(humanReadable(cluster['relicindex']['replicaspace'])),str(humanReadable(cluster['relicindex']['relicspace']))))
        count += 1
    print("---")

def waitForThreads():
    slowDown = True
    while slowDown:
        if threading.active_count() > maxThreadCount:
            #print("Max Threads of "+str(maxThreadCount)+" reached, waiting for threads to complete")
            time.sleep(5)
        else:
            slowDown = False
        
def selectSource():
    keeplooping = True
    displayfilter = ""
    while keeplooping:
        displayReplication(displayfilter)
        choice = input("Select a source to index, (F) to filter, (C) for custom entry, or (X) to finish: ")
        if choice.lower() == "f":
            print("")
            displayfilter = input("Enter Filter by Text: ")
            continue
        if choice.lower() == "c":
            addCluster()
            continue
        if choice.lower() == "x":
            keeplooping = False
            return
        if relicdatabase['clusters'][int(choice)-1]['relicindex']['indexstatus'] == "Queued":
            relicdatabase['clusters'][int(choice)-1]['relicindex']['indexstatus'] = "Not Run"
        elif relicdatabase['clusters'][int(choice)-1]['relicindex']['indexstatus'] == "Not Run":
            relicdatabase['clusters'][int(choice)-1]['relicindex']['indexstatus'] = "Queued"

def slaIndexWorker(sla):
    print("place holder")
    
def checkObjectPrimary(obj, clusuuid):
    if obj['objectType'] == "VirtualMachine":
        url = baseurl+"v1/vmware/vm/"+obj['id']
    elif obj['objectType'] == "NutanixVirtualMachine":
        url = baseurl+"internal/nutanix/vm/"+obj['id']
    elif obj['objectType'] == "HypervVirtualMachine":
        url = baseurl+"internal/hyperv/vm/"+obj['id']
    elif obj['objectType'] == "MssqlDatabase":
        url = baseurl+"v1/mssql/db/"+obj['id']
    elif obj['objectType'] == "VolumeGroup":
        url = baseurl+"v1/volume_group/"+obj['id']
    elif obj['objectType'] == "OracleDatabase":
        url = baseurl+"internal/oracle/db/"+obj['id']
    elif "Fileset" in obj['objectType']:
        url = baseurl+"v1/fileset/"+obj['id']
    elif obj['objectType'] == "ManagedVolume":
        url = baseurl+"internal/managed_volume/"+obj['id']
    else:
        syslog.syslog(syslog.LOG_ERR, "Unknown ObjectType: "+obj['objectType'])
    response = rubrik.get(url=url)
    try:
        dataset = response.json()
    except:
        print(response.status_code)
        syslog.syslog(syslog.LOG_ERR, "Tried to get url: "+url)
        syslog.syslog(syslog.LOG_ERR, "Dataset response: "+response)
        quit()
    if not "fileset" in url:
        snapurl = url+"/snapshot"
        response = rubrik.get(url=snapurl)
        dataset['snapshots'] = response.json()
    else:
        data = dataset['snapshots'].copy()
        dataset['snapshots'] = {}
        dataset['snapshots']['data'] = data.copy()
    return dataset.copy()
        
def snapAudit(obj, rub):
    reliccount = 0
    keepforever = 0
    keepforeverids = []
    ondemand = 0
    ondemandids = []
    allkeepforever = False
    allondemand = False
    #print(obj)
    # Issue here may be "no snapshots"
    if not ("snapshots") in obj:
        syslog.syslog(syslog.LOG_INFO, obj['name']+" snaphots field missing: "+str(obj))
    elif not "data" in obj['snapshots']:
        syslog.syslog(syslog.LOG_INFO, obj['name']+" No data in snapthots field.")
    for snap in obj['snapshots']['data']:
        #print(snap)
        if snap['slaName'] == "Unprotected":
            ## snap['cloudState'] --> 0 and 6 has a local copy. all others do not. Integer value that represents the archival state of a snapshot. 0 means the snapshot is not archived. 2 means the snapshot is archived. 3 means the snapshot is downloaded from the archival location. 4 means the snapshot is in the process of being downloaded from the archival location. 6 means the snapshot is stored locally and at the archival location.
            if (snap['cloudState'] == 0) or (snap['cloudState'] == 6):
                if snap['snapshotRetentionInfo']['localInfo']['snapshotFrequency'] == "Forever":
                    keepforeverids.append(snap['id'])
                    keepforever += 1
            if (snap['cloudState'] == 2):
                try:
                    if snap['snapshotRetentionInfo']['archivalInfos'][0]['snapshotFrequency'] == "Forever":
                        keepforeverids.append(snap['id'])
                        keepforever += 1
                except:
                    syslog.syslog(syslog.LOG_ERR, "Archive Issue: "+json.dumps(snap))
        if snap['isOnDemandSnapshot']:
            ondemand += 1
            ondemandids.append(snap['id'])
    syslog.syslog(syslog.LOG_INFO, obj['name']+" snaps are (forever/ondemand/total): "+str(keepforever)+"/"+str(ondemand)+"/"+str(len(obj['snapshots']['data'])))
    if len(obj['snapshots']) == keepforever:
        allkeepforever = True
    if len(obj['snapshots']) == ondemand:
        allondemand = True
    obj['keepforever'] = keepforever
    obj['keepforeverids'] = keepforeverids
    obj['ondemand'] = ondemand
    obj['ondemandids'] = ondemandids
    obj['allforever'] = allkeepforever
    obj['allondemand'] = allondemand

def clusterIndexWorker(cluster):
    slaurl = baseurl+"v2/sla_domain?primary_cluster_id="+cluster['sourceClusterUuid']
    slaresponse = rubrik.get(url=slaurl)
    slajson = slaresponse.json()
    cluster['relicindex']['indexstatus'] = "Building SLA List"
    cluster['relicindex']['slaidlist'] = []
    cluster['sladata'] = slajson.copy()
    cluster['reliccount'] = 0
    cluster['snapcount'] = 0
    # Get SLA info
    if slajson['total'] > 0:
        for sla in slajson['data']:
            cluster['relicindex']['slaidlist'].append(sla['id'])
    else:
        cluster['relicindex']['indexstatus'] = "None"
    cluster['relicindex']['indexstatus'] = "Comparing Relics 0/"+str(len(relicdatabase['unmanagedObjects']))
    # Attach Unmanaged Objects to Clusters
    for relic in relicdatabase['unmanagedObjects']:
        if relic['retentionSlaDomainId'] in cluster['relicindex']['slaidlist']:
            objectdata = checkObjectPrimary(relic, cluster['sourceClusterUuid'])
            relic['snapshots'] = objectdata['snapshots'].copy()
            relic['primary_cluster_id'] = cluster['sourceClusterUuid']
            cluster['reliccount'] += 1
            syslog.syslog(syslog.LOG_INFO, "object "+relic['name']+" matched with source "+cluster['sourceClusterName'])
        elif relic['retentionSlaDomainId'] == "UNPROTECTED":
            if "primary_cluster_id" in relic:
                if relic['primary_cluster_id'] == cluster['sourceClusterUuid']:
                    cluster['reliccount'] += 1
                    objectdata = checkObjectPrimary(relic, cluster['sourceClusterUuid'])
                    relic['snapshots'] = objectdata['snapshots'].copy()
                    syslog.syslog(syslog.LOG_INFO, "object "+relic['name']+" matched with source "+cluster['sourceClusterName'])
            else:
                objectdata = checkObjectPrimary(relic, cluster['sourceClusterUuid'])
                relic['primary_cluster_id'] = objectdata['primaryClusterId']
                relic['snapshots'] = objectdata['snapshots'].copy()
                if objectdata['primaryClusterId'] == cluster['sourceClusterUuid']:
                    syslog.syslog(syslog.LOG_INFO, "UNPROTECTED object "+relic['name']+" matched with source "+cluster['sourceClusterName'])
                    cluster['reliccount'] += 1
        cluster['relicindex']['indexstatus'] = "Relic Matches "+str(cluster['reliccount'])+"/"+str(len(relicdatabase['unmanagedObjects']))
    for relic in relicdatabase['unmanagedObjects']:
        if "primary_cluster_id" in relic:
            if relic['primary_cluster_id'] == cluster['sourceClusterUuid']:
                
                snapjob = threading.Thread(target=snapAudit, args=(relic, cluster))
                snapjob.start()
    snapjob.join()
    cluster['relicindex']['indexstatus'] = "Indexed "+str(cluster['reliccount'])
    cluster['relicindex']['objectcount'] = cluster['reliccount']

def runIndex(full):
    for cluster in relicdatabase['clusters']:
        if (not full) and (not cluster['relicindex']['indexstatus']=="Queued"):
            continue
        indexThread = threading.Thread(target=clusterIndexWorker, args=(cluster,))
        waitForThreads()
        indexThread.start()

def buildUnmanagedList():
    relicdatabase['unmanagedObjects'] = []
    relicdatabase['unmanagedCount'] = 0
    url = baseurl+"v1/unmanaged_object"
    response = rubrik.get(url=url+"?limit=50")
    responsejson = response.json()
    hasMore = responsejson['hasMore']
    while hasMore:
        for relic in responsejson['data']:
            relic['selected'] = False
            relicdatabase['unmanagedObjects'].append(relic)
        relicdatabase['unmanagedCount'] = len(relicdatabase['unmanagedObjects'])
        suffix = "?limit=50&after_id="+responsejson['data'][-1]['id']
        response = rubrik.get(url=url+suffix)
        responsejson = response.json()
        hasMore = responsejson['hasMore']

def clusterMenu(cluster, namefilter):
    os.system('clear')
    thelist = []
    print("============================================================================================================================================")
    print("Cluster: "+str(cluster['sourceClusterName'])+" UUID: "+str(cluster['sourceClusterUuid']))
    print("Object Count: "+str(cluster['relicindex']['objectcount']))
    print("============================================================================================================================================")
    tbltemplatea = "{0:<35}| {1:<20} | {2:<14} | {3:>7} |"
    print(tbltemplatea.format("Object Name","Type","Snaps Sel/Total","Size"))
    print("--------------------------------------------------------------------------------------------------------------------------------------------")
    index = 0
    listcount = 0
    sample = {
        'listid' : 0,
        'indexid' : 0,
        'name': ""
        }
    for relic in relicdatabase['unmanagedObjects']:
        if "primary_cluster_id" in relic:
            if (relic['primary_cluster_id'] == cluster['sourceClusterUuid']) and (namefilter in relic['name']):
                selectedcount = 0
                for snap in relic['snapshots']['data']:
                    if "isSelected" in snap:
                        if snap['isSelected']:
                            selectedcount += 1
                print(tbltemplatea.format(str(listcount+1)+") "+relic['name'][0:35],relic['objectType'],str(selectedcount)+"/"+str(len(relic['snapshots']['data'])),str(humanReadable(relic['localStorage']))))
                sample['listid'] = listcount
                sample['indexid'] = index
                sample['name'] = relic['name']
                thelist.append(sample.copy())
                listcount += 1
                index += 1
                continue
            else:
                index += 1
                continue
        else:
            index += 1
    #syslog.syslog(syslog.LOG_INFO, json.dumps(thelist))
    return thelist

def addCluster():
    relicindex = { 
        'objectcount':0,
        'snapcount':0,
        'indexstatus': "Not Run",
        'replicaspace': 0,
        'relicspace': 0,
        }
    print()
    newCluster = {      "id": "",
      "sourceClusterUuid": "",
      "sourceClusterName": "",
      "sourceClusterAddress": "",
      "isReplicationTargetPauseEnabled": False,
      "isRemoteGlobalBlackoutActive": False
    }
    newCluster['sourceClusterName'] = input("Enter source Cluster friendsly name: ")
    newCluster['sourceClusterUuid'] = input("Enter source Cluster UUID (must be exact): ")
    newCluster['id'] = "DataLocation:::"+newCluster['sourceClusterUuid']
    newCluster['relicindex'] = relicindex.copy()
    relicdatabase['clusters'].append(newCluster.copy())
    print("Added.")

def showObjectDetails(obj):
    #print(obj)
    print("")
    moreofthesame = True
    template = "{0:<45}| {1:<20} | {2:<6} | {3:<6} | {4:<6}"
    while moreofthesame:
        print("Selected Object: "+obj['name'])
        print(template.format("Snap Time Stamp","SLA","Legal","Lock","On Demand"))
        print("--------------------------------------------------------------------------------------------------------------------")
        count = 0
        for thesnap in obj['snapshots']['data']:
            count += 1
            prefix = str(count)+") "
            if "isSelected" in thesnap:
                if thesnap['isSelected']:
                    prefix = "*"+str(count)+") "
            else:
                thesnap['isSelected'] = False
            print(template.format(prefix+thesnap['date'][0:42],thesnap['slaName'],str(thesnap['isPlacedOnLegalHold']),str(thesnap['isRetainedByRetentionLockSla']),str(thesnap['isOnDemandSnapshot'])))
        print("-----")
        choose = input("Enter Number to Select Snap, (A)ll, (N)one, (O)n Demand, or e(X)it:")
        if choose.lower() == "x":
            moreofthesame = False
            continue
        if choose.lower() == "a":
            for theSnap in obj['snapshots']['data']:
                theSnap['isSelected'] = True
        if choose.lower() == "n":
            for theSnap in obj['snapshots']['data']:
                theSnap['isSelected'] = False
        if choose.lower() == "o":
            for theSnap in obj['snapshots']['data']:
                if theSnap['isOnDemandSnapshot']:
                    theSnap['isSelected'] = True
        try:
            indexchoice = int(choose)
        except:
            print("bad choice")
            continue
        print("Snap Choice = "+obj['snapshots']['data'][indexchoice-1]['date'])
        obj['snapshots']['data'][indexchoice-1]['isSelected'] = not obj['snapshots']['data'][indexchoice-1]['isSelected']
        
def displaySelectedSnaps(uuid):
    template = "{0:25} | {1:25} | {2:25} |"
    selectedsnaps = []
    print(template.format("Obj Name","Snap Date","Current SLA"))
    templated = {
        "id": "",
        "snaps": []
        }
    for relic in relicdatabase['unmanagedObjects']:
        templated['id'] = relic['id']
        selectlist = []
        if "primary_cluster_id" in relic:
            if uuid in relic['primary_cluster_id']:
                for snap in relic['snapshots']['data']:
                    try:
                        if snap['isSelected']:
                            print(template.format(relic['name'][0:25],snap['date'],snap['slaName']))
                            #syslog.syslog(syslog.LOG_INFO, str(snap))
                            selectlist.append(snap)
                    except:
                        continue
        templated['snaps'] = selectlist
        #print(selectlist)
        selectedsnaps.append(templated.copy())
    #syslog.syslog(syslog.LOG_INFO, str(selectedsnaps))
    return selectedsnaps

def slaReassignment(cisobject,slaId):
    url = baseurl+"v2/sla_domain/assign_to_snapshot"
    payload = {
        "objectId": cisobject['id'],
        "slaDomainId": slaId,
        "snapshotIds": []
        }
    for snap in cisobject['snaps']:
        payload['snapshotIds'].append(snap['id'])
    response = rubrik.post(url=url, json=payload)
    syslog.syslog(syslog.LOG_INFO, "Reassignment: "+str(response.status_code))
    if str(response.status_code) == "202":
        reassignTask = response.json()
        stillRunning = True
        statusUrl = baseurl+"v2/sla_domain/request/"+reassignTask['responses'][0]['id']
        failcount = 0
        while stillRunning:
            response = rubrik.get(url=statusUrl)
            #print(response.text)
            try:
                result = response.json()
            except:
                failcount += 1
                syslog.syslog(syslog.LOG_ERR, "SLA Reassignment Status Check Failed "+str(failcount)+" of 3")
                if failcount == 3:
                    stillRunning = False
                    input("Process Failed, status: "+response.status_code+": Press Enter to continue")
                continue
            print("---")
            if "progress" in result:
                print("SLA Reassignment progress: "+str(result['progress']))
            print("SLA Reassignment status: "+result['status'])
            if "error" in result:
                print("SLA Reassignment Error: "+result['error']['message'])
            if result['status'] == "SUCCEEDED":
                stillRunning = False
            time.sleep(3)

def displayAvailableSLAs():
    url = baseurl+"v2/sla_domain?primary_cluster_id=local"
    response = rubrik.get(url=url)
    sladata = response.json()
    samesame = True
    while samesame:
        print("---")
        count = 0
        for sla in sladata['data']:
            count += 1
            print(str(count)+") "+sla['name'])
        print("---")
        choice = input("Select New SLA: ")
        if choice.lower() == "x":
            samesame = False
            return None
        if int(choice) > count:
            print("too high, try again")
            continue
        else:
            return sladata['data'][int(choice)-1]
        
def updateSla(uuid):
    os.system("clear")
    tobeupdated = displaySelectedSnaps(uuid)
    print("---")
    templated = {
        "id": "",
        "name": "",
        "snaps": []
        }
    allobjects = []
    newSla = displayAvailableSLAs()
    print("---")
    if newSla == None:
        return
    confirm = input("Type YES to reassign these snaps to "+newSla['name']+": ")
    if confirm == "YES":
        for relic in relicdatabase['unmanagedObjects']:
            templated['id'] = relic['id']
            templated['name'] = relic['name']
            if "primary_cluster_id" in relic:
                selectlist = []
                selectlist.clear()
                if uuid in relic['primary_cluster_id']:
                    for snap in relic['snapshots']['data']:
                        try:
                            if snap['isSelected']:
                                selectlist.append(snap)
                                snap['isSelected'] = False
                        except:
                            continue
            if len(selectlist) > 0:
                templated['snaps'] = selectlist.copy()
                selectlist.clear()
                allobjects.append(templated.copy())
        #print(selectlist)
        for obj in allobjects:
           slaReassignment(obj,newSla['id'])
        print("All Snaps have been reassigned to '"+newSla['name']+"'")
        print("---")

def deleteSelectedSnaps(uuid):
    os.system("clear")
    tobedeleted = displaySelectedSnaps(uuid)
    print("---")
    templated = {
        "id": "",
        "name": "",
        "snaps": []
        }
    allobjects = []
    confirm = input("Type YES to delete these snaps: ")
    if confirm == "YES":
        selectlist = []
        for relic in relicdatabase['unmanagedObjects']:
            templated['id'] = relic['id']
            templated['name'] = relic['name']
            if "primary_cluster_id" in relic:
                selectlist.clear()
                if uuid in relic['primary_cluster_id']:
                    for snap in relic['snapshots']['data']:
                        try:
                            if snap['isSelected']:
                                selectlist.append(snap)
                                snap['isSelected'] = False
                                snap['isDeleted'] = True
                                relic['name'] = relic['name']+"_DELETED"
                        except:
                            continue
            if len(selectlist) > 0:
                templated['snaps'] = selectlist.copy()
                selectlist.clear()
                allobjects.append(templated.copy())
        #print(selectlist)
        for obj in allobjects:
           slaReassignment(obj,'UNPROTECTED')
        print("All Snaps have been reassigned to 'UNPROTECTED'")
        print("---")
        print("Executing bulk delete")
        payload = {
            "snapshotIds": []
            }
        for obj in allobjects:
            for snap in obj['snaps']:
                payload['snapshotIds'].append(snap['id'])
            url = baseurl+"v1/data_source/"+obj['id']+"/snapshot/bulk_delete"
            response = rubrik.post(url=url, json=payload)
            print("---")
            print(obj['name']+": Snaps deleted with response: "+str(response.status_code))
            if str(response.status_code) != "204":
                print(response.text)
                if str(response.status_code) == "422":
                    print(response.json())
        print("BALETED -- Cleaning Database")
        for relic in relicdatabase['unmanagedObjects']:
            for delobj in allobjects:
                if relic['id'] == delobj['id']:
                    for delsnap in delobj['snaps']:
                        print(relic)
                        if "snapshots" in relic:
                            print("Relic Contains Snapshots")
                            try:
                                for thesnap in relic['snaphots']['data']:
                                    if delsnap['id'] == snap['id']:
                                        thesnap['isSelected'] = False
                                        thesnap['isDeleted'] = True
                                        relic['name'] = relic['name']+"_DELETED"
                            except KeyError:
                                print("Stupid Key Error Again")
        input("Pausing to let the trauma sink in")
    

def objSelection(cluster):
    namefilter = ""
    selectlist = []
    samesame = True
    while samesame:
        selectlist = clusterMenu(cluster,namefilter)
        print("----")
        print("F) Filter Results")
        print("V) View Object's snaps")
        print("S) Select all snaps for object")
        print("U) Un-select all snaps for an object")
        print("A) Select all snaps for all objects")
        print("N) Select no snaps for all objects")
        print("O) Select all ondemand snaps")
        print("L) List selected snaps")
        print("R) Re-Assign SLA for selected snaps")
        print("D) Delete selected snaps")
        print("Enter number to select item")
        choice = input("Selection: ")
        if choice.lower() == "x":
            samesame = False
            continue
        if choice.lower() == "f":
            namefilter = input("Enter name Filter: ")
            continue
        if choice.lower() == "v":
            whichone = input("Object Number: ")
            print("")
            #print(selectlist)
            showObjectDetails(relicdatabase['unmanagedObjects'][selectlist[int(whichone)-1]['indexid']])
        if choice.lower() == "s":
            whichone = input("Object Number: ")
            print("")
            for snap in relicdatabase['unmanagedObjects'][selectlist[int(whichone)-1]['indexid']]['snapshots']['data']:
                if "isDeleted" in snap:
                    if snap['isDeleted']:
                        snap['isSelected'] = False
                    else:
                        snap['isSelected'] = True
                else:
                    snap['isSelected'] = True
        if choice.lower() == "u":
            whichone = input("Object Number: ")
            print("")
            for snap in relicdatabase['unmanagedObjects'][selectlist[int(whichone)-1]['indexid']]['snapshots']['data']:
                snap['isSelected'] = False
        if choice.lower() == "a":
            print("")
            for obj in selectlist:
                for snap in relicdatabase['unmanagedObjects'][obj['indexid']]['snapshots']['data']:
                    if "isDeleted" in snap:
                        if snap['isDeleted']:
                            snap['isSelected'] = False
                        else:
                            snap['isSelected'] = True
                    else:
                        snap['isSelected'] = True
        if choice.lower() == "n":
            print("")
            for obj in selectlist:
                for snap in relicdatabase['unmanagedObjects'][obj['indexid']]['snapshots']['data']:
                    snap['isSelected'] = False        
        if choice.lower() == "o":
            print("")
            for obj in selectlist:
                for snap in relicdatabase['unmanagedObjects'][obj['indexid']]['snapshots']['data']:
                    if snap['isOnDemandSnapshot']:
                        if "isDeleted" in snap:
                            if snap['isDeleted']:
                                snap['isSelected'] = False
                            else:
                                snap['isSelected'] = True
                        else:
                            snap['isSelected'] = True
        if choice.lower() == "l":
            print("")
            shownsnaps = displaySelectedSnaps(cluster['sourceClusterUuid'])
            print("****")
            input("Press enter to contine")
        if choice.lower() == "r":
            updateSla(cluster['sourceClusterUuid'])
        if choice.lower() == "d":
            results = deleteSelectedSnaps(cluster['sourceClusterUuid'])
            
            
            
            
            

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
homepath = str(os.path.expanduser('~'))
answerpath = homepath+'/.runbookntanswerfile.json'
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

# Initiate Relic Database
grabReplicaClusters()
localcluster = {
      "id": localid,
      "sourceClusterUuid": localid,
      "sourceClusterName": clusterjson['name'],
      "sourceClusterAddress": clusterip,
      "sourceGateway": {
        "address": clusterip,
        "ports": [
          7785
        ]
      },
      "replicationSetup": "NAT"
    }
relicdatabase['clusters'].append(localcluster)
    
for cluster in relicdatabase['clusters']:
    relicindex = { 
        'objectcount':0,
        'snapcount':0,
        'indexstatus': "Not Run",
        'replicaspace': 0,
        'relicspace': 0,
        }
    cluster['relicindex'] = relicindex.copy()

addStoredAmounts()
# SORT
relicdatabase['clusters'] = sorted(relicdatabase['clusters'], key=lambda k: k['sourceClusterName'])

# Set some Base Data
relicdatabase['totalReplicationSources'] = len(relicdatabase['clusters'])
relicdatabase['storedReplicaData'] = 0
relicdatabase['runningIndexJobs'] = 0

# Start the backend Inventory
inventorythread = threading.Thread(target=buildUnmanagedList)
inventorythread.start()

# Global Menu
samesame = True
while samesame:
    os.system('clear')
    clusterindex = []
    clusterindex.clear()
    print("============================================================================================================================================")
    print("Cluster: "+str(clusterjson['name']))
    print("Running Index Jobs: "+str(relicdatabase['runningIndexJobs']))
    print("Total Replica Sources: "+str(relicdatabase['totalReplicationSources']))
    if inventorythread.is_alive():
        print("Inventory (in progress): "+str(relicdatabase['unmanagedCount'])+" so far")
    else:
        print("Inventory: "+str(relicdatabase['unmanagedCount']))
    print("============================================================================================================================================")
    tbltemplatea = "{0:25}| {1:36} | {2:25} | {3:>7} | {4:>9} | {5:>13} | {6:>11} |"
    print(tbltemplatea.format("Cluster Name","UUID","Index Status","Objects","Snapcount","Replica Space","Relic Space"))
    print("--------------------------------------------------------------------------------------------------------------------------------------------")
    menuid = 6
    clusterid = 0
    for cluster in relicdatabase['clusters']:
        if not cluster['relicindex']['indexstatus'] == "Not Run":
            template = {
                "menu": menuid,
                "cluster": clusterid
                }
            clusterindex.append(template)
            print(tbltemplatea.format(cluster['sourceClusterName'],cluster['sourceClusterUuid'],cluster['relicindex']['indexstatus'],cluster['relicindex']['objectcount'],cluster['relicindex']['snapcount'],str(humanReadable(cluster['relicindex']['replicaspace'])),str(humanReadable(cluster['relicindex']['relicspace']))))
            menuid += 1
        clusterid += 1
    print("***")
    print("1) Run Complete Relic Indexing (LONG)")
    print("2) Select Source Clusters to Index")
    print("3) Index current Queue")
    print("4) Refresh Current Status")
    print("5) Display Selected Snaps")
    if len(clusterindex) > 0:
        for option in clusterindex:
            print(str(option['menu'])+") "+relicdatabase['clusters'][option['cluster']]['sourceClusterName'])
    choice = input("Select your choice:")
    if choice == "1":
        runIndex(True)
    if choice == "2":
        selectSource()
        #runIndex(False)
    if choice == "3":
        runIndex(False)
    if choice == "4":
        continue
    if choice == "5":
        print("---")
        displaySelectedSnaps("")
        print("---")
        input("Press Enter to Continue")
    if choice.lower() == "x":
        samesame = False
        continue
    try:
        int(choice)
    except:
        print("Bad Choice")
        continue
    if int(choice) > 4:
        for option in clusterindex:
            if option['menu'] == int(choice):
                if "Indexed" in relicdatabase['clusters'][option['cluster']]['relicindex']['indexstatus']:
                    objSelection(relicdatabase['clusters'][option['cluster']])
                    continue
        print("Bad Choice")
        continue