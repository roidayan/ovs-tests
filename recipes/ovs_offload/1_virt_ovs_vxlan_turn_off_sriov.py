from lnst.Controller.Task import ctl
from lnst.RecipeCommon.ModuleWrap import ping, ping6
from Testlib import Testlib
import logging

# ------
# SETUP
# ------

tl = Testlib(ctl)

# hosts
host1 = ctl.get_host("host1")
host2 = ctl.get_host("host2")

# guest machines
guest1 = ctl.get_host("guest1")

guest1.sync_resources(modules=["IcmpPing", "Icmp6Ping"])

# ------
# TESTS
# ------

ipv = ctl.get_alias("ipv")

g1_nic = guest1.get_interface("if1")
h2_nic = host2.get_interface("if1")

vxlan_port = ctl.get_alias("vxlan_port")
vxlan_dev = "vxlan_sys_%s" % vxlan_port


def  turn_off_sriov():
    nic = host1.get_interface("if1").get_devname()
    sriov = '/sys/class/net/%s/device/sriov_numvfs' % nic
    host1.run("echo 0 > %s" % sriov)


def do_test():
    ping_opts = {"count": 200}
    if ipv in ['ipv4', 'both']:
        ping_proc = ping((guest1, g1_nic, 0, {"scope": 0}),
                         (host2, h2_nic, 0, {"scope": 0}),
                         options=ping_opts, expect="pass", bg=True)
        ctl.wait(2)
        turn_off_sriov()
        ctl.wait(2)
        ping_proc.intr()
        verify_tc_rules('ipv4')

    if ipv in ['ipv6', 'both']:
        ping_proc = ping6((guest1, g1_nic, 1, {"scope": 0}),
                          (host2, h2_nic, 1, {"scope": 0}),
                          options=ping_opts, expect="pass", bg=True)
        ctl.wait(2)
        turn_off_sriov()
        ctl.wait(2)
        ping_proc.intr()
        verify_tc_rules('ipv6')


def verify_tc_rules(proto):
    g1_mac = g1_nic.get_hwaddr()
    h2_mac = h2_nic.get_hwaddr()

    # encap rule
    m = tl.find_tc_rule(host1, 'tap1', g1_mac, h2_mac, proto, 'tunnel_key set')
    desc = "TC rule %s tunnel_key set" % proto
    if m:
        tl.custom(host1, desc)
    else:
        tl.custom(host1, desc, 'ERROR: cannot find tc rule')

    # decap rule
    m = tl.find_tc_rule(host1, vxlan_dev, h2_mac, g1_mac, proto, 'tunnel_key unset')
    desc = "TC rule %s tunnel_key unset" % proto
    if m:
        tl.custom(host1, desc)
    else:
        tl.custom(host1, desc, 'ERROR: cannot find tc rule')


do_test()
