# -*- coding: utf-8 -*-
from typing import Mapping, Any, Sequence

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle

from .util import compute_vertices, IndTemplate


class IndCore(IndTemplate):
    """Inductor Core with multiple turns, 'R0' orientation"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndTemplate.__init__(self, temp_db, params, **kwargs)
        self._term_coords = []
        self._turn_coords = []

    @property
    def term_coords(self) -> Sequence[PointType]:
        return self._term_coords

    @property
    def turn_coords(self) -> Sequence[Mapping[str, Sequence[PointType]]]:
        return self._turn_coords

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='Inductor top layer ID',
            bot_lay_id='Inductor bot layer ID; same as top layer by default',
            n_turns='Number of turns; 1 by default',
            width='Metal width for inductor turns',
            spacing='Metal spacing between inductor turns',
            radius_x='radius along X-axis',
            radius_y='radius along Y-axis',
            term_sp='Spacing between inductor terminals, -1 for differential non-interleaved inductors',
            ind_shape='"Rectangle" or "Octagon"; "Octagon" by default',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            bot_lay_id=-1,
            n_turns=1,
            ind_shape='Octagon',
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
        ind_shape: str = self.params['ind_shape']

        if ind_shape == 'Rectangle':
            n_sides = 4
            v_bot, v_top = 0, 1
        elif ind_shape == 'Octagon':
            n_sides = 8
            v_bot, v_top = 1, 2
        else:
            raise ValueError(f'Unknown ind_shape={ind_shape}. Use "Rectangle" or "Octagon".')

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

        if term_sp != -1:
            # Check feasibility based on outer turn and term_sp
            if vertices[0][0][0] - vertices[0][-1][0] < term_sp + 4 * width:
                raise ValueError(f'Either increase radius_x={radius_x} or decrease term_sp={term_sp}')

        # Check feasibility based on inner turn and bridge space
        bridge_sp = spacing + 3 * width
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
            if gidx == 0:
                if term_sp == -1:
                    _start_x = vertices[0][0][0]
                    _stop_x = vertices[0][-1][0]
                else:
                    _start_x = off_x + (term_sp + width) // 2
                    _stop_x = off_x - (term_sp + width) // 2
            else:
                _start_x, _stop_x = _bridge_xr, _bridge_xl

            _lay_id = geo_specs['lay_id']
            turn_coords.append(self._draw_turn(_lay_id, width, n_sides, geo_specs['vertices'], _start_x, _stop_x,
                                               _bridge_xl, _bridge_xr, f'{_lay_id}_{gidx}'))

        # Compute bridge co-ordinates
        # --- top bridge --- #
        if n_geo % 2:
            # innermost top turn connects directly
            _lay_id = geo_list[-1]['lay_id']
            self._draw_bridge(turn_coords[-1]['left'][0], turn_coords[-1]['right'][-1], _lay_id, _lay_id, _lay_id,
                              width, PathStyle.extend)
        if n_geo > 1:
            for gidx in range(1, n_geo, 2):
                _bot_lay = geo_list[gidx]['lay_id']
                _top_lay = geo_list[gidx - 1]['lay_id']

                _bot_l = turn_coords[gidx]['left'][0]
                _top_r = turn_coords[gidx - 1]['right'][-1]
                self._draw_bridge(_bot_l, _top_r, _bot_lay, _top_lay, _top_lay, width, PathStyle.extend)

                _top_l = turn_coords[gidx - 1]['left'][0]
                _bot_r = turn_coords[gidx]['right'][-1]
                self._draw_bridge(_top_l, _bot_r, _top_lay, _bot_lay, _top_lay - 1, width, PathStyle.extend)

        # --- bottom bridge --- #
        if n_geo > 1:
            if n_geo % 2 == 0:
                # innermost bottom turn connects directly
                _lay_id = geo_list[-1]['lay_id']
                self._draw_bridge(turn_coords[-1]['left'][-1], turn_coords[-1]['right'][0], _lay_id, _lay_id, _lay_id,
                                  width, PathStyle.extend)
            for gidx in range(1, n_geo - 1, 2):
                _bot_lay = geo_list[gidx]['lay_id']
                _top_lay = geo_list[gidx + 1]['lay_id']

                _top_l = turn_coords[gidx + 1]['left'][-1]
                _bot_r = turn_coords[gidx]['right'][0]
                self._draw_bridge(_top_l, _bot_r, _top_lay, _bot_lay, _bot_lay, width, PathStyle.extend)

                _top_r = turn_coords[gidx + 1]['right'][0]
                _bot_l = turn_coords[gidx]['left'][-1]
                self._draw_bridge(_bot_l, _top_r, _bot_lay, _top_lay, _bot_lay - 1, width, PathStyle.extend)

        # set attributes
        self._term_coords = [turn_coords[0]['left'][-1], turn_coords[0]['right'][0]]
        self._turn_coords = turn_coords[:n_turns]

        # set size
        self._actual_bbox = BBox(0, 0, 2 * radius_x + width, 2 * radius_y + width)
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)
