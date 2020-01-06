#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import atexit
import psutil


def daemonize(pid_file):
    if os.path.exists(pid_file):
        with open(pid_file, 'r') as f:
            if psutil.pid_exists(int(f.read())):
                raise RuntimeError('Already running')
            else:
                os.remove(pid_file)

    # First fork (detaches from parent)
    try:
        if os.fork() > 0:
            raise SystemExit(0)  # Parent exit
    except OSError as e:
        raise RuntimeError('fork #1 failed.')

    os.chdir('/')
    os.umask(0)
    os.setsid()
    # Second fork (relinquish session leadership)
    try:
        if os.fork() > 0:
            raise SystemExit(0)
    except OSError as e:
        raise RuntimeError('fork #2 failed.')

    # Flush I/O buffers
    sys.stdout.flush()
    sys.stderr.flush()

    # Write the PID file
    with open(pid_file, 'w') as f:
        print(os.getpid(), file=f)

    # Arrange to have the PID file removed on exit/signal
    atexit.register(lambda: os.remove(pid_file))

    # Signal handler for termination (required)
    # def sigterm_handler(signo, frame):
    #    raise SystemExit(1)

    # signal.signal(signal.SIGTERM, sigterm_handler)


def output_to_log(*, stdin='/dev/null',
                  stdout='/dev/null',
                  stderr='/dev/null'):
    # Replace file descriptors for stdin, stdout, and stderr
    with open(stdin, 'rb', 0) as f:
        os.dup2(f.fileno(), sys.stdin.fileno())
    with open(stdout, 'ab', 0) as f:
        os.dup2(f.fileno(), sys.stdout.fileno())
    with open(stderr, 'ab', 0) as f:
        os.dup2(f.fileno(), sys.stderr.fileno())
