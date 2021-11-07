#!/usr/bin/python

import re
import os
import sys
import socket
import logging
import traceback
from glob import glob
from time import sleep
from itertools import chain
from argparse import ArgumentParser
from subprocess import check_call
from subprocess import check_output
from subprocess import CalledProcessError


def runcmd(cmd):
    return check_call(cmd, shell=True)


def runcmd2(cmd):
    try:
        return check_call(cmd, shell=True)
    except CalledProcessError:
        return 1


def runcmd_output(cmd):
    return check_output(cmd, shell=True).decode()


class Host(object):
    def __init__(self, name):
        self.name = name
        self.PNics = []


class SetupConfigure(object):
    MLNXToolsPath = '/opt/mellanox/ethtool/sbin:/opt/mellanox/iproute2/sbin:/opt/verutils/bin/'

    def ParseArgs(self):
        parser = ArgumentParser(prog=self.__class__.__name__)
        parser.add_argument('--second-server', '-s', help='Second server config', action='store_true')
        parser.add_argument('--dpdk', help='Add DPDK=1 to configuration file', action='store_true')
        parser.add_argument('--sw-steering-mode', help='Configure software steering mode', action='store_true')

        args = parser.parse_args()

        for key, value in vars(args).items():
            setattr(self, key, value)

    def set_ovs_service(self):
        self.ID = ''
        try:
            with open("/etc/os-release", 'r') as f:
                for line in f.readlines():
                    line = line.strip().split('=')
                    if line[0] == 'ID':
                        self.ID = line[1].strip('"')
                        break
            # lsb_release lib doesnt always exists
            # self.is_ubuntu = lsb_release.get_os_release()['ID'].lower() == 'ubuntu'
        except:
            pass

        if self.ID:
            self.Logger.info(self.ID)

        if self.ID == 'ubuntu':
            self.ovs_service = "openvswitch-switch"
        else:
            self.ovs_service = "openvswitch"

    def Run(self):
        try:
            self.flow_steering_mode_supp = True

            self.set_ovs_service()
            self.StopOVS()
            self.ReloadModules()

            self.host = Host(socket.gethostbyname(socket.gethostname()))

            self.UpdatePATHEnvironmentVariable()

            self.LoadPFInfo()
            if not self.host.PNics:
                self.Logger.error("Cannot find PNics")
                return 1

            self.DestroyVFs()
            self.CreateVFs()
            self.LoadVFInfo()

            self.UnbindVFs()

            self.ConfigureSteeringMode()
            self.ConfigurePF()
            self.SetVFMACs()

            self.LoadRepInfo()

            self.EnableDevOffload()

            if self.dpdk:
                self.configure_hugepages()

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
        runcmd2('modprobe -rq act_ct')
        runcmd2('modprobe -rq cls_flower')
        runcmd2('modprobe -rq mlx5_fpga_tools')
        runcmd2('modprobe -rq mlx5_vdpa')
        runcmd2('modprobe -rq mlx5_ib')
        runcmd2('modprobe -rq mlx5_core')
        runcmd2('modprobe -aq mlx5_ib mlx5_core')
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

            port_name = self.get_port_name(PFName)
            if port_name and not re.match(r'p\d+', port_name):
                continue

            PFInfo = {
                      'vfs'    : [],
                      'sw_id'  : None,
                      'topoID' : None,
                      'name'   : PFName,
                      'bus'    : bus,
                     }

            self.Logger.info("Found PF %s", PFName)
            self.host.PNics = sorted(getattr(self.host, 'PNics', []) + [PFInfo], key=lambda k: k['bus'])

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
                PFInfo['vfs'].append(VFInfo)

            PFInfo['vfs'] = sorted(PFInfo['vfs'], key=lambda k: k['bus'])
            if len(PFInfo['vfs']) == 0:
                raise RuntimeError("Cannot find VFs for PF %s" % PFInfo['name'])

    def UpdateVFInfo(self):
        for PFInfo in self.host.PNics:
            PFInfo['vfs'] = []

        self.LoadVFInfo()
        self.LoadRepInfo()

    def get_switch_id(self, port):
        try:
            with open('/sys/class/net/%s/phys_switch_id' % port, 'r') as f:
                sw_id = f.read().strip()
        except IOError:
            sw_id = ''
        return sw_id

    def get_port_name(self, port):
        try:
            with open('/sys/class/net/%s/phys_port_name' % port, 'r') as f:
                port_name = f.read().strip()
        except IOError:
            port_name = ''
        return port_name

    def get_port_info(self, port):
        return (self.get_switch_id(port), self.get_port_name(port))

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

            self.Logger.info("Load rep info rep %s", repName)
            pfIndex = int(re.search('pf(\d+)vf\d+', port_name).group(1)) & 0x7
            vfIndex = int(re.search('(?:pf\d+vf)?(\d+)', port_name).group(1))
            PFInfo = self.get_pf_info(sw_id, pfIndex)
            if not PFInfo:
                continue

            if vfIndex >= len(PFInfo['vfs']):
                raise RuntimeError("Cannot find relevant VF for rep %s" % repName)

            PFInfo['vfs'][vfIndex]['rep'] = repName

    def DestroyVFs(self):
        for PFInfo in self.host.PNics:
            if not os.path.exists("/sys/class/net/%s/device/sriov_numvfs" % PFInfo['name']):
                continue
            self.Logger.info('Destroying VFs over %s' % PFInfo['name'])
            runcmd('echo 0 > /sys/class/net/%s/device/sriov_numvfs' % PFInfo['name'])
            sleep(2)

    def CreateVFs(self):
        for PFInfo in self.host.PNics:
            self.Logger.info('Creating 2 VFs over %s' % PFInfo['name'])
            runcmd('echo 2 > /sys/class/net/%s/device/sriov_numvfs' % PFInfo['name'])
            sleep(2)

    def SetVFMACs(self):
        for PFInfo in self.host.PNics:
            for VFInfo in PFInfo['vfs']:
                splitedBus = [int(x, 16) for x in VFInfo['bus'].replace('.', ':').split(':')[1:]]
                splitedIP = [int(x) for x in self.host.name.split('.')[-2:]]
                VFInfo['mac'] = 'e4:%02x:%02x:%02x:%02x:%02x' % tuple(splitedIP + splitedBus)
                vfIndex = PFInfo['vfs'].index(VFInfo)
                self.Logger.info('Setting MAC %s on %s vf %d (bus %s)' % (VFInfo['mac'], PFInfo['name'], vfIndex, VFInfo['bus']))
                command = 'ip link set %s vf %d mac %s' % (PFInfo['name'], vfIndex, VFInfo['mac'])
                runcmd(command)

    def UnbindVFs(self):
        for PFInfo in self.host.PNics:
            for VFBus in map(lambda VFInfo: VFInfo['bus'], PFInfo['vfs']):
                self.Logger.info('Unbind %s' % VFBus)
                runcmd2('echo %s > /sys/bus/pci/drivers/mlx5_core/unbind' % VFBus)

    @property
    def flow_steering_mode(self):
        return 'smfs' if self.sw_steering_mode else 'dmfs'

    def ConfigureSteeringMode(self):
        mode = self.flow_steering_mode
        mode2 = 'software' if self.sw_steering_mode else 'firmware'

        for PFInfo in self.host.PNics:
            self.Logger.info("Setting %s steering mode to %s steering" % (PFInfo['name'], 'software' if self.sw_steering_mode else 'firmware'))

            if os.path.exists('/sys/class/net/%s/compat/devlink/steering_mode' % PFInfo['name']):
                cmd = "echo %s > /sys/class/net/%s/compat/devlink/steering_mode" % (mode, PFInfo['name'])
            else:
                # try to set the mode only if kernel supports flow_steering_mode parameter
                try:
                    runcmd_output('devlink dev param show pci/%s name flow_steering_mode' % (PFInfo['bus']))
                except CalledProcessError:
                    self.flow_steering_mode_supp = False
                    self.Logger.info("The kernel does not support devlink flow_steering_mode param! Skipping.")
                    return
                cmd = 'devlink dev param set pci/%s name flow_steering_mode value "%s" cmode runtime' % (PFInfo['bus'], mode)

            runcmd_output(cmd)

    def ConfigurePF(self):
        for PFInfo in self.host.PNics:
            self.Logger.info("Changing %s to switchdev mode" % (PFInfo['name']))

            if os.path.exists('/sys/class/net/%s/compat/devlink/mode' % PFInfo['name']):
                cmd = "echo switchdev > /sys/class/net/%s/compat/devlink/mode" % PFInfo['name']
            elif os.path.exists('/sys/kernel/debug/mlx5/%s/compat/mode' % PFInfo['bus']):
                cmd = "echo switchdev > /sys/kernel/debug/mlx5/%s/compat/mode" % PFInfo['bus']
            else:
                cmd = "devlink dev eswitch set pci/%s mode switchdev" % PFInfo['bus']

            runcmd_output(cmd)

        sleep(5)

    def StopOVS(self):
        runcmd_output("systemctl stop %s" % self.ovs_service)

    def RestartOVS(self):
        runcmd_output("systemctl restart %s" % self.ovs_service)

    def ConfigureOVS(self):
        self.Logger.info("Setting [hw-offload=true] configuration to OVS" )
        self.RestartOVS()
        runcmd_output('ovs-vsctl set Open_vSwitch . other_config:hw-offload=true')
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
            runcmd2('ethtool -K %s hw-tc-offload on' % devName)

    def BringUpDevices(self):
        reps = self.get_reps()
        for devName in reps:
            self.Logger.info("Bringing up %s" % devName)
            runcmd2('ip link set dev %s up' % devName)

    def AttachVFs(self):
        for VFInfo in chain.from_iterable(map(lambda PFInfo: PFInfo['vfs'], self.host.PNics)):
            self.Logger.info("Binding %s" % VFInfo['bus'])
            runcmd2('echo %s > /sys/bus/pci/drivers/mlx5_core/bind' % VFInfo['bus'])
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
            self.Logger.error('Failed to read cloud_tools/.setup_info')

        if cloud_player_2_ip == self.host.name:
            conf += '\nREMOTE_SERVER=%s' % cloud_player_1_ip
        else:
            conf += '\nREMOTE_SERVER=%s' % cloud_player_2_ip

        conf += '\nREMOTE_NIC=%s' % self.host.PNics[0]['name']

        if len(self.host.PNics) > 1:
            conf += '\nREMOTE_NIC2=%s' % self.host.PNics[1]['name']

        conf += '\nB2B=1'

        if self.flow_steering_mode_supp:
            conf += '\nSTEERING_MODE=%s' % self.flow_steering_mode

        if self.dpdk:
            conf += '\nDPDK=1'

        with open('/workspace/dev_reg_conf.sh', 'w+') as f:
            f.write(conf)

    def configure_hugepages(self):
        self.Logger.info("Allocating 2MB in the RAM for DPDK")
        runcmd2('echo 2048 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages')

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