#!/bin/sh
[ "$PAM_TYPE" = "open_session" ] || exit 0
/usr/bin/curl -s --max-time 10 -H "Title: SSH Login - $PAM_USER" -H "Priority: high" -H "Tags: warning" -H "Authorization: Bearer {{ ntfy_token }}" -d "User: $PAM_USER from $PAM_RHOST" "https://{{ ntfy_host }}/serverlogin" > /dev/null 2>&1
exit 0
