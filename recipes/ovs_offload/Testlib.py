import re
import logging


class Testlib:
    def __init__(self, ctl):
        self._ctl = ctl

    def set_hw_offload(self, host, nics, state):
        cmd = "ethtool -K {nic} hw-tc-offload %s" % state
        for nic in nics:
            logging.info("Set hw-tc-offload=%s for %s" % (state, nic))
            host.run(cmd.format(nic=nic))

    def enable_hw_offload(self, host, nics):
        self.set_hw_offload(host, nics, 'on')

    def disable_hw_offload(self, host, nics):
        self.set_hw_offload(host, nics, 'off')

    def custom(self, host, desc, err_msg=None, opts=None):
        host.sync_resources(modules=["Custom"])
        options = {}
        if opts:
            options.update(opts)
        if err_msg:
            options["fail"] = "yes"
            options["msg"] = err_msg
        custom_mod = self._ctl.get_module("Custom", options=options)
        host.run(custom_mod, desc=desc)

    def find_tc_rule(self, host, nic, src_mac, dst_mac, proto='.*', action='.*', tunnel=''):
        # find dev. i.e. ens5f0
        try:
            if1 = host.get_interface(nic)
            dev = if1.get_devname()
        except KeyError:
            dev = nic

        # tc output
        cmd = host.run("tc -s filter show dev %s ingress" % dev)
        out = cmd.out().strip()

        if not out:
            return None

        # find rule
        pat_filter = r"^protocol %s pref .* dst_mac %s\n\s*src_mac %s\n.*\n\s*action order \s*\d+\s*:\s* %s" % (
                proto, str(dst_mac).lower(), str(src_mac).lower(), action)
        pat_action = r".*\n\s*action order .* %s.*\n\s*Sent (?P<bytes>\d+) bytes (?P<pkts>\d+) pkt \(dropped (?P<drop>\d+), overlimits \d+ requeues \d+\)" % action

        logging.debug("device %s pattern '%s' action '%s'", dev, pat_filter, pat_action)

        for f in re.split('\n\s*filter\s*', out):
            if re.match(pat_filter, f, re.S + re.M):
                logging.debug("matched filter")
                m = re.match(pat_action, f, re.S + re.M)
                if m:
                    logging.debug("matched action")
                    return m.groupdict()
                return None
        return None

    def find_ovs_rule(self, host, in_port, dst_mac, proto='.*', action='.*', type='offloaded'):
        cmd = host.run("ovs-appctl dpctl/dump-flows type=%s" % type)
        out = cmd.out().strip()

        if not out:
            return None

        if type == 'offloaded':
            # in offloaded the first attr is in_port so make sure it is.
            pat_prefix = '^'
        else:
            pat_prefix = '.*,'

        pat_filter = pat_prefix + r"in_port\(%s\).*,eth\(.*dst=%s\).*,eth_type\(%s\).*" % (in_port, str(dst_mac).lower(), proto)
        pat_action = r".*\spackets:(?P<pkts>\d+), bytes:(?P<bytes>\d+), used:(?P<used>[\d.]+)s, actions:%s" % action

        logging.debug("in_port '%s' filter '%s' action '%s'", in_port, pat_filter, pat_action)

        for f in out.splitlines():
            logging.debug("rule: %s" % f)
            if re.match(pat_filter, f):
                logging.debug("matched ovs rule")
                m = re.match(pat_action, f)
                if m:
                    logging.debug("matched action")
                    return m.groupdict()
        return None

    def _get_iperf_srv_mod(self, iperf3=False):
        modules_options = {
            "role": "server",
        }
        if iperf3:
            return self._ctl.get_module("Iperf3", options=modules_options)
        return self._ctl.get_module("Iperf", options=modules_options)

    def _get_iperf_cli_mod(self, server, duration, iperf3=False, iperf_opts=''):
        modules_options = {
            "role": "client",
            "iperf_server": server,
            "duration": duration,
            "iperf_opts": iperf_opts
        }
        if iperf3:
            return self._ctl.get_module("Iperf3", options=modules_options)
        return self._ctl.get_module("Iperf", options=modules_options)

    def iperf(self, cli_if, srv_if, duration, desc, iperf3=False, iperf_opts='-l 1024k -P 12'):
        srv_ip = srv_if.get_ip(0)
        srv_m = self._get_iperf_srv_mod(iperf3)
        cli_m = self._get_iperf_cli_mod(srv_ip, duration, iperf3, iperf_opts)

        cli_host = cli_if.get_host()
        srv_host = srv_if.get_host()

        srv_proc = srv_host.run(srv_m, bg=True)
        self._ctl.wait(2)
        cli_host.run(cli_m, timeout=duration + 15, desc=desc)
        srv_proc.intr()
