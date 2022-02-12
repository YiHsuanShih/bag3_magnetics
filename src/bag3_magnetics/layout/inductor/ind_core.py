# -*- coding: utf-8 -*-
from typing import Mapping, Any, Sequence

from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle
from .util import compute_vertices, IndLayoutHelper


class IndCore(TemplateBase):
    """Inductor Core with multiple turns, 'R0' orientation"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox = BBox(0, 0, 0, 0)
        self._term_coords = []
        self._turn_coords = []

    @property
    def actual_bbox(self) -> BBox:
        return self._actual_bbox

    @property
    def term_coords(self) -> Sequence[PointType]:
        return self._term_coords

    @property
    def turn_coords(self) -> Sequence[Mapping[str, Sequence[PointType]]]:
        return self._turn_coords

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='Inductor layer ID: top layer available in the process',
            n_turns='Number of turns',
            width='Metal width for inductor turns',
            spacing='Metal spacing between inductor turns',
            radius_x='radius along X-axis',
            radius_y='radius along Y-axis',
            term_sp='Spacing between inductor terminals',
            ind_shape='"Rectangle" or "Octagon"; "Octagon" by default',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            ind_shape='Octagon',
        )

    def draw_layout(self) -> None:
        lay_id: int = self.params['lay_id']
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]

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

        # Check feasibility based on outer turn and term_sp
        if vertices[0][0][0] - vertices[0][-1][0] < term_sp + 4 * width:
            raise ValueError(f'Either increase radius_x={radius_x} or decrease term_sp={term_sp}')

        # Check feasibility based on inner turn and bridge space
        bridge_sp = spacing + 3 * width
        if n_turns > 1:
            if vertices[-1][0][0] - vertices[-1][-1][0] < bridge_sp + 4 * width:
                raise ValueError(f'Either increase radius_x={radius_x} or decrease n_turns={n_turns}')

        # Check feasibility based on inner turn and radius_y
        if vertices[-1][v_top][1] - vertices[-1][v_bot][1] < width:
            raise ValueError(f'Either increase radius_y={radius_y} or decrease n_turns={n_turns}')

        # Compute path co-ordinates
        turn_coords = []
        off_x = radius_x + width // 2
        for tidx in range(n_turns):
            _vertices = vertices[tidx]

            _bridge_xl = off_x - bridge_sp // 2
            _bridge_xr = off_x + bridge_sp // 2
            if tidx == 0:
                _start_x = off_x + (term_sp + width) // 2
                _stop_x = off_x - (term_sp + width) // 2
            else:
                _start_x, _stop_x = _bridge_xr, _bridge_xl

            _mid = n_sides // 2
            _turn_r = [(_start_x, _vertices[0][1]), (_bridge_xr, _vertices[_mid - 1][1])]
            _turn_r[1:1] = _vertices[:_mid]
            _turn_l = [(_bridge_xl, _vertices[_mid][1]), (_stop_x, _vertices[-1][1])]
            _turn_l[1:1] = _vertices[_mid:]

            # cannot draw all paths in this layout because of mysterious C++ error.
            # Create separate sub layouts with each turn.
            path_list = [
                dict(lay_id=lay_id, width=width, points=_turn_l),
                dict(lay_id=lay_id, width=width, points=_turn_r),
            ]
            _master: IndLayoutHelper = self.new_template(IndLayoutHelper, params=dict(path_list=path_list))
            self.add_instance(_master, inst_name=f'IndTurn{tidx}')
            turn_coords.append(dict(left=_turn_l, right=_turn_r))

        # Compute bridge co-ordinates
        bridge_lp = self.grid.tech_info.get_lay_purp_list(lay_id - 1)[0]
        bridge_dir = self.grid.get_direction(lay_id - 1)
        # --- top bridge --- #
        if n_turns % 2:
            # innermost top turn connects directly
            self.add_path(lp, width, [turn_coords[-1]['left'][0], turn_coords[-1]['right'][-1]], PathStyle.round)
        if n_turns > 1:
            for tidx in range(1, n_turns, 2):
                _top_l = turn_coords[tidx - 1]['left'][0]
                _top_r = turn_coords[tidx - 1]['right'][-1]
                _bot_l = turn_coords[tidx]['left'][0]
                _bot_r = turn_coords[tidx]['right'][-1]
                self.add_path(lp, width, [_bot_l, (_bot_l[0] + width, _bot_l[1]),
                                          (_top_r[0] - width, _top_r[1]), _top_r], PathStyle.round)
                self.add_path(bridge_lp, width, [(_top_l[0] - 2 * width, _top_l[1]), (_top_l[0] + width, _top_l[1]),
                                                 (_bot_r[0] - width, _bot_r[1]), (_bot_r[0] + 2 * width, _bot_r[1])],
                              PathStyle.round)
                via_bbox0 = BBox(_top_l[0] - 2 * width, _top_l[1] - width // 2, _top_l[0], _top_l[1] + width // 2)
                self.add_via(via_bbox0, bridge_lp, lp, bridge_dir, extend=False)
                via_bbox1 = BBox(_bot_r[0], _bot_r[1] - width // 2, _bot_r[0] + 2 * width, _bot_r[1] + width // 2)
                self.add_via(via_bbox1, bridge_lp, lp, bridge_dir, extend=False)

        # --- bottom bridge --- #
        if n_turns > 1:
            if n_turns % 2 == 0:
                # innermost bottom turn connects directly
                self.add_path(lp, width, [turn_coords[-1]['left'][-1], turn_coords[-1]['right'][0]],
                              PathStyle.round)
            for tidx in range(1, n_turns - 1, 2):
                _top_l = turn_coords[tidx + 1]['left'][-1]
                _top_r = turn_coords[tidx + 1]['right'][0]
                _bot_l = turn_coords[tidx]['left'][-1]
                _bot_r = turn_coords[tidx]['right'][0]
                self.add_path(lp, width, [_top_l, (_top_l[0] + width, _top_l[1]),
                                          (_bot_r[0] - width, _bot_r[1]), _bot_r], PathStyle.round)
                self.add_path(bridge_lp, width,
                              [(_bot_l[0] - 2 * width, _bot_l[1]), (_bot_l[0] + width, _bot_l[1]),
                               (_top_r[0] - width, _top_r[1]), (_top_r[0] + 2 * width, _top_r[1])],
                              PathStyle.round)
                via_bbox0 = BBox(_bot_l[0] - 2 * width, _bot_l[1] - width // 2, _bot_l[0], _bot_l[1] + width // 2)
                self.add_via(via_bbox0, bridge_lp, lp, bridge_dir, extend=False)
                via_bbox1 = BBox(_top_r[0], _top_r[1] - width // 2, _top_r[0] + 2 * width, _top_r[1] + width // 2)
                self.add_via(via_bbox1, bridge_lp, lp, bridge_dir, extend=False)

        # set attributes
        self._term_coords = [turn_coords[0]['left'][-1], turn_coords[0]['right'][0]]
        self._turn_coords = turn_coords

        # set size
        self._actual_bbox = BBox(0, 0, 2 * radius_x + width, 2 * radius_y + width)
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)
