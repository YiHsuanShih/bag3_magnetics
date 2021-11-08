# -*- coding: utf-8 -*-
from typing import List, Mapping, Any, Union

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import Orientation, RoundMode, Direction, PinMode

from .util import IndTemplate


class IndRing(IndTemplate):
    """An inductor guard ring.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndTemplate.__init__(self, temp_db, params, **kwargs)
        self._outer_path_coord = None
        self._inner_path_coord = None
        self._tot_dim = 0
        self._opening = 0

    @property
    def outer_path_coord(self) -> List[List[List[PointType]]]:
        return self._outer_path_coord

    @property
    def inner_path_coord(self) -> List[List[List[PointType]]]:
        return self._inner_path_coord

    @property
    def tot_dim(self) -> int:
        return self._tot_dim

    @property
    def opening(self) -> int:
        return self._opening

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
            core_dim='Dimension of core inductor',
            core_opening='Opening of core inductor',
            core_width='Width of core inductor',
            ring_spacing='spacing between ring and inductor',
            ring_width='ring width',
            ring_gap='gap distance between rings',
            ring_turn='ring turn number',
            ring_laylist='ring layer list',
            ring_conn_n='ring connection numbers',
            ring_conn_width='ring connection width',
            ring_sup='supply name fpr ring; VSS by default',
            layid='inductor layer id',
            orient='orientation of inductor',
            pin_len='pin length',
            pin_tr_w='pin track width',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            orient=Orientation.R0,
            pin_tr_w=1,
            ring_sup='VSS',
        )

    def draw_layout(self):
        core_dim: int = self.params['core_dim']
        core_opening: int = self.params['core_opening']
        # core_width: int = self.params['core_width']
        ring_spacing: int = self.params['ring_spacing']
        ring_width: int = self.params['ring_width']
        ring_gap: int = self.params['ring_gap']
        ring_turn: int = self.params['ring_turn']
        ring_laylist: List[int] = self.params['ring_laylist']
        ring_conn_n: int = self.params['ring_conn_n']
        ring_conn_width: int = self.params['ring_conn_width']
        ring_sup: str = self.params['ring_sup']
        layid: int = self.params['layid']
        orient: Union[str, Orientation] = self.params['orient']
        if isinstance(orient, str):
            orient = Orientation[orient]
        pin_len: int = self.params['pin_len']
        pin_tr_w: int = self.params['pin_tr_w']

        self._opening = ring_opening = 3 * core_opening

        # ring half length
        tot_dim = core_dim + 2 * (ring_spacing + ring_width)
        ring_hflen = -(- tot_dim // 2) - (ring_width // 2)
        ring_arr, ring_lenarr = self._draw_ind_ring(ring_hflen, ring_width, ring_gap, ring_turn, ring_conn_n,
                                                    ring_conn_width, ring_opening, layid, ring_laylist,
                                                    orient=orient, pin_len=pin_len)

        # connect ring to VSS
        self._outer_path_coord = ring_arr[-1][-1]
        #  2-----1      2-----1
        #  |     |      3     |
        #  |     |            |
        #  |     |      4     |
        #  3-4 5-0      5-----0
        lp = self.grid.tech_info.get_lay_purp_list(ring_laylist[-1])[0]
        if orient is Orientation.R0:
            vss_path = self._outer_path_coord[1]
            ym = vss_path[0][1]
            xl = vss_path[1][0]
            xh = vss_path[0][0]
            vss_bbox = BBox(xl - ring_width // 2, ym - ring_width // 2,
                            xh + ring_width // 2, ym + ring_width // 2)
            vss_bbox1 = BBox(xl - ring_width // 2, ym - ring_width // 2,
                             xh + ring_width // 2, ym + ring_width // 2 - 4)
            self.add_pin_primitive(ring_sup, lp[0], vss_bbox, hide=True)
            # TODO: hack: VSS pin on top layer should have off-center label, otherwise EMX errors
            self.add_pin_primitive(f'{ring_sup}1', lp[0], vss_bbox1, label=ring_sup, show=False)
        else:
            # --- complete guard ring on (ind_layid - 1) --- #
            top_path = self._outer_path_coord[2]
            bot_path = self._outer_path_coord[3]
            # get track index
            warr_tidx = self.grid.coord_to_track(layid - 1, top_path[0][0], RoundMode.NEAREST)
            warr = self.add_wires(layid - 1, warr_tidx, bot_path[0][1], top_path[1][1], width=pin_tr_w)

            top_bbox = BBox(top_path[0][0] - ring_width // 2, top_path[1][1] - ring_width // 2,
                            top_path[0][0] + ring_width // 2, top_path[0][1] + ring_width // 2)
            self.connect_bbox_to_track_wires(Direction.UPPER, lp, top_bbox, warr)

            bot_bbox = BBox(bot_path[0][0] - ring_width // 2, bot_path[1][1] - ring_width // 2,
                            bot_path[0][0] + ring_width // 2, bot_path[0][1] + ring_width // 2)
            self.connect_bbox_to_track_wires(Direction.UPPER, lp, bot_bbox, warr)
            self.add_pin(ring_sup, warr, mode=PinMode.MIDDLE)

        # set properties
        self._tot_dim = tot_dim = ring_lenarr[-1] + ring_width // 2
        self._inner_path_coord = ring_arr[0]

        # set size
        tot_bbox = BBox(0, 0, tot_dim, tot_dim)
        self.set_size_from_bound_box(layid, tot_bbox, round_up=True)
