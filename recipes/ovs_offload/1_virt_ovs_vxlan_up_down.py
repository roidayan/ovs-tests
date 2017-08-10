"""
This test verifies proper handling of up/down events on bridge device.
Test generates traffic from guest using ping and checks that no errors
reported on dmesg after each up/down event.
Created for fix of issue 1048140.
"""

from lnst.Controller.Task import ctl
from lnst.RecipeCommon.ModuleWrap import ping
from Testlib import Testlib
from time import time


# ------
# SETUP
# ------

tl = Testlib(ctl)

# hosts
host1 = ctl.get_host("h1")
host2 = ctl.get_host("h2")

# guest machines
guest1 = ctl.get_host("test_host1")

guest1.sync_resources(modules=["IcmpPing"])

# ------
# TESTS
# ------

g1_nic = guest1.get_interface("if1")
h2_nic = host2.get_device("int0")

bridge_dev = host1.get_interface("br-pys")
total_time_sec = 60


def start_pings(seconds):
    ping_opts = {"count": seconds, "interval": 1.0, "limit_rate": 40}
    return ping((guest1, g1_nic, 0, {"scope": 0}),
                (host2, h2_nic, 0, {"scope": 0}),
                options=ping_opts, expect="pass", bg=True)


def check_dmesg():
    desc = "check for syndrome"
    sec = int(time() - start_of_test)
    cmd = host1.run("journalctl --since '%s seconds ago' | grep syndrome || true" % sec)
    if cmd.out():
        tl.custom(host1, desc, 'ERROR: %s' % cmd.out())
        return False
    else:
        tl.custom(host1, desc)
        return True


def do_iface_up_down(seconds, sleep_time):
    while check_dmesg() and seconds >= sleep_time * 2:
        bridge_dev.set_link_down()
        ctl.wait(sleep_time)
        bridge_dev.set_link_up()
        ctl.wait(sleep_time)
        seconds -= sleep_time * 2


host1.run("which journalctl")
ctl.wait(1)
start_of_test = time()

ping_proc = start_pings(total_time_sec)
do_iface_up_down(total_time_sec, 10)
ping_proc.kill()
