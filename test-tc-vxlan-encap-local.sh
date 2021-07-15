#!/bin/bash
#
# Verify adding vxlan encap rule does not use local route which results in dst/src mac 0.
#
# Feature #2619265: [Alibaba-RoCE] local and remote VTEPs are in the same host for vxlan

my_dir="$(dirname "$0")"
. $my_dir/common.sh

config_sriov 2
enable_switchdev
unbind_vfs
bind_vfs

local_ip="39.0.10.60"
remote_ip="39.0.10.180"
dst_mac="e4:1d:2d:fd:8b:02"
dst_port=4789
id=98


function cleanup() {
    ip link del dev vxlan1 2> /dev/null
    ip n del ${remote_ip} dev $NIC 2>/dev/null
    ifconfig $NIC down
    ip addr flush dev $NIC
    reset_tc $NIC
}

function config_vxlan() {
    echo "config vxlan dev"
    ip link add vxlan1 type vxlan id $id dev $NIC dstport $dst_port
    ip link set vxlan1 up
    ifconfig $NIC $local_ip/24 up
}

function tc_filter_fail() {
    eval tc -s filter $@ && err "Expected to fail adding rule"
}

function add_vxlan_rule() {
    local local_ip="$1"
    local remote_ip="$2"
    local fail="$3"

    echo "local_ip $local_ip remote_ip $remote_ip"

    reset_tc $NIC $REP vxlan1

    # tunnel key set
    tc_filter_fail add dev $REP protocol arp parent ffff: prio 1 \
        flower dst_mac $dst_mac skip_sw \
        action tunnel_key set \
        id $id src_ip ${local_ip} dst_ip ${remote_ip} dst_port ${dst_port} \
        action mirred egress redirect dev vxlan1
}

function test_add_encap_rule_neigh_local() {
    ifconfig $NIC up
    local mac2=`cat /sys/class/net/$NIC2/address`
    ifconfig $NIC2 $remote_ip/24 up
    ip r show dev $NIC
    ip n show $remote_ip
    add_vxlan_rule $local_ip $remote_ip fail
    ifconfig $NIC2 0
    reset_tc $REP
}

function do_test() {
    title $1
    eval $1
}

cleanup
config_vxlan
do_test test_add_encap_rule_neigh_local

cleanup
test_done