#! /bin/bash


# find the vitio netdevice associated with a vdpa device
# @1 - the vdpa device name
# return: the netdevice or epmty string if not found
function vdpa_find_netdev
{
    local ndevs=$(ls /sys/class/net/ 2>/dev/null)

    for nd in $ndevs; do
        if ethtool -i $nd | grep "bus-info: $1" > /dev/null; then
            echo $nd
            return
        fi
    done
}

function vdpa_wait_mgtdev
{
    local mgtdev=$1
    local i

    for (( i = 0 ; i < 5 ; i++ )); do
        if vdpa mgmtdev show | grep $mgtdev > /dev/null 2>&1 ; then
            return
        fi
        sleep 1
    done
    fail "$mgtdev not seen on management bus"
}

