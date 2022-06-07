# -*- coding: utf-8 -*-
from typing import Mapping, Any, Sequence

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle

from ..inductor.util import compute_vertices, IndTemplate


class TcoilDiffCore(IndTemplate):
    """Differential t-coil Core with 1 turn, 'R0' orientation"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndTemplate.__init__(self, temp_db, params, **kwargs)
        self._term_coords = []
        self._bot_term_coords = []
        self._center_tap_coords = []
        self._turn_coords = []
        self._bridge_sp = 0

    @property
    def term_coords(self) -> Sequence[PointType]:
        return self._term_coords

    @property
    def bot_term_coords(self) -> Sequence[PointType]:
        return self._bot_term_coords

    @property
    def center_tap_coords(self) -> Sequence[PointType]:
        return self._center_tap_coords

    @property
    def turn_coords(self) -> Sequence[Mapping[str, Sequence[PointType]]]:
        return self._turn_coords

    @property
    def bridge_sp(self) -> int:
        return self._bridge_sp

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='Tcoil top layer ID',
            bot_lay_id='Tcoil bot layer ID; same as top layer by default',
            n_turns='Number of turns; 1 by default',
            width='Metal width for inductor turns',
            spacing='Metal spacing between inductor turns',
            radius_x='radius along X-axis',
            radius_y='radius along Y-axis',
            term_sp='Spacing between inductor terminals',
            tcoil_shape='"Rectangle" or "Octagon"; "Octagon" by default',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            bot_lay_id=-1,
            n_turns=1,
            tcoil_shape='Octagon',
        )

    def draw_layout(self) -> None:
        lay_id: int = self.params['lay_id']
        bot_lay_id: int = self.params['bot_lay_id']
        if bot_lay_id < 1:
            bot_lay_id = lay_id

        if bot_lay_id < lay_id:
            n_turns = 2
        else:
            n_turns: int = self.params['n_turns']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        radius_x: int = self.params['radius_x']
        radius_y: int = self.params['radius_y']
        term_sp: int = self.params['term_sp']
        tcoil_shape: str = self.params['tcoil_shape']

        if tcoil_shape == 'Rectangle':
            n_sides = 4
            v_bot, v_top = 0, 1
        elif tcoil_shape == 'Octagon':
            n_sides = 8
            v_bot, v_top = 1, 2
        else:
            raise ValueError(f'Unknown tcoil_shape={tcoil_shape}. Use "Rectangle" or "Octagon".')

        vertices = compute_vertices(n_sides, n_turns, radius_x, radius_y, width, spacing)
        # compute geometry list
        if bot_lay_id == lay_id:
            # single or multi turn inductor on same layer
            geo_list = [{'vertices': vertices[tidx], 'lay_id': lay_id} for tidx in range(n_turns)]
            n_geo = n_turns
        else:
            # single or multi turn inductor on multiple layers
            geo_list = [{'vertices': vertices[(lay_id - lidx) % 2], 'lay_id': lidx}
                        for lidx in range(lay_id, bot_lay_id - 1, -1)]
            n_geo = lay_id - bot_lay_id + 1

        # Check feasibility based on outer turn and term_sp
        if vertices[0][0][0] - vertices[0][-1][0] < term_sp + 4 * width:
            raise ValueError(f'Either increase radius_x={radius_x} or decrease term_sp={term_sp}')

        # Check feasibility based on inner turn and bridge space
        self._bridge_sp = bridge_sp = spacing + 3 * width
        if n_turns > 1:
            if vertices[-1][0][0] - vertices[-1][-1][0] < bridge_sp + 2 * width:
                raise ValueError(f'Either increase radius_x={radius_x} or decrease n_turns={n_turns}')

        # Check feasibility based on inner turn and radius_y
        if vertices[-1][v_top][1] - vertices[-1][v_bot][1] < width:
            raise ValueError(f'Either increase radius_y={radius_y} or decrease n_turns={n_turns}')

        # Compute path co-ordinates
        turn_coords = []
        off_x = radius_x + width // 2
        for gidx, geo_specs in enumerate(geo_list):
            _bridge_xl = off_x - bridge_sp // 2
            _bridge_xr = off_x + bridge_sp // 2
            _start_x = off_x + (term_sp + width) // 2
            _stop_x = off_x - (term_sp + width) // 2

            _lay_id = geo_specs['lay_id']
            turn_coords.append(self._draw_turn(_lay_id, width, n_sides, geo_specs['vertices'], _start_x, _stop_x,
                                               _bridge_xl, _bridge_xr, f'{_lay_id}_{gidx}'))

        # Compute bridge co-ordinates
        # --- top bridge --- #
        _bot_lay = geo_list[1]['lay_id']
        _top_lay = geo_list[0]['lay_id']

        _bot_l = turn_coords[1]['left'][0]
        _top_r = turn_coords[0]['right'][-1]
        self._draw_bridge(_bot_l, _top_r, _bot_lay, _top_lay, _top_lay, width)

        _top_l = turn_coords[0]['left'][0]
        _bot_r = turn_coords[1]['right'][-1]
        self._draw_bridge(_top_l, _bot_r, _top_lay, _bot_lay, _top_lay - 1, width)

        self._center_tap_coords = [_top_l, _top_r]

        # --- bottom: terminals --- #
        self._draw_second_terms(turn_coords[-1]['left'][-1], turn_coords[-1]['right'][0], geo_list[-1]['lay_id'], width)

        # set attributes
        self._term_coords = [turn_coords[0]['left'][-1], turn_coords[0]['right'][0]]
        self._turn_coords = turn_coords[:n_turns]

        # set size
        self._actual_bbox = BBox(0, 0, 2 * radius_x + width, 2 * radius_y + width)
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)

    def _draw_second_terms(self, coord_l: PointType, coord_r: PointType, lay_id: int, width: int) -> None:
        style = PathStyle.truncate
        w2 = width // 2

        # extend terminals down
        _lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        coord_l_bot = (coord_l[0], coord_l[1] - w2 - 2 * width)
        self.add_path(_lp, width, [coord_l, coord_l_bot], style, join_style=style)
        coord_r_bot = (coord_r[0], coord_r[1] - w2 - 2 * width)
        self.add_path(_lp, width, [coord_r, coord_r_bot], style, join_style=style)

        # via down to lay_id - 1
        via_bbox_l = BBox(coord_l_bot[0] - w2, coord_l_bot[1], coord_l_bot[0] + w2, coord_l_bot[1] + 2 * width)
        via_bbox_r = BBox(coord_r_bot[0] - w2, coord_r_bot[1], coord_r_bot[0] + w2, coord_r_bot[1] + 2 * width)
        bot_lp = self.grid.tech_info.get_lay_purp_list(lay_id - 1)[0]
        top_lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        bot_dir = self.grid.get_direction(lay_id - 1)
        self.add_via(via_bbox_l, bot_lp, top_lp, bot_dir, extend=False)
        self.add_via(via_bbox_r, bot_lp, top_lp, bot_dir, extend=False)

        self._bot_term_coords = [coord_l_bot, coord_r_bot]
