# -*- coding: utf-8 -*-
import numpy as np
from typing import List, Mapping, Any, Optional

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
        self._center_tap_coord = None
        self._tot_dim = 0

    @property
    def lead_coord(self) -> List[PointType]:
        return self._lead_coord

    @property
    def center_tap_coord(self) -> PointType:
        return self._center_tap_coord

    @property
    def tot_dim(self) -> int:
        return self._tot_dim

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
            min_width='minimum width because of CV via',
            min_spacing='minmum spacing between turns',
            w_fill='True to have metal fill',
            fill_specs='Specs for metal fill',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            w_fill=False,
            fill_specs=None,
        )

    def draw_layout(self):
        n_turn: int = self.params['n_turn']
        layid: int = self.params['layid']
        radius: int = self.params['radius']
        spacing: int = self.params['spacing']
        width: int = self.params['width']
        opening: int = self.params['opening']
        via_width: int = self.params['via_width']
        min_width: int = self.params['min_width']
        min_spacing: int = self.params['min_spacing']
        w_fill: bool = self.params['w_fill']
        fill_specs: Optional[Mapping[str, Any]] = self.params['fill_specs']

        # inputs
        n_side = 8

        # get layer
        ind_layid = layid
        bdg_layid = layid - 1

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
        path_coord = []
        lead_coord = []
        top_coord = []
        bot_coord = []
        via_coord = []
        center_tap_coord = None
        for turn in range(n_turn):
            path, lead, top, bot, via, center_tap = self._draw_ind_turn(n_turn, radius, n_side, width, spacing, opening,
                                                                        ind_layid, bdg_layid, via_width, turn)
            path_coord.append(path)
            # get to coord list for bridges
            if turn == 0:
                lead_coord = lead
            if turn == n_turn - 1:
                center_tap_coord = center_tap
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

        # set array_box
        tot_dim = 2 * round_up(radius * np.cos(np.pi / n_side)) + width
        tot_bbox = BBox(0, 0, tot_dim, tot_dim)
        self.set_size_from_bound_box(ind_layid, tot_bbox, round_up=True)

        # add inductor ID layer
        id_lp = self.grid.tech_info.tech_params['inductor']['id_lp']
        self.add_rect(id_lp, tot_bbox)

        # add fill
        if w_fill:
            self._draw_fill(n_side, path_coord, width, ind_layid, fill_specs)

        # set properties
        self._lead_coord = lead_coord
        self._center_tap_coord = center_tap_coord
        self._tot_dim = tot_dim
