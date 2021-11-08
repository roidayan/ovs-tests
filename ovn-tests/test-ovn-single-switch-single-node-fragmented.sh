#!/bin/bash
#
# Test fragmented traffic between VFs configured with OVN and OVS then check traffic is not offloaded
#

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
    # Add REP to OVS
    ovs_add_port_to_switch $OVN_BRIDGE_INT $REP
    ovs_add_port_to_switch $OVN_BRIDGE_INT $REP2

    ovs-vsctl show

    # Bind OVS ports to OVN
    ovn_bind_ovs_port $REP $PORT1
    ovn_bind_ovs_port $REP2 $PORT2

    ovn-sbctl show

    # Move VFs to namespaces and set MACs and IPS
    config_vf ns0 $VF $REP $IP1 $MAC1
    ip netns exec ns0 ip -6 addr add $IP_V6_1/124 dev $VF
    config_vf ns1 $VF2 $REP2 $IP2 $MAC2
    ip netns exec ns1 ip -6 addr add $IP_V6_2/124 dev $VF2

    title "Test ICMP traffic between $VF($IP1) -> $VF2($IP2)"
    check_fragmented_ipv4_traffic $REP ns0 $IP2 1500

    title "Test ICMP6 traffic between $VF($IP_V6_1) -> $VF2($IP_V6_2)"
    check_fragmented_ipv6_traffic $REP ns0 $IP_V6_2 1500
}

IS_FRAGMENTED=1

ovn_clean_up

# trap for existing script to clean up
trap ovn_clean_up EXIT

ovn_config
run_test


# Clean up and clear trap
ovn_clean_up
trap - EXIT

test_done
