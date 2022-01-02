#!/bin/bash
#
# Test fragmented traffic between VFs configured with OVN and OVS then check traffic is not offloaded
#

IS_FRAGMENTED=1

my_dir="$(dirname "$0")"
. $my_dir/common-ovn-test-utils.sh

TOPOLOGY=$TOPOLOGY_SINGLE_SWITCH
SWITCH=$(ovn_get_switch_name_with_vif_port $TOPOLOGY)

PORT1=$(ovn_get_switch_vif_port_name $TOPOLOGY $SWITCH 0)
MAC1=$(ovn_get_switch_port_mac $TOPOLOGY $SWITCH $PORT1)
IP1=$(ovn_get_switch_port_ip $TOPOLOGY $SWITCH $PORT1)
IP_V6_1=$(ovn_get_switch_port_ipv6 $TOPOLOGY $SWITCH $PORT1)

PORT2=$(ovn_get_switch_vif_port_name $TOPOLOGY $SWITCH 1)
MAC2=$(ovn_get_switch_port_mac $TOPOLOGY $SWITCH $PORT2)
IP2=$(ovn_get_switch_port_ip $TOPOLOGY $SWITCH $PORT2)
IP_V6_2=$(ovn_get_switch_port_ipv6 $TOPOLOGY $SWITCH $PORT2)

function run_test() {
    ovn_config_interface_namespace $VF $REP ns0 $PORT1 $MAC1 $IP1 $IP_V6_1
    ovn_config_interface_namespace $VF2 $REP2 ns1 $PORT2 $MAC2 $IP2 $IP_V6_2

    ovs-vsctl show
    ovn-sbctl show

    title "Test ICMP traffic between $VF($IP1) -> $VF2($IP2)"
    check_fragmented_ipv4_traffic $REP ns0 $IP2 1500

    title "Test ICMP6 traffic between $VF($IP_V6_1) -> $VF2($IP_V6_2)"
    check_fragmented_ipv6_traffic $REP ns0 $IP_V6_2 1500
}

ovn_execute_test
