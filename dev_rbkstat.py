# Script for Discovering the Rubrik Zabbix Components

# add JSON modules
import json
import requests
import urllib
import urllib3
import sys
import os
import datetime
import time
import random
import mysql.connector
import socket
import syslog
import pytz

from dateutil import parser


# Assign Time to a Variable -- Setting to UTC
os.environ['TZ'] = 'UTC'
timevar = datetime.datetime.now()
now = "%s-%s-%sT%s:%s:00Z" % (timevar.year, timevar.month, timevar.day, timevar.hour, timevar.minute-1)

# Silence warnings
# requests.packages.urllib3.disable_warnings()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Get current SLA size
def slaCurrentSize(slaid):
    slaurl = baseurl+"internal/stats/sla_domain_storage/time_series?id="+slaid
    size = 0
    slaresponse = session.get(url=slaurl)
    slajson = slaresponse.json()
    currenttime = datetime.datetime.now()
    currenttime = currenttime.replace(tzinfo=None)
    timediff = 3700.20
    for point in slajson:
        latesttime = parser.parse(point['time'])
        latesttime = latesttime.replace(tzinfo=None)
        checkdiff = currenttime - latesttime
        secdiff = checkdiff.total_seconds()
        if secdiff < timediff:
            if point['stat'] > 0:
                size = point['stat']
            timediff = checkdiff.total_seconds()
    return size

def getEvents(rubrik, status, type, hoursback):
    yesterday = datetime.datetime.now() - datetime.timedelta(hours=hoursback)
    daystring = yesterday.strftime("%m/%d/%Y %H:%M")
    payload = { 'limit': '25', 'status': status, 'after_date': daystring, 'object_type': type , 'event_type': 'Backup' }
    if versmajor < 5:
        notifyurl = baseurl+"internal/event"
    else:
        notifyurl = baseurl+"internal/event_series"
    param = urllib.parse.urlencode(payload)
    eventresponse = session.get(url=notifyurl,params=param)
    eventjson = eventresponse.json()
    count = len(eventjson['data'])
    for event in eventjson['data']:
        if event['status'] == "Canceled":
            count = count - 1
    if count == 0:
        print ("0")
        quit()
    else:
        print(str(count))
        quit()

def testConnection(rubrikSession):
    testurl = baseurl+'v1/cluster/me'
    testresp = 503
    try:
        testcall = rubrikSession.get(url=testurl)
        testresp = testcall.status_code
    except:
        testresp = 503
    if testresp == 200:
        myClusterData['clusterMe'] = testcall.json()
    syslog.syslog(syslog.LOG_INFO, 'Testresponse '+str(testresp))
    return testresp

def setupRubrik():
    tokenpath = '/var/log/zabbix/_rbkzbxtoken_'+myClusterData['id']+'.tk'
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
        status = testConnection(rubrik)
        syslog.syslog(syslog.LOG_INFO, 'Status test of cluster: '+str(status))
        if status != 200:
            try:
                os.remove(tokenpath)
                rubrik.auth = (username, password)
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
                    rubrik.auth = (username, password)
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
        rubrik.auth = (username, password)
        sesurl = baseurl + "v1/session"
        try:
            tokenresponse = rubrik.post(url=sesurl)
        except:
            quit()
        token = tokenresponse.json()
        with open(tokenpath, 'w') as dmpfile:
            json.dump(token, dmpfile)
    status = testConnection(rubrik)
    if status == 200:
        syslog.syslog(syslog.LOG_ERR, 'Successful Test, moving forward')
        return rubrik
    else:
        syslog.syslog(syslog.LOG_ERR, 'Failed Second Test, bailing')
        quit()

def isWithinSchedule(schedule):
    tz = pytz.timezone(myClusterData['clusterMe']['timezone']['timezone'])
    nowtime = datetime.datetime.now()
    daynum = nowtime.isoweekday()+1
    limit = 0
    if daynum == 8:
        daynum = 1
    timenum = int(str(nowtime.hour)+str(nowtime.minute))
    for override in schedule:
        if daynum in override['daysOfWeek']:
            if override['startTime'] <= timenum <= override['endTime']:
                limit = override['throttleLimit']
            if override['endTime'] < override['startTime']:
                if (timenum <= override['endTime']) or (timenum >= override['startTime']):
                    limit = override['throttleLimit']
    return limit
    
    
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

# Establish Global variables
mysqljson = collect2config['DEFAULT']['MYSQL']
clustercount = 0
count = 0

# Get Cluster Connection information
syslog.syslog(syslog.LOG_INFO, 'Getting Cluster Data....')
rubrikjson = getClusterData(sys.argv[1])

# Identify the Cluster contact information
myClusterData = rubrikjson
myClusterData['clusterMe'] = {}
baseurl = myClusterData['url']
username = myClusterData['username']
password = myClusterData['password']
nodeip = myClusterData['IP']

# Open a session with a token file if it exists
# If the session fails to authenticate, recreate the token file
session = setupRubrik()

clustjson = {}
clustjson = myClusterData['clusterMe']

version = clustjson['version']
versmajor = int(version[0])
versminor = int(version[2])
versfix = int(version[4])
#print version

# Report on ipaddress
if sys.argv[2] == "ipaddress":
    print(nodeip)

# Report on clusterid
if sys.argv[2] == "clusterid":
    rbkresponse = session.get(baseurl + "v1/cluster/me")
    rbkjson = rbkresponse.json()
    print(rbkjson['id'])

# Report on Code Version
if sys.argv[2] == "version":
    print(version)

# Report on used space
if sys.argv[2] == "usedspace":
    rbkresponse = session.get(baseurl + "internal/stats/system_storage")
    rbkjson = rbkresponse.json()
    print(rbkjson['used'])

# Report on total space
if sys.argv[2] == "totalspace":
        rbkresponse = session.get(baseurl + "internal/stats/system_storage")
        rbkjson = rbkresponse.json()
        print(rbkjson['total'])

# Report on free space
if sys.argv[2] == "freespace":
        rbkresponse = session.get(baseurl + "internal/stats/system_storage")
        rbkjson = rbkresponse.json()
        print(rbkjson['available'])

# Report on Support Tunnel
if sys.argv[2] == "tunnelport":
    if versmajor == 4:
        if versminor == 0:
            rbkresponse = session.get(baseurl + "internal/support/tunnel")
            rbkjson = rbkresponse.json()
            if not rbkjson['status']:
                print("Tunnel Disabled")
            else:
                print(rbkjson['port'])
        if versminor > 0:
            rbkresponse = session.get(baseurl + "internal/node")
            rbkjson = rbkresponse.json()
            for node in rbkjson['data']:
                if node['supportTunnel']['isTunnelEnabled']:
                    print(node['supportTunnel']['port'])
                    exit()
            print("Tunnel Disabled")
    else:
        rbkresponse = session.get(baseurl + "internal/node")
        rbkjson = rbkresponse.json()
        for node in rbkjson['data']:
            if node['supportTunnel']['isTunnelEnabled']:
                print(node['supportTunnel']['port'])
                exit()
        print("Tunnel Disabled")

# Report on Blackout window for Paused backup activity
if sys.argv[2] == "pause":
    if ((versmajor == 5) and (versminor > 0) or (versmajor > 5)):
        rbkresponse = session.get(baseurl + "v1/blackout_window")
    else:
        rbkresponse = session.get(baseurl + "internal/blackout_window")
    rbkjson = rbkresponse.json()
    if rbkjson['isGlobalBlackoutActive']:
        print ("Active")
    else:
        print ("Disabled")

# Archive Bandwidth
if sys.argv[2] == "archivebw":
    rbkresponse = session.get(baseurl + "internal/stats/archival/bandwidth/time_series?range=-30min")
    rbkjson = rbkresponse.json()
    count = 0
    avgcount = 0
    valuesum = 0
    for datapoint in rbkjson:
        count = count+1
        if count > (len(rbkjson)-5):
            valuesum = valuesum + datapoint['stat']
            avgcount = avgcount + 1
    print(str(valuesum/avgcount))

# Archive Speed Limit
if sys.argv[2] == "archivelimit":
    rbkresponse = session.get(baseurl + "internal/network_throttle")
    rbkjson = rbkresponse.json()
    limit = 0
    for limiter in rbkjson['data']:
        if limiter['resourceId'] == "ArchivalEgress":
            if limiter['isEnabled']:
                limit = isWithinSchedule(limiter['scheduledThrottles'])
                if (limit == 0) and ('defaultThrottleLimit' in limiter):
                    limit = limiter['defaultThrottleLimit']
            elif ('defaultThrottleLimit' in limiter):
                limit = limiter['defaultThrottleLimit']
    print(str(int(limit*1024*1024)))
    
# Replication Speed Limit
if sys.argv[2] == "replicatelimit":
    rbkresponse = session.get(baseurl + "internal/network_throttle")
    rbkjson = rbkresponse.json()
    limit = 0
    for limiter in rbkjson['data']:
        if limiter['resourceId'] == "ReplicationEgress":
            if limiter['isEnabled']:
                limit = isWithinSchedule(limiter['scheduledThrottles'])
                if (limit == 0) and ('defaultThrottleLimit' in limiter):
                    limit = limiter['defaultThrottleLimit']
            elif ('defaultThrottleLimit' in limiter):
                limit = limiter['defaultThrottleLimit']
    print(str(int(limit*1024*1024)))

# Replication Bandwidth
if sys.argv[2] == "replicationbw":
    rbkresponse = session.get(baseurl + "internal/stats/replication/outgoing/time_series?range=-30min")
    rbkjson = rbkresponse.json()
    count = 0
    avgcount = 0
    valuesum = 0
    for datapoint in rbkjson:
        count = count+1
        if count > (len(rbkjson)-5):
            valuesum = valuesum + datapoint['stat']
            avgcount = avgcount + 1
    print(str(valuesum/avgcount))
    
# Report on Node Data
if sys.argv[2] == "node":
    clusidresponse = session.get(baseurl + "v1/cluster/me")
    clustercall = clusidresponse.json()
    # Check if cluster is a single node
    manynoderesponse = session.get(baseurl+"internal/cluster/"+clustercall['id']+"/node")
    manynode = manynoderesponse.json()
    rbknodecount = manynode['total']
    for manynode in manynode['data']:
        if manynode['id'] == sys.argv[3]:
            returnfield = sys.argv[4]
            print(manynode[returnfield])

# Report on Node Disk Status
if sys.argv[2] == "disks":
    clusidresponse = session.get(baseurl+"internal/node/"+sys.argv[3])
    diskjson = clusidresponse.json()
    for diskjson in diskjson['ssd']:
        if diskjson['id'] == sys.argv[4]:
            print(diskjson[sys.argv[5]])
    clusidresponse = session.get(baseurl+"internal/node/"+sys.argv[3])
    diskjson = clusidresponse.json() 
    for diskjson in diskjson['hdd']:
        if diskjson['id'] == sys.argv[4]:
            print(diskjson[sys.argv[5]])

# Report LiveMount Count
if sys.argv[2] == "lmcount":
    mountcount = 0
    clusidresponse = session.get(baseurl+"v1/vmware/vm/snapshot/mount")
    lmdata = clusidresponse.json()
    mountcount = mountcount + lmdata['total']
    clusidresponse = session.get(baseurl+"v1/mssql/db/mount")
    lmdata = clusidresponse.json()
    mountcount = mountcount + lmdata['total']
    clusidresponse = session.get(baseurl+"internal/hyperv/vm/snapshot/mount")
    lmdata = clusidresponse.json()
    mountcount = mountcount + lmdata['total']
    clusidresponse = session.get(baseurl+"internal/managed_volume/snapshot/export")
    lmdata = clusidresponse.json()
    mountcount = mountcount + lmdata['total']
    print(mountcount)

# Pull SLA Statistics
if (sys.argv[2] == "sla") or (sys.argv[2] == "remotesla"):
    slaid = sys.argv[3]
    if versmajor < 5:
        slaurl = baseurl+"v1/sla_domain/"+slaid
    else:
        slaurl = baseurl+"v2/sla_domain/"+slaid
    slaresponse = session.get(url=slaurl)
    slajson = slaresponse.json()
    if sys.argv[4] == "size":
        size = slaCurrentSize(slajson['id'])
        print(size)
        exit()
    if sys.argv[4] == "hash":
        buildhash = "["+str(json.dumps(slajson['frequencies']))+","
        buildhash = buildhash + str(json.dumps(slajson['allowedBackupWindows']))+", "
        buildhash = buildhash + str(json.dumps(slajson['firstFullAllowedBackupWindows']))+", "
        buildhash = buildhash + str(json.dumps(slajson['archivalSpecs']))+", "
        buildhash = buildhash + str(json.dumps(slajson['replicationSpecs']))+"]"
        print (buildhash)
        slahash = json.loads(buildhash)
        print (json.dumps(slahash, indent=4, sort_keys=False))
    else:
        print(slajson[sys.argv[4]])

# Pull ARCHIVE Statistics
if (sys.argv[2] == "archive"):
    archiveid = sys.argv[3]
    fieldname = sys.argv[4]
    archurl = baseurl+"internal/stats/data_location/usage"
    archresponse = session.get(url=archurl)
    try:
        archjson = archresponse.json()
    except:
        print(0)
        quit()
    for location in archjson['data']:
        if location['locationId'] == archiveid:
            print(location[fieldname])

# Report on Host Status
if sys.argv[2] == "host":
    hostid = sys.argv[3]
    hosturl = baseurl+"v1/host/"+hostid
    hostresponse = session.get(url=hosturl)
    hostjson = hostresponse.json()
    fieldname = sys.argv[4]
    print(hostjson[fieldname])
    
# Report on Host Status
if sys.argv[2] == "vcenter":
    vcenterid = sys.argv[3]
    hosturl = baseurl+"v1/vmware/vcenter/"+vcenterid+"?ignore_connection_status=false"
    hostresponse = session.get(url=hosturl)
    hostjson = hostresponse.json()
    #print versmajor
    #print versminor
    if (versmajor > 3) :
        if sys.argv[4] == "message":
            if hostjson['connectionStatus']['status'] == "BadlyConfigured":
                print(hostjson['connectionStatus']['message'])
                quit()
            else:
                print("No Message")
                quit()
        if sys.argv[4] == "status":
            print(hostjson['connectionStatus']['status'])
            quit()
    else:
        if sys.argv[4] == "message":
            print("Pre-4.1 Codebase")
        if sys.argv[4] == "status":
            print(hostjson['status'])

# Report on Stuck Job Count
if sys.argv[2] == "stuckcount":
    if versmajor > 4:
        print(0)
        quit()
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    daystring = yesterday.strftime("%m/%d/%Y %H:%M")
    payload = { 'limit': '25', 'status': 'Failure', 'after_date': daystring }
    notifyurl = baseurl+"internal/user_notification"
    param = urllib.parse.urlencode(payload)
    stucklist = session.get(url=notifyurl,params=param)
    notifyjson = stucklist.json()
    stuckcount = 0
    if notifyjson['total'] > 0:
        for alert in notifyjson['data']:
            if alert['name'] == "STUCK_JOB_WARNING" and alert['state'] == "NEW":
                stuckcount = stuckcount + 1
    print(stuckcount)

# Report on Failed SQL Count
if sys.argv[2] == "failedmssql":
    if versmajor > 4:
        getEvents(session, "Failure", "Mssql", 24)
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    daystring = yesterday.strftime("%m/%d/%Y %H:%M")
    payload = { 'limit': '25', 'status': 'Failure', 'after_date': daystring, 'object_type':'Mssql' }
    notifyurl = baseurl+"internal/user_notification"
    param = urllib.parse.urlencode(payload)
    notifylist = session.get(url=notifyurl,params=param)
    notifyjson = notifylist.json()
    failcount = 0
    if notifyjson['total'] > 0:
        for alert in notifyjson['data']:
            if (alert['state'] == "NEW") and (not "UPLOAD" in alert['name']):
                if not "REPLICATE" in alert['name']:
                    failcount = failcount + 1
    print(failcount)

# Report on Failed VM Count
if sys.argv[2] == "failedvmware":
    if versmajor > 4:
        getEvents(session, "Failure", "VmwareVm", 24)
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    daystring = yesterday.strftime("%m/%d/%Y %H:%M")
    payload = { 'limit': '25', 'status': 'Failure', 'after_date': daystring, 'object_type':'VmwareVm' }
    notifyurl = baseurl+"internal/user_notification"
    param = urllib.parse.urlencode(payload)
    notifylist = session.get(url=notifyurl,params=param)
    notifyjson = notifylist.json()
    failcount = 0
    if notifyjson['total'] > 0:
        for alert in notifyjson['data']:
            if (alert['state'] == "NEW") and (not "REPLICATE" in alert['name']):
                failcount = failcount + 1
    print(failcount)

if sys.argv[2] == "volume":
        if versmajor < 5:
                yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
                daystring = yesterday.strftime("%m/%d/%Y %H:%M")
                payload = { 'limit': '25', 'status': 'Failure', 'after_date': daystring, 'object_type': 'VolumeGroup', 'event_type':'Backup'}
                param = urllib.parse.urlencode(payload)
                eventurl = baseurl+"internal/event"
                eventresponse = session.get(url=eventurl, params=param)
                eventjson = eventresponse.json()
                failcount = len(eventjson['data'])
                print(failcount)
                quit()
        getEvents(session, "Failure", "VolumeGroup", 24)

if sys.argv[2] == "failhyperv":
    getEvents(session, "Failure", "HypervVm", 24)

# Report on Running Backup jobs with more than X hours of duration
if sys.argv[2] == "longjob":
    if versmajor < 5:
        print(0)
        quit()
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=int(sys.argv[3]))
    #daystring = yesterday.strftime("%m/%d/%Y %H:%M")
    payload = { 'limit': '25', 'status': 'Active', 'event_type': 'Backup' }
    eventsurl = baseurl+"internal/event_series"
    param = urllib.parse.urlencode(payload)
    eventresponse = session.get(url=eventsurl, params=param)
    eventjson = eventresponse.json()
    longcount = 0
    if len(eventjson['data'])>0:
        for eseries in eventjson['data']:
            startTime = datetime.datetime.strptime(eseries['startTime'],'%Y-%m-%dT%H:%M:%S.%fZ')
            if startTime < cutoff:
                count = count+1
    print(count)
                
if sys.argv[2] == "repl":
    filepath = "/var/log/zabbix/"+sys.argv[1]+".json"
    repldata = json.load(open(filepath))
    offsetarray = []
    output = { "min": -9999, "max": -9999, "median": -9999, "avg": -9999, "count": 0, "total": 0 }
    if len(repldata[sys.argv[1]][sys.argv[3]][sys.argv[4]]) == 0:
        print(output[sys.argv[5]])
        quit()
    #print(repldata[sys.argv[1]][sys.argv[3]][sys.argv[4]][0]['id'])
    for data in repldata[sys.argv[1]][sys.argv[3]][sys.argv[4]]: # repldata[collectorUUid][RemoteClusterUUID][SLAuuid]
        #print(json.dumps(data))
        if data['id'] == sys.argv[5]:
            output[sys.argv[5]] = data['offset']
        if output['min'] == -9999:
            output['min'] = data['offset']
        if output['min'] > data['offset']:
            output['min'] = data['offset']
        if output['max'] == -9999:
            output['max'] = data['offset']
        if output['max'] < data['offset']:
            output['max'] = data['offset']
        output['total'] = output['total'] + data['offset']
        output['count'] = output['count'] + 1
        offsetarray.append(data['offset'])
    #offsetarray.sort()
    #print (offsetarray)
    #print (output[sys.argv[5]])
    output['avg'] = output['total']/output['count']
    if output['count'] % 2 == 0:
        median1 = offsetarray[output['count']//2]
        median2 = offsetarray[output['count']//2 - 1]
        output['median'] = (median1 + median2) / 2
    else:
        #print(int(output['count']//2))
        output['median'] = offsetarray[int(output['count']//2)]
    print(output[sys.argv[5]])
    
if sys.argv[2] == "replqueue":
    filepath = "/var/log/zabbix/_"+sys.argv[1]+".q"
    queuedata = json.load(open(filepath))
    print(queuedata[sys.argv[3]])

if sys.argv[2] == "mysql":
    database = mysql.connector.connect(
      host=mysqljson['HOST'],
      user=mysqljson['USER'],
      passwd=mysqljson['PASSWD'],
      database=mysqljson['DB']
      )
    cursor = database.cursor()
    
    query = "SELECT * FROM "+mysqljson['DB']+".event where (status = 'Failure' AND objectType = '"+sys.argv[3]+"' AND eventType = 'Backup' AND (time > (NOW() - INTERVAL 1 DAY)))"
    
    cursor.execute(query)
    
    queryresult = cursor.fetchall()
    
    if len(queryresult) < 1:
        print(0)
    else:
        print(len(queryresult))
