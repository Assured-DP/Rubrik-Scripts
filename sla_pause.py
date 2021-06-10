# Script for Discovering the Rubrik Zabbix Components

# add JSON modules
import json
import sys
import requests
import urllib
import urllib3
import os
import datetime
import time
import random
import mysql.connector
import socket
import syslog

# Silence warnings
# requests.packages.urllib3.disable_warnings()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

clustercount = 0
count = 0

# Convert ClusterId To Cluster Name
def getSourceName(session, clusid, baseurl):
    replurl = baseurl+"internal/replication/source"
    replresponse = session.get(url=replurl)
    repljson = replresponse.json()
    for source in repljson['data']:
        if source['sourceClusterUuid'] == clusid:
            return source['sourceClusterName']

def compareConfigs(**kwargs):
    # Setup Common JSON framework
    clusterjson = {
        "uuid": "",
        "username": "",
        "password": "",
        "ip": ""
        }
    localuuid = ""
    if len(globaluuid) > 1:
        localuuid = globaluuid
    output = []
    #print(localuuid)
    # Do we have both a collector config file AND a protect view configuration?
    if (pview and legacyjson):
        # Do all Cluster UUIDs in ProtectView have a match in the legacy collector-config?
        allmatching = False
        syslog.syslog(syslog.LOG_INFO, "Legacy and New Files Exist, Comparing...")
        for region in collect2config['DEFAULT']['RUBRIK']['REGIONS']:
            for pvclust in region['CLUSTERS']:
                clustmatch = False
                if pvclust['CLUSTERUUID'] == localuuid:
                    clusterjson['uuid'] = pvclust['CLUSTERUUID']
                    clusterjson['ip'] = pvclust['URI'][8:]
                    clusterjson['username'] = pvclust['USER']
                    clusterjson['password'] = pvclust['PASSWD']
                    clusterjson['url'] = "https://"+pvclust['URI'][8:]+"/api/"
                    return clusterjson.copy()
                for legclust in coljson['rubrik']['clusters']:
                    if (legclust['id'] == localuuid):
                        clusterjson['uuid'] = legclust['id']
                        clusterjson['ip'] = legclust['nodes'][0]['ipAddress']
                        clusterjson['username'] = legclust['username']
                        clusterjson['password'] = legclust['password']
                        clusterjson['url'] = "https://"+legclust['nodes'][0]['ipAddress']+"/api/"
                        return clusterjson.copy()
                    if legclust['id'] == pvclust['CLUSTERUUID']:
                        clustmatch = True
                if clustmatch:
                    allmatching = True
                else:
                    allmatching = False
        # If every CLUSTERUUID finds a match in collector-config
        if allmatching:
            syslog.syslog(syslog.LOG_INFO, "All UUIDs in both files match")
            for region in collector2config['DEFAULT']['RUBRIK']['REGIONS']:
                for clust in region['CLUSTERS']:
                    clusterjson['uuid'] = clust['CLUSTERUUID']
                    clusterjson['ip'] = clust['URI'][8:]
                    clusterjson['username'] = clust['USER']
                    clusterjson['password'] = clust['PASSWD']
                    clusterjson['url'] = "https://"+clust['URI'][8:]+"/api/"
                    if clust['CLUSTERUUID'] == localuuid:
                        return clusterjson.copy()
                    output.append(clusterjson.copy())
        else:
            syslog.syslog(syslog.LOG_INFO, "UUIDs in both files don't match")
            for clust in coljson['rubrik']['clusters']:
                clusterjson['uuid'] = clust['id']
                clusterjson['ip'] = clust['nodes'][0]['ipAddress']
                clusterjson['username'] = clust['username']
                clusterjson['password'] = clust['password']
                clusterjson['url'] = "https://"+clust['nodes'][0]['ipAddress']+"/api/"
                if clust['id'] == localuuid:
                    return clusterjson.copy()
                output.append(clusterjson.copy())
    elif pview:
        for region in collector2config['DEFAULT']['RUBRIK']['REGIONS']:
            for clust in region['CLUSTERS']:
                clusterjson['uuid'] = clust['CLUSTERUUID']
                clusterjson['ip'] = clust['URI'][8:]
                clusterjson['username'] = clust['USER']
                clusterjson['password'] = clust['PASSWD']
                clusterjson['url'] = "https://"+clust['URI'][8:]+"/api/"
                if clust['CLUSTERUUID'] == localuuid:
                    return clusterjson.copy()
                output.append(clusterjson.copy())
    else:
        for clust in coljson['rubrik']['clusters']:
            clusterjson['uuid'] = clust['id']
            clusterjson['ip'] = clust['nodes'][0]['ipAddress']
            clusterjson['username'] = clust['username']
            clusterjson['password'] = clust['password']
            clusterjson['url'] = "https://"+clust['nodes'][0]['ipAddress']+"/api/"
            if clust['id'] == localuuid:
                return clusterjson.copy()
            output.append(clusterjson.copy())
    return output

def testConnection(rubrikSession, baseurl):
    testurl = baseurl+'v1/cluster/me'
    testresp = 503
    try:
        testcall = rubrikSession.get(url=testurl)
        testresp = testcall.status_code
    except:
        testresp = 503
    syslog.syslog(syslog.LOG_INFO, 'Testresponse '+str(testresp))
    return testresp

def setupRubrik(target):
    uuid = target['uuid']
    baseurl = target['url']
    tokenpath = '/var/log/zabbix/_rbkzbxtoken_'+uuid+'.tk'
    syslog.syslog(syslog.LOG_INFO, 'Checking for '+tokenpath)
    rubrik = requests.Session()
    rubrik.verify = False
    if os.path.exists(tokenpath):
        syslog.syslog(syslog.LOG_INFO, tokenpath+' exists. Loading...')
        try:
            syslog.syslog(syslog.LOG_INFO, 'Loading '+tokenpath)
            tokenfile = json.load(open(tokenpath))
        except:
            syslog.syslog(syslog.LOG_ERR, 'Failed to load '+tokenpath)
            time.sleep(2)
            try:
                os.remove(tokenpath)
                syslog.syslog(syslog.LOG_INFO, 'Removing '+tokenpath)
                quit()
            except:
                time.sleep(2)
                syslog.syslog(syslog.LOG_INFO, 'Failed to remove token, attempting reload')
                tokenfile = json.load(open(tokenpath))
        token = tokenfile['token']
        bearer = "Bearer "+token
        header = {'Authorization': bearer}
        rubrik.headers = header
        status = testConnection(rubrik,baseurl)
        syslog.syslog(syslog.LOG_INFO, 'Status test of cluster: '+str(status))
        if status != 200:
            try:
                os.remove(tokenpath)
                rubrik.auth = (target['username'], target['password'])
                sesurl = baseurl + "v1/session"
                tokenresponse = rubrik.post(url=sesurl)
                token = tokenresponse.json()
                with open(tokenpath, 'w') as dmpfile:
                    json.dump(token, dmpfile)
            except:
                time.sleep(random.randint(2,11))
                try:
                    tokenfile = json.load(open(tokenpath))
                except:
                    rubrik.auth = (target['username'], target['password'])
                    sesurl = baseurl + "v1/session"
                    tokenresponse = rubrik.post(url=sesurl)
                    token = tokenresponse.json()
                    with open(tokenpath, 'w') as dmpfile:
                        json.dump(token, dmpfile)
                    tokenfile = json.load(open(tokenpath))
                token = tokenfile['token']
                bearer = "Bearer " + token
                header = {'Authorization': bearer}
                rubrik.headers = header
                testurl = baseurl + "v1/cluster/me"
                testcall = rubrik.get(url=testurl)
    else:
        rubrik.auth = (target['username'], target['password'])
        sesurl = baseurl + "v1/session"
        try:
            tokenresponse = rubrik.post(url=sesurl)
        except:
            syslog.syslog(syslog.LOG_INFO, 'Failed at line 169 ')
            quit()
        token = tokenresponse.json()
        with open(tokenpath, 'w') as dmpfile:
            json.dump(token, dmpfile)
    status = testConnection(rubrik,baseurl)
    if status == 200:
        syslog.syslog(syslog.LOG_ERR, 'Successful Test, moving forward')
        return rubrik
    else:
        syslog.syslog(syslog.LOG_ERR, 'Failed Second Test, bailing')
        quit()
    
def getClusterData(uuidtarget):
    if pview:
        for region in collect2config['DEFAULT']['RUBRIK']['REGIONS']:
            for cluster in region['CLUSTERS']:
                if cluster['CLUSTERUUID'] == uuidtarget:
                    clusterjson = {
                        "id": uuidtarget,
                        "username": cluster['USER'],
                        "password": cluster['PASSWD'],
                        "IP": cluster['URI'][8:],
                        "url": cluster['URI']+'/api/'
                        }
                    syslog.syslog(syslog.LOG_INFO, 'Zabbix Key found in '+dbfilename)
                    return clusterjson
    if legacyjson:
        for cluster in coljson['rubrik']['clusters']:
            if cluster['id'] == uuidtarget:
                url = "https://"+cluster['nodes'][0]['ipAddress']+"/api/"
                clusterjson = {
                    "id": uuidtarget,
                    "username": cluster['username'],
                    "password": cluster['password'],
                    "IP": cluster['nodes'][0]['ipAddress'],
                    "url": url
                    }
                syslog.syslog(syslog.LOG_INFO, 'Zabbix Key found in /etc/adp/collector-config.json')
                return clusterjson
          
# load source file(s) (needs to be full path to collector file)
if os.path.exists('/etc/adp/collector-config.json'):
    coljson = json.load(open('/etc/adp/collector-config.json'))
    legacyjson = True
    syslog.syslog(syslog.LOG_INFO, 'Loaded /etc/adp/collector-config.json')
else:
    syslog.syslog(syslog.LOG_WARNING, 'Legacy JSON /etc/adp/collector-config.json not found')
    legacyjson = False

fqdn = socket.getfqdn()
hostname = fqdn.split(".")[0]
dbfilename = "/etc/adp/"+hostname+"-config.json"
if os.path.exists(dbfilename):
    collect2config = json.load(open(dbfilename))
    pview = True
    syslog.syslog(syslog.LOG_INFO, 'Loaded '+dbfilename)
else:
    syslog.syslog(syslog.LOG_WARNING, dbfilename+' Not Found')
    pview = False

# Initiate output JSON
slalist = [  "Dynamic Air File-servers", "Dynamic Air Exchange", "Dynamic Air DB-servers", "Dynamic Air Bronze" ]
globaluuid = ""

globaluuid = sys.argv[2]
myCluster = compareConfigs()
#print(myCluster)

# Pause all SLAs in "slalist" variable
if sys.argv[1] == "sla_pause":
    if sys.argv[3] == "pause":
        body = { "isPaused" : True }
    else:
        body = { "isPaused" : False }
    session = setupRubrik(myCluster)
    baseurl = myCluster['url']
    getslaurl = baseurl+"v2/sla_domain"
    response = session.get(url=getslaurl)
    try:
        slalistjson = response.json()
    except:
        print("FAILED TO GET JSON")
    for changesla in slalist:
        for rubriksla in slalistjson['data']:
            if changesla == rubriksla['name']:
                pauseurl = baseurl+"v2/sla_domain/"+rubriksla['id']+"/pause"
                pauseresponse = session.post(url=pauseurl,json=body)
                if pauseresponse.status_code== 200:
                    print("SLA "+rubriksla['name']+" "+sys.argv[3]+" completed successful.")
                else:
                    print("Call to "+sys.argv[3]+" "+rubriksla['name']+" failed: "+str(pauseresponse))
                    
                
