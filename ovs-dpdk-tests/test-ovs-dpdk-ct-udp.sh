#!/bin/bash
#
# Test OVS-DPDK UDP traffic with CT
#
# Require external server
#

my_dir="$(dirname "$0")"
. $my_dir/common-dpdk.sh

require_remote_server

IP=1.1.1.7
REMOTE=1.1.1.8

config_sriov 2
enable_switchdev
require_interfaces REP NIC
unbind_vfs
bind_vfs

trap cleanup_test EXIT

function config() {
    cleanup_test
    debug "Restarting OVS"
    start_clean_openvswitch

    config_simple_bridge_with_rep 1
    config_ns ns0 $VF $IP
}

function config_remote() {
    on_remote ip a flush dev $REMOTE_NIC
    on_remote ip a add $REMOTE/24 dev $REMOTE_NIC
    on_remote ip l set dev $REMOTE_NIC up
}

function add_openflow_rules() {
    ovs-ofctl del-flows br-phy
    ovs-ofctl add-flow br-phy "arp,actions=NORMAL"
    ovs-ofctl add-flow br-phy "icmp,actions=NORMAL"
    ovs-ofctl add-flow br-phy "table=0,udp,ct_state=-trk,actions=ct(zone=5, table=1)"
    ovs-ofctl add-flow br-phy "table=1,udp,ct_state=+trk+new,actions=ct(zone=5, commit),NORMAL"
    ovs-ofctl add-flow br-phy "table=1,udp,ct_state=+trk+est,ct_zone=5,actions=normal"
    debug "\nOVS flow rules:"
    ovs-ofctl dump-flows br-phy --color
}

function run() {
    config
    config_remote
    add_openflow_rules

    verify_ping
    debug "Testing UDP traffic"
    t=5
    # traffic
    ip netns exec ns0 timeout -k 1 $((t+2)) iperf -s &
    pid1=$!
    sleep 1
    on_remote timeout -k 1 $((t+2)) iperf -c $IP -t $t -u -l 1000 &
    pid2=$!

    # verify pid
    sleep 2
    kill -0 $pid2 &>/dev/null
    if [ $? -ne 0 ]; then
        err "iperf failed"
        return
    fi

    sleep $t
    # check offloads
    check_dpdk_offloads $IP

    killall -9 iperf &>/dev/null
    debug "wait for bgs"
    wait
}

run
start_clean_openvswitch
trap - EXIT
cleanup_test
test_done
