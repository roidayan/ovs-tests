#!/bin/bash
#
# test moving to swtichdev mode and trafic while using legacy vport_match mode
#
# [MLNX OFED] Bug SW #2571799: can't move to switchdev mode if vport_match is legacy
#

my_dir="$(dirname "$0")"
. $my_dir/common.sh

test -z "$VF2" && fail "Missing VF2"
test -z "$REP2" && fail "Missing REP2"

IP1="7.7.7.1"
IP2="7.7.7.2"

function cleanup() {
    ip netns del ns0 2> /dev/null
    ip netns del ns1 2> /dev/null
    sleep 0.5 # wait for VF to bind back
    for i in $REP $REP2 $VF $VF2 ; do
        ip link set $i mtu 1500 &>/dev/null
        ifconfig $i 0 &>/dev/null
    done
}

function cleanup_vport_match_mode() {
    cleanup
    disable_sriov
    set_vport_match_metadata
    enable_sriov
    enable_switchdev
}

trap cleanup_vport_match_mode EXIT
cleanup

disable_sriov
set_vport_match_legacy
enable_sriov
enable_switchdev
unbind_vfs
bind_vfs

require_interfaces VF VF2 REP REP2
start_clean_openvswitch
start_check_syndrome
config_vf ns0 $VF $REP $IP1
config_vf ns1 $VF2 $REP2 $IP2
BR=ov1
ovs-vsctl add-br $BR
ovs-vsctl add-port $BR $REP
ovs-vsctl add-port $BR $REP2

title "Test ping $VF($IP1) -> $VF2($IP2)"
ip netns exec ns0 ping -q -c 10 -i 0.2 -w 4 $IP2 && success || err


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


title "Test ping $VF($IP1) -> $VF2($IP2)"
ip netns exec ns0 ping -q -c 2 -w 2 $IP2 || err
echo "start sniff $REP"
start_sniff $REP icmp
ip netns exec ns0 ping -q -f -w 4 $IP2 && success || err
echo "verify tcpdump"
verify_timedout $tpid

ovs_clear_bridges
cleanup
trap - EXIT
check_syndrome
test_done