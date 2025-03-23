#!/bin/bash

if [ "$PAM_TYPE" = "open_session" ]; then
        USERID="{{ telegram_user_id }}"
        KEY="{{ telegram_api_token }}"
        TIMEOUT="10"
        URL="https://api.telegram.org/bot$KEY/sendMessage"
        DATE_EXEC="$(date "+%d %b %Y %H:%M")"
        TMPFILE='/tmp/ipinfo-$DATE_EXEC.txt'
        IP=$(echo $SSH_CLIENT | awk '{print $1}')
        PORT=$(echo $SSH_CLIENT | awk '{print $3}')
        HOSTNAME=$(hostname -f)
        IPADDR=$(hostname -I | awk '{print $1}')
        curl http://ipinfo.io/$IP -s -o $TMPFILE
        CITY=$(cat $TMPFILE | jq '.city' | sed 's/"//g')
        REGION=$(cat $TMPFILE | jq '.region' | sed 's/"//g')
        COUNTRY=$(cat $TMPFILE | jq '.country' | sed 's/"//g')
        ORG=$(cat $TMPFILE | jq '.org' | sed 's/"//g')
        TEXT="$DATE_EXEC # ${USER} logged into $HOSTNAME ($IPADDR) from $IP - $ORG - $CITY, $REGION, $COUNTRY"
        curl -s --max-time $TIMEOUT -d "chat_id=$USERID&disable_web_page_preview=1&text=$TEXT" $URL > /dev/null
        rm $TMPFILE
else
        :
fi

exit 0