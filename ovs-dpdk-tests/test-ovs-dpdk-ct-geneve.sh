#!/bin/bash
#
# Test OVS-DPDK with geneve traffic
#
# Require external server
#

my_dir="$(dirname "$0")"
. $my_dir/common-dpdk.sh

require_remote_server

config_sriov 2
require_interfaces REP NIC
unbind_vfs
bind_vfs

trap cleanup_test EXIT

function config() {
    cleanup_test

    config_tunnel "geneve"
    config_remote_tunnel "geneve"
    config_local_tunnel_ip $LOCAL_TUN_IP br-phy
}

function add_openflow_rules() {
    ovs-ofctl del-flows br-int
    ovs-ofctl add-flow br-int "arp,actions=NORMAL"
    ovs-ofctl add-flow br-int "table=0,ip,ct_state=-trk,actions=ct(zone=5, table=1)"
    ovs-ofctl add-flow br-int "table=1,ip,ct_state=+trk+new,actions=ct(zone=5, commit),NORMAL"
    ovs-ofctl add-flow br-int "table=1,ip,ct_state=+trk+est,ct_zone=5,actions=normal"
    debug "OVS flow rules:"
    ovs-ofctl dump-flows br-int --color
}

function run() {
    config
    add_openflow_rules

    verify_ping $REMOTE_IP ns0

    generate_traffic "remote" $LOCAL_IP
}

run
trap - EXIT
cleanup_test
test_done
