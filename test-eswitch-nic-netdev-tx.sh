#!/bin/bash
#
# Test nic tx works when switchdev mode in nic_netdev mode
# We got into an issue where we need to down/up the nic for it to work again.
#

my_dir="$(dirname "$0")"
. $my_dir/common.sh


config_sriov 0
config_sriov 2
set_uplink_rep_mode_nic_netdev
fail_if_err

title "Toggle switchdev for $NIC"
ifconfig $NIC 1.1.1.1/24 up
enable_switchdev

title "Verify traffic with TX counter"
count1=`get_tx_pkts $NIC`
ping -c 10 -i 0.1 -w 3 -q 1.1.1.2 &>/dev/null
count2=`get_tx_pkts $NIC`
((diff=count2-count1))
if [ "$diff" -lt 10 ]; then
    err "Nic $NIC tx is not increasing (diff: $diff)"
fi

enable_legacy
ifconfig $NIC 0
config_sriov 0
config_sriov 2
set_uplink_rep_mode_new_netdev
config_sriov 0
test_done
