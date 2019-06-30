#!/bin/bash

if [ "$ID_NET_DRIVER" != "mlx5_core" ]; then
	exit 0
fi

if [ -z "$ID_NET_NAME_PATH" ]; then
	exit 0
fi

echo NAME=$ID_NET_NAME_PATH
