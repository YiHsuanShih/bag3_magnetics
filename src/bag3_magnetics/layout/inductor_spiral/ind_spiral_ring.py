# -*- coding: utf-8 -*-
from typing import Mapping, Any, Sequence

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle

from .util import IndSpiralTemplate
from ..inductor.util import compute_vertices


class IndSpiralRing(IndSpiralTemplate):
    """Inductor Ring, 'R0' orientation"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndSpiralTemplate.__init__(self, temp_db, params, **kwargs)
        self._turn_coords = []

    @property
    def turn_coords(self) -> Sequence[PointType]:
        return self._turn_coords

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='Inductor top layer ID',
            bot_lay_id='Inductor bot layer ID; same as top layer by default',
            width='Metal width for ring',
            gap='Gap in ring for inductor leads',
            radius='Outermost radius',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            bot_lay_id=-1,
        )

    def draw_layout(self) -> None:
        lay_id: int = self.params['lay_id']
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]

        bot_lay_id: int = self.params['bot_lay_id']
        width: int = self.params['width']
        gap: int = self.params['gap']
        radius: int = self.params['radius']

        vertices = compute_vertices(4, 1, radius, radius, width, 0)[0]
        ring_path = [vertices[0]]
        ring_path[0:0] = vertices

        outer_radius = radius + width // 2
        ring_bbox = BBox(0, 0, 2 * outer_radius, 2 * outer_radius)

        if bot_lay_id < 1:
            # ring for interleaved spiral inductors
            # complete circle on top layer, ports "ref0" and "ref1" for the 4 leads
            self.add_path(lp, width, ring_path, PathStyle.extend, join_style=PathStyle.extend)

            # pins for EM sim
            ref0_bbox = BBox(ring_bbox.xm - width, ring_bbox.yl,
                             ring_bbox.xm + width, ring_bbox.yl + width)
            self.add_pin_primitive('ref0', lp[0], ref0_bbox, hide=True)

            ref1_bbox = BBox(ring_bbox.xm - width, ring_bbox.yh - width,
                             ring_bbox.xm + width, ring_bbox.yh)
            self.add_pin_primitive('ref1', lp[0], ref1_bbox, hide=True)
        else:
            # ring for multi layer spiral inductor
            # ring with break on top and bottom layers, complete circle on middle layers
            gap2 = -(- gap // 2)
            break_path = [(outer_radius + gap2, vertices[0][1]), (outer_radius - gap2, vertices[-1][1])]
            break_path[1:1] = vertices

            # --- top layer
            self.add_path(lp, width, break_path, PathStyle.extend, join_style=PathStyle.extend)
            # pin beside lead
            pin_bbox0 = BBox(break_path[-1][0] - width // 2, break_path[-1][1] - width // 2,
                             break_path[-1][0] + width // 2, break_path[-1][1] + width // 2)
            self.add_pin_primitive('ref_p', lp[0], pin_bbox0, hide=True)

            # via down
            _bbox_l = BBox(vertices[2][0] - width // 2, outer_radius - width,
                           vertices[2][0] + width // 2, outer_radius + width)
            _bbox_r = BBox(vertices[0][0] - width // 2, outer_radius - width,
                           vertices[0][0] + width // 2, outer_radius + width)
            _bot_lp = self.grid.tech_info.get_lay_purp_list(lay_id - 1)[0]
            _dir = self.grid.get_direction(lay_id - 1)
            self.add_via(_bbox_l, _bot_lp, lp, _dir, extend=False)
            self.add_via(_bbox_r, _bot_lp, lp, _dir, extend=False)

            # --- bot layer
            bot_lp = self.grid.tech_info.get_lay_purp_list(bot_lay_id)[0]
            self.add_path(bot_lp, width, break_path, PathStyle.extend, join_style=PathStyle.extend)
            # pin beside lead
            pin_bbox1 = BBox(break_path[0][0] - width // 2, break_path[0][1] - width // 2,
                             break_path[0][0] + width // 2, break_path[0][1] + width // 2)
            self.add_pin_primitive('ref_m', bot_lp[0], pin_bbox1, hide=True)

            # --- middle layers
            for _lay_id in range(lay_id - 1, bot_lay_id, -1):
                _lp = self.grid.tech_info.get_lay_purp_list(_lay_id)[0]
                self.add_path(_lp, width, ring_path, PathStyle.extend, join_style=PathStyle.extend)

                # via down
                _bot_lp = self.grid.tech_info.get_lay_purp_list(_lay_id - 1)[0]
                _dir = self.grid.get_direction(_lay_id - 1)
                self.add_via(_bbox_l, _bot_lp, _lp, _dir, extend=False)
                self.add_via(_bbox_r, _bot_lp, _lp, _dir, extend=False)

        # set size
        self._actual_bbox = ring_bbox
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)
