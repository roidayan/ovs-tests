#!/bin/bash
#
# Test OVS CT udp traffic
#

my_dir="$(dirname "$0")"
. $my_dir/common.sh

require_act_ct

IP1="7.7.7.1"
IP2="7.7.7.2"

enable_switchdev_if_no_rep $REP
require_interfaces REP REP2
unbind_vfs
bind_vfs
reset_tc $REP
reset_tc $REP2

function cleanup() {
    ip netns del ns0 2> /dev/null
    ip netns del ns1 2> /dev/null
    reset_tc $REP
    reset_tc $REP2
}
trap cleanup EXIT

function config_vf() {
    local ns=$1
    local vf=$2
    local rep=$3
    local ip=$4

    echo "[$ns] $vf ($ip) -> $rep"
    ifconfig $rep 0 up
    ip netns add $ns
    ip link set $vf netns $ns
    ip netns exec $ns ifconfig $vf $ip/24 up
}

function run() {
    title "Test OVS CT UDP"
    config_vf ns0 $VF $REP $IP1
    config_vf ns1 $VF2 $REP2 $IP2

    echo "setup ovs"
    start_clean_openvswitch
    ovs-vsctl add-br br-ovs
    ovs-vsctl add-port br-ovs $REP
    ovs-vsctl add-port br-ovs $REP2

    ovs-ofctl add-flow br-ovs in_port=$REP,dl_type=0x0806,actions=output:$REP2
    ovs-ofctl add-flow br-ovs in_port=$REP2,dl_type=0x0806,actions=output:$REP

    ovs-ofctl add-flow br-ovs "table=0, udp,ct_state=-trk actions=ct(table=1)"
    ovs-ofctl add-flow br-ovs "table=1, udp,ct_state=+trk+new actions=ct(commit),normal"
    ovs-ofctl add-flow br-ovs "table=1, udp,ct_state=+trk+est actions=normal"

    ovs-ofctl dump-flows br-ovs

    t=10
    echo "run traffic for $t seconds"
    ip netns exec ns1 timeout $((t+1)) iperf -t $t -u -c $IP1 &
    ip netns exec ns0 timeout $((t+1)) iperf -t $t -u -c $IP2 &

    # first 4 packets not offloaded until conn is in established state.
    sleep 2
    echo "sniff packets on $REP"
    timeout $t tcpdump -qnei $REP -c 6 'icmp' &
    pid=$!

    sleep $t
    killall -9 iperf &>/dev/null
    wait $! 2>/dev/null

    # test sniff timedout
    wait $pid
    rc=$?
    if [[ $rc -eq 124 ]]; then
        :
    elif [[ $rc -eq 0 ]]; then
        err "Didn't expect to see packets"
    else
        err "Tcpdump failed"
    fi

    ovs-vsctl del-br br-ovs

    # wait for traces as merging & offloading is done in workqueue.
    sleep 3
}


run
test_done
