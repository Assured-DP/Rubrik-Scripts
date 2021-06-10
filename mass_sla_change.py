## Mass SLA Change
## mass_sla_change.py <path_to_json_of_file_with_object_list>
## JSON Output is identical to the returned JSON of the Rubrik API v1/vmware/vm or internal/volumegroup or internal/hypervvm
## File format:
"""
{
  "hasMore": false,
  "data": [
    {
      "isEffectiveSlaDomainRetentionLocked": false,
      "configuredSlaDomainName": "Inherit",
      "effectiveSlaDomainId": "UNPROTECTED",
      "primaryClusterId": "7520934e-9d1f-41ea-820b-f1e3352889db",
      "effectiveSlaSourceObjectId": "VolumeGroup:::739af010-0ca4-48d9-b698-1868772dcef1",
      "slaAssignment": "Unassigned",
      "effectiveSlaSourceObjectName": "Object Name volumes",
      "hostId": "Host:::ca0ce137-67f3-43e5-8c6a-d900d16e8d48",
      "configuredSlaDomainId": "INHERIT",
      "effectiveSlaDomainName": "Unprotected",
      "hostname": "Hostname",
      "isConfiguredSlaDomainRetentionLocked": false,
      "isRelic": false,
      "name": "ObjectName",
      "id": "VolumeGroup:::739af010-0ca4-48d9-b698-1868772dcef1"
    }
"""

import json
import base64
import requests
import urllib3
import syslog
import sys
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

"""
## Remove Quotes for detailed Requests logging
try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client
http_client.HTTPConnection.debuglevel = 1
"""

## Rubrik Connections
def connectRubrik(hostname, username, password):
    session = requests.Session()
    session.verify = False
    sessurl = "https://"+hostname+"/api/v1/session"
    try:
        sessionTokenResponse = requests.request('POST', url=sessurl, auth=(username,password), verify=False)
    except:
        return "None", "Bad Login"
    try:
        sessionJson = sessionTokenResponse.json()
    except:
        print("Unable to generate token for "+hostname+": "+str(sessionTokenResponse))
        quit()
    try:
        sessionToken = sessionJson['token']
        sessionBearer = "Bearer "+sessionToken
        sessionHeader = {'Authorization': sessionBearer}
        session.headers = sessionHeader
    except:
        sessionToken = "Bad Login"
    return session, sessionToken
	
def getJson(url, session):
    try:
        response = session.get(url=url)
    except requests.exceptions.RequestException as e:
        syslog.syslog(syslog.LOG_ERR, 'Failed to get JSON from: '+url)
        syslog.syslog(syslog.LOG_ERR, 'Requests Exception: '+string(e))
    try:
        jsonresponse = response.json()
    except:
        syslog.syslog(syslog.LOG_ERR, 'Failed to Parse JSON from: '+url)
        syslog.syslog(syslog.LOG_ERR, 'Response test: '+response.text)
    return jsonresponse

def buildSnapUrl(target, targeturl):
	if target['type'] == "vmware":
		fullurl = targeturl+"v1/vmware/vm/"+target['objid']+"/snapshot"
	return fullurl

def buildJobUrl(jobdata, targeturl):
	if jobdata['type'] == "vmware":
		fullurl = targeturl+"v1/vmware/vm/request/"+jobdata['id']
	return fullurl

def buildChangeUrl(jobdata, targeturl):
	if "HypervVirtualMachine" in jobdata['id']:
		fullurl = targeturl+"internal/hyperv/vm/"+jobdata['id']
	return fullurl

def createPayload(slaid, session):
	payload = {
		"slaId": slaid
		}
	return payload

###
### Main Body of Code

sourcefile = sys.argv[1]
objectjson = json.load(open(sourcefile))
queuedjobs = []

hostname = raw_input("Enter Rubrik IP: ")
user = raw_input("Enter Rubrik User: ")
password = raw_input("Enter Rubrik Password: ")
targetslaid = raw_input("Enter Target SLA ID: ")

## Setup the Rubrik
rubrik, rubriktoken = connectRubrik(hostname, user, password)


## Loop through the objects
getheader = rubrik.headers

baseurl = "https://"+hostname+"/api/"

snaplist = []

for object in objectjson['data']:
	url = buildChargeUrl(object, baseurl)
	payload = createPayload(targetslaid, rubrik)
	response = rubrik.post(url=url, data=json.dumps(payload))
	syslog.syslog(syslog.LOG_INFO, 'Submitted object: '+object['objid']+' Response: '+str(response.status_code))
	respjson = response.json()
	respjson['type'] = object['type']
	respjson['objid'] = object['objid']
	queuedjobs.append(respjson.copy())

jobsrunning = True
jobcount = len(queuedjobs)
successcount = 0


while jobsrunning:
	for jobs in queuedjobs:
		url = buildJobUrl(jobs, baseurl)
		response = rubrik.get(url=url)
		jobstatus = response.json()
		if jobstatus['status'] == "RUNNING":
			syslog.syslog(syslog.LOG_INFO, 'STATUS: '+jobstatus['status']+' at '+str(jobstatus['progress'])+'% for '+jobs['objid'])
		else:
			syslog.syslog(syslog.LOG_INFO, 'STATUS: '+jobstatus['status']+' for '+jobs['objid'])
		if jobstatus['status'] == "SUCCEEDED":
			successcount = successcount + 1
	time.sleep(5)
	if successcount == jobcount:
		jobsrunning = False
