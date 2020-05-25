#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import signal
import time
from libs import daemon
import node
from config import config
import click


@click.group()
@click.option('-c', "--conf", default='config/config.json', help="Set config file")
@click.pass_context
def cli(ctx, conf):
    ctx.ensure_object(dict)
    cfg = config.read_cfg(conf)
    ctx.obj['cfg'] = cfg
    ctx.obj['pid'] = cfg['global']['pid']


@cli.command()
@click.pass_context
def start(ctx):
    # auto fetch boot nodes
    ctx.obj['cfg'] = config.auto_insert_boot_nodes(ctx.obj['cfg'])
    # find out latest image tag
    ctx.obj['cfg'] = config.check_image_latest_version(ctx.obj['cfg'])
    start_daemon(ctx.obj['pid'], ctx.obj['cfg'])


@cli.command()
@click.pass_context
def stop(ctx):
    stop_daemon(ctx.obj['pid'])


@cli.command()
@click.pass_context
def restart(ctx):
    stop_daemon(ctx.obj['pid'])
    print("Ready to start ....")
    time.sleep(3)
    start_daemon(ctx.obj['pid'], ctx.obj['cfg'])


def sigterm_handler(signum, frame):
    print('try to stop %s' % glue.pid)
    sys.stdout.flush()
    os.kill(glue.pid, signal.SIGTERM)
    glue.join()
    raise SystemExit(1)


def start_daemon(_pid, _cfg):
    global glue
    signal.signal(signal.SIGTERM, sigterm_handler)
    if not os.getenv("DOCKER_MODE") == "True":
        try:
            daemon.daemonize(_pid)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            raise SystemExit(1)

    glue = node.Monitor(_cfg)
    glue.daemon = True
    glue.start()

    while True:
        if not glue.is_alive():
            print('%d: 服务进程丢失，重启进程' % time.time())
            glue = node.Monitor(_cfg)
            glue.daemon = True
            glue.start()
            print('%d: new pid=%d' % (time.time(), glue.pid))
            sys.stdout.flush()
        time.sleep(_cfg['global']['monitor_interval'])


def stop_daemon(_pid):
    if os.path.exists(_pid):
        with open(_pid) as _f:
            os.kill(int(_f.read()), signal.SIGTERM)
            print("Stop success")
    else:
        print('Not running', file=sys.stderr)


if __name__ == '__main__':
    cli(obj={})
    cli.add_command(start)
    cli.add_command(stop)
    cli.add_command(restart)
