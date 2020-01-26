#!/bin/bash

if [ "$ID_NET_DRIVER" != "mlx5_core" ]; then
    exit 0
fi

if [ -z "$ID_NET_NAME_SLOT" ]; then
    echo NAME="${ID_NET_NAME_SLOT%%np[[:digit:]]}"
    exit 0
fi

if [ -z "$ID_NET_NAME_PATH" ]; then
    echo NAME="${ID_NET_NAME_PATH%%np[[:digit:]]}"
    exit 0
fi
