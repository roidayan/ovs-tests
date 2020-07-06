#!/bin/bash
#
# Testing hairpin by adding rules to TC
# Creating rule from P1 --> P2 and from P2 --> P1
# on the same NIC in legacy mode
#

my_dir="$(dirname "$0")"
. $my_dir/common.sh

function test_hairpin() {
    local nic=$1
    local nic2=$2

    reset_tc $nic

    title "Add hairpin rule $nic to $nic2"
    tc_filter_success add dev $nic protocol ip parent ffff: \
          prio 1 flower skip_sw ip_proto udp \
          action mirred egress redirect dev $nic2

    reset_tc $nic
}

start_check_syndrome

title "Test hairpin rules in legacy mode"
disable_sriov
enable_sriov

test_hairpin $NIC $NIC2
test_hairpin $NIC2 $NIC

config_sriov 0 $NIC2
check_syndrome
test_done
