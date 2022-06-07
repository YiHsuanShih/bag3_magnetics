# -*- coding: utf-8 -*-
from typing import Mapping, Any, Optional, Type

from bag.layout.template import TemplateDB
from bag.util.immutable import Param
from bag.design.module import Module

from pybag.core import Transform

from ..inductor.util import IndTemplate
from .tcoil_core import TcoilDiffCore
from .tcoil_ring import TcoilDiffRing
from ...schematic.tcoil_diff_wrap import bag3_magnetics__tcoil_diff_wrap


class TcoilDiffWrap(IndTemplate):
    """A wrapper for differential t-coil."""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndTemplate.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__tcoil_diff_wrap

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='T-coil top layer ID',
            bot_lay_id='T-coil bot layer ID; same as top layer by default',
            n_turns='Number of turns; 1 by default',
            width='Metal width for t-coil turns',
            spacing='Metal spacing between t-coil turns',
            radius_x='radius along X-axis',
            radius_y='radius along Y-axis',
            term_sp='Spacing between t-coil terminals',
            tcoil_shape='"Rectangle" or "Octagon"; "Octagon" by default',

            w_ring='True to have guard ring, False by default',
            ring_specs='Specs for guard ring, Optional',

            w_fill='True to have metal fill',
            fill_specs='Specs for metal fill',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            bot_lay_id=-1,
            n_turns=1,
            tcoil_shape='Octagon',
            w_ring=False,
            ring_specs=None,
            w_fill=False,
            fill_specs=None,
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

        assert bot_lay_id == lay_id - 1 and n_turns == 2, 'Not supported in layout generator currently'

        width: int = self.params['width']
        spacing: int = self.params['spacing']
        radius_x: int = self.params['radius_x']
        radius_y: int = self.params['radius_y']
        term_sp: int = self.params['term_sp']
        tcoil_shape: str = self.params['tcoil_shape']

        w_ring: bool = self.params['w_ring']
        ring_specs: Optional[Mapping[str, Any]] = self.params['ring_specs']

        w_fill: bool = self.params['w_fill']
        fill_specs: Optional[Mapping[str, Any]] = self.params['fill_specs']

        # make t-coil core
        core_params = dict(
            lay_id=lay_id,
            bot_lay_id=bot_lay_id,
            n_turns=n_turns,
            width=width,
            spacing=spacing,
            radius_x=radius_x,
            radius_y=radius_y,
            term_sp=term_sp,
            tcoil_shape=tcoil_shape,
        )
        core_master: TcoilDiffCore = self.new_template(TcoilDiffCore, params=core_params)

        # make inductor guard ring
        if w_ring:
            ring_width: int = ring_specs['width']
            ring_spacing: int = ring_specs['spacing']
            ring_sup: str = ring_specs.get('ring_sup', 'VSS')
            ring_params = dict(
                lay_id=lay_id,
                bot_lay_id=bot_lay_id,
                width=ring_width,
                gap=term_sp + 2 * width + 2 * ring_spacing + ring_width,
                gap_t=core_master.bridge_sp + width + 2 * ring_spacing + ring_width,
                radius_x=radius_x + width // 2 + ring_spacing + ring_width // 2,
                radius_y=radius_y + width // 2 + ring_spacing + ring_width // 2,
                ring_sup=ring_sup,
            )
            dx = dy = ring_width + ring_spacing
            ring_master: TcoilDiffRing = self.new_template(TcoilDiffRing, params=ring_params)
            ring_inst = self.add_instance(ring_master, inst_name='XRING')
            self.reexport(ring_inst.get_port(ring_sup))
            ring_turn_coords = ring_master.turn_coords
            self._actual_bbox = ring_master.actual_bbox
        else:
            ring_width = 0
            ring_sup = ''
            ring_turn_coords = []
            dx = dy = 0
            self._actual_bbox = core_master.actual_bbox

        # place inductor core
        self.add_instance(core_master, inst_name='XCORE', xform=Transform(dx=dx, dy=dy))

        # draw leads
        terms = {}
        term_coords = []
        for _coord in core_master.term_coords:
            term_coords.append((_coord[0] + dx, _coord[1] + dy))
        res1_l = width // 2
        res2_l = width // 4
        terms[1], terms[4] = self._draw_leads(lay_id, width, term_coords, res1_l, res2_l, self._actual_bbox.yl)

        center_tap_coords = []
        for _coord in core_master.center_tap_coords:
            center_tap_coords.append((_coord[0] + dx, _coord[1] + dy))
        res3_l = width
        res4_l = width // 3
        terms[3], terms[6] = self._draw_leads(lay_id, width, center_tap_coords, res3_l, res4_l, self._actual_bbox.yh,
                                              up=True)

        bot_terms = {}
        bot_term_coords = []
        for _coord in core_master.bot_term_coords:
            bot_term_coords.append((_coord[0] + dx, _coord[1] + dy))
        bot_terms[5], bot_terms[2] = self._draw_leads(lay_id - 2, width, bot_term_coords, res1_l, res2_l,
                                                      self._actual_bbox.yl)

        # add pins
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        for key, _term in terms.items():
            self.add_pin_primitive(f'P{key}', lp[0], _term)

        lp_bot = self.grid.tech_info.get_lay_purp_list(lay_id - 2)[0]
        for key, _term in bot_terms.items():
            self.add_pin_primitive(f'P{key}', lp_bot[0], _term)

        # draw fill
        if tcoil_shape == 'Rectangle':
            n_sides = 4
        elif tcoil_shape == 'Octagon':
            n_sides = 8
        else:
            raise ValueError(f'Unknown tcoil_shape={tcoil_shape}. Use "Rectangle" or "Octagon".')
        if w_fill:
            for _specs in fill_specs:
                self._draw_fill(n_sides, _specs, core_master.turn_coords, width, dx, dy, ring_turn_coords, ring_width)

        # add inductor ID layer
        id_lp = self.grid.tech_info.tech_params['inductor'].get('id_lp', [])
        for _lp in id_lp:
            self.add_rect(_lp, self._actual_bbox)

        # set size
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)

        # get schematic parameters
        self.sch_params = dict(
            res_params={
                1: {'w': width, 'l': res1_l, 'layer': lay_id},
                2: {'w': width, 'l': res2_l, 'layer': lay_id - 2},
                3: {'w': width, 'l': res3_l, 'layer': lay_id},
                4: {'w': width, 'l': res2_l, 'layer': lay_id},
                5: {'w': width, 'l': res1_l, 'layer': lay_id - 2},
                6: {'w': width, 'l': res4_l, 'layer': lay_id},
            },
            w_ring=w_ring,
            ring_sup=ring_sup,
        )
