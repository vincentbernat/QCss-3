#!/bin/sh
### BEGIN INIT INFO
# Provides:          qcss3
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Qcss3
# Description:       layer 2 network discovery application
### END INIT INFO

PATH=/sbin:/bin:/usr/sbin:/usr/bin

user=qcss3
group=qcss3
pidfile=/var/run/qcss3/qcss3.pid
logfile=/var/log/qcss3/qcss3.log
configfile=/etc/qcss3/qcss3.cfg

test -x /usr/bin/twistd || exit 0
test -f $configfile || exit 0

version="$(twistd --version | head -1 | awk '{print $NF}')"

case "$1" in
    start)
        echo -n "Starting qcss3: twistd"
	case "$version" in
	    8.*)
		start-stop-daemon -c $user -g $group --start \
		    --quiet --exec /usr/bin/twistd -- \
                    --pidfile=$pidfile \
		    --no_save \
                    --logfile=$logfile \
	            qcss3 --config=/etc/qcss3/qcss3.cfg
		;;
	    *)
		start-stop-daemon -c $user -g $group --start \
		    --quiet --exec /usr/bin/twistd -- \
                    --pidfile=$pidfile \
		    --no_save \
                    --logfile=$logfile \
	            --python $(python -c 'import imp ; print imp.find_module("qcss3/core/tac")[1]')
		;;
	esac
        echo "."	
    ;;

    stop)
        echo -n "Stopping qcss3: twistd"
        start-stop-daemon --stop --quiet --retry=TERM/30/KILL/5  \
            --pidfile $pidfile
        echo "."	
    ;;

    restart)
        $0 stop
        sleep 1
        $0 start
    ;;

    force-reload)
        $0 restart
    ;;

    *)
        echo "Usage: /etc/init.d/qcss3 {start|stop|restart|force-reload}" >&2
        exit 1
    ;;
esac

exit 0
