#!/usr/bin/env bash

# generate a message of random length
fail=0
while [ $fail -eq 0 ]; do
    export PYTHONIOENCODING=utf8
    len=`expr $RANDOM % 1024`
    # random string line adopted from http://www.howtogeek.com/howto/30184/10-ways-to-generate-a-random-password-from-the-command-line/
    < /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c$len | xargs echo > /tmp/msg
    cat /tmp/msg | ./encode.py 2> /tmp/seed | ./decode.py > /tmp/msgout
    md1=`md5sum /tmp/msg | awk '{print $1}'`
    md2=`md5sum /tmp/msgout | awk '{print $1}'`
    if [ "$md1" != "$md2" ]; then
        fail=1
    fi
    echo -n .
done

