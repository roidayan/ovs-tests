#!/bin/bash

set -e
DIR=$(cd `dirname $0` && pwd)

export WITH_VMS=1
$DIR/load-test.sh
