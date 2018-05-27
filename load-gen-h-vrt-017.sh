#!/bin/bash

CX4=p1p1
CX4_2=p1p2

CX5=p1p1
CX5_2=p1p2

if [ "$1" == "cx5" ]; then
    nic=$CX5
    nic2=$CX5_2
else
    nic=$CX4
    nic2=$CX4_2
fi

vfs=2
vms="gen-h-vrt-017-005 gen-h-vrt-017-006"

##############################################################################

function set_modes() {
    local pci=$(basename `readlink /sys/class/net/$nic/device`)
    devlink dev eswitch set pci/$pci inline-mode transport
#    devlink dev eswitch set pci/$pci encap yes
}

function reset_tc_nic() {
    local nic1="$1"

    echo "reset tc for $nic1"

    # reset ingress
    tc qdisc del dev $nic1 ingress >/dev/null 2>&1

    # add ingress
    tc qdisc add dev $nic1 ingress

    # activate hw offload
    ethtool -K $nic1 hw-tc-offload on
}

function reset_tc() {
#		tc filter del dev $nic1 parent ffff:
    for n in $nic $nic2 ; do
        for p in `ls -1d /sys/class/net/$n*`; do
            nic1=`basename $p`
            reset_tc_nic $nic1
        done
    done
}

function stop_sriov() {
    local sriov

    for n in $nic $nic2 ; do
        sriov=/sys/class/net/$n/device/sriov_numvfs
        /labhome/roid/scripts/ovs/devlink-mode.sh $n legacy
        if [ -e $sriov ]; then
            echo 0 > $sriov
        fi
    done
}

function unbind() {
    echo "Unbind VFs"
    for n in $nic $nic2 ; do
        for i in `ls -1d  /sys/class/net/$n/device/virtfn*`; do
            pci=$(basename `readlink $i`)
            echo "unbind $pci"
            echo $pci > /sys/bus/pci/drivers/mlx5_core/unbind
        done
    done
}

function stop_vms() {
    echo "Stop vms"
    for i in `virsh list --name` ; do virsh -q destroy $i ; done
}

function start_vms() {
    echo "Start vms"
    for i in $vms; do virsh -q start $i-RH-7.5 ; done
}

function wait_vms() {
    echo "Wait vms"
    for i in $vms; do
        wait_vm $i
        break; # waiting for the first one
    done
}

function wait_vm() {
    local vm=$1

    for i in 1 2 3 4; do
        ping -q -w 1 -c 1 $vm && break
        sleep 15
    done

    sleep 10 ; # wait little more for lnst to be up
}

function del_ovs_bridges() {
    ovs-vsctl list-br | xargs -r -l ovs-vsctl del-br
}

function reset_ovs() {
    service openvswitch-switch restart
    del_ovs_bridges
    ovs-vsctl set Open_vSwitch . other_config:hw-offload=true
    service openvswitch-switch restart
}

function clean() {
    echo "Cleanup"
    stop_vms
    reset_ovs
    reset_tc
    stop_sriov
}

function warn_extra() {
    local m="$1"
    local path=`modinfo $m | grep ^filename`
    if echo $path | grep -q extra ; then
        echo "*** WARNING *** $m -> $path"
    fi
}

function reload_modules() {
    echo "Reload modules"
    set -e
    local modules="mlx5_ib mlx5_core devlink cls_flower"
    for m in $modules ; do
        warn_extra $m
    done
    modprobe -r $modules ; modprobe -a $modules
    set +e
}

function nic_up() {
    echo "Nic up"
    for n in $nic $nic2 ; do
        for p in `ls -1d /sys/class/net/$n*`; do
            nic1=`basename $p`
            ifconfig $nic1 up
        done
    done
}


echo "********** LOAD `basename $0` **************" > /dev/kmsg

clean
if [ "$FAST" == "" ]; then
    reload_modules
fi

echo "Enable $vfs VFs"
/labhome/roid/scripts/ovs/set-macs.sh $nic $vfs
if [ "$NICS" == "2" ]; then
    /labhome/roid/scripts/ovs/set-macs.sh $nic2 $vfs
fi

test -e /sys/class/net/$nic/device/virtfn0 && nosriov=0 || nosriov=1
if [ "$nosriov" == 1 ]; then
    echo "Missing sriov interfaces"
    exit 1
fi

nic_up
sleep 1
reset_tc

echo "Change mode to switchdev"
unbind
/labhome/roid/scripts/ovs/devlink-mode.sh $nic switchdev
if [ "$NICS" == "2" ]; then
    /labhome/roid/scripts/ovs/devlink-mode.sh $nic2 switchdev
fi
sleep 2
nic_up
reset_tc
set_modes

if [ "$WITH_VMS" == "1" ]; then
    start_vms
    wait_vms
fi
