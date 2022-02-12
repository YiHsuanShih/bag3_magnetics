# -*- coding: utf-8 -*-
from typing import Mapping, Any, Sequence

from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle
from .util import compute_vertices


class IndRing(TemplateBase):
    """Inductor Ring, 'R0' orientation"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox = BBox(0, 0, 0, 0)
        self._turn_coords = []

    @property
    def actual_bbox(self) -> BBox:
        return self._actual_bbox

    @property
    def turn_coords(self) -> Sequence[PointType]:
        return self._turn_coords

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='Inductor layer ID: top layer available in the process',
            width='Metal width for ring',
            gap='Gap in ring for inductor leads',
            radius_x='radius along X-axis',
            radius_y='radius along Y-axis',
            ring_sup='supply name for ring; VSS by default',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            ring_sup='VSS',
        )

    def draw_layout(self) -> None:
        lay_id: int = self.params['lay_id']
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]

        width: int = self.params['width']
        gap: int = self.params['gap']
        radius_x: int = self.params['radius_x']
        radius_y: int = self.params['radius_y']
        ring_sup: str = self.params['ring_sup']

        vertices = compute_vertices(4, 1, radius_x, radius_y, width, 0)[0]

        # Compute path co-ordinates
        off_x = radius_x + width // 2
        gap2 = -(- gap // 2)
        _turn = [(off_x + gap2, vertices[0][1]), (off_x - gap2, vertices[-1][1])]
        _turn[1:1] = vertices
        self.add_path(lp, width, _turn, PathStyle.extend, join_style=PathStyle.extend)

        # --- complete guard ring on (lay_id - 1) --- #
        #     R0
        #   2-----1
        #   |     |
        #   |     |
        #   3-----0
        bot_path = [(off_x - gap2 - width, vertices[-1][1]), (off_x + gap2 + width, vertices[0][1])]
        bot_lay_id = lay_id - 1
        bot_lp = self.grid.tech_info.get_lay_purp_list(bot_lay_id)[0]
        self.add_path(bot_lp, width, bot_path, PathStyle.extend, join_style=PathStyle.extend)

        bot_dir = self.grid.get_direction(bot_lay_id)
        via_bbox0 = BBox(bot_path[0][0] - width // 2, bot_path[0][1] - width // 2,
                         _turn[-1][0] + width // 2, bot_path[0][1] + width // 2)
        self.add_via(via_bbox0, bot_lp, lp, bot_dir, extend=False)
        via_bbox1 = BBox(_turn[0][0] - width // 2, bot_path[1][1] - width // 2,
                         bot_path[1][0] + width // 2, bot_path[1][1] + width // 2)
        self.add_via(via_bbox1, bot_lp, lp, bot_dir, extend=False)

        pin_bbox = BBox(off_x - width, _turn[0][1] - width // 2, off_x + width, _turn[0][1] + width // 2)
        self.add_pin_primitive(ring_sup, bot_lp[0], pin_bbox)

        # set attributes
        self._turn_coords = _turn

        # set size
        self._actual_bbox = BBox(0, 0, 2 * radius_x + width, 2 * radius_y + width)
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)
