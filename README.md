OVS developer’s tests brief overview

August 2018

Run tests steps
===============

1.  install required packages:

    1.  upstream kernel under test (branch net-next)

    2.  openvswitch:
        if not altered use (https://github.com/openvswitch/ovs.git branch
        master), installation instructions can be found at
        http://docs.openvswitch.org/en/latest/intro/install/ ,
        note: need to install ovs using rpms so ovs scripts is also installed
        as part of the installation.

    3.  iproute2:
        if not altered use:
          1.  for upstream master version:
              http://git.kernel.org/pub/scm/linux/kernel/git/shemminger/iproute2.git
          2.  for “next“ version:
              http://git.kernel.org/pub/scm/network/iproute2/iproute2-next.git

    4.  install iperf latest version

    5.  install iperf3 latest version

    6.  make sure python scapy library installed as some tests uses it,
        python2-scapy.noarch or python34-scapy.noarch (or using python install
        pip install scapy)

2.  for the NIC under test need to define a custom configurations file (at
    asap_dev_reg project root directory), which includes relevant NIC network
    interfaces data (PF0, PF1, VF0,VF1,REP0,REP1):

    1.  Nic type should be dual port NIC ConnectX-5/ConnectX-4Lx in Ethernet mode where:

        1.  <PF0> is the network interface of the NIC’s first physical function

        2.  <PF1> is the network interface of the NIC’s second physical function
            (the second port)

        3.  <VF0> is the network interface of the first virtual function created
            on PF0

        4.  <VF1> is the network interface of the second virtual function created
            on PF0

        5.  <REP0> is the network interface of the first representor created when
            switched to switchdev mode on PF0

        6.  <REP1> is the network interface of the second representor created when
            switched to switchdev mode on PF0

    2.  example configuration file needed (some example config files can be found
        at project root directory named “config_*.sh“):
        NIC=<PF0>
        NIC2=<PF1>
        VF=<VF0>
        VF1=$VF
        VF2=<VF1>
        REP=<REP0>
        REP2=<REP1>

3.  to run tests (at asap_dev_reg project root directory):

    1.  Make sure sriov is enabled on the NIC and that the number
        of vfs allowed on the device is at least two

    2.  Make sure device is in ETH mode

    3.  export configuration file:
        export CONFIG=<file from 3>

    4.  run ./test-all-dev.py


Notes
=====

1. For Dell setups need to add a grub parameter “biosdevname=0” to
   disable consistent network device naming.

Add new test steps
==================

1.  add relevant test with test naming convention “test-<…>.sh”

2.  add a matching xml configuration file under “tests_conf” directory with
    naming convention <test_name from 2>.xml , the xml will include the
    following data (see existing XML file for exact structure):

    1.  Test info section:

        1.  name

        2.  description

        3.  owner

    2.  timeout for the test

    3.  tags relevant to test (tags could be passed to tests-all-dev script
        using --exclude_tag argument to exclude all tests with these tags
        defined from executing)

    4.  ignore section that could have one or more of the following sections:

        1.  bug: to input known RM bug number related to this tests

        2.  IgnoreByTestAll: to ignore still unsupported tests for upstream or
            to mark a test that is currently support to it still not merged to
            the current upstream branch and so on.


Notes
=====

1.  a lot of common utility functions for example get Mellanox interfaces,
    unbind/bind vfs and many other utility functions are part of “common.sh”
    script file (can be found at asap_dev_reg root directory) recommended to add
    the following lines at the top of each new test script to load common
    functions into the current shell script:
    my_dir="\$(dirname "\$0")"
    . \$my_dir/common.sh

2. there is a utility script “gen_test_xml.py” provided to automate step “2.“
   when adding a new test:
        usage: gen_test_xml.py [-h] --fname FNAME --desc DESC --owner OWNER
                       [--tout TOUT] --tag TAG [--ignore_test] [--bug BUG]

	optional arguments:
		-h, --help     show this help message and exit
		--fname FNAME  Pass the file name of the test (Mandatory)
		--desc DESC    Pass a small description of the test (Mandatory)
		--owner OWNER  test owner name
		--tout TOUT    time out for the test (default 1000)
		--tag TAG      associate a tag(s) with this test (Mandatory)
		--ignore_test  ignore this test when running test-all-dev.py
		--bug BUG      associate a bug(s) with this test

