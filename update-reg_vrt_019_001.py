#!/usr/bin/env python
# vim: expandtab shiftwidth=4 softtabstop=4

import os
import sys
import rpyc
import re
import xml.etree.ElementTree as ET


host = 'reg-r-vrt-019-001'
xml = 'ovs02_reg_vrt_019_001/reg_vrt_019_001.xml'


AF_LINK = 17

if not os.path.exists(xml):
    raise RuntimeError('Cannot find %s' % xml)

con = rpyc.classic.connect(host)
tree = ET.parse(xml)
root = tree.getroot()
eths = root.findall('.//eth')

for eth in eths:
    if not eth.attrib['label'].startswith('net'):
        continue
    print eth.attrib['label'], eth.attrib['id']
    nic = eth.attrib['id']
    try:
        new_mac = con.modules.netifaces.ifaddresses(nic)[AF_LINK][0]['addr']
    except ValueError, e:
        print 'Failed to get mac for %s' % nic
        continue
    param = eth.find('./params/param')
    old_mac = param.attrib['value']
    print old_mac + ' -> ' + new_mac
    param.set('value', new_mac)

tree.write(xml)
