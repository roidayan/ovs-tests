#!/bin/bash

set -e

HOST=`hostname -s`
SHORT=`hostname -s | sed 's/-r-vrt-//'`

echo "HOST $HOST"
echo "SHORT $SHORT"

SCRIPT="load-${SHORT}.sh"

echo "SCRIPT $SCRIPT"

DIR=$(cd `dirname $0` && pwd)

$DIR/$SCRIPT
