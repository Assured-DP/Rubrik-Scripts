#!/bin/bash
########################################################################################################
# Title:    oracle_managed_volume_setup.sh
# Summary:  Creates begin and end snapshot commands, nfs mounts and sample rman script
# Author:   Julian Zgoda, DevOps SA, julian.zgoda@rubrik.com
#
# REQUIREMENTS:
# jq is required to parse curl response. You can usually get the jq utility in the add on
# repository of most linux distros.
#
# The password can be passed as an option or entered on the command line.
#
# USAGE: ./oracle_managed_volume_setup.sh -c 192.168.45.5 -u admin -p mypassword -m managed_volume_name
########################################################################################################

# Function to print the usage
usage() { echo "Usage: $0 [-c <IP_ADDRESS>] [-u <USERNAME>] [optional -p <PASSWORD> ] [-m <MV_NAME>]" 1>&2; exit 1; }
# Start of variables
# Read variables
while getopts c:u:p:m: option
do
 case "${option}"
 in
 c) CLUSTER=${OPTARG};;
 u) USERNAME=${OPTARG};;
 p) PASSWORD=${OPTARG};;
 m) MV_NAME=$OPTARG;;
 *) usage;;
 esac
done
shift $((OPTIND-1))
if [ -z "${CLUSTER}" ] || [ -z "${USERNAME}" ] || [ -z "${MV_NAME}" ]; then
    usage
fi
#
# End of variables
# Get Authorization Hash
# Add Check for jq
if ! JQ_LOC="$(type -p jq)" || [ -z "$JQ_LOC" ]; then
  printf '%s\n' "The jq utility is not installed"
  printf '%s\n' "Please install from the addons repository"
  exit 1
fi
# check if password was enter in command arguments, if not prompt for password
if [ -z $PASSWORD ]; then
  printf '%s' "Enter the $USERNAME password: "
  read -s PASSWORD
  echo
fi
AUTH_HASH=$(echo -n "$USERNAME:$PASSWORD" | openssl enc -base64)
# Get the managed volume id
API_RETURN=$(curl -w '%{http_code}' -s -H 'Content-Type: application/json' -H 'Authorization: Basic '"$AUTH_HASH"'' -X GET -k -l "https://$CLUSTER/api/internal/managed_volume?name=$MV_NAME")
if [ $? != 0 ]; then
   printf '%s\n' "Curl failed with exit status: $?"
   exit 1
fi
HTTP_CODE=$(echo $API_RETURN | sed 's/{.*}//g')
API_RETURN=$(echo $API_RETURN | sed 's/...$//g')
# Bash 4.2 String manipulation version
#HTTP_CODE=${API_RETURN: -3}
#API_RETURN=${API_RETURN::-3}
if [[ HTTP_CODE -lt 200 ]]; then
    echo "API POST return was informational. Status Code: $HTTP_CODE"
    exit 1
elif [[ HTTP_CODE -ge 200 ]] && [[ HTTP_CODE -lt 300 ]]; then
    MV_ID=$(echo $API_RETURN | jq -r '.data[0].id')
    if [ -z $MV_ID ] || [ $MV_ID = 'null' ]; then
        printf '%s\n' "Invalid Managed Volume Name..."
        exit 1
    fi
elif [[ HTTP_CODE -ge 300 ]] && [[ HTTP_CODE -lt 400 ]]; then
    printf '%s\n' "API POST was redirected. Status Code: $HTTP_CODE"
    exit 1
elif [[ HTTP_CODE -ge 400 ]] && [[ HTTP_CODE -lt 500  ]]; then
    printf '%s\n' "API POST returned Error. Status Code: $HTTP_CODE"
    printf '%s\n' $(echo $API_RETURN | jq -r '.message')
    exit 1
elif [[ HTTP_CODE -ge 500 ]] && [[ HTTP_CODE -lt 600 ]]; then
    printf '%s\n' "API POST returned Server Error. Status Code: $HTTP_CODE"
    exit 1
fi

# Print Managed Volume ID and the begin/end snapshot commands
printf '%s\n' ""
printf '%s\n' "------------------------------------------------------"
printf '%s\n' "       Rubrik Oracle Backup Configuration             "
printf '%s\n' "------------------------------------------------------"
printf '%s\n' "Managed Volume Name is $MV_NAME";
printf '%s\n' "Managed Volume ID is $MV_ID";
BEGIN_SNAPSHOT="curl -k -X POST -H 'Authorization: Basic "$AUTH_HASH"' 'https://"$CLUSTER"/api/internal/managed_volume/"$MV_ID"/begin_snapshot'"
printf '%s\n' "------------------------------------------------------"
printf '%s\n' "This is the ReST API call to begin a Rubrik snapshot:"
printf '%s\n' "$BEGIN_SNAPSHOT"
END_SNAPSHOT="curl -k -X POST -H 'Authorization: Basic "$AUTH_HASH"' 'https://"$CLUSTER"/api/internal/managed_volume/"$MV_ID"/end_snapshot'"
printf '%s\n' "------------------------------------------------------"
printf '%s\n' "This is the ReST API call to end a Rubrik snapshot:"
printf '%s\n' "$END_SNAPSHOT"
printf '%s\n' "------------------------------------------------------"
# Get the managed volume nfs exports
MOUNT_IPS=($(curl -s -H 'Content-Type: application/json' -H 'Authorization: Basic '"$AUTH_HASH"'' -X GET -k -l "https://$CLUSTER/api/internal/managed_volume/$MV_ID" | jq -r '.mainExport.channels[].ipAddress'))
MOUNT_POINTS=($(curl -s -H 'Content-Type: application/json' -H 'Authorization: Basic '"$AUTH_HASH"'' -X GET -k -l "https://$CLUSTER/api/internal/managed_volume/$MV_ID" | jq -r '.mainExport.channels[].mountPoint'))
# Build and print the nfs mounts
printf '%s\n' "These are the exports and mount points for /etc/fstab:"
for ((i=0;i<${#MOUNT_IPS[@]};++i)); do
    MOUNTS[i]="/mnt/rubrik/"$MV_NAME"-ch$i"
    printf "%s /mnt/rubrik/"$MV_NAME"-ch$i  nfs rw,bg,hard,nointr,rsize=32768,wsize=32768,tcp,actimeo=0,vers=3,timeo=600 0 0 %s\n" "${MOUNT_IPS[i]}:${MOUNT_POINTS[i]}"
done
printf '%s\n' "------------------------------------------------------"
printf '%s\n' "These are the commands to create the directories for the mount points:"
for DIR in "${MOUNTS[@]}"; do
  printf '%s\n' "mkdir -p $DIR"
done
printf '%s\n' "------------------------------------------------------"
printf '%s\n' "These are the commands to mount the nfs file systems:"
for DIR in "${MOUNTS[@]}"; do
  printf '%s\n' "mount $DIR"
done
printf '%s\n' "------------------------------------------------------"
# Build and print a sample rman script
printf '%s\n' "This is a sample RMAN script to do a 3 day incremental merge backup:"
printf '%s\n' "configure controlfile autobackup on;"
printf '%s\n' "configure retention policy to recovery window of 3 days;"
printf '%s\n' "run {"
printf '%s\n' "set controlfile autobackup format for device type disk to '"${MOUNTS[0]}"/%F';"
CHANNEL=0
for PATH in "${MOUNTS[@]}"; do
  printf '%s\n' "allocate channel ch"$CHANNEL" device type disk format '"$PATH"/%U';"
  ((CHANNEL++))
done
printf '%s\n' "backup incremental level 1 for recover of copy with tag '"$MV_NAME"_incmrg' database plus archivelog delete all input;"
printf '%s\n' "recover copy of database with tag '"$MV_NAME"_incmrg' until time 'SYSDATE-3';"
printf '%s\n' "backup as copy current controlfile;"
CHANNEL=0
for PATH in "${MOUNTS[@]}"; do
  printf '%s\n' "release channel ch"$CHANNEL";"
  ((CHANNEL++))
done
printf '%s\n' "}"
printf '%s\n' "allocate channel for maintenance device type disk;"
printf '%s\n' "crosscheck backup;"
printf '%s\n' "crosscheck copy;"
printf '%s\n' "delete noprompt obsolete;"
printf '%s\n' "release channel;"
printf '%s\n' "------------------------------------------------------"
exit 0
