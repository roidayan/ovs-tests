#!/bin/bash
#
# Test OVS-DPDK with geneve traffic
#
# Require external server
#
# IGNORE_FROM_TEST_ALL

my_dir="$(dirname "$0")"
. $my_dir/../common.sh
. $my_dir/common-dpdk.sh

REMOTE_SERVER=${REMOTE_SERVER:-$1}
REMOTE_NIC=${REMOTE_NIC:-$2}
require_remote_server

IP=1.1.1.7
REMOTE=1.1.1.8

LOCAL_TUN=7.7.7.7
REMOTE_IP=7.7.7.8
GENEVE_ID=42

config_sriov 2
require_interfaces REP NIC
unbind_vfs
bind_vfs


function cleanup_remote() {
    on_remote ip a flush dev $REMOTE_NIC
    on_remote ip l del dev geneve1 &>/dev/null
}

function cleanup() {
    ip a flush dev $NIC
    ip netns del ns0 &>/dev/null
    cleanup_e2e_cache
    cleanup_remote
    sleep 0.5
}
trap cleanup EXIT

function config() {
    cleanup
    disable_e2e_cache
    echo "Restarting OVS"
    start_clean_openvswitch

    config_simple_bridge_with_rep 0
    config_remote_bridge_tunnel $GENEVE_ID $REMOTE_IP geneve
    config_local_tunnel_ip $LOCAL_TUN br-phy
    config_ns ns0 $VF $IP
}

function config_remote() {
    on_remote ip link del geneve1 &>/dev/null
    on_remote ip link add geneve1 type geneve id $GENEVE_ID remote $LOCAL_TUN dstport 6081
    on_remote ip a flush dev $REMOTE_NIC
    on_remote ip a add $REMOTE_IP/24 dev $REMOTE_NIC
    on_remote ip a add $REMOTE/24 dev geneve1
    on_remote ip l set dev geneve1 up
    on_remote ip l set dev $REMOTE_NIC up
}

function run() {
    config
    config_remote
    ovs-ofctl dump-flows br-int --color

    echo -e "Testing ping"
    ip netns exec ns0 ping -q -c 1 -w 1 $REMOTE
    if [ $? -ne 0 ]; then
        err "ping failed"
        return
    fi

    echo -e "\nTesting TCP traffic"
    t=15
    # traffic
    ip netns exec ns0 timeout $((t+2)) iperf -s &
    pid1=$!
    sleep 2
    on_remote timeout $((t+2)) iperf -c $IP -t $t &
    pid2=$!

    # verify pid
    sleep 2
    kill -0 $pid2 &>/dev/null
    if [ $? -ne 0 ]; then
        err "iperf failed"
        return
    fi

    # check offloads
    x=$(ovs-appctl dpctl/dump-flows -m | grep -v 'ipv6\|icmpv6\|arp\|drop\|ct_state(0x21/0x21)' | grep -- $IP'\|tnl_pop' | wc -l)
    echo "Number of filtered rules: $x"
    y=$(ovs-appctl dpctl/dump-flows -m type=offloaded | grep -v 'ipv6\|icmpv6\|arp\|drop\|flow-dump' | wc -l)
    echo "Number of offloaded rules: $y"

    if [ $x -ne $y ]; then
        err "offloads failed"
    fi

    kill -9 $pid1 &>/dev/null
    killall iperf &>/dev/null
    echo "wait for bgs"
    wait
}

run
start_clean_openvswitch
test_done
