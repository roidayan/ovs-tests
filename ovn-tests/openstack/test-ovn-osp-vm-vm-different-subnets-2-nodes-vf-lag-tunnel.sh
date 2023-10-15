#!/bin/bash
#
# Test traffic VM to VM on different subnet different nodes configured with OSP and OVN tunnel over VF LAG then verify traffic is offloaded
#

CONFIG_REMOTE=1
HAS_BOND=1

my_dir="$(dirname "$0")"
. $my_dir/common-ovn-osp-test.sh

require_interfaces NIC NIC2
require_remote_server

read_osp_topology_vm_vm_different_subnets
ovn_set_ips

function config_test() {
    ovn_start_northd_central $ovn_central_ip
    ovn_create_topology

    config_ovn_vf_lag $ovn_central_ip $ovn_controller_ip CLIENT_VF CLIENT_REP
    ovn_config_interface_namespace $CLIENT_VF $CLIENT_REP $CLIENT_NS $CLIENT_PORT $CLIENT_MAC $CLIENT_IPV4 $CLIENT_IPV6 $CLIENT_GATEWAY_IPV4 $CLIENT_GATEWAY_IPV6

    on_remote_exec "config_ovn_vf_lag $ovn_central_ip $ovn_remote_controller_ip SERVER_VF SERVER_REP
                    ovn_config_interface_namespace $SERVER_VF $SERVER_REP $SERVER_NS $SERVER_PORT $SERVER_MAC $SERVER_IPV4 $SERVER_IPV6 $SERVER_GATEWAY_IPV4 $SERVER_GATEWAY_IPV6"
}

function run_test() {
    ovs-vsctl show
    ovn-sbctl show

    WA_dpdk_initial_ping_and_flush

    run_remote_traffic "icmp6_is_not_offloaded"
}

ovn_clean_up
trap ovn_clean_up EXIT

config_test
run_test

trap - EXIT
ovn_clean_up

test_done
