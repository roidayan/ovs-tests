#!/bin/bash
#
# Test CT-CT NAT optimization
#
# Feature Request #3169344: [ASAP^2][upstream gap] CT-CT NAT optimization
#
# IGNORE_FROM_TEST_ALL

my_dir="$(dirname "$0")"
. $my_dir/common.sh
. $my_dir/common-ovs-ct.sh
pktgen="$DIR/network-testing/pktgen/pktgen_sample04_many_flows.sh"

require_module act_ct pktgen

IP1="7.7.7.1"
IP2="7.7.7.2"
IP2_FAKE="7.7.7.3"

mac2=""
function set_ct_action_on_nat_conns() {
    local value=$1

    config_sriov 0
    devlink dev param set pci/$PCI name ct_action_on_nat_conns value $value cmode driverinit
    devlink dev reload pci/$PCI
    config_sriov 2
    enable_switchdev
    require_interfaces REP REP2
    unbind_vfs
    bind_vfs
    mac2=`cat /sys/class/net/$VF2/address`
}

pid_pktgen=""
function kill_pktgen() {
    test $pid_pktgen || return
    [ -e /proc/$pid_pktgen ] || return
    kill $pid_pktgen
    wait $pid_pktgen 2>/dev/null
    pid_pktgen=""
}

pid_testpmd=""
function kill_testpmd() {
    test $pid_testpmd || return
    [ -e /proc/$pid_testpmd ] || return
    kill $pid_testpmd
    wait $pid_testpmd 2>/dev/null
    pid_testpmd=""
}

function cleanup() {
    kill_testpmd
    kill_pktgen
    conntrack -F

    ip netns del ns0 2> /dev/null
    ip netns del ns1 2> /dev/null
    reset_tc $REP
    reset_tc $REP2
}
trap cleanup EXIT

function run_pktgen() {
    echo "run traffic"
    ip netns exec ns0 timeout --kill-after 1 $t $pktgen -i $VF -t 1 -d $IP2_FAKE -m $mac2 &
    pid_pktgen=$!
    sleep 4
    if [ ! -e /proc/$pid_pktgen ]; then
        pid_pktgen=""
        err "pktgen failed"
        return 1
    fi
    return 0
}

function run_testpmd() {
    echo "run fwder"
    ip link set dev $NIC up
    echo 2048 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
    timeout --kill-after=10 $t ip netns exec ns1 sh -c "tail -f /dev/null | $testpmd --no-pci --vdev=eth_af_packet0,iface=$VF2 -- --forward-mode=5tswap -a --total-num-mbufs=4096" &
    pid_testpmd=$!
    sleep 8
    if [ ! -e /proc/$pid_testpmd ]; then
        pid_testpmd=""
        err "testpmd failed"
        return 1
    fi
    return 0
}

function config_ovs() {
    echo "setup ovs"
    start_clean_openvswitch

    ovs-vsctl add-br br-ovs
    ovs-vsctl add-port br-ovs $REP
    ovs-vsctl add-port br-ovs $REP2
}

function reconfig_flows() {
    ovs-ofctl del-flows br-ovs
    ovs-ofctl add-flow br-ovs arp,actions=normal
    ovs-ofctl add-flow br-ovs "table=0, ip,ct_state=-trk actions=ct(zone=12,table=1,nat)"
    ovs-ofctl add-flow br-ovs "table=1, ip,ct_state=+trk+new actions=ct(zone=12,commit,nat(dst=$IP2)),normal"
    ovs-ofctl add-flow br-ovs "table=1, ip,ct_state=+trk+est,ct_zone=12 actions=normal"
}

used=0
function run() {
    title "Test OVS CT TCP"

    config_vf ns0 $VF $REP $IP1
    config_vf ns1 $VF2 $REP2 $IP2
    config_ovs
    reconfig_flows
    ovs-ofctl dump-flows br-ovs --color

    echo "prepare for offload"
    sysctl -w 'net.netfilter.nf_conntrack_max=524288'

    echo "add zone 12 rule for priming offload callbacks"
    tc_filter add dev $REP prio 1337 proto ip chain 1337 ingress flower \
        skip_sw ct_state -trk action ct zone 12 pipe \
        action mirred egress redirect dev $REP2

    echo "sleep 3 sec, fg now"
    sleep 3

    t=50
    echo "running for $t seconds"
    used_before=$(free | awk '/Mem/{print $3}')
    run_testpmd || return
    run_pktgen || return

    sleep $((t-10))
    verify_ct_hw_counter 120000
    used_after=$(free | awk '/Mem/{print $3}')
    sleep 20

    log "flush"
    kill_pktgen
    kill_testpmd
    ovs-vsctl del-br br-ovs

    used=$((used_after - used_before))
}

# warnup run
set_ct_action_on_nat_conns true
cleanup
run

cleanup
run
used_true=$used
echo "With set_ct_action_on_nat_conns=true, used memory $used_true"

set_ct_action_on_nat_conns false
cleanup
run
used_false=$used
echo "With set_ct_action_on_nat_conns=false, used memory $used_false"

ratio=$(echo "scale=2;($used_true-$used_false)/$used_true*100" | bc)

if [ `echo "$ratio > 30" | bc` -eq 1 ]; then
    success "saved memory ratio: $ratio"
else
    fail "saved memory ratio: $ratio (<%30)"
fi

cleanup
trap - EXIT
test_done
