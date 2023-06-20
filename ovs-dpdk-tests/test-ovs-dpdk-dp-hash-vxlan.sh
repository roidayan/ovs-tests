#!/bin/bash
#
# Test dp-hash after vxlan encap
#
# Require external server
#

my_dir="$(dirname "$0")"
. $my_dir/common-dpdk.sh

require_remote_server

config_sriov 2
enable_switchdev
require_interfaces REP NIC
unbind_vfs
bind_vfs

trap cleanup_test EXIT

function config() {
    cleanup_test
    set_e2e_cache_enable false
    debug "Restarting OVS"
    start_clean_openvswitch

    config_tunnel "vxlan" 1 br-phy br-phy
    config_local_tunnel_ip $LOCAL_TUN_IP br-phy
    ip link add dev dummy type veth peer name rep-dummy
    ovs-vsctl add-port br-phy rep-dummy
    ovs-vsctl show
}

function add_openflow_rules() {
    ovs-ofctl del-flows br-phy
    ovs-ofctl add-group br-phy group_id=1,type=select,bucket=watch_port=pf,output:pf,bucket=watch_port=rep-dummy,output:rep-dummy

    ovs-ofctl add-flow br-phy in_port=$REP,actions=vxlan_br-phy
    ovs-ofctl add-flow br-phy in_port=vxlan_br-phy,actions=$REP

    ovs-ofctl add-flow br-phy in_port=LOCAL,actions=group:1
    ovs-ofctl add-flow br-phy in_port=pf,actions=LOCAL

    debug "OVS groups:"
    ovs-ofctl dump-groups br-phy --color
    debug "OVS flow rules:"
    ovs-ofctl dump-flows br-phy --color
}

function run() {
    config
    config_remote_tunnel vxlan
    add_openflow_rules

    verify_ping $REMOTE_IP ns0
    generate_traffic "remote" $LOCAL_IP
    ovs-appctl dpctl/dump-flows -m
}

run
start_clean_openvswitch
ip link del dummy
trap - EXIT
cleanup_test
test_done
