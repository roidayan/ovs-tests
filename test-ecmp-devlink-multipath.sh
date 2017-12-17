#!/bin/bash
#
#  desc: TODO
#
#  test: TODO
#

NIC=${1:-ens5f0}

my_dir="$(dirname "$0")"
. $my_dir/common.sh

reset_tc_nic $NIC
rep=${NIC}_0
if [ -e /sys/class/net/$rep ]; then
    reset_tc_nic $rep
fi

function disable_sriov() {
    title "- Disable SRIOV"
    echo 0 > /sys/class/net/$NIC/device/sriov_numvfs
    echo 0 > /sys/class/net/$NIC2/device/sriov_numvfs
}

function enable_sriov() {
    title "- Enable SRIOV"
    echo 2 > /sys/class/net/$NIC/device/sriov_numvfs
    echo 2 > /sys/class/net/$NIC2/device/sriov_numvfs
}

function enable_disable_multipath() {
    disable_sriov

    title "- Enable multipath"
    disable_multipath
    enable_multipath || err "Failed to enable multipath"

    enable_sriov

    title "- show devlink shows multipath enabled"
    mode=`get_multipath_mode`
    if [ -z "$mode" ]; then
        mode='X'
    fi
    test $mode = "enable" || err "Expected multipath mode enabled but got $mode"

    disable_sriov

    title "- Disable multipath"
    disable_multipath || err "Failed to disable multipath"
}


function fail_to_disable_in_sriov() {
    disable_sriov

    title "- Enable multipath"
    disable_multipath
    enable_multipath || err "Failed to enable multipath"

    enable_sriov

    title "- Verify cannot disable multipath while in SRIOV"
    disable_multipath 2>/dev/null && err "Disabled multipath while in SRIOV" || true
}

function fail_to_enable_in_sriov() {
    disable_sriov

    title "- Disable multipath"
    disable_multipath

    title "- Enable SRIOV"
    echo 2 > /sys/class/net/$NIC/device/sriov_numvfs

    title "- Verify cannot enable multipath while in SRIOV"
    enable_multipath 2>/dev/null && err "Enabled multipath while in SRIOV" || true
}

function change_pf0_to_switchdev_and_back_to_legacy_with_multipath() {
    disable_sriov

    title "- Enable multipath"
    disable_multipath
    enable_multipath || err "Failed to enable multipath"

    title "- Enable SRIOV and switchdev"
    echo 2 > /sys/class/net/$NIC/device/sriov_numvfs
    enable_switchdev

    title "- Disable SRIOV"
    echo 0 > /sys/class/net/$NIC/device/sriov_numvfs

    title "- Disable multipath"
    disable_multipath || err "Failed to disable multipath"
}

function change_both_ports_to_switchdev_and_back_to_legacy_with_multipath() {
    disable_sriov

    title "- Enable multipath"
    disable_multipath
    enable_multipath || err "Failed to enable multipath"

    title "- Enable SRIOV and switchdev"
    enable_sriov
    enable_switchdev $NIC
    enable_switchdev $NIC2

    disable_sriov

    title "- Disable multipath"
    disable_multipath || err "Failed to disable multipath"

    # leave where NIC is in sriov
    echo 2 > /sys/class/net/$NIC/device/sriov_numvfs
}

function multipath_ready_and_change_pf0_switchdev_legacy() {
    disable_sriov

    title "- Enable multipath"
    disable_multipath
    enable_multipath || err "Failed to enable multipath"

    title "- Enable SRIOV and switchdev"
    enable_sriov
    enable_switchdev $NIC
    enable_switchdev $NIC2

    disable_sriov

    title "- Enable SRIOV and switchdev"
    echo 2 > /sys/class/net/$NIC/device/sriov_numvfs
    enable_switchdev

    title "- Disable SRIOV"
    echo 0 > /sys/class/net/$NIC/device/sriov_numvfs

    title "- Disable multipath"
    disable_multipath || err "Failed to disable multipath"

    # leave where NIC is in sriov
    echo 2 > /sys/class/net/$NIC/device/sriov_numvfs
}

function do_test() {
    title $1
    eval $1 && success
}


do_test enable_disable_multipath
do_test fail_to_disable_in_sriov
do_test fail_to_enable_in_sriov
do_test change_pf0_to_switchdev_and_back_to_legacy_with_multipath
do_test change_both_ports_to_switchdev_and_back_to_legacy_with_multipath
do_test multipath_ready_and_change_pf0_switchdev_legacy

test_done
