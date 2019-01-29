#!/usr/bin/python

import os
import re
import sys
import argparse
import subprocess, threading
from glob import glob
from lxml import etree
from tempfile import mkdtemp
from mlxredmine import MlxRedmine


MYNAME = os.path.basename(__file__)
MYDIR = os.path.abspath(os.path.dirname(__file__))
LOGDIR = None
DEST_DIR = os.path.join(MYDIR,"tests_conf")

TESTS = sorted(glob(MYDIR + '/test-*.sh'))
IGNORE_TESTS = [MYNAME,"test-all.py"]
SKIP_TESTS = {}
SKIP_TAGS = []

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
    def __init__(self, cmd, rc, logname):
        self._cmd = cmd
        self._rc = rc
        self._logname = logname

    def __str__(self):
        return self._logname

class Command(object):
    def __init__(self, cmd,timeout):
        self.cmd = cmd
        self.timeout = timeout
        self.process = None
        self.output = None
        self.logname = None

    def run(self):
        def target():
            #print 'Thread started'
            self.logname = os.path.join(LOGDIR, os.path.basename(self.cmd)+'.log')
            with open(self.logname, 'w') as f1:
                # piping stdout to file seems to miss stderr msgs so we use pipe
                # and write to file at the end.
                self.process = subprocess.Popen(self.cmd, shell=True, stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT, close_fds=True)
                self.out = self.process.communicate()
                f1.write(self.out[0])
            #print 'Thread finished'
            return

        try:
            thread = threading.Thread(target=target)
            thread.start()

            thread.join(int(float(self.timeout)))
            if thread.is_alive():
               self.process.terminate()
               thread.join()
               status = "Test Timeout (> %s sec) - %s "%(self.timeout,self.logname)
               raise ExecCmdFailed(self.cmd, self.process.returncode, status)
        except KeyboardInterrupt:
               self.process.terminate()
               thread.join(0)
               print 'Interrupted'
               sys.exit(1)
        status = self.out[0].splitlines()[-1].strip()
        status = strip_color(status)
        if self.process.returncode:
           status = "(%s) %s" % (status, self.logname)
           raise ExecCmdFailed(self.cmd, self.process.returncode, status)
        return status


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
    parser.add_argument('--exclude', '-e', action='append',
                        help='exclude test')
    parser.add_argument('--glob', '-g',
                        help='glob of tests')
    parser.add_argument('--parm', '-p',
                        help='Pass parm to each test')
    parser.add_argument('--exclude_tag', action='append',  
                        help='exclude all tests with tag')
    parser.add_argument('--logs_dir',
                        help='Set path to logs dir')
    args = parser.parse_args()
    return args

# add timeout
def run_test(cmd):
    logname = os.path.join(LOGDIR, os.path.basename(cmd)+'.log')
    with open(logname, 'w') as f1:
        # piping stdout to file seems to miss stderr msgs so we use pipe
        # and write to file at the end.
        subp = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, close_fds=True)
        out = subp.communicate()
        f1.write(out[0])

    status = out[0].splitlines()[-1].strip()
    status = strip_color(status)

    if subp.returncode:
        status = "(%s) %s" % (status, logname)
        raise ExecCmdFailed(cmd, subp.returncode, status)

    return status


def deco(line, color):
    return "\033[%dm%s\033[0m" % (COLOURS[color], line)


def strip_color(line):
    return re.sub("\033\[[0-9 ;]*m", '', line)


def print_result(res, out):
    res_color = {
        'SKIP': 'yellow',
        'TEST PASSED': 'green',
        'OK': 'green',
        'DRY': 'yellow',
        'FAILED': 'red',
        'IGNORED': 'yellow',
    }
    color = res_color.get(res, 'yellow')
    cres = deco(res, color)
    if out:
        if res == 'SKIP':
            out = ' (%s)' % out
        else:
            out = ' %s' % out
        cres += deco(out, color)
    print cres


def glob_tests(args, tests):
    if not args.glob:
        return
    from fnmatch import fnmatch
    for test in tests[:]:
        name = os.path.basename(test)
        if not fnmatch(name, args.glob):
            tests.remove(test)


def update_skip_according_to_xml():
    global SKIP_TESTS
    SKIP_TESTS = {}
    rm = MlxRedmine()
    print "Check redmine for open issues XML"
    for t in TESTS:
       test_name = os.path.basename(t)
       test_conf_f = "{0}".format(os.path.splitext(test_name)[0]+".xml")
       test_conf_f = os.path.join(DEST_DIR,test_conf_f)
       if not os.path.exists(test_conf_f):
          SKIP_TESTS[test_name] = "noneupstream"
          continue
       tree = etree.parse(test_conf_f) 
       for bug_en in tree.findall("./ignore/bug"):
           if bug_en.text is not None:
              task = rm.get_issue(bug_en.text)
              if rm.is_issue_open(task):
                 SKIP_TESTS[test_name] = "RM #%s: %s" % (bug_en.text, task['subject'])
              print '.',
              sys.stdout.flush()
       if t in SKIP_TESTS:
          continue
       if tree.find("./ignore/IgnoreByTestAll") is not None:
          SKIP_TESTS[test_name] = "IGNORE_FROM_TEST_ALL"
       for tag in tree.findall("./tags/tag"):
           if tag.text in SKIP_TAGS:
              SKIP_TESTS[test_name] = "Skipped by tag: %s" % (tag.text)
    print
  
def should_ignore_test(name):
    if name in IGNORE_TESTS or name in ' '.join(IGNORE_TESTS):
        return True
    else:
        return False

# TBD: parse xml for 
def get_test_timeout(test_path):
    test_name = os.path.basename(test_path)
    test_conf_f = "{0}".format(os.path.splitext(test_name)[0]+".xml")
    test_conf_f = os.path.join(DEST_DIR,test_conf_f)
    tree = etree.parse(test_conf_f)
    return tree.find("./tout").text

def main():
    args = parse_args()
    ignore = False
    global LOGDIR
    if args.logs_dir:
            LOGDIR = args.logs_dir
    else:
            LOGDIR = mkdtemp(prefix='log')
    if args.from_test:
        ignore = True
    if args.exclude:
        IGNORE_TESTS.extend(args.exclude)
    if args.exclude_tag:
        SKIP_TAGS.extend(args.exclude_tag)
    glob_tests(args, TESTS)

    print "Log dir: " + LOGDIR
    try:
        update_skip_according_to_xml()
    except KeyboardInterrupt:
        print 'Interrupted'
        sys.exit(1)

    for test in TESTS:
        name = os.path.basename(test)
        if name == MYNAME:
            continue
        if ignore:
            if args.from_test != name:
                continue
            ignore = False
        if name in SKIP_TESTS and SKIP_TESTS[name]=="noneupstream":
           continue
        print "Test: %-60s  " % deco(name, 'blue'),
        sys.stdout.flush()

        failed = False
        res = 'OK'
        out = ''

        if should_ignore_test(name):
            res = 'IGNORED'
        elif name in SKIP_TESTS:
            res = 'SKIP'
            out = SKIP_TESTS[name]
        elif args.dry:
            res = 'DRY'
        else:
            try:
                cmd = test
                if args.parm:
                    cmd += ' ' + args.parm
                cmdRun = Command(cmd,get_test_timeout(test))
                res = cmdRun.run()
            except ExecCmdFailed, e:
                failed = True
                res = 'FAILED'
                out = str(e)
            except KeyboardInterrupt:
                print 'Interrupted'
                sys.exit(1)

        print_result(res, out)

        if args.stop and failed:
            sys.exit(1)
    # end test loop


if __name__ == "__main__":
    main()
