#!/bin/sh

export REPO="https://github.com/openvswitch/ovs"
export BRANCH="master"
export TMPDIR="/tmp/ovs-upstream-$$"

set -e

/labhome/roid/scripts/ovs/make-ovs-rpm.sh

REPODIR=$TMPDIR/repo
openvswitch=`ls -1 $REPODIR/openvswitch-2*x86_64.rpm | tail -1`
echo "Install $openvswitch"
rpm -Uvh --force $openvswitch

echo "Restart openvswitch"
service openvswitch stop
sleep 1
killall ovs-vswitchd ovsdb-server || true
sleep 1
service openvswitch start
