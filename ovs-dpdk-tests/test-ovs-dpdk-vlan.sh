#!/bin/bash
#
# Test OVS with vlan traffic
#
# Require external server
#

my_dir="$(dirname "$0")"
. $my_dir/common-dpdk.sh

require_remote_server

vlan=5
vlan_dev=${REMOTE_NIC}.$vlan

config_sriov 2
enable_switchdev
require_interfaces REP NIC
unbind_vfs
bind_vfs

trap 'cleanup_test $vlan_dev' EXIT

function config() {
    debug "Restarting OVS"
    start_clean_openvswitch

    config_simple_bridge_with_rep 1
    start_vdpa_vm
    ovs-vsctl set port $REP tag=$vlan
    config_ns ns0 $VF $LOCAL_IP
}

cleanup_test $vlan_dev
config
config_remote_vlan $vlan $vlan_dev

title "Testing traffic before removing and adding the vlan tag"
verify_ping $REMOTE_IP
generate_traffic "remote" $LOCAL_IP

debug "Removing the vlan tag, purging the rules and re-adding the tag"
ovs-vsctl remove port $REP tag $vlan
ovs-appctl revalidator/purge
ovs-vsctl set port $REP tag=$vlan

title "Testing traffic after removing and adding the vlan tag"
verify_ping $REMOTE_IP
generate_traffic "remote" $LOCAL_IP

start_clean_openvswitch
test_done
