#!/usr/bin/python

import os
import sys
import argparse
import subprocess
from glob import glob

MYNAME = os.path.basename(__file__)
MYDIR = os.path.abspath(os.path.dirname(__file__))

TESTS = sorted(glob(MYDIR + '/test-*'))
IGNORE_TESTS = [MYNAME]
SKIP_TESTS = [
    "test-tc-max-rules.sh"
]

COLOURS = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 25,
    "cyan": 36,
    "light-gray": 37,
    "dark-gray": 90,
    "light-red": 91,
    "light-green": 92,
    "light-yellow": 93,
    "light-blue": 94,
    "light-magenta": 95,
    "light-cyan": 96,
    "white": 97,
}

class ExecCmdFailed(Exception):
    def __init__(self, cmd, rc, stdout, stderr):
        self._cmd = cmd
        self._rc = rc
        self._stdout = stdout
        self._stderr = stderr

    def __str__(self):
        retval = " (exited with %d)" % self._rc
        stderr = " [%s]" % self._stderr
        return "Command execution failed%s%s" % (retval, stderr)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='verbose output')
    parser.add_argument('--stop', '-s', action='store_true',
                        help='stop on first error')
    parser.add_argument('--dry', '-d', action='store_true',
                        help='not to actually run the test')
    parser.add_argument('--from_test', '-f',
                        help='start from test')

    args = parser.parse_args()
    return args


def run(cmd):
  subp = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, close_fds=True)
  (data_stdout, data_stderr) = subp.communicate()
  if subp.returncode:
      err = ExecCmdFailed(cmd, subp.returncode, data_stdout, data_stderr)
      raise err

  return (data_stdout, data_stderr)


def deco(line, color):
    return "\033[%dm%s\033[0m" % (COLOURS[color], line)


class TestResult(object):
    def __init__(self, name, res):
        self._name = name
        self._res = res

    def __str__(self):
        res_color = {
            'SKIP': 'yellow',
            'OK': 'green',
            'DRY': 'yellow'
        }
        color = res_color.get(self._res, 'red')
        res = deco(self._res, color)
        name = deco(self._name, 'blue')
        return "Test: %-50s  %s" % (name, res)


tests_results = []

args = parse_args()

if args.from_test:
    ignore = True

for test in TESTS:
    name = os.path.basename(test)
    if name in IGNORE_TESTS:
        continue
    if ignore:
        if args.from_test != name:
            continue
        ignore = False
    print "Execute test: %s" % name
    failed = False
    res = 'OK'
    if args.dry:
        res = 'DRY'
    elif name in SKIP_TESTS:
        res = 'SKIP'
    else:
        try:
            run(test)
        except ExecCmdFailed, e:
            failed = True
            res = str(e)
    testob = TestResult(name, res)
    print testob
    if args.stop and failed:
        sys.exit(1)
