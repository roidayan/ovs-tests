#!/bin/bash

#Test macsec with extended packet number enabled
#while having multiple SAs configured to check
#the functionality of macsec update function
#with extended packet number

my_dir="$(dirname "$0")"
. $my_dir/macsec-common.sh

require_remote_server

function config() {
    config_macsec_env
}

function cleanup() {
    macsec_cleanup
}

function run_test() {
    run_test_macsec 1500 ipv4 ipv4 tcp both on on
}

trap cleanup EXIT
cleanup
config
run_test
trap - EXIT
cleanup
test_done