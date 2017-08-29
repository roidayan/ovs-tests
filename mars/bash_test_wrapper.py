#!/usr/bin/env python

__author__ = 'Roi Dayan'

import os
import sys
from subprocess import Popen
#from commands import getstatusoutput
from reg2_wrapper.common.error_code import ErrorCode
from reg2_wrapper.test_wrapper.standalone_wrapper import StandaloneWrapper
from reg2_wrapper.utils.parser.cmd_argument import RunningStage


wrapper_dir = os.path.abspath(__file__)
root_dir = os.path.abspath(os.path.join(wrapper_dir, '..', '..'))
ovs_tests_dir = os.path.join('..', '..', 'ovs-tests')


class BashTestWrapper(StandaloneWrapper):
    def __init__(self):
        super(BashTestWrapper, self).__init__('Bash Test Wrapper')

    def get_prog_path(self):
        return os.path.join(ovs_tests_dir, self.test)

    def __set_envvar(self):
        self.Logger.info('Setting environment variables')
        for player in self.Players:
            player.putenv('CONFIG', self.config)
            if self.option:
                for o in self.option:
                    o = o.split('=')
                    player.putenv(o[0], o[1])
            if self.env:
                for o in self.env.split():
                    o = o.split('=')
                    player.putenv(o[0], o[1])

    def run_pre_commands(self):
        try:
            self.__set_envvar()
        except Exception, e:
            self.Logger.error('run_pre_commands failed: %s' % str(e))
            return ErrorCode.FAIL
        return ErrorCode.SUCCESS

    def configure_parser(self):
        super(BashTestWrapper, self).configure_parser()
        self.add_argument('--config', required=True, help="config")
        self.add_argument('--test', required=True, help="test")
        self.add_argument('--env', required=False, help="env options")
        self.add_argument('--option', required=False, help="env option", action='append')


if __name__ == "__main__":
    test_name = str(__file__)
    bashtest = BashTestWrapper()
    rc = bashtest.execute(sys.argv[1:])
    sys.exit(rc)
