# Copyright (c) 2013 OpenStack Foundation.
# Copyright (c) 2015 Rackspace.
# All Rights Reserved.
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

from neutron_lbaas.drivers.common import agent_driver_base
from neutron_lbaas.drivers.akanda import driver as akanda_driver


class AkandaPluginDriver(agent_driver_base.AgentDriverBase):
    device_driver = akanda_driver.DRIVER_NAME

