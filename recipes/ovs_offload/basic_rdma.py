from lnst.Controller.Task import ctl
from Testlib import Testlib

# ------
# SETUP
# ------

tl = Testlib(ctl)

g1 = ctl.get_host("guest1")
h2 = ctl.get_host("host2")

# ------
# TESTS
# ------

h2_ip = h2.get_interface('if1').get_ip()

p = h2.run('rping -s', bg=True)
g1.run('rping -C 100 -c -a %s' % h2_ip)
p.intr()
