# Assured Rubrik Development Tools
# Created by Andrew Eva Jan 10, 2024
# Purpose to simplify Rubrik Calls across automated scripts in Python

# Modules
import json
import requests
import urllib3
import syslog
import getpass
from datetime import datetime
from dateutil import parser

# Silence warnings
# requests.packages.urllib3.disable_warnings()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
globalsession = requests.session()
globaltoken = ""
globalhostname = ""
globalcache = {}

def sessionCreate(hostname, token):
    global globalsession, globalhostname, globalcache
    #Hostname expects a hostname, FQDN, or IP address without any prefix or suffix
    #token expects the API Key or Token key of an authenticated Rubrik session
    #Configure Requests Session
    rubriksession = requests.Session()
    rubriksession.verify = False
    bearerToken = "Bearer "+token
    header = { 'Authorization': bearerToken }
    rubriksession.headers = header
    target = "https://"+hostname+"/api/v1/cluster/me"
    syslog.syslog(syslog.LOG_INFO, "Connecting to "+hostname+"...")
    failed = False
    try:
        response = rubriksession.get(url=target)
    except rubriksession.exceptions.Timeout:
        syslog.syslog(syslog.LOG_ERR, hostname+" has timed out. Connection Failed")
        failed = True
    syslog.syslog(syslog.LOG_INFO, hostname+" status code: "+str(response.status_code))
    if response.status_code == 200:
        globalsession = rubriksession
        globalhostname = hostname
        globalcache['v1/cluster/me'] = response.json()
        return rubriksession

def connectCluster(hostname, **credentials):
    global globalhostname
    # Pass in the hostname, FQDN, or IP address without any prefix or suffic
    # Also expecting "username" and "password" variables. If a TOTP variable is passed in then we will attempt to use it.
    thesession = requests.Session()
    thesession.verify = False
    baseurl = "https://"+hostname+"/api/"
    url = baseurl+"internal/session"
    payload = {"initParams":{}}
    if 'username' in credentials:
        username = credentials['username']
    else:
        username = input("Username: ")
    if 'password' in credentials:
        password = credentials['password']
    else:
        password = getpass.getpass('Password: ')
    if 'totp' in credentials:
        code = credentials['totp']
    else:
        code = input("Enter TOTP Code: ")
    response = thesession.post(url=url, auth=(username, password), json=payload)
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
    orgId = challengeResponse.json()['session']['organizationId']
    tagIt = credentials.get('keyTag',"rubrikADPSDK")
    apiTokenData = {
        "initParams": {
            "apiToken": {
                "expiration": 525000,
                "tag": tagIt
                },
            "organizationId": orgId
            }
        }
    try:
        token = "Bearer "+challengeResponse.json()['session']['token']
    except:
        print("TOTP Authentication Failure, session not created")
        return 
    header = {'Authorization': token}
    thesession.headers = header
    saveToken = credentials.get('saveToken', False)
    if saveToken:
        tokenCreateResponse = thesession.post(url=url, json=apiTokenData)
        finalToken = tokenCreateResponse.json()['session']['token']
    else:
        finalToken = challengeResponse.json()['session']['token']
    globalhostname = hostname
    return finalToken

def getSession(hostname, username, password, totp):
    token = connectCluster(hostname, username=username, password=password, totp=totp, saveToken=False)
    if token is None:
        print("Unable to authenticate")
        raise ExceptionGroup('Unable to Connect to Rubrik')
    session = sessionCreate(hostname, token)
    if session is None:
        print("Unable to create session")
        raise ExceptionGroup('Unable to create session')
    return session

def cache(key, value):
    global globalcache
    globalcache['key'] = value

def getCache():
    return globalcache

def clearCache():
    global globalcache
    globalcache.clear()

def getClusterId():
    apiEndpoint = "v1/cluster/me"
    if apiEndpoint in globalcache:
        return globalcache[apiEndpoint]
    else:
        url = "https://"+globalhostname+"/api/v1/cluster/me"
        response = globalsession.get(url=url)
        data = response.json()
        cache(apiEndpoint, data)
        return data

def getUser(userId):
    apiEndpoint = "internal/user/"+userId
    if apiEndpoint in globalcache:
        return globalcache['apiEndpoint']
    else:
        url = "https://"+globalhostname+"/api/"+apiEndpoint
        response = globalsession.get(url=url)
        data = response.json()
        cache(apiEndpoint, data)
        return data

def getUserSession(userId, **kwargs):
    apiEndpoint = "internal/session?user_id="+userId
    refreshCache = kwargs.get('refreshCache', False)
    if (apiEndpoint in globalcache) and (not refreshCache):
        return globalcache['apiEndpoint']
    else:
        url = "https://"+globalhostname+"/api/"+apiEndpoint
        response = globalsession.get(url=url)
        data = response.json()
        cache(apiEndpoint, data)
        return data

def sortByDate(data, sortKey, **kwargs):
    reverseOrder = kwargs.get('reverseOrder', False)
    ascending = kwargs.get('ascending', True)
    descending = kwargs.get('descending', False)
    if descending:
        reverseOrder = True
    sorted_data = sorted(data, key=lambda x: parser.parse(x[sortKey]), reverse=reverseOrder)
    return sorted_data

def tokenCleanup(tokenKey, **kwargs):
    apiEndpoint = "internal/session/bulk_delete"
    userId = getUser(kwargs.get('userId',"me"))
    tokenSummary = getUserSession(userId['id'][7:], refreshCache=True)
    keepLatest = kwargs.get('keepLatest', False)
    latestType = kwargs.get('latestType', 'lastUsageTime')
    body = {
        "tokenIds": [],
        "userId": userId['id'][7:]
        }
    tokenSummary['data'] = sortByDate(tokenSummary['data'], latestType, reverseOrder=False)
    for sess in tokenSummary['data']:
        if sess['tag'] == tokenKey:
            body['tokenIds'].append(sess['id'])
    syslog.syslog(syslog.LOG_INFO, "Deleting "+str(len(body['tokenIds']))+" API Tokens that match "+tokenKey)
    if keepLatest:
        body['tokenIds'].pop()
        syslog.syslog(syslog.LOG_INFO, "Most Recent Token Retained")
    syslog.syslog(syslog.LOG_INFO, "Deleting "+str(len(body['tokenIds']))+" API Tokens that match "+tokenKey)
    url = "https://"+globalhostname+"/api/"+apiEndpoint
    response = globalsession.post(url=url, json=body)
    if response.status_code == 204:
        syslog.syslog(syslog.LOG_INFO, "Successful deletion of tokens matching "+tokenKey)
    else:
        syslog.syslog(syslog.LOG_ERR, "Deletion failed "+str(response.text))
    
def getNodes():
    apiEndpoint = "internal/node"
    if apiEndpoint in globalcache:
        return globalcache[apiEndpoint]
    else:
        url = "https://"+globalhostname+"/api/"+apiEndpoint
        response = globalsession.get(url=url)
        data = response.json()
        cache(apiEndpoint, data)
        return data

def getSLADomain(**kwargs):
    apiEndpoint = "v2/sla_domain"
    refreshCache = kwargs.get('refreshCache', False)
    primaryClusterId = kwargs.get('primaryClusterId', "local")
    apiEndpoint = apiEndpoint+"?primary_cluster_id="+primaryClusterId
    if (apiEndpoint in globalcache) and (not refreshCache):
        return globalcache[apiEndpoint]
    else:
        url = "https://"+globalhostname+"/api/"+apiEndpoint
        response = globalsession.get(url=url)
        data = response.json()
        cache(apiEndpoint, data)
        return data

def getReplication(location, **kwargs):
    apiEndpoint = "internal/replication"
    if (location == "source") or (location == "target"):
        apiEndpoint = apiEndpoint+"/"+location
    else:
        raise ExceptionGroup('Unknown location type, source or target are acceptable types.')
    refreshCache = kwargs.get('refreshCache', False)
    name = kwargs.get('name',"")
    if (apiEndpoint in globalcache) and (not refreshCache):
        return globalcache[apiEndpoint]
    else:
        url = "https://"+globalhostname+"/api/"+apiEndpoint
        if len(kwargs) != 0:
            count = 1
            for key in kwargs.keys():
                if count > 1:
                    url = url+"&"
                else:
                    url = url+"?"
                url = url+key+"="+kwargs[key]
                count+=1
        #print(url)
        response = globalsession.get(url=url)
        globalcache[apiEndpoint] = response.json()
        return response.json()

def searchObject(searchdata):
    # Requirements: needs to be sent the Rubrik search model JSON
    #{"searchText":"string","searchProperties":["name"],"objectTypes":["AppBlueprint"],"primaryClusterId":"string","offset":0,"limit":0}
    # No Caching of searches
    apiEndpoint = "internal/hierarchy/search"
    url = "https://"+globalhostname+"/api/"+apiEndpoint
    body = searchdata
    response = globalsession.post(url=url, json=body)
    data = response.json()
    return data

def getObject(text, **kwargs):
    # Default search Criteria
    defaulttypes = [ "VirtualMachine", "WindowsHost", "HypervVirtualMachine","NutanixVirtualMachine","NasShare","NutanixVirtualMachine","MssqlDatabase","ManagedVolume","LinuxHost"]
    body = {"searchText":"","searchProperties":["name"],"objectTypes": defaulttypes,"primaryClusterId":"","offset":0,"limit":100}
    body['searchText'] = text
    body['searchProperties'] = kwargs.get('searchProperties',["name"])
    body['objectTypes'] = kwargs.get('objectTypes', defaulttypes)
    body['primaryClusterId'] = kwargs.get('primaryClusterId', getClusterId()['id'])
    if 'offset' in kwargs:
        body['offset'] = kwargs['offset']
    if 'limit' in kwargs:
        body['limit'] = kwargs['limit']
    results = searchObject(body)
    #print(json.dumps(results, indent=4))
        
def getLivemount(objectType, **kwargs):
    refreshCache = kwargs.get('refreshCache', False)
    baseurl = "https://"+globalhostname+"/api/"
    objId = kwargs.get('objId',"")
    if objectType == "VirtualMachine":
        url = baseurl+"v1/vmware/vm/snapshot/mount"
    if objectType == "NutanixVirtualMachine":
        url = baseurl+"v1/nutanix/vm/snapshot/mount"
    if objectType == "HypervVirtualMachine":
        url = baseurl+"internal/hyperv/vm/snapshot/mount"
    if objectType == "WindowsVolumeGroup":
        url = baseurl+"v1/volume_group/snapshot/mount"
    if objectType == "MssqlDatabase":
        url = baseurl+"v1/mssql/db/mount"
    if objectType == "ManagedVolume":
        url = baseurl+"internal/managed_volume/snapshot/export"
    if len(objId) > 1:
        url = url + "/"+objId
    apiEndpoint = url
    if (apiEndpoint in globalcache) and (not refreshCache):
        return globalcache[apiEndpoint]
    else:
        response = globalsession.get(url=url)
        data = response.json()
        cache(apiEndpoint, data)
        return data
    
    

