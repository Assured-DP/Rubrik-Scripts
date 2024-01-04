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

    

#### Setup Rubrik
glob_rubrikip = input("Enter Rubrik Hostname or IP: ")
glob_user = input("Enter username: ")
glob_pass = getpass.getpass('Enter Rubrik Password: ')

localprimaryclusterid = ""
clustermeresponse = {}

glob_token = ""
glob_rubrik_session, glob_token = connectRubrik(glob_rubrikip, glob_user, glob_pass)

outputfile = './'+glob_rubrikip+'archive_data.csv'

url = "https://"+glob_rubrikip+"/api/v1/event/latest?limit=100&event_series_status=Success&event_status=Success&event_type=Archive&should_include_event_series=false"

response = glob_rubrik_session.get(url=url)

print("Beginning Event Pull")
events = response.json()

allevents = []
keepGoing = True
count = 1
while keepGoing:
    print("Pulling another 100...")
    for event in events['data']:
        if (event['latestEvent']['eventName'] == "Snapshot.SmartTieringSuccess") or (event['latestEvent']['eventName'] == "Snapshot.SnapshotUploadSucceeded"):
            allevents.append(event)
    print("Length of Events: "+str(len(events['data'])))
    print("Current Count: "+str(count))
    if (len(events['data']) == 100):
        keepGoing = True
        url = "https://"+glob_rubrikip+"/api/v1/event/latest?limit=100&event_series_status=Success&event_status=Success&event_type=Archive&after_id="+events['data'][99]['afterId']+"&should_include_event_series=false"
        response = glob_rubrik_session.get(url=url)
        try:
            events = response.json()
        except:
            print("Failed response: "+str(response.text))
        try:
            print("Last Event: "+events['data'][99]['latestEvent']['id'])
        except:
            keepGoing = False
        count = count + 1
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
            if event['latestEvent']['eventName'] == "Snapshot.SmartTieringSuccess":
                eventType = "Tiering"
            if event['latestEvent']['eventName'] == "Snapshot.SnapshotUploadSucceeded":
                eventType = "Upload"
            outputline = event['eventSummary']['objectName']+","+event['eventSummary']['objectType']+","
            outputline = outputline+eventType+","+event['eventSummary']['slaName']
            outputline = outputline+","+event['eventSummary']['startTime']+","+event['eventSummary']['endTime']+","
            outputline = outputline+str(event['eventSummary']['dataTransferred'])+"\n"
            csv.write(outputline)
        except Exception as e:
            print(e)
            print(json.dumps(event, indent=4))
            continue
         
        

