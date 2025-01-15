##
##
##
##
## Reads all archive tier export data and dumps it into a CSV to be analyed
##
##
import getpass
import json
import requests
import urllib3
import rubrikSDK

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def generateToken(target, username, password):
    thesession = requests.Session()
    thesession.verify = False
    baseurl = "https://"+target+"/api/"
    url = baseurl+"internal/session"
    payload = {"initParams":{}}
    code = input("Enter TOTP Code: ")
    response = thesession.post(url=url, auth=(username, password), json=payload)
    #print(response.json())
    attemptId = response.json()['mfaResponse']['attemptId']
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
    #print(challengeResponse.json())
    return challengeResponse.json()['session']['token']
'''
    orgId = challengeResponse.json()['session']['organizationId']
    tagIt = "DR"+username+"DR"
    apiTokenData = {
        "initParams": {
            "apiToken": {
                "expiration": 525000,
                "tag": tagIt[0:19]
                },
            "organizationId": orgId
            }
        }
    token = "Bearer "+challengeResponse.json()['session']['token']
    header = {'Authorization': token}
    thesession.headers = header
    tokenCreateResponse = thesession.post(url=url, json=apiTokenData)
    print(tokenCreateResponse.json())
    finalToken = tokenCreateResponse.json()['session']['token']
'''
    

# Function for Opening the Rubrik Session
def connectRubrik(dripaddress,username,password):
    global localprimaryclusterid, clustermeresponse
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
    localprimaryclusterid = drtestjson['id']
    clustermeresponse = drtestjson
    print("Token Auth Test: "+str(drtestresponse))
    return drrbksess, drbearer;

def getSLAReplication(sla,objtype): 
    global missingcount
    basedrurl = "https://"+glob_rubrikip+"/api/"
    if objtype == "Vms":
        listurl = basedrurl+"v1/vmware/vm?effective_sla_domain_id="+sla
        objtype = "VMWare VM"
        snappath = "v1/vmware/vm/"
        snapend = "/snapshot"
        reversesort = False
    if objtype == "Dbs":
        listurl = basedrurl+"v1/mssql/db?effective_sla_domain_id="+sla
        objtype = "MSSQL DB"
        snappath = "v1/mssql/db/"
        snapend = "/snapshot"
        reversesort = False
    if objtype == "NutanixVms":
        listurl = basedrurl+"internal/nutanix/vm?effective_sla_domain_id="+sla
        objtype = "Nutanix VM"
        snappath = "internal/nutanix/vm/"
        snapend = "/snapshot"
        reversesort = True
    if objtype == "HypervVms":
        listurl = basedrurl+"internal/hyperv/vm?effective_sla_domain_id="+sla
        objtype = "Hyper-V VM"
        snappath = "internal/hyperv/vm/"
        snapend = "/snapshot"
        reversesort = False
    if objtype == "Filesets":
        listurl = basedrurl+"v1/fileset?effective_sla_domain_id="+sla
        objtype = "Fileset"
        snappath = "v1/fileset/"
        filesetresponse = glob_rubrik_session.get(url=listurl)
        filesetjson = filesetresponse.json()
        for obj in filesetjson['data']:
            glob_objlist['data'].append(obj)
            glob_objlist['uuidlist'].append(obj['id'])
        return()
    #print(listurl)
    listresponse = glob_rubrik_session.get(url=listurl)
    #print(listresponse.text)
    listjson = listresponse.json()
    #print(json.dumps(listjson, indent=4))
    for obj in listjson['data']:
        glob_objlist['data'].append(obj)
        glob_objlist['uuidlist'].append(obj['id'])
    return()
  

#### Setup Rubrik
glob_rubrikip = input("Enter Rubrik Hostname or IP: ")
glob_user = input("Enter username: ")
glob_pass = getpass.getpass('Enter Rubrik Password: ')
glob_totp = input("Enter Totp: ")
glob_objlist = {
    "data": [],
    "uuidlist": []
    }

localprimaryclusterid = ""
clustermeresponse = {}

glob_token = ""
#glob_rubrik_session, glob_token = connectRubrik(glob_rubrikip, glob_user, glob_pass)
glob_rubrik_session = rubrikSDK.getSession(glob_rubrikip, glob_user, glob_pass, glob_totp)

outputfile = './'+glob_rubrikip+'replica_data.csv'

glob_EventTarget = 2000
eventCount = input("Enter total events to grab (2000 is default): ")
if eventCount == "":
    glob_EventTarget = 2000
else:
    glob_EventTarget = int(eventCount)

glob_sourceCluster = input("Enter source cluster name: ")
replication = rubrikSDK.getReplication("source", name=glob_sourceCluster)

slaList = rubrikSDK.getSLADomain(primaryClusterId=replication['data'][0]['sourceClusterUuid'])


for slajson in slaList['data']:
    sla = slajson['id']
    if slajson['numVms'] > 0:
        objtype = "Vms"
        getSLAReplication(sla,objtype)
    if slajson['numDbs'] > 0:
        objtype = "Dbs"
        getSLAReplication(sla,objtype)
    if slajson['numFilesets'] > 0:
        objtype = "Filesets"
        getSLAReplication(sla,objtype)
    if slajson['numNutanixVms'] > 0:
        objtype = "NutanixVms"
        getSLAReplication(sla,objtype)
    if slajson['numHypervVms'] > 0:
        objtype = "HypervVms"
        getSLAReplication(sla,objtype)

#input("press any key to get response")
#print(json.dumps(glob_objlist, indent=4))
#input("halting here")

url = "https://"+glob_rubrikip+"/api/v1/event/latest?limit=100&event_series_status=Success&event_status=Success&event_type=Replication&should_include_event_series=false"

response = glob_rubrik_session.get(url=url)

print("Beginning Event Pull")
events = response.json()

allevents = []
keepGoing = True
count = 1
loaded = 0
while keepGoing:
    print("Pulling another 100...")
    for event in events['data']:
        if (event['latestEvent']['eventName'] == "Replication.ReplicationSucceeded") and (event['latestEvent']['objectId'] in glob_objlist['uuidlist']):
            allevents.append(event)
    print("Length of Events: "+str(len(events['data'])))
    print("Current Found Events: "+str(count)+" of "+str(loaded)+" events loaded")
    if (len(events['data']) == 100):
        keepGoing = True
        url = "https://"+glob_rubrikip+"/api/v1/event/latest?limit=100&event_series_status=Success&event_status=Success&event_type=Replication&after_id="+events['data'][99]['afterId']+"&should_include_event_series=false"
        response = glob_rubrik_session.get(url=url)
        try:
            events = response.json()
        except:
            print("Failed response: "+str(response.text))
        try:
            print("Last Event: "+events['data'][99]['latestEvent']['id'])
        except:
            keepGoing = False
        count = len(allevents)
        loaded = loaded+100
        if count > glob_EventTarget:
            keepGoing = False
    else:
        keepGoing = False

print("Discovered "+str(len(allevents))+" Events of tiering. Building export...")
total_count = len(allevents)
count = 1
for event in allevents:
    url = "https://"+glob_rubrikip+"/api/v1/event_series/"+event['latestEvent']['eventSeriesId']
    response = glob_rubrik_session.get(url=url)
    data = response.json()
    event['eventSummary'] = data
    print(str(count)+"/"+str(total_count)+": pulling event for "+event['latestEvent']['objectName'])
    count = count + 1

print("Generating CSV File...")
titlerow = "Object Name, Object Type, Event Type, SLA Name, Start Time, End Time, Data Transferrred (B)"
with open(outputfile, 'w+') as csv:
    csv.write(titlerow+"\n")
    for event in allevents:
        try:
            if event['latestEvent']['eventName'] == "Replication.ReplicationSucceeded":
                eventType = "Replication"
            outputline = event['eventSummary']['objectName']+","+event['eventSummary']['objectType']+","
            outputline = outputline+eventType+","+event['eventSummary']['slaName']
            outputline = outputline+","+event['eventSummary']['startTime']+","+event['eventSummary']['endTime']+","
            outputline = outputline+str(event['eventSummary']['dataTransferred'])+"\n"
            csv.write(outputline)
        except Exception as e:
            print(e)
            print(json.dumps(event, indent=4))
            continue
         
        

