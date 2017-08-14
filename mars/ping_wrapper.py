#!/usr/bin/env python

# Built-in modules
import sys

# Local modules
from reg2_wrapper.test_wrapper.client_server_wrapper import ClientServerWrapper, RunnerMode

class Ping( ClientServerWrapper ):

    def get_prog_path(self):
        return "ping"

    def configure_parser(self):
        super(Ping, self).configure_parser()

        # Client arguments
        self.add_client_cmd_argument('--count', help='Number of echo requests to send.', type=int, default=10, alias='-c')
        self.add_client_cmd_argument('--interval', help='Wait interval seconds between sending each packet.', type=float, alias='-i')
        self.add_client_cmd_argument('--packet_size', help='Specifies the number of data bytes to be sent.', type=int, alias='-s')
        self.add_client_cmd_argument('--flood', help='Flood ping.', action='store_true', alias='-f')
        self.add_epoint_attr_client_argument('--src_interface', "interface_name", priority=0, alias='-I')
        self.add_dynamic_client_argument('server_ipv4', self.get_server_epoint_attr, "ipv4", priority=100, value_only=True)

if __name__ == "__main__":
    ping = Ping("ping", RunnerMode.CLIENT)
    ping.execute(sys.argv[1:])
