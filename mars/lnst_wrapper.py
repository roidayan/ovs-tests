#!/usr/bin/env python

__author__ = 'Roi Dayan'

import os
import sys
from subprocess import Popen
#from commands import getstatusoutput
from reg2_wrapper.common.error_code import ErrorCode
from reg2_wrapper.test_wrapper.test_wrapper import TestWrapper


wrapper_dir = os.path.abspath(__file__)
root_dir = os.path.abspath(os.path.join(wrapper_dir, '..', '..'))
recipes_dir = os.path.join(root_dir, 'recipes', 'ovs_offload')


class LnstWrapper(TestWrapper):
    """
    A class to run the e2e tests using the test wrapper methods
    """

    def __init__(self):
        super(LnstWrapper, self).__init__('Lnst Wrapper')

    def get_prog_path(self):
        return 'lnst-ctl'

    def __set_pythonpath_envvar(self):
        self.Logger.info('Setting environment variables')
        for player in self.Players:
            pythonPath = os.path.abspath(os.path.join(self.get_remote_test_path(player), os.path.pardir))
            player.putenv('PYTHONPATH', pythonPath)
            player.putenv('REGRESSION_BASE_DIR', os.path.join(pythonPath, 'tests', 'sx_regression'))
            player.putenv('TEST_SUITE_PATH', '/mswg/projects/test_suite2/shlib')

    def run_pre_commands(self):
        try:
            self.__set_pythonpath_envvar()
        except Exception, e:
            self.Logger.error('run_pre_commands failed: %s' % str(e))
            return ErrorCode.FAIL
        return ErrorCode.SUCCESS

    def run_post_commands(self):
        self.Logger.info('No post commands to do')
        return ErrorCode.SUCCESS

    def set_python(self, venv=None):
        if venv:
            p = os.path.join(venv, 'bin', 'python')
        else:
            p = 'python'
        self._python = p

    def update_pools(self):
        cmd = self._python + ' update-%s.py' % self.pools
        rc = self.call(cmd)
        self.Logger.info('Result of %s: %s' % (cmd, rc))

    def run(self):
        """
        Run the tests given
        """
        self.Logger.info("wrapper_dir=%s" % wrapper_dir)
        self.Logger.info("root_dir=%s" % root_dir)
        self.Logger.info("recipes_dir=%s" % recipes_dir)

        os.chdir(root_dir)
        self.Logger.info("pwd=%s" % os.getcwd())

        # TODO get venv from argparse
        venv = '/root/venv1'
        prog = self.get_prog_path()
        config = 'lnst-ctl.conf'
        recipe = os.path.join(recipes_dir, self.recipe)

        if venv:
            prog = os.path.join(venv, 'bin', prog)

        sys.argv = [prog, '-d', '-C', config, '--pools', self.pools]
        for a in self.alias:
            sys.argv.extend(['-A', a])

        sys.argv.extend(self.get_extra_args())
        sys.argv.extend(['run', recipe])
        cmd = ' '.join(sys.argv)

        self.set_python(venv)
        self.update_pools()

        rc = self.call(cmd)
        self.Logger.info("Result of %s: %s" % (cmd, rc))

        if rc:
            return ErrorCode.FAIL
        return ErrorCode.SUCCESS

    def call(self, cmd):
        self.Logger.info('Execute command: %s' % cmd)
        rc = Popen(cmd, shell=True).wait()
        #rc, out = getstatusoutput(cmd)
        return rc

    def configure_parser(self):
        super(LnstWrapper, self).configure_parser()
        self.add_argument('--recipe', required=True, help="lnst recipe")
        self.add_argument('--pools', required=True, help="lnst pools")
        self.add_argument('--alias', required=False, help="lnst recipe alias", action='append')


if __name__ == "__main__":
    test_name = str(__file__)
    lnst = LnstWrapper()
    rc = lnst.execute(sys.argv[1:])
    sys.exit(rc)
