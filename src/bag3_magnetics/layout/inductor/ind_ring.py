# -*- coding: utf-8 -*-
from typing import List, Mapping, Any, Union

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import Orientation

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
            layid='inductor layer id',
            orient='orientation of inductor',
            pin_len='pin length',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            orient=Orientation.R0,
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
        layid: int = self.params['layid']
        orient: Union[str, Orientation] = self.params['orient']
        if isinstance(orient, str):
            orient = Orientation[orient]
        pin_len: int = self.params['pin_len']

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
        if orient is Orientation.R0:
            vss_path = self._outer_path_coord[1]
            ym = vss_path[0][1]
            xl = vss_path[1][0]
            xh = vss_path[0][0]
            vss_bbox = BBox(xl - ring_width // 2, ym - ring_width // 2,
                            xh + ring_width // 2, ym + ring_width // 2)
            vss_bbox1 = BBox(xl - ring_width // 2, ym - ring_width // 2,
                             xh + ring_width // 2, ym + ring_width // 2 - 4)
        else:
            vss_path = self._outer_path_coord[0]
            xm = vss_path[0][0]
            yl = vss_path[0][1]
            yh = vss_path[1][1]
            vss_bbox = BBox(xm - ring_width // 2, yl - ring_width // 2,
                            xm + ring_width // 2, yh + ring_width // 2)
            vss_bbox1 = BBox(xm - ring_width // 2, yl - ring_width // 2,
                             xm + ring_width // 2 - 4, yh + ring_width // 2)
        lp = self.grid.tech_info.get_lay_purp_list(ring_laylist[-1])[0]
        self.add_pin_primitive('VSS', lp[0], vss_bbox, hide=True)
        # TODO: hack: VSS pin on top layer should have off-center label, otherwise EMX errors
        self.add_pin_primitive('VSS1', lp[0], vss_bbox1, label='VSS', show=False)

        # set properties
        self._tot_dim = tot_dim = ring_lenarr[-1] + ring_width // 2
        self._inner_path_coord = ring_arr[0]

        # set size
        tot_bbox = BBox(0, 0, tot_dim, tot_dim)
        self.set_size_from_bound_box(layid, tot_bbox, round_up=True)
