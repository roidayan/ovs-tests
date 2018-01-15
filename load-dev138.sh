#!/bin/sh


#81:00.0 Ethernet controller: Mellanox Technologies MT27710 Family [ConnectX-4 Lx]
#81:00.1 Ethernet controller: Mellanox Technologies MT27710 Family [ConnectX-4 Lx]
#82:00.0 Ethernet controller: Mellanox Technologies MT28800 Family [ConnectX-5 Ex]
#82:00.1 Ethernet controller: Mellanox Technologies MT28800 Family [ConnectX-5 Ex]

#lrwxrwxrwx 1 root root 0 Mar  7 09:05 ens1f0 -> ../../devices/pci0000:80/0000:80:02.0/0000:82:00.0/net/ens1f0
#lrwxrwxrwx 1 root root 0 Mar  7 09:05 ens1f1 -> ../../devices/pci0000:80/0000:80:02.0/0000:82:00.1/net/ens1f1
#lrwxrwxrwx 1 root root 0 Mar  7 09:05 ens2f0 -> ../../devices/pci0000:80/0000:80:01.0/0000:81:00.0/net/ens2f0
#lrwxrwxrwx 1 root root 0 Mar  7 09:05 ens2f1 -> ../../devices/pci0000:80/0000:80:01.0/0000:81:00.1/net/ens2f1

CX4=ens2f0
CX4_2=ens2f0
CX5=ens1f0
CX5_2=ens1f1

nic=${1:-$CX4}
nic2=${2:-$CX4_2}
vfs=2
vms=`seq 5 6`
hv=`hostname -s`

##############################################################################

function set_inline_mode() {
    local mode="$1"
    local pci=$(basename `readlink /sys/class/net/$nic/device`)
    if [ "$nic" == "$CX4" ]; then
        devlink dev eswitch set pci/$pci inline-mode $mode
    fi
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
    for i in $vms; do virsh -q start ${hv}-00${i}-Fedora-24 ; done
}

function del_ovs_bridges() {
    ovs-vsctl show | grep Bridge | awk {'print $2'} | xargs -I {} ovs-vsctl del-br {}
}

function clean() {
    echo "Cleanup"
    stop_vms
    del_ovs_bridges
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
set_inline_mode transport

if [ "$WITH_VMS" == "1" ]; then
    start_vms
fi
