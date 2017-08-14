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
recipes_dir = os.path.join(root_dir, 'recipes', 'ovs_offload')


class BashTestWrapper(StandaloneWrapper):
    def __init__(self):
        super(BashTestWrapper, self).__init__('Bash Test Wrapper')

    def get_command(self, running_stage=RunningStage.RUN):
        # TODO include bash to env and then execute bash script
        cmd = self.test
        return 'abcabc'

    def __set_pythonpath_envvar(self):
        logging.info('Setting environment variables')
        for player in self.Players:
            player.putenv('CONFIG', self.config)

    def run_pre_commands(self):
        try:
            self.__set_envvar()
        except Exception, e:
            return ErrorCode.FAIL
        return ErrorCode.SUCCESS

    def configure_parser(self):
        super(BashTestWrapper, self).configure_parser()
        self.add_argument('--config', required=True, help="config")
        self.add_argument('--test', required=True, help="test")


if __name__ == "__main__":
    test_name = str(__file__)
    format_str = "%(asctime)-15s  " + test_name + "  %(levelname)-5s :  %(message)s"
    bashtest = BashTestWrapper()
    rc = bashtest.execute(sys.argv[1:])
    sys.exit(rc)
