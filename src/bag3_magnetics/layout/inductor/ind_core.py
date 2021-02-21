# -*- coding: utf-8 -*-
import numpy as np
from typing import List, Mapping, Any

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import RoundMode, PathStyle

from .util import IndTemplate, round_up


class IndCore(IndTemplate):
    """A inductor core template.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndTemplate.__init__(self, temp_db, params, **kwargs)
        self._lead_coord = None

    @property
    def lead_coord(self) -> List[PointType]:
        return self._lead_coord

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        """Returns a dictionary containing parameter descriptions.

        Override this method to return a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Mapping[str, str]
            dictionary from parameter name to description.
        """
        return dict(
            n_turn='inductor turn number',
            layid='inductor layer id',
            radius='inductor outer radius',
            spacing='inductor turn space',
            width='inductor width',
            opening='inductor opening',
            via_width='inductor via width at bridges',
            # lead_len='inductor terminal length',
            # tap_len='inductor tap length',

            # ring_spacing='spacing between ring and inductor',
            # ring_width='ring width',
            # ring_gap='gap distance between rings',
            # ring_turn='ring turn number',
            # ring_laylist='ring layer list',
            # ring_conn_n='ring connection numbers',
            # ring_conn_width='ring connection width',

            # w_ring='with ring or not',
            # w_shield='with shield or not',
            # w_dummy='with dummy or not',
            # dum_indlay='with inductor layer dummy or not',
            # dum_bdglay='with inductor-1 layer dummy or not',
            # dum_lowlay='with low layer dummy or not',
            # dum_pood='with poly/od dummy or not',
            min_width='minimum width because of CV via',
            min_spacing='minmum spacing between turns',
            # res1_l='length of metal resistor connecting to P1',
            # res2_l='length of metal resistor connecting to P2',
            # res3_l='length of metal resistor connecting to P3',
            # pin_len='pin length',
            # res_space='metal resistor space to pin',
            # tapped='True to have tap lead',
            # debug_ring='True to debug ring',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            # debug_ring=False,
        )

    def draw_layout(self):
        n_turn: int = self.params['n_turn']
        layid: int = self.params['layid']
        radius: int = self.params['radius']
        spacing: int = self.params['spacing']
        width: int = self.params['width']
        opening: int = self.params['opening']
        via_width: int = self.params['via_width']
        # lead_len: int = self.params['lead_len']
        # tap_len: int = self.params['tap_len']
        # ring_spacing: int = self.params['ring_spacing']
        # ring_width: int = self.params['ring_width']
        # ring_gap: int = self.params['ring_gap']
        # ring_turn: int = self.params['ring_turn']
        # ring_laylist: List[int] = self.params['ring_laylist']
        # ring_conn_n: List[int] = self.params['ring_conn_n']
        # ring_conn_width: int = self.params['ring_conn_width']
        # w_ring: bool = self.params['w_ring']
        # w_shield: bool = self.params['w_shield']
        # w_dummy: bool = self.params['w_dummy']
        # dum_indlay: int = self.params['dum_indlay']
        # dum_bdglay: int = self.params['dum_bdglay']
        # dum_lowlay: int = self.params['dum_lowlay']
        # dum_pood: int = self.params['dum_pood']
        min_width: int = self.params['min_width']
        min_spacing: int = self.params['min_spacing']
        # res1_l: int = self.params['res1_l']
        # res2_l: int = self.params['res2_l']
        # res3_l: int = self.params['res3_l']
        # pin_len: int = self.params['pin_len']
        # res_space: int = self.params['res_space']
        # tapped: bool = self.params['tapped']
        # debug_ring: bool = self.params['debug_ring']

        # inputs
        n_side = 8

        # get layer
        ind_layid = layid
        bdg_layid = layid - 1

        # get step phase and initial phase
        step_phase = 2 * np.pi / n_side

        # get opening on tracks
        track_op = self.grid.dim_to_num_tracks(layid, (opening + width) // 2, round_mode=RoundMode.GREATER_EQ)
        opening = self.grid.track_to_coord(layid, track_op) * 2

        # ***** 1st check *******
        if width < min_width:
            self._feasibility = False
            raise ValueError('Width is too small')
        # ***** 2nd check *******
        if spacing < min_spacing:
            self._feasibility = False
            raise ValueError('Spacing is too small')

        # Step 1: draw each turn of the layout
        lead_coord = []
        top_coord = []
        bot_coord = []
        via_coord = []
        for turn in range(n_turn):
            lead, top, bot, via = self._draw_ind_turn(n_turn, radius, n_side, width, spacing, opening, ind_layid, 
                                                      bdg_layid, via_width, turn)
            # get to coord list for bridges
            if turn == 0:
                lead_coord = lead
            # if top is not None:
            top_coord.append(top)
            # if bot is not None:
            bot_coord.append(bot)
            via_coord += via

        # ***** 2nd check *******
        # if len(via_coord) > 0:
        #     if np.abs(via_coord[0][0]) + via_width // 2 > np.ceil(inner_radius * np.sin(np.pi/n_side)):
        #         self._feasibility = False
        #         raise ValueError('Warning Inductor is not feasible!!!')

        # Step 2: draw bridges between turns
        bdg_upper_coord = []
        bdg_lower_coord = []
        # get bridge coordinates
        for i in range(n_turn):
            if i % 2 == 0 and i != n_turn-1:
                if top_coord[i][0][0] < 0:
                    bdg_upper_coord.append([top_coord[i][0], top_coord[i+1][1]])
                    bdg_lower_coord.append([top_coord[i][1], top_coord[i+1][0]])
                else:
                    bdg_upper_coord.append([top_coord[i][1], top_coord[i+1][0]])
                    bdg_lower_coord.append([top_coord[i][0], top_coord[i+1][1]])
            if i % 2 != 0 and i != n_turn-1:
                if bot_coord[i][0][0] < 0:
                    bdg_upper_coord.append([bot_coord[i][0], bot_coord[i+1][1]])
                    bdg_lower_coord.append([bot_coord[i][1], bot_coord[i+1][0]])
                else:
                    bdg_upper_coord.append([bot_coord[i][1], bot_coord[i+1][0]])
                    bdg_lower_coord.append([bot_coord[i][0], bot_coord[i+1][1]])

        # draw bridge paths
        if bdg_upper_coord:
            self.draw_path(ind_layid, width, bdg_upper_coord, end_style=PathStyle.round, join_style=PathStyle.round)
        if bdg_lower_coord:
            self.draw_path(bdg_layid, width, bdg_lower_coord, end_style=PathStyle.round, join_style=PathStyle.round)
        if via_coord:
            self.draw_via(via_coord, via_width, width, bdg_layid, ind_layid)

        # put dummy filling, guard ring and lead/tap in wrapper level

        # set array_box
        tot_dim = 2 * round_up(radius * np.cos(np.pi / n_side))
        self.set_size_from_bound_box(ind_layid, BBox(0, 0, tot_dim, tot_dim), round_up=True)
        # set properties
        self._lead_coord = lead_coord
