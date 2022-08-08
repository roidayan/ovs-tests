IPSEC_LIBRESWAN_DIR=$(cd "$(dirname ${BASH_SOURCE[0]})" && pwd)
. $IPSEC_LIBRESWAN_DIR/common-ipsec.sh

IPSEC_CONFIG_DIR="/etc/ipsec.d"
IPSEC_CONN="mytunnel"
IPSEC_MYTUNNEL_CONF="$IPSEC_CONFIG_DIR/${IPSEC_CONN}.conf"

function require_ipsec() {
    require_cmd ipsec
    ipsec --version | grep -q Libreswan || fail "ipsec is not Libreswan"
}

require_ipsec

function ipsec_dump_hostkeys() {
    ipsec showhostkey --dump | grep -o "RSA keyid: [A-Za-z0-9]*" | cut -d: -f 2
}

# get the first rsa key
function ipsec_get_hostkey() {
    ipsec_dump_hostkeys | head -1
}

function ipsec_get_left_key() {
    local rsaid=$1
    ipsec showhostkey --left --rsaid $rsaid
}

#note: runs on remote
function ipsec_get_right_key() {
    local rsaid=$1
    on_remote ipsec showhostkey --right --rsaid $rsaid
}

function ipsec_setup_start() {
    log "Start ipsec service"
    ipsec setup start
    on_remote ipsec setup start
}

function ipsec_setup_stop() {
    log "Stop ipsec service"
    ipsec setup stop
    on_remote ipsec setup stop
}

function ipsec_trafficstatus() {
    local conn=$1
    [ -z "$conn" ] && ipsec trafficstatus
    [ -n "$conn" ] && ipsec trafficstatus | grep -w $conn
}

function ipsec_newhostkey() {
    ipsec newhostkey
}

function ipsec_config_conn() {
    local key=`ipsec_get_hostkey`
    local remote_key=`on_remote_exec ipsec_get_hostkey`

    if [ -z "$key" ]; then
        fail "Missing ipsec local host key"
    fi

    if [ -z "$remote_key" ]; then
        fail "Missing ipsec remote host key"
    fi

    log "Create ipsec config"
    ipsec_create_conf > $IPSEC_MYTUNNEL_CONF
    log "Copy ipsec config to remote"
    scp2 $IPSEC_MYTUNNEL_CONF $REMOTE_SERVER:$IPSEC_CONFIG_DIR/
}

function ipsec_create_conf() {
    local leftsig=`ipsec_get_left_key $key`
    local rightsig=`ipsec_get_right_key $remote_key`
    echo "
conn $IPSEC_CONN
    leftid=@west
    left=$LIP
    $leftsig
    rightid=@east
    right=$RIP
    $rightsig
    authby=rsasig
    auto=ondemand"
}

function ipsec_config_setup() {
    ipsec_setup_stop
    ip a r dev $NIC $LIP/24
    ip l s dev $NIC up
    on_remote "ip a r dev $NIC $RIP/24
               ip l s dev $NIC up"
    ipsec_config_conn
    ipsec_setup_start
    ipsec auto --add $IPSEC_CONN || fail "Failed to add ipsec tunnel"
    ipsec auto --start $IPSEC_CONN || fail "Failed to start ipsec tunnel"
}

function ipsec_clear_setup() {
    ipsec auto --down $IPSEC_CONN
    ipsec auto --delete $IPSEC_CONN
    ipsec_setup_stop
}
