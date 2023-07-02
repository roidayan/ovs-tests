#!/bin/bash

# This test will yield some OVS errors which are expected.
# This will test removal of an esw manager port while having offloads.
# We expect the members to get a "Resource temporarily unavailable" error
# and we expect to still be able to offload rules after re-attaching the PF.

my_dir="$(dirname "$0")"
. $my_dir/common-dpdk.sh

config_sriov 2
enable_switchdev
require_interfaces REP NIC
unbind_vfs
bind_vfs

trap cleanup EXIT

function cleanup() {
    cleanup_test
    ovs_conf_remove max-idle
}

function config() {
    cleanup_test
    debug "Restarting OVS"
    start_clean_openvswitch

    config_simple_bridge_with_rep 2
    config_ns ns0 $VF $LOCAL_IP
    config_ns ns1 $VF2 $REMOTE_IP
    ovs_conf_set max-idle 300000
}

function del_and_add_pf() {
    local pci=$(get_pf_pci)

    ovs_del_pf
    ovs_add_pf
}

function run() {
    config

    verify_ping $REMOTE_IP ns0 56 50

    validate_offload $LOCAL_IP

    del_and_add_pf

    sleep 3

    verify_ping $REMOTE_IP ns0 56 50

    validate_offload $LOCAL_IP
}

run
trap - EXIT
cleanup
test_done
