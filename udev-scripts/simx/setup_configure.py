#!/usr/bin/env python2.7
# Author:  Anton Metsner - Antonm@mellanox.com
# --
# Copyright (c) 2018-2020 Mellanox Technologies. All rights reserved.
#
# This software is available to you under a choice of one of two
# licenses.  You may choose to be licensed under the terms of the GNU
# General Public License (GPL) Version 2, available from the file
# COPYING in the main directory of this source tree, or the
# OpenIB.org BSD license below:
#
#     Redistribution and use in source and binary forms, with or
#     without modification, are permitted provided that the following
#     conditions are met:
#
#      - Redistributions of source code must retain the above
#        copyright notice, this list of conditions and the following
#        disclaimer.
#
#      - Redistributions in binary form must reproduce the above
#        copyright notice, this list of conditions and the following
#        disclaimer in the documentation and/or other materials
#        provided with the distribution.
#
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE

import re
import os
import sys
import time
import socket
import logging
import commands
import traceback
from itertools import chain
from argparse import ArgumentParser

class DynamicObject(object):
    pass

class SetupConfigure(object):

    MLNXToolsPath = '/opt/mellanox/ethtool/sbin:/opt/mellanox/iproute2/sbin:/opt/verutils/bin/'

    def ParseArgs(self, args):
        self.Parser.add_argument('--skip_ovs_config', help='Skip openvswitch configuration', action='store_true')
        self.Parser.add_argument('--second-server', help='Second server config', action='store_true')

        (namespaces, args) = self.Parser.parse_known_args(args)

        for key, value in vars(namespaces).items():
            setattr(self, key, value)

    def Run(self):
        try:
            self.host = DynamicObject()

            self.host.name = socket.gethostbyname(socket.gethostname())

            self.UpdatePATHEnvironmentVariable()

            self.LoadPFInfo()
            self.DestroyVFs()

            self.UpdatePFInfo()
            self.CreateVFs()
            self.LoadVFInfo()

            self.UnbindVFs()

            self.ConfigurePF()
            self.UpdatePFInfo()
            self.SetVFMACs()

            self.LoadRepInfo()

            self.EnableDevOffload()

            if not self.skip_ovs_config:
                self.ConfigureOVS()

            self.AttachVFs()
            self.UpdateVFInfo()

            self.BringUpDevices()

            if self.second_server:
                return

            self.CreateConfFile()

        except:
            self.Logger.error(str(traceback.format_exc()))
            return 1

        return 0

    def UpdatePATHEnvironmentVariable(self):
        os.environ['PATH'] = self.MLNXToolsPath + os.pathsep + os.environ.get('PATH')
        with open('/etc/profile.d/zz_dev_reg_env.sh', 'w') as f:
            f.write('if [[ ! "$PATH" =~ "/opt/mellanox" ]]; then\n')
            f.write('    PATH="%s:$PATH"\n' % self.MLNXToolsPath)
            f.write('fi\n')

    def LoadPFInfo(self):
        (rc, output) = commands.getstatusoutput('ls /sys/class/net/')

        if rc:
            raise RuntimeError('Failed to query interface names\n%s' % (output))

        for PFName in set(output.strip().split()) - set(['lo']):
            (rc, output) = commands.getstatusoutput('readlink /sys/class/net/%s/device' % PFName)

            if rc:
                continue

            (rc, output) = commands.getstatusoutput('readlink /sys/class/net/%s/device/physfn' % PFName)

            if not rc:
                continue

            (rc, output) = commands.getstatusoutput('ethtool -i %s' % PFName)

            if rc and 'Operation not supported' not in output and 'No such device' not in output:
                raise RuntimeError('Failed to query %s info\n%s' % (PFName, output))

            if 'mlx5' in output:
                PFInfo = {
                          'vfs'    : [],
                          'sw_id'  : None,
                          'topoID' : None,
                          'name'   : PFName,
                          'bus'    : re.search('bus-info: (.*)', output, re.MULTILINE).group(1),
                         }

                if not PFInfo['bus']:
                    continue
                self.host.PNics = sorted(getattr(self.host, 'PNics', []) + [PFInfo], key=lambda k: k['bus'])

    def UpdatePFInfo(self):
        for PFInfo in self.host.PNics:
            if not PFInfo['bus']:
                continue
            (rc, output) = commands.getstatusoutput('readlink /sys/class/net/* | grep -m1 %s' % PFInfo['bus'])

            if rc:
                raise RuntimeError('Failed to query interface names\n%s' % (output))

            new_name = os.path.basename(output.strip())
            self.Logger.info("Update PF name %s -> %s", PFInfo['name'], new_name)
            PFInfo['name'] = new_name

    def LoadVFInfo(self):
        for PFInfo in self.host.PNics:
            (rc, output) = commands.getstatusoutput('ls /sys/class/net/%s/device/ | grep virt' % PFInfo['name'])

            if rc:
                raise RuntimeError('Failed to query %s VF IDs\n%s' % (PFInfo['name'], output))

            for vfID in sorted(output.strip().split()):
                (rc, nameOutput) = commands.getstatusoutput('ls /sys/class/net/%s/device/%s/net/' % (PFInfo['name'], vfID))

                if rc:
                    raise RuntimeError('Failed to query %s VF name\n%s' % (PFInfo['name'], nameOutput))

                (rc, busOutput) = commands.getstatusoutput('basename `readlink /sys/class/net/%s/device/%s`' % (PFInfo['name'], vfID))

                if rc:
                    raise RuntimeError('Failed to query %s VF Bus address\n%s' % (PFInfo['name'], busOutput))

                VFInfo        = {
                                 'rep'  : None,
                                 'name' : nameOutput.strip(),
                                 'bus'  : busOutput.strip(),
                                }

                PFInfo['vfs'] = sorted(PFInfo['vfs'] + [VFInfo], key=lambda k: k['bus'])

    def UpdateVFInfo(self):
        for PFInfo in self.host.PNics:
            PFInfo['vfs'] = []

        self.LoadVFInfo()
        self.LoadRepInfo()

    def LoadRepInfo(self):
        for PFInfo in self.host.PNics:
            (rc, output) = commands.getstatusoutput('cat /sys/class/net/%s/phys_switch_id' % PFInfo['name'])

            if rc:
                raise RuntimeError('Failed to query %s phys_switch_id\n%s' % (PFInfo['name'], output))

            PFInfo['sw_id'] = output.strip()

            (rc, output) = commands.getstatusoutput('cat /sys/class/net/%s/phys_port_name' % PFInfo['name'])

            if rc:
                raise RuntimeError('Failed to query %s phys_port_name\n%s' % (PFInfo['name'], output))

            PFInfo['port_index'] = int(re.search('p(\d+)', output.strip()).group(1))

        (rc, output) = commands.getstatusoutput('ls /sys/class/net/')

        if rc:
            raise RuntimeError('Failed to query interface names\n%s' % (output))

        DevInfos = list(chain.from_iterable(map(lambda PFInfo: PFInfo['vfs'], self.host.PNics))) + self.host.PNics

        for repName in set(output.strip().split()) - set(['lo'] + map(lambda DevInfo: DevInfo['name'], DevInfos)):
            (rc0, switch_id) = commands.getstatusoutput('cat /sys/class/net/%s/phys_switch_id' % repName)
            (rc1, port_name) = commands.getstatusoutput('cat /sys/class/net/%s/phys_port_name' % repName)

            if rc0 or rc1:
                continue

            self.Logger.info("Load rep info %s rc %d %d" % repName)
            pfName  = int(re.search('pf(\d+)vf\d+', port_name).group(1)) & 0x7
            vfIndex = int(re.search('(?:pf\d+vf)?(\d+)', port_name).group(1))
            pfInfo  = next(iter(filter(lambda PNic: PNic['sw_id'] == switch_id.strip() and PNic['port_index'] == pfName, self.host.PNics)), None)

            if pfInfo:
                pfInfo['vfs'][vfIndex]['rep'] = repName

    def DestroyVFs(self):
        for PFInfo in self.host.PNics:
            if not os.path.exists("/sys/class/net/%s/device/sriov_numvfs" % PFInfo['name']):
                continue

            self.Logger.info('Destroying VFs over %s' % PFInfo['name'])
            (rc, output) = commands.getstatusoutput('echo 0 > /sys/class/net/%s/device/sriov_numvfs' % PFInfo['name'])

            if rc:
                raise RuntimeError('Failed to delete VFs over %s\n%s' % (PFInfo['name'], output))

            time.sleep(2)

    def CreateVFs(self):
        for PFInfo in self.host.PNics:
            self.Logger.info('Creating 2 VFs over %s' % PFInfo['name'])

            (rc, output) = commands.getstatusoutput('echo 2 > /sys/class/net/%s/device/sriov_numvfs' % PFInfo['name'])

            if rc:
                raise RuntimeError('Failed to configure VFs over %s\n%s' % (PFInfo['name'], output))

            time.sleep(2)

    def SetVFMACs(self):
        for PFInfo in self.host.PNics:
            for VFInfo in PFInfo['vfs']:
                splitedBus    = map(lambda x: int(x, 16), VFInfo['bus'].replace('.', ':').split(':')[1:])
                splitedIP     = map(lambda x: int(x), self.host.name.split('.'))[-2:]
                VFInfo['mac'] = 'e4:%02x:%02x:%02x:%02x:%02x' % tuple(splitedIP + splitedBus)
                command       = 'ip link set %s vf %d mac %s' % (PFInfo['name'], PFInfo['vfs'].index(VFInfo), VFInfo['mac'])

                self.Logger.info('Setting MAC %s to %s' % (VFInfo['mac'], VFInfo['bus']))
                self.Logger.info('command: %s' % command)
                (rc, output) = commands.getstatusoutput(command)

                if rc:
                    raise RuntimeError('Failed to set MAC address to %s\n%s' % (VFInfo['bus'], output))

    def UnbindVFs(self):
        for PFInfo in self.host.PNics:
            for VFBus in map(lambda VFInfo: VFInfo['bus'], PFInfo['vfs']):
                self.Logger.info('Unbind %s' % (VFBus))
                (rc, output) = commands.getstatusoutput('echo %s > /sys/bus/pci/drivers/mlx5_core/unbind' % VFBus)

                if rc:
                    raise RuntimeError('Failed to unbind %s\n%s' % (VFBus, output))

    def ConfigurePF(self):
        for PFInfo in self.host.PNics:
            self.Logger.info("Changing %s to switchdev mode" % (PFInfo['name']))

            if os.path.exists('/sys/class/net/%s/compat/devlink/mode' % PFInfo['name']):
                (rc, output) = commands.getstatusoutput("echo switchdev > /sys/class/net/%s/compat/devlink/mode" % PFInfo['name'])

            elif os.path.exists('/sys/kernel/debug/mlx5/%s/compat/mode' % PFInfo['bus']):
                (rc, output) = commands.getstatusoutput("echo switchdev > /sys/kernel/debug/mlx5/%s/compat/mode" % PFInfo['bus'])

            else:
                (rc, output) = commands.getstatusoutput("devlink dev eswitch set pci/%s mode switchdev" % PFInfo['bus'])

            if rc:
                raise RuntimeError('Failed to change %s mode to switchdev\n%s' % (PFInfo['name'], output))

        time.sleep(5)

    def ConfigureOVS(self):
        self.Logger.info("Setting [hw-offload=true] configuration to OVS" )

        (rc, output) = commands.getstatusoutput('systemctl restart openvswitch')

        if rc:
            raise RuntimeError('Failed to restart openvswitch service\n%s' % (output))

        (rc, output) = commands.getstatusoutput('ovs-vsctl set Open_vSwitch . other_config:hw-offload=true')

        if rc:
            raise RuntimeError("Failed to set openvswitch configuration [hw-offload=true]]\n%s" % output)

        (rc, output) = commands.getstatusoutput('systemctl restart openvswitch')

        if rc:
            raise RuntimeError('Failed to restart openvswitch service\n%s' % (output))

    def EnableDevOffload(self):
        for PFInfo in self.host.PNics:
            for devName in [PFInfo['name']] + map(lambda VFInfo: VFInfo['rep'], PFInfo['vfs']):
                if commands.getstatusoutput('ethtool -k %s | grep hw-tc-offload' % devName)[0]:
                    continue

                self.Logger.info("Enabling hw-tc-offload for %s" % (devName))

                (rc, output) = commands.getstatusoutput('ethtool -K %s hw-tc-offload on' % devName)

                if rc:
                    raise RuntimeError('Failed to enable hw-tc-offload for %s:\n%s' % (devName, output))

    def BringUpDevices(self):
        PFNames  = map(lambda pfInfo: pfInfo['name'], self.host.PNics)
        RepNames = [VFInfo['rep'] for PFInfo in self.host.PNics for VFInfo in PFInfo['vfs'] if VFInfo['rep'] is not None]

        for devName in PFNames + RepNames:
            self.Logger.info("Bringing up %s " % devName)
            (rc, output) = commands.getstatusoutput('ip link set dev %s up' % devName)

            if rc:
                raise RuntimeError('Failed to bring up %s\n%s' % (devName, output))

    def AttachVFs(self):
        for VFInfo in chain.from_iterable(map(lambda PFInfo: PFInfo['vfs'], self.host.PNics)):
            self.Logger.info("Binding %s" % VFInfo['bus'])
            (rc, output) = commands.getstatusoutput('echo %s > /sys/bus/pci/drivers/mlx5_core/bind' % VFInfo['bus'])

            if rc:
                raise RuntimeError('Failed to bind %s\n%s' % (VFInfo['bus'], output))

    def CreateConfFile(self):
        conf = 'PATH="%s:$PATH"' % self.MLNXToolsPath
        conf += '\nNIC=%s' % self.host.PNics[0]['name']

        if len(self.host.PNics) > 1:
            conf += '\nNIC2=%s' % self.host.PNics[1]['name']

        conf += '\nVF=%s' % self.host.PNics[0]['vfs'][0]['name']
        conf += '\nVF1=%s' % self.host.PNics[0]['vfs'][0]['name']
        conf += '\nVF2=%s' % self.host.PNics[0]['vfs'][1]['name']
        conf += '\nREP=%s' % self.host.PNics[0]['vfs'][0]['rep']
        conf += '\nREP2=%s' % self.host.PNics[0]['vfs'][1]['rep']

        cloud_player_1_ip = ''
        cloud_player_2_ip = ''
        try:
            with open('/workspace/cloud_tools/.setup_info', 'r') as f:
                for line in f.readlines():
                    if 'CLOUD_PLAYER_1_IP' in line:
                        cloud_player_1_ip = line.strip().split('=')[1]
                    if 'CLOUD_PLAYER_2_IP' in line:
                        cloud_player_2_ip = line.strip().split('=')[1]
        except e:
            self.Logger.debug('Failed to read cloud_tools/.setup_info')

        if cloud_player_2_ip == self.host.name:
            conf += '\nREMOTE_SERVER=%s' % cloud_player_1_ip
        else:
            conf += '\nREMOTE_SERVER=%s' % cloud_player_2_ip

        conf += '\nREMOTE_NIC=%s' % self.host.PNics[0]['name']

        if len(self.host.PNics) > 1:
            conf += '\nREMOTE_NIC2=%s' % self.host.PNics[1]['name']

        conf += '\nB2B=1'

        with open('/workspace/dev_reg_conf.sh', 'w+') as f:
            f.write(conf)

    def GetLogger(self):
        if not hasattr(self, 'logger'):
            self.logger = logging

            self.logger.getLogger().setLevel(logging.INFO)
            self.logger.basicConfig(format='%(levelname)s     : %(message)s')

        return self.logger

    def GetParser(self):
        if not hasattr(self, 'parser'):
            self.parser = ArgumentParser(prog=self.__class__.__name__)

        return self.parser

    Logger = property(GetLogger)
    Parser = property(GetParser)

if __name__ == "__main__":
    setupConfigure = SetupConfigure()
    setupConfigure.ParseArgs(sys.argv[1:])
    sys.exit(setupConfigure.Run())
