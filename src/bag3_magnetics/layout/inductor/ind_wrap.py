# -*- coding: utf-8 -*-
from typing import Mapping, Any, Optional, Type

from bag.layout.template import TemplateDB
from bag.util.immutable import Param
from bag.design.module import Module

from pybag.core import Transform

from .util import IndTemplate
from .ind_core import IndCore
from .ind_ring import IndRing
from ...schematic.ind_wrap import bag3_magnetics__ind_wrap


class IndWrap(IndTemplate):
    """A wrapper for Inductor."""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndTemplate.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__ind_wrap

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='Inductor top layer ID',
            bot_lay_id='Inductor bot layer ID; same as top layer by default',
            n_turns='Number of turns; 1 by default',
            width='Metal width for inductor turns',
            lead_width='Inductour lead width',
            spacing='Metal spacing between inductor turns',
            radius_x='radius along X-axis',
            radius_y='radius along Y-axis',
            term_sp='Spacing between inductor terminals',
            ind_shape='"Rectangle" or "Octagon"; "Octagon" by default',

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
            ind_shape='Octagon',
            w_ring=False,
            ring_specs=None,
            w_fill=False,
            fill_specs=None,
            lead_width=None,
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
        lead_width: int = self.params.get('lead_width', width)
        spacing: int = self.params['spacing']
        radius_x: int = self.params['radius_x']
        radius_y: int = self.params['radius_y']
        term_sp: int = self.params['term_sp']
        ind_shape: str = self.params['ind_shape']

        w_ring: bool = self.params['w_ring']
        ring_specs: Optional[Mapping[str, Any]] = self.params['ring_specs']

        w_fill: bool = self.params['w_fill']
        fill_specs: Optional[Mapping[str, Any]] = self.params['fill_specs']

        # make inductor core
        core_params = dict(
            lay_id=lay_id,
            bot_lay_id=bot_lay_id,
            n_turns=n_turns,
            width=width,
            spacing=spacing,
            radius_x=radius_x,
            radius_y=radius_y,
            term_sp=term_sp,
            ind_shape=ind_shape,
        )
        core_master: IndCore = self.new_template(IndCore, params=core_params)

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
                radius_x=radius_x + width // 2 + ring_spacing + ring_width // 2,
                radius_y=radius_y + width // 2 + ring_spacing + ring_width // 2,
                ring_sup=ring_sup,
                ring_pin_w=term_sp + 2 * width,
            )
            dx = dy = ring_width + ring_spacing
            ring_master: IndRing = self.new_template(IndRing, params=ring_params)
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
        term_coords = []
        for _coord in core_master.term_coords:
            term_coords.append((_coord[0] + dx, _coord[1] + dy))
        lead_width = 6100
        res1_l = lead_width // 2
        res2_l = lead_width // 4
        term0, term1 = self._draw_leads(lay_id, lead_width, term_coords, res1_l, res2_l)

        # add pins
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        self.add_pin_primitive('P1', lp[0], term0)
        self.add_pin_primitive('P2', lp[0], term1)

        # draw fill
        if ind_shape == 'Rectangle':
            n_sides = 4
        elif ind_shape == 'Octagon':
            n_sides = 8
        else:
            raise ValueError(f'Unknown ind_shape={ind_shape}. Use "Rectangle" or "Octagon".')
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
            res1_l=res1_l,
            res2_l=res2_l,
            res_w=lead_width,
            res_layer=lay_id,
            w_ring=w_ring,
            ring_sup=ring_sup,
        )
