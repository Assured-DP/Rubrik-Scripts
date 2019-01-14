#from cassandra.cluster import Cluster
import requests
import urllib3
import getpass
#requests.packages.urllib3.disable_warnings()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

global billingSize

rubrikip = raw_input("Rubrik IP: ")
rubrikuser = raw_input("Rubrik user: ")
rubrikpass = getpass.getpass("Rubrik Pass: ")


tokenUrl = "https://"+rubrikip+"/api/v1/session"
username = rubrikuser
password = rubrikpass
session = requests.post(tokenUrl, verify=False, auth=(username, password))
session = session.json()
token = 'Bearer ' + session['token']

localip = "172.20.160.100"



print "#############################"
print "oranfstab begins here"
print "#############################"


def buildVolumeList():
    vmurl = "https://"+rubrikip+"/api/internal/managed_volume"
    volsresponse = requests.get(vmurl, headers= { 'Accept': 'application/json', 'Authorization': token },verify=False, stream=True)
    voljson = volsresponse.json()
    count = 1
    if voljson['total'] > 1:
        for volume in voljson['data']:
            if count < 10:
		print ("server: rbk_"+volume['name'].lower()+"_00"+str(count))
	    elif count < 100:
		print ("server: rbk_"+volume['name'].lower()+"_0"+str(count))
	    else:
		print ("server: rbk_"+volume['name'].lower()+"_"+str(count))
	    print ("local: "+localip)
	    count = count + 1
	    # Print Paths
	    for path in volume['mainExport']['channels']:
	    	print ("path: "+path['ipAddress'])
	    mntcount = 0
	    for mounts in volume['mainExport']['channels']:
		mntname = str(volume['name'])+"-ch"+str(mntcount)
		print ("export: "+mounts['mountPoint']+" mount: /mnt/rubrik/"+mntname)
		mntcount = mntcount + 1
	    print("nfs_version: nfsv3")
	    print("")

def buildTab():
    vmurl = "https://uscust008mon001.us.assured.local/api/internal/managed_volume"
    volsresponse = requests.get(vmurl, headers= { 'Accept': 'application/json', 'Authorization': token },verify=False, stream=True)
    voljson = volsresponse.json()
    nfs_path = "/mnt/rubrik/"
    nfs_settings = " nfs rw,noatime,bg,hard,nointr,rsize=131072,wsize=131072,tcp,actimeo=0,vers=3,timeo=600,addr="
    nfs_close = " 0 0"
    if voljson['total'] > 1:
        for volume in voljson['data']:
            # Print Paths
            mountcount = 0
            for path in volume['mainExport']['channels']:
                print (path['ipAddress']+":"+path['mountPoint']+" "+nfs_path+volume['name']+"-ch"+str(mountcount)+nfs_settings+path['ipAddress']+nfs_close)
		mountcount = mountcount + 1

buildVolumeList()
print("")
print("########################")
print("mtab information below")
print("########################")
buildTab()
