#!/bin/bash
#
# Test PCI reset while in nic mode and config sriov
# reload modules again, seems there was a bug unloading modules got stuck.
#

my_dir="$(dirname "$0")"
. $my_dir/common.sh


config_sriov 0
echo 1 > /sys/bus/pci/devices/$PCI/reset
sleep 10 # wait for the reset
config_sriov
reload_modules
check_kasan
test_done