# SPDX-License-Identifier: Apache-2.0
# Copyright 2020 Blue Cheetah Analog Design Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# -*- coding: utf-8 -*-

from typing import Mapping, Any

import pkg_resources
from pathlib import Path

from bag.design.module import Module
from bag.design.database import ModuleDB
from bag.util.immutable import Param


# noinspection PyPep8Naming
class bag3_magnetics__ind_wrap(Module):
    """Module for library bag3_magnetics cell ind_wrap.

    Fill in high level description here.
    """

    yaml_file = pkg_resources.resource_filename(__name__,
                                                str(Path('netlist_info',
                                                         'ind_wrap.yaml')))

    def __init__(self, database: ModuleDB, params: Param, **kwargs: Any) -> None:
        Module.__init__(self, self.yaml_file, database, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Mapping[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            res1_l='Length of first metal resistor',
            res2_l='Length of second metal resistor',
            res3_l='Length of center metal resistor',
            res_w='Width of metal resistors',
            res_layer='Layer of metal resistor',
            center_tap='True to have center tap',
            w_ring='True to have guard ring, False by default',
            ring_sup='supply name for ring; VSS by default',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(res3_l=0, w_ring=False, center_tap=False, ring_sup='VSS')

    def design(self, res1_l: int, res2_l: int, res3_l: int, res_w: int, res_layer: int, center_tap: bool,
               w_ring: bool, ring_sup: str) -> None:
        """To be overridden by subclasses to design this module.

        This method should fill in values for all parameters in
        self.parameters.  To design instances of this module, you can
        call their design() method or any other ways you coded.

        To modify schematic structure, call:

        rename_pin()
        delete_instance()
        replace_instance_master()
        reconnect_instance_terminal()
        restore_instance()
        array_instance()
        """
        self.instances['XRP'].design(w=res_w, l=res1_l, layer=res_layer)
        self.instances['XRM'].design(w=res_w, l=res2_l, layer=res_layer)
        if center_tap:
            self.instances['XRC'].design(w=res_w, l=res3_l, layer=res_layer)
        else:
            self.remove_instance('XRC')
            self.remove_pin('PC')
        if not w_ring:
            self.remove_pin('VSS')
            self.remove_instance('XNC')
        else:
            if ring_sup != 'VSS':
                self.rename_pin('VSS', ring_sup)
                self.reconnect_instance_terminal('XNC', 'noConn', ring_sup)
