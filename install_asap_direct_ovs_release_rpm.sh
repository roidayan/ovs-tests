#!/bin/sh

DIR=$(cd `dirname $0` ; pwd)
RELEASE="/mswg/release/linux/ovs_release/latest/"
RPMS="$RELEASE/RPMS"

set -e

openvswitch=`ls -1 $RPMS/openvswitch-2*x86_64.rpm | tail -1`

if [ -z $openvswitch ]; then
    echo "Cannot find openvswitch rpm"
    exit 1
fi

echo "Packages:"
echo $openvswitch
sleep 1

echo "Install `basename $openvswitch`"
rpm -Uvh --force $openvswitch

echo "Restart openvswitch"
service openvswitch stop
sleep 1
killall ovs-vswitchd ovsdb-server || true
sleep 1
service openvswitch start
