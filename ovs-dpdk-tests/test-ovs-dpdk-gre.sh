#!/bin/bash
#
# Test OVS-DPDK with gre traffic
#
# Require external server
#

my_dir="$(dirname "$0")"
. $my_dir/common-dpdk.sh

trap cleanup_test EXIT

require_remote_server

gre_set_entropy

config_sriov 2
enable_switchdev
bind_vfs

cleanup_test

config_tunnel gre
config_local_tunnel_ip $LOCAL_TUN_IP br-phy
config_remote_tunnel gre
start_vdpa_vm1

verify_ping
generate_traffic "remote" $LOCAL_IP

trap - EXIT
cleanup_test
test_done
