#!/bin/bash
#
# Ping and ping flood between two VFs
#

my_dir="$(dirname "$0")"
. $my_dir/common.sh

IP1="7.7.7.1"
IP2="7.7.7.2"

function cleanup() {
    ovs_clear_bridges
    ip netns del ns0 2> /dev/null
    ip netns del ns1 2> /dev/null
    sleep 0.5 # wait for VF to bind back
    for i in $REP $REP2 $VF $VF2 ; do
        ip link set $i mtu 1500 &>/dev/null
        ifconfig $i 0 &>/dev/null
    done
}

config_sriov 2
enable_switchdev
unbind_vfs
bind_vfs
require_interfaces VF VF2 REP REP2

trap cleanup EXIT
cleanup
start_clean_openvswitch
config_vf ns0 $VF $REP $IP1
config_vf ns1 $VF2 $REP2 $IP2
BR=ov1
ovs-vsctl add-br $BR
ovs-vsctl add-port $BR $REP
ovs-vsctl add-port $BR $REP2

title "Test ping $VF($IP1) -> $VF2($IP2)"
ip netns exec ns0 ping -q -c 10 -i 0.2 -w 4 $IP2 && success || err

function set_mtu() {
    local mtu=$1
    ip link set $REP mtu $mtu || fail "Failed to set mtu to $REP"
    ip link set $REP2 mtu $mtu || fail "Failed to set mtu to $REP2"
    ip netns exec ns0 ip link set $VF mtu $mtu || fail "Failed to set mtu to $VF"
    ip netns exec ns1 ip link set $VF2 mtu $mtu || fail "Failed to set mtu to $VF2"
}

function verify_timedout() {
    local pid=$1
    wait $pid
    local rc=$?
    [ $rc == 124 ] && success || err "Didn't expect to see packets"
}

function start_sniff() {
    local dev=$1
    local filter=$2
    timeout 5 tcpdump -qnnei $dev -c 4 $filter &
    tpid=$!
    sleep 0.5
}


mtu=576
title "Test ping $VF($IP1) -> $VF2($IP2) MTU $mtu"
set_mtu $mtu
ip netns exec ns0 ping -q -c 2 -w 4 $IP2 || err
echo "start sniff $REP"
start_sniff $REP icmp
ip netns exec ns0 ping -q -f -w 4 $IP2 && success || err
echo "verify tcpdump"
verify_timedout $tpid

trap - EXIT
cleanup
test_done
