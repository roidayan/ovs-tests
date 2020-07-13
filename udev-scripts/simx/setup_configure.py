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
import socket
import logging
import commands
import traceback
from glob import glob
from time import sleep
from itertools import chain
from argparse import ArgumentParser


class DynamicObject(object):
    pass


class SetupConfigure(object):
    MLNXToolsPath = '/opt/mellanox/ethtool/sbin:/opt/mellanox/iproute2/sbin:/opt/verutils/bin/'

    def ParseArgs(self):
        parser = ArgumentParser(prog=self.__class__.__name__)
        parser.add_argument('--skip_ovs_config', help='Skip openvswitch configuration', action='store_true')
        parser.add_argument('--second-server', help='Second server config', action='store_true')
        parser.add_argument('--dpdk', help='Add DPDK=1 to configuration file', action='store_true')
        parser.add_argument('--sw-steering-mode', help='Configure software steering mode', action='store_true')

        (namespaces, args) = parser.parse_known_args()

        for key, value in vars(namespaces).items():
            setattr(self, key, value)

    def Run(self):
        try:
            self.ReloadModules()

            self.host = DynamicObject()

            self.host.name = socket.gethostbyname(socket.gethostname())

            self.UpdatePATHEnvironmentVariable()

            self.LoadPFInfo()
            self.DestroyVFs()

            self.UpdatePFInfo()
            self.CreateVFs()
            self.LoadVFInfo()

            self.UnbindVFs()

            self.ConfigureSWSteering()
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

    def ReloadModules(self):
        self.Logger.info("Reload modules")
        # workaround because udev rules changed in jenkins script but didn't take affect
        commands.getstatusoutput('modprobe -rq act_ct')
        commands.getstatusoutput('modprobe -rq cls_flower')
        commands.getstatusoutput('modprobe -rq mlx5_fpga_tools')
        commands.getstatusoutput('modprobe -rq mlx5_ib')
        commands.getstatusoutput('modprobe -rq mlx5_core')
        # load mlx5_core
        commands.getstatusoutput('modprobe -q mlx5_core')
        sleep(5)

    def UpdatePATHEnvironmentVariable(self):
        os.environ['PATH'] = self.MLNXToolsPath + os.pathsep + os.environ.get('PATH')
        with open('/etc/profile.d/zz_dev_reg_env.sh', 'w') as f:
            f.write('if [[ ! "$PATH" =~ "/opt/mellanox" ]]; then\n')
            f.write('    PATH="%s:$PATH"\n' % self.MLNXToolsPath)
            f.write('fi\n')

    def LoadPFInfo(self):
        for net in sorted(glob('/sys/class/net/*')):
            device = os.path.join(net, 'device')

            if not os.path.exists(device):
                continue

            # if physfn exists its a VF
            if os.path.exists(os.path.join(device, 'physfn')):
                continue

            driver = os.path.basename(os.readlink(os.path.join(device, 'driver')))
            if 'mlx5' not in driver:
                continue

            bus = os.path.basename(os.readlink(device))
            if not bus:
                continue

            PFName = os.path.basename(net)

            PFInfo = {
                      'vfs'    : [],
                      'sw_id'  : None,
                      'topoID' : None,
                      'name'   : PFName,
                      'bus'    : bus,
                     }

            self.Logger.info("Found PF %s", PFName)
            self.host.PNics = sorted(getattr(self.host, 'PNics', []) + [PFInfo], key=lambda k: k['bus'])

    def UpdatePFInfo(self):
        for PFInfo in self.host.PNics:
            (rc, output) = commands.getstatusoutput('readlink /sys/class/net/* | grep -m1 %s' % PFInfo['bus'])

            if rc:
                raise RuntimeError('Failed to query interface names\n%s' % (output))

            new_name = os.path.basename(output.strip())
            self.Logger.info("Update PF name %s -> %s", PFInfo['name'], new_name)
            PFInfo['name'] = new_name

    def LoadVFInfo(self):
        for PFInfo in self.host.PNics:
            for vfID in sorted(glob('/sys/class/net/%s/device/virtfn*/net/*' % PFInfo['name'])):
                nameOutput = os.path.basename(vfID)
                device = os.path.join(vfID, 'device')
                busOutput = os.path.basename(os.readlink(device))

                VFInfo = {
                            'rep'  : None,
                            'name' : nameOutput,
                            'bus'  : busOutput,
                        }

                self.Logger.info('PF %s VF %s', PFInfo['name'], nameOutput)
                PFInfo['vfs'] = sorted(PFInfo['vfs'] + [VFInfo], key=lambda k: k['bus'])

    def UpdateVFInfo(self):
        for PFInfo in self.host.PNics:
            PFInfo['vfs'] = []

        self.LoadVFInfo()
        self.LoadRepInfo()

    def get_port_info(self, port):
        try:
            with open('/sys/class/net/%s/phys_switch_id' % port, 'r') as f:
                sw_id = f.read().strip()
            with open('/sys/class/net/%s/phys_port_name' % port, 'r') as f:
                port_name = f.read().strip()
        except IOError:
            sw_id = ''
            port_name = ''
        return (sw_id, port_name)

    def get_pf_info(self, sw_id, port_index):
        for PNic in self.host.PNics:
            if PNic['sw_id'] == sw_id and PNic['port_index'] == port_index:
                return PNic
        return None

    def LoadRepInfo(self):
        for PFInfo in self.host.PNics:
            (sw_id, port_name) = self.get_port_info(PFInfo['name'])

            if not sw_id or not port_name:
                raise RuntimeError('Failed get phys switch id or port name for %s' % PFInfo['name'])

            PFInfo['sw_id'] = sw_id
            PFInfo['port_index'] = int(re.search('p(\d+)', port_name).group(1))

        devinfos = []
        for pnic in self.host.PNics:
            devinfos.append(pnic['name'])
            devinfos += [vf['name'] for vf in pnic['vfs']]

        for net in sorted(glob('/sys/class/net/*')):
            repName = os.path.basename(net)
            if repName in devinfos:
                continue

            (sw_id, port_name) = self.get_port_info(repName)
            if not sw_id or not port_name:
                continue

            self.Logger.info("Load rep info PF %s rep %s", PFInfo['name'], repName)

            pfIndex = int(re.search('pf(\d+)vf\d+', port_name).group(1)) & 0x7
            vfIndex = int(re.search('(?:pf\d+vf)?(\d+)', port_name).group(1))
            PFInfo = self.get_pf_info(sw_id, pfIndex)
            if not PFInfo:
                continue

            PFInfo['vfs'][vfIndex]['rep'] = repName

    def DestroyVFs(self):
        for PFInfo in self.host.PNics:
            if not os.path.exists("/sys/class/net/%s/device/sriov_numvfs" % PFInfo['name']):
                continue

            self.Logger.info('Destroying VFs over %s' % PFInfo['name'])
            (rc, output) = commands.getstatusoutput('echo 0 > /sys/class/net/%s/device/sriov_numvfs' % PFInfo['name'])

            if rc:
                raise RuntimeError('Failed to delete VFs over %s\n%s' % (PFInfo['name'], output))

            sleep(2)

    def CreateVFs(self):
        for PFInfo in self.host.PNics:
            self.Logger.info('Creating 2 VFs over %s' % PFInfo['name'])

            (rc, output) = commands.getstatusoutput('echo 2 > /sys/class/net/%s/device/sriov_numvfs' % PFInfo['name'])

            if rc:
                raise RuntimeError('Failed to configure VFs over %s\n%s' % (PFInfo['name'], output))

            sleep(2)

    def SetVFMACs(self):
        for PFInfo in self.host.PNics:
            for VFInfo in PFInfo['vfs']:
                splitedBus = map(lambda x: int(x, 16), VFInfo['bus'].replace('.', ':').split(':')[1:])
                splitedIP = map(lambda x: int(x), self.host.name.split('.'))[-2:]
                VFInfo['mac'] = 'e4:%02x:%02x:%02x:%02x:%02x' % tuple(splitedIP + splitedBus)
                vfIndex = PFInfo['vfs'].index(VFInfo)

                self.Logger.info('Setting MAC %s on %s vf %d (bus %s)' % (VFInfo['mac'], PFInfo['name'], vfIndex, VFInfo['bus']))

                command = 'ip link set %s vf %d mac %s' % (PFInfo['name'], vfIndex, VFInfo['mac'])
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

    def ConfigureSWSteering(self):
        mode = 'smfs' if self.sw_steering_mode else 'dmfs'
        mode2 = 'software' if self.sw_steering_mode else 'firmware'

        for PFInfo in self.host.PNics:
            self.Logger.info("Setting %s steering mode to %s steering" % (PFInfo['name'], 'software' if self.sw_steering_mode else 'firmware'))

            if os.path.exists('/sys/class/net/%s/compat/devlink/steering_mode' % PFInfo['name']):
                (rc, output) = commands.getstatusoutput("echo %s > /sys/class/net/%s/compat/devlink/steering_mode" % (mode, PFInfo['name']))
            else:
                (rc, output) = commands.getstatusoutput('devlink dev param set pci/%s name flow_steering_mode value "%s" cmode runtime' % (PFInfo['bus'], mode))

            if rc:
                raise RuntimeError('Failed to set %s steering mode to %s\n%s' % (PFInfo['name'], mode2, output))

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

        sleep(5)

    def RestartOVS(self):
        (rc, output) = commands.getstatusoutput('systemctl restart openvswitch')

        if rc:
            raise RuntimeError('Failed to restart openvswitch service\n%s' % (output))

    def ConfigureOVS(self):
        self.Logger.info("Setting [hw-offload=true] configuration to OVS" )
        self.RestartOVS()
        (rc, output) = commands.getstatusoutput('ovs-vsctl set Open_vSwitch . other_config:hw-offload=true')
        if rc:
            raise RuntimeError("Failed to set openvswitch configuration [hw-offload=true]]\n%s" % output)
        self.RestartOVS()

    def get_reps(self):
        reps = []
        for PFInfo in self.host.PNics:
            reps.append(PFInfo['name'])
            for VFInfo in PFInfo['vfs']:
                if VFInfo['rep']:
                    reps.append(VFInfo['rep'])
        return reps

    def EnableDevOffload(self):
        reps = self.get_reps()
        for devName in reps:
            self.Logger.info("Enabling hw-tc-offload for %s" % (devName))
            commands.getstatusoutput('ethtool -K %s hw-tc-offload on' % devName)

    def BringUpDevices(self):
        reps = self.get_reps()
        for devName in reps:
            self.Logger.info("Bringing up %s" % devName)
            commands.getstatusoutput('ip link set dev %s up' % devName)

    def AttachVFs(self):
        for VFInfo in chain.from_iterable(map(lambda PFInfo: PFInfo['vfs'], self.host.PNics)):
            self.Logger.info("Binding %s" % VFInfo['bus'])
            (rc, output) = commands.getstatusoutput('echo %s > /sys/bus/pci/drivers/mlx5_core/bind' % VFInfo['bus'])

            if rc:
                raise RuntimeError('Failed to bind %s\n%s' % (VFInfo['bus'], output))
        # might need a second to let udev rename
        sleep(1)

    def CreateConfFile(self):
        conf = 'PATH="%s:$PATH"' % self.MLNXToolsPath
        conf += '\nNIC=%s' % self.host.PNics[0]['name']

        if len(self.host.PNics) > 1:
            conf += '\nNIC2=%s' % self.host.PNics[1]['name']

        conf += '\nVF=%s' % self.host.PNics[0]['vfs'][0]['name']
        conf += '\nVF1=%s' % self.host.PNics[0]['vfs'][0]['name']
        conf += '\nVF2=%s' % self.host.PNics[0]['vfs'][1]['name']
        rep = self.host.PNics[0]['vfs'][0]['rep']
        rep2 = self.host.PNics[0]['vfs'][1]['rep']
        if not rep or not rep2:
            raise RuntimeError('Cannot find representors')
        conf += '\nREP=%s' % rep
        conf += '\nREP2=%s' % rep2

        cloud_player_1_ip = ''
        cloud_player_2_ip = ''
        try:
            with open('/workspace/cloud_tools/.setup_info', 'r') as f:
                for line in f.readlines():
                    if 'CLOUD_PLAYER_1_IP' in line:
                        cloud_player_1_ip = line.strip().split('=')[1]
                    if 'CLOUD_PLAYER_2_IP' in line:
                        cloud_player_2_ip = line.strip().split('=')[1]
        except IOError:
            self.Logger.debug('Failed to read cloud_tools/.setup_info')

        if cloud_player_2_ip == self.host.name:
            conf += '\nREMOTE_SERVER=%s' % cloud_player_1_ip
        else:
            conf += '\nREMOTE_SERVER=%s' % cloud_player_2_ip

        conf += '\nREMOTE_NIC=%s' % self.host.PNics[0]['name']

        if len(self.host.PNics) > 1:
            conf += '\nREMOTE_NIC2=%s' % self.host.PNics[1]['name']

        conf += '\nB2B=1'

        if self.dpdk:
            conf += '\nDPDK=1'

        with open('/workspace/dev_reg_conf.sh', 'w+') as f:
            f.write(conf)

    @property
    def Logger(self):
        if not hasattr(self, 'logger'):
            self.logger = logging
            self.logger.getLogger().setLevel(logging.INFO)
            self.logger.basicConfig(format='%(levelname)-7s: %(message)s')

        return self.logger


if __name__ == "__main__":
    setupConfigure = SetupConfigure()
    setupConfigure.ParseArgs()
    sys.exit(setupConfigure.Run())
