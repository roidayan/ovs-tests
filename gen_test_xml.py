import os
import sys
from glob import glob
from lxml import etree
from xml.etree import ElementTree
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, Comment
from mlxredmine import MlxRedmine
import argparse

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

MYNAME = os.path.basename(__file__)
MYDIR = os.path.abspath(os.path.dirname(__file__))
DEST_DIR = os.path.join(MYDIR,"tests_conf")
TAGS = []
BUGS = []

def deco(line, color):
    return "\033[%dm%s\033[0m" % (COLOURS[color], line)

# https://lxml.de/tutorial.html for how to use
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


def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="	")

def create_xml_file(testname,desc,owner,tout,tagsl,ignore_by_test_all,bugsl):
 testdef_ = etree.Element('testdef')

 # info section
 info_ = etree.SubElement(testdef_, 'info')
 etree.SubElement(info_, 'name').text = testname
 desc_ = etree.SubElement(info_, 'desc').text = desc
 owner_ = etree.SubElement(info_, 'owner').text = owner

 # timeout section
 tout_ = etree.SubElement(testdef_, 'tout').text = tout

 # tags section
 tags_ = etree.SubElement(testdef_, 'tags')
 for tag_name in tagsl:
  etree.SubElement(tags_, 'tag').text = tag_name

 # ignore by bug section
 ignore_ = etree.SubElement(testdef_, 'ignore')
 if bugsl != "":
  rm = MlxRedmine()
  for bugn in bugsl:
    try:
        task = rm.get_issue(bugn)
    except:
	print_result('FAILED', "RM number \'%s\' is not Valid"%bugn)
        sys.exit(1)
    etree.SubElement(ignore_, 'bug').text = bugn
 else:
  etree.SubElement(ignore_, 'bug')
 if ignore_by_test_all:
    etree.SubElement(ignore_,'IgnoreByTestAll')
 outputfilen = "{0}".format(testname+".xml")
 outputfilen = os.path.join(DEST_DIR,outputfilen)
 with open(outputfilen, "w") as text_file:
    text_file.write("{0}".format(etree.tostring(testdef_, pretty_print=True)))

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fname',required=True,
                         help='Pass the file name of the test (Mandatory)')
    parser.add_argument('--desc',required=True,
                         help='Pass a small description of the test (Mandatory)')                         
    parser.add_argument('--owner',required=True,
                         help='test owner name')
    parser.add_argument('--tout', default=1000,
                        help='time out for the test (default 1000)')
    parser.add_argument('--tag', action='append',required=True,
                        help='associate a tag(s) with this test (Mandatory)')
    parser.add_argument('--ignore_test', action='store_true',
                        help='ignore this test when running test-all-dev.py')
    parser.add_argument('--bug', action='append',
                        help='associate a bug(s) with this test')

    args = parser.parse_args()
    return args

if not os.path.exists(DEST_DIR):
   os.makedirs(DEST_DIR)
args = parse_args()
test_name = os.path.splitext(args.fname)[0]
if args.tag:
        TAGS.extend(args.tag)
if args.bug:
        BUGS.extend(args.bug)
create_xml_file(test_name,args.desc,args.owner,args.tout,TAGS,args.ignore_test,BUGS)
