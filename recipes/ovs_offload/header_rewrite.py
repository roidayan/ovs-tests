from lnst.Controller.Task import ctl
from Testlib import Testlib

# ------
# SETUP
# ------

tl = Testlib(ctl)

# ------
# TESTS
# ------

hv = ctl.get_host("host1")
test_with_veth = ctl.get_alias("test_with_veth")


if test_with_veth == 'yes':
    g1 = hv
    g2 = hv
    nic1 = hv.get_interface("vm1")
    nic2 = hv.get_interface("vm2")
else:
    g1 = ctl.get_host("guest1")
    g2 = ctl.get_host("guest2")
    nic1 = g1.get_interface("if1")
    nic2 = g2.get_interface("if2")


g1.sync_resources(modules=["IcmpPing", "Icmp6Ping", "Iperf"])
if g1 != g2:
    g2.sync_resources(modules=["Iperf"])

nic1_mac = nic1.get_hwaddr()
nic2_mac = nic2.get_hwaddr()
ovs = hv.get_interface("ovs1")
ovs_br_name = ovs.get_devname()

ping_count = 30
ping_interval = 0.2
ping_timeout = 10


def ping(nic, options={}):
    options = dict(options)
    options.update({
       "count": ping_count,
       "interval": ping_interval
    })
    ping_mod = ctl.get_module("IcmpPing", options=options)
    nic.get_host().run(ping_mod, timeout=ping_timeout, netns=nic.get_netns())


def ofctl_add_flow(flow):
    hv.run("ovs-ofctl add-flow %s '%s'" % (ovs_br_name, flow))


def report_test_result(desc, m):
    if m:
        tl.custom(hv, desc, opts=m)
    else:
        tl.custom(hv, desc, 'ERROR: cannot find OVS rule')


def prepare_for_test():
    # initial cleanup
    hv.run("ovs-ofctl del-flows %s" % ovs_br_name)

    # to force matching on dst mac
    ofctl_add_flow("priority=999, dl_dst=aa:aa:bb:bb:cc:cc actions=drop")

    # arp responder for mac mod
    # TODO: use static arp?
    ofctl_add_flow("priority=10, arp, nw_dst=8.9.10.11, nw_src=8.9.10.01, actions=load:0x2->NXM_OF_ARP_OP[], move:NXM_OF_ETH_SRC[]->NXM_OF_ETH_DST[], mod_dl_src:aa:bb:cc:dd:ee:99, move:NXM_NX_ARP_SHA[]->NXM_NX_ARP_THA[], move:NXM_OF_ARP_SPA[]->NXM_OF_ARP_TPA[], load:0xaabbccddee99->NXM_NX_ARP_SHA[], load:0x08090a0b->NXM_OF_ARP_SPA[], in_port")
    ofctl_add_flow("priority=10, arp, nw_dst=8.9.10.01, nw_src=8.9.10.11, actions=load:0x2->NXM_OF_ARP_OP[], move:NXM_OF_ETH_SRC[]->NXM_OF_ETH_DST[], mod_dl_src:aa:bb:cc:dd:ee:99, move:NXM_NX_ARP_SHA[]->NXM_NX_ARP_THA[], move:NXM_OF_ARP_SPA[]->NXM_OF_ARP_TPA[], load:0xaabbccddee99->NXM_NX_ARP_SHA[], load:0x08090a01->NXM_OF_ARP_SPA[], in_port")

    # neighbor for ipv4 mod
    nic1.get_host().run("ip -4 n replace %s dev %s lladdr %s" % ("8.9.10.55", nic1.get_devname(), nic2_mac), netns=nic1.get_netns())
    nic2.get_host().run("ip -4 n replace %s dev %s lladdr %s" % (nic1.get_ip(2), nic2.get_devname(), nic1_mac), netns=nic2.get_netns())

    # neighbor for ipv6 mod
    nic1.get_host().run("ip -6 n replace %s dev %s lladdr %s" % ("2002:0db8:0:f101::55", nic1.get_devname(), nic2_mac), netns=nic1.get_netns())
    nic2.get_host().run("ip -6 n replace %s dev %s lladdr %s" % (nic1.get_ip(4), nic2.get_devname(), nic1_mac), netns=nic2.get_netns())

    # icmp + mod mac
    ofctl_add_flow("priority=2, in_port=11, dl_dst=aa:bb:cc:dd:ee:99, ip, icmp, nw_dst=8.9.10.01, actions=mod_dl_src:aa:bb:cc:dd:ee:99, mod_dl_dst:%s, output:1" % nic1_mac)
    ofctl_add_flow("priority=2, in_port=1, dl_dst=aa:bb:cc:dd:ee:99, ip, icmp, nw_dst=8.9.10.11, actions=mod_dl_src:aa:bb:cc:dd:ee:99, mod_dl_dst:%s, output:11" % nic2_mac)

    # tcp + mod ipv4
    ofctl_add_flow("priority=2, in_port=1, tcp, nw_dst=8.9.10.55, actions=mod_nw_dst:8.9.10.13, output:11")
    ofctl_add_flow("priority=2, in_port=11, tcp, nw_src=8.9.10.13, actions=mod_nw_src:8.9.10.55, output:1")

    # tcp + mod tcp ports
    ofctl_add_flow("priority=2, in_port=11, ip, tcp, nw_dst=8.9.10.02, tp_dst=5050, actions=mod_tp_dst=5051, output:1")
    ofctl_add_flow("priority=2, in_port=1, ip, tcp, nw_dst=8.9.10.12, tp_src=5051, actions=mod_tp_src=5050, output:11")

    # udp + mod udp ports
    ofctl_add_flow("priority=2, in_port=11, ip, udp, nw_dst=8.9.10.02, tp_dst=4050, actions=mod_tp_dst=4051, output:1")
    ofctl_add_flow("priority=2, in_port=1, ip, udp, nw_dst=8.9.10.12, tp_src=4051, actions=mod_tp_src=4050, output:11")

    # icmp6 + mod ipv6
    ofctl_add_flow("priority=2, in_port=1, ip6, icmp6, ipv6_dst=2002:0db8:0:f101::55, actions=set_field:2002:0db8:0:f101::2->ipv6_dst, output:11")
    ofctl_add_flow("priority=2, in_port=11, ip6, icmp6, ipv6_dst=2002:0db8:0:f101::1, actions=set_field:2002:0db8:0:f101::55->ipv6_src, output:1")

    # tcp + mod ttl
    ofctl_add_flow("priority=2, in_port=11, ip, tcp, nw_dst=8.9.10.4, actions=dec_ttl, output:1")
    ofctl_add_flow("priority=2, in_port=1, ip, tcp, nw_dst=8.9.10.14, actions=dec_ttl, output:11")


    # everything else
    ofctl_add_flow("priority=1, actions=normal")
    #ofctl_add_flow("priority=1, ip, actions=normal")
    #ofctl_add_flow("priority=1, arp, actions=normal")


class IperfTest:
    def __init__(self, ctl):
        self._ctl = ctl

    def _get_iperf_srv_mod(self, iperf_opts):
        modules_options = {
            "role": "server",
            "iperf_opts": iperf_opts,
        }
        return self._ctl.get_module("Iperf", options=modules_options)

    def _get_iperf_cli_mod(self, server, duration, iperf_opts):
        modules_options = {
            "role": "client",
            "iperf_server": server,
            "duration": duration,
            "iperf_opts": iperf_opts,
        }
        return self._ctl.get_module("Iperf", options=modules_options)

    def iperf(self, cli_if, srv_if, duration, desc, iperf_server='', iperf_client_opts='', iperf_server_opts=''):
        if not iperf_server:
            iperf_server = srv_if.get_ip(0)

        srv_m = self._get_iperf_srv_mod(iperf_server_opts)
        cli_m = self._get_iperf_cli_mod(iperf_server, duration, iperf_client_opts)

        cli_host = cli_if.get_host()
        srv_host = srv_if.get_host()

        srv_proc = srv_host.run(srv_m, bg=True, netns=srv_if.get_netns())
        self._ctl.wait(2)
        cli_host.run(cli_m, timeout=duration + 15, desc=desc, netns=cli_if.get_netns())
        srv_proc.intr()


#TODO make var for fake_ip
def test_rewrite_ipv4():
    # TODO server needs bind to ip?
    iperf.iperf(nic1, nic2, 3, 'vm1->vm2', '8.9.10.55', '-B %s' % nic1.get_ip(2), '-B %s' % nic2.get_ip(2))
    m = tl.find_ovs_rule(hv, '2', '.*', '0x0800', 'set\(ipv4\(.*dst=8.9.10.13\)\),3')
    report_test_result("OVS rule: rewrite ipv4 dst (vm1->vm2)", m)
    m = tl.find_ovs_rule(hv, '3', '.*', '0x0800', 'set\(ipv4\(.*dst=8.9.10.3\)\),2')
    report_test_result("OVS rule: rewrite ipv4 dst (vm2->vm1)", m)


def test_rewrite_mac():
    ping(nic1, { "addr": nic2.get_ip(0) })
    m = tl.find_ovs_rule(hv, '2', 'aa:bb:cc:dd:ee:99', '0x0800', 'set\(eth\(src=aa:bb:cc:dd:ee:99,dst=%s\)\),3' % str(nic2_mac).lower())
    report_test_result("OVS rule: rewrite macs (vm1->vm2)", m)
    m = tl.find_ovs_rule(hv, '3', 'aa:bb:cc:dd:ee:99', '0x0800', 'set\(eth\(src=aa:bb:cc:dd:ee:99,dst=%s\)\),2' % str(nic1_mac).lower())
    report_test_result("OVS rule: rewrite macs (vm2->vm1)", m)


def test_rewrite_tcp_ports():
    # TODO server bind ip needed?
    iperf.iperf(nic2, nic1, 3, 'vm1->vm2', nic1.get_ip(1), '-p 5050 -B %s' % nic2.get_ip(1), '-p 5051 -B %s' % nic1.get_ip(1))
    m = tl.find_ovs_rule(hv, '2', '.*', '0x0800', 'set\(tcp\(src=5050\)\),3')
    report_test_result("OVS rule: rewrite tcp src (vm1->vm2)", m)
    m = tl.find_ovs_rule(hv, '3', '.*', '0x0800', 'set\(tcp\(dst=5051\)\),2')
    report_test_result("OVS rule: rewrite tcp dst (vm2->vm1)", m)


def test_rewrite_udp_ports():
    # TODO server bind ip needed?
    iperf.iperf(nic2, nic1, 3, 'vm1->vm2', nic1.get_ip(1), '-p 4050 -u -B %s' % nic2.get_ip(1), '-p 4051 -u -B %s' % nic1.get_ip(1))
    m = tl.find_ovs_rule(hv, '2', '.*', '0x0800', 'set\(udp\(src=4050\)\),3')
    report_test_result("OVS rule: rewrite udp src (vm1->vm2)", m)
    m = tl.find_ovs_rule(hv, '3', '.*', '0x0800', 'set\(udp\(dst=4051\)\),2')
    report_test_result("OVS rule: rewrite udp dst (vm2->vm1)", m)


def test_rewrite_ipv4_ttl():
    # TODO server bind ip needed?
    iperf.iperf(nic2, nic1, 3, 'vm1->vm2', nic1.get_ip(3), '-B %s' % nic2.get_ip(3), '-B %s' % nic1.get_ip(3))
    m = tl.find_ovs_rule(hv, '2', '.*', '0x0800', 'set\(ipv4\(.*ttl=63.*\)\),3')
    report_test_result("OVS rule: rewrite ipv4 ttl (vm1->vm2)", m)
    m = tl.find_ovs_rule(hv, '3', '.*', '0x0800', 'set\(ipv4\(.*ttl=63.*\)\),2')
    report_test_result("OVS rule: rewrite ipv4 ttl (vm2->vm1)", m)


def test_rewrite_ipv6():
    ping(nic1, { "addr": "2002:0db8:0:f101::55" })
    m = tl.find_ovs_rule(hv, '2', nic2_mac, '0x86dd', 'set\(ipv6\(dst=2002:db8:0:f101::2\)\),3')
    report_test_result("OVS rule: rewrite ipv6 dst (vm1->vm2)", m)
    m = tl.find_ovs_rule(hv, '3', nic1_mac, '0x86dd', 'set\(ipv6\(src=2002:db8:0:f101::55,dst=2002:db8:0:f101::1\)\),2')
    report_test_result("OVS rule: rewrite ipv6 src (vm2->vm1)", m)


rewrite_tests = [
    test_rewrite_ipv4,
    test_rewrite_mac,
    test_rewrite_tcp_ports,
    test_rewrite_udp_ports,
    test_rewrite_ipv4_ttl,
    test_rewrite_ipv6,
]

prepare_for_test()
iperf = IperfTest(ctl)

for _test in rewrite_tests:
    _test()
