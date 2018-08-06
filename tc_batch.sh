#!/bin/bash

num=${1:?num}
SKIP=${2:-skip_sw}
ETH=${3:-p2p1}
set_index=${4:-0}	# if set_index == 1, all filters share the same action
set_prio=${5:-0}	# if set_prio == 1, all filters will have different prio

echo "SKIP $SKIP ETH $ETH NUM $num INDEX $set_index PRIO $set_prio"
TC=tc
$TC qdisc del dev $ETH ingress > /dev/null 2>&1

dir=/tmp
mkdir -p $dir/sw
mkdir -p $dir/hw
if [[ "$SKIP" == "skip_sw" ]]; then
	OUT="$dir/hw/batch"
	ethtool -K $ETH hw-tc-offload on
fi
if [[ "$SKIP" == "skip_hw" ]]; then
	OUT="$dir/sw/batch"
	ethtool -K $ETH hw-tc-offload off
fi

n=0
/bin/rm -rf $OUT.*

count=0
prio=1

if (( set_index == 1 )); then
	index_str="index 1"
else
	index_str=""
fi

for ((i = 0; i < 99; i++)); do
	for ((j = 0; j < 99; j++)); do
		for ((k = 0; k < 99; k++)); do
			for ((l = 0; l < 99; l++)); do
				SMAC="e4:11:$i:$j:$k:$l"
				DMAC="e4:12:$i:$j:$k:$l"
				echo "filter add dev ${ETH} prio $prio \
protocol ip \
parent ffff: \
flower \
$SKIP \
src_mac $SMAC \
dst_mac $DMAC \
action drop $index_str" >> $OUT.$n
				((count+=1))
				if (( set_prio == 1 )); then
					((prio+=1))
				fi
				let p=count%500000
				if [ $p == 0 ]; then
					((n++))
					echo -n " $count" > /dev/stderr
				fi
				if ((count>=num)); then
					break;
				fi
			done
			if ((count>=num)); then
				break;
			fi
		done
		if ((count>=num)); then
			break;
		fi
	done
	if ((count>=num)); then
		break;
	fi
done
echo > /dev/stderr

$TC qdisc add dev $ETH ingress

time for file in $OUT.*; do
	set -x
	$TC -b $file
	set +x
	ret=$?
	(( ret != 0)) && exit $ret
done

exit 0
