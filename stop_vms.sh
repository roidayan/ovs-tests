#!/bin/sh

# Configure timeout (in seconds).
TIMEOUT=5
VIRSH=/usr/bin/virsh

# List running domains.
list_running_domains() {
    $VIRSH list --state-running --name
}

stop_vms() {
    echo "Try to cleanly shut down all running KVM domains..."

    # Try to shutdown each domain, one by one.
    for DOMAIN in `list_running_domains`; do
        # Try to shutdown given domain.
        $VIRSH shutdown $DOMAIN
    done

    # Wait until all domains are shut down or timeout has reached.
    END_TIME=$(date -d "$TIMEOUT seconds" +%s)

    while [ $(date +%s) -lt $END_TIME ]; do
        # Break while loop when no domains are left.
        test -z "$(list_running_domains)" && break
        # Wait a litte, we don't want to DoS libvirt.
        sleep 1
    done

    # Clean up left over domains, one by one.
    for DOMAIN in `list_running_domains`; do
        # Try to shutdown given domain.
        $VIRSH destroy $DOMAIN
        # Give libvirt some time for killing off the domain.
        sleep 1
    done
}


stop_vms
