# Copyright 2013 New Dream Network, LLC (DreamHost)
# Copyright 2015 Rackspace
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import shutil
import socket

import netaddr
from neutron.agent.linux import ip_lib
from neutron.agent.linux import utils as linux_utils
from neutron.common import exceptions
from neutron.common import utils as n_utils
from neutron.i18n import _LI, _LE, _LW
from neutron.plugins.common import constants
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import importutils

from neutron_lbaas.agent import agent_device_driver
from neutron_lbaas.services.loadbalancer import constants as lb_const
from neutron_lbaas.services.loadbalancer import data_models
from neutron_lbaas.services.loadbalancer.drivers.haproxy import jinja_cfg
from neutron_lbaas.services.loadbalancer.drivers.haproxy \
    import namespace_driver

LOG = logging.getLogger(__name__)
NS_PREFIX = 'qlbaas-'
STATS_TYPE_BACKEND_REQUEST = 2
STATS_TYPE_BACKEND_RESPONSE = '1'
STATS_TYPE_SERVER_REQUEST = 4
STATS_TYPE_SERVER_RESPONSE = '2'
DRIVER_NAME = 'akanda'

STATE_PATH_V2_APPEND = 'v2'

cfg.CONF.register_opts(namespace_driver.OPTS, 'haproxy')


def get_ns_name(namespace_id):
    return NS_PREFIX + namespace_id


class AkandaDriver(agent_device_driver.AgentDeviceDriver):

    def __init__(self, conf, plugin_rpc):
        super(AkandaDriver, self).__init__(conf, plugin_rpc)
        self._loadbalancer = LoadBalancerManager(self)
        self._listener = ListenerManager(self)
        self._pool = PoolManager(self)
        self._member = MemberManager(self)
        self._healthmonitor = HealthMonitorManager(self)

    @property
    def loadbalancer(self):
        return self._loadbalancer

    @property
    def listener(self):
        return self._listener

    @property
    def pool(self):
        return self._pool

    @property
    def member(self):
        return self._member

    @property
    def healthmonitor(self):
        return self._healthmonitor

    def get_name(self):
        return DRIVER_NAME

    def undeploy_instance(self, loadbalancer_id, **kwargs):
        return

    def remove_orphans(self, known_loadbalancer_ids):
        return

    def get_stats(self, loadbalancer_id):
        return {}

    def deploy_instance(self, loadbalancer):
        return True

#    def update(self, loadbalancer):
#        pid_path = self._get_state_file_path(loadbalancer.id, 'haproxy.pid')
#        extra_args = ['-sf']
#        extra_args.extend(p.strip() for p in open(pid_path, 'r'))
#        self._spawn(loadbalancer, extra_args)
#
#    def exists(self, loadbalancer_id):
#        namespace = get_ns_name(loadbalancer_id)
#        root_ns = ip_lib.IPWrapper()
#
#        socket_path = self._get_state_file_path(
#            loadbalancer_id, 'haproxy_stats.sock', False)
#        if root_ns.netns.exists(namespace) and os.path.exists(socket_path):
#            try:
#                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
#                s.connect(socket_path)
#                return True
#            except socket.error:
#                pass
#        return False
#
#    def create(self, loadbalancer):
#        namespace = get_ns_name(loadbalancer.id)
#
#        self._plug(namespace, loadbalancer.vip_port, loadbalancer.vip_address)
#        self._spawn(loadbalancer)
#
#    def deployable(self, loadbalancer):
#        """Returns True if loadbalancer is active and has active listeners."""
#        if not loadbalancer:
#            return False
#        acceptable_listeners = [
#            listener for listener in loadbalancer.listeners
#            if (listener.provisioning_status != constants.PENDING_DELETE and
#                listener.admin_state_up)]
#        return (bool(acceptable_listeners) and loadbalancer.admin_state_up and
#                loadbalancer.provisioning_status != constants.PENDING_DELETE)
#
#    def _get_stats_from_socket(self, socket_path, entity_type):
#        try:
#            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
#            s.connect(socket_path)
#            s.send('show stat -1 %s -1\n' % entity_type)
#            raw_stats = ''
#            chunk_size = 1024
#            while True:
#                chunk = s.recv(chunk_size)
#                raw_stats += chunk
#                if len(chunk) < chunk_size:
#                    break
#
#            return self._parse_stats(raw_stats)
#        except socket.error as e:
#            LOG.warn(_LW('Error while connecting to stats socket: %s'), e)
#            return {}
#
#    def _parse_stats(self, raw_stats):
#        stat_lines = raw_stats.splitlines()
#        if len(stat_lines) < 2:
#            return []
#        stat_names = [name.strip('# ') for name in stat_lines[0].split(',')]
#        res_stats = []
#        for raw_values in stat_lines[1:]:
#            if not raw_values:
#                continue
#            stat_values = [value.strip() for value in raw_values.split(',')]
#            res_stats.append(dict(zip(stat_names, stat_values)))
#
#        return res_stats
#
#    def _get_backend_stats(self, parsed_stats):
#        for stats in parsed_stats:
#            if stats.get('type') == STATS_TYPE_BACKEND_RESPONSE:
#                unified_stats = dict((k, stats.get(v, ''))
#                                     for k, v in jinja_cfg.STATS_MAP.items())
#                return unified_stats
#
#        return {}
#
#    def _get_servers_stats(self, parsed_stats):
#        res = {}
#        for stats in parsed_stats:
#            if stats.get('type') == STATS_TYPE_SERVER_RESPONSE:
#                res[stats['svname']] = {
#                    lb_const.STATS_STATUS: (constants.INACTIVE
#                                            if stats['status'] == 'DOWN'
#                                            else constants.ACTIVE),
#                    lb_const.STATS_HEALTH: stats['check_status'],
#                    lb_const.STATS_FAILED_CHECKS: stats['chkfail']
#                }
#        return res
#
#    def _get_state_file_path(self, loadbalancer_id, kind,
#                             ensure_state_dir=True):
#        """Returns the file name for a given kind of config file."""
#        confs_dir = os.path.abspath(os.path.normpath(self.state_path))
#        conf_dir = os.path.join(confs_dir, loadbalancer_id)
#        if ensure_state_dir:
#            n_utils.ensure_dir(conf_dir)
#        return os.path.join(conf_dir, kind)
#
#    def _plug(self, namespace, port, vip_address, reuse_existing=True):
#        self.plugin_rpc.plug_vip_port(port.id)
#
#        interface_name = self.vif_driver.get_device_name(port)
#
#        if ip_lib.device_exists(interface_name,
#                                namespace=namespace):
#            if not reuse_existing:
#                raise exceptions.PreexistingDeviceFailure(
#                    dev_name=interface_name
#                )
#        else:
#            self.vif_driver.plug(
#                port.network_id,
#                port.id,
#                interface_name,
#                port.mac_address,
#                namespace=namespace
#            )
#
#        cidrs = [
#            '%s/%s' % (ip.ip_address,
#                       netaddr.IPNetwork(ip.subnet.cidr).prefixlen)
#            for ip in port.fixed_ips
#        ]
#        self.vif_driver.init_l3(interface_name, cidrs, namespace=namespace)
#
#        # Haproxy socket binding to IPv6 VIP address will fail if this address
#        # is not yet ready(i.e tentative address).
#        if netaddr.IPAddress(vip_address).version == 6:
#            device = ip_lib.IPDevice(interface_name, namespace=namespace)
#            device.addr.wait_until_address_ready(vip_address)
#
#        gw_ip = port.fixed_ips[0].subnet.gateway_ip
#
#        if not gw_ip:
#            host_routes = port.fixed_ips[0].subnet.host_routes
#            for host_route in host_routes:
#                if host_route.destination == "0.0.0.0/0":
#                    gw_ip = host_route.nexthop
#                    break
#        else:
#            cmd = ['route', 'add', 'default', 'gw', gw_ip]
#            ip_wrapper = ip_lib.IPWrapper(namespace=namespace)
#            ip_wrapper.netns.execute(cmd, check_exit_code=False)
#            # When delete and re-add the same vip, we need to
#            # send gratuitous ARP to flush the ARP cache in the Router.
#            gratuitous_arp = self.conf.haproxy.send_gratuitous_arp
#            if gratuitous_arp > 0:
#                for ip in port.fixed_ips:
#                    cmd_arping = ['arping', '-U',
#                                  '-I', interface_name,
#                                  '-c', gratuitous_arp,
#                                  ip.ip_address]
#                    ip_wrapper.netns.execute(cmd_arping, check_exit_code=False)
#
#    def _unplug(self, namespace, port):
#        self.plugin_rpc.unplug_vip_port(port.id)
#        interface_name = self.vif_driver.get_device_name(port)
#        self.vif_driver.unplug(interface_name, namespace=namespace)
#
#    def _spawn(self, loadbalancer, extra_cmd_args=()):
#        namespace = get_ns_name(loadbalancer.id)
#        conf_path = self._get_state_file_path(loadbalancer.id, 'haproxy.conf')
#        pid_path = self._get_state_file_path(loadbalancer.id,
#                                             'haproxy.pid')
#        sock_path = self._get_state_file_path(loadbalancer.id,
#                                              'haproxy_stats.sock')
#        user_group = self.conf.haproxy.user_group
#        haproxy_base_dir = self._get_state_file_path(loadbalancer.id, '')
#        jinja_cfg.save_config(conf_path,
#                              loadbalancer,
#                              sock_path,
#                              user_group,
#                              haproxy_base_dir)
#        cmd = ['haproxy', '-f', conf_path, '-p', pid_path]
#        cmd.extend(extra_cmd_args)
#
#        ns = ip_lib.IPWrapper(namespace=namespace)
#        ns.netns.execute(cmd)
#
#        # remember deployed loadbalancer id
#        self.deployed_loadbalancers[loadbalancer.id] = loadbalancer


class LoadBalancerManager(agent_device_driver.BaseLoadBalancerManager):
    def refresh(self, loadbalancer):
        print 'xxx lb refresh'

    def delete(self, loadbalancer):
        print 'xxx lb delete'

    def create(self, loadbalancer):
        print 'xxx lb create'

    def get_stats(self, loadbalancer_id):
        return {}

    def update(self, old_loadbalancer, loadbalancer):
        print 'xxx lb update'
        return


class ListenerManager(agent_device_driver.BaseListenerManager):
    def update(self, old_listener, new_listener):
        print 'xxx listener update'

    def create(self, listener):
        print 'xxx listener create'

    def delete(self, listener):
        print 'xxx listener delete'


class PoolManager(agent_device_driver.BasePoolManager):
    def update(self, old_pool, new_pool):
        print 'xxx pool update'

    def create(self, pool):
        print 'xxx pool create'


    def delete(self, pool):
        print 'xxx pool delete'


class MemberManager(agent_device_driver.BaseMemberManager):
    def update(self, old_member, new_member):
        print 'xxx member update'

    def create(self, member):
        print 'xxx member create'

    def delete(self, member):
        print 'xxx member delete'


class HealthMonitorManager(agent_device_driver.BaseHealthMonitorManager):

    def update(self, old_hm, new_hm):
        print 'xxx hm update'
        self.driver.loadbalancer.refresh(new_hm.pool.listener.loadbalancer)

    def create(self, hm):
        print 'xxx hm create'

    def delete(self, hm):
        print 'xxx hm delete'

