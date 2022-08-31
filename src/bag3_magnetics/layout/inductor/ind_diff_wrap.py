# -*- coding: utf-8 -*-
from typing import Mapping, Any, Optional, Type

from bag.layout.template import TemplateDB
from bag.util.immutable import Param
from bag.design.module import Module

from pybag.core import Transform
from pybag.enum import Orientation, PathStyle

from .util import IndTemplate
from .ind_core import IndCore
from .ind_ring import IndRing
from ...schematic.ind_diff_wrap import bag3_magnetics__ind_diff_wrap


class IndDiffWrap(IndTemplate):
    """A wrapper for differential non-interleaved inductors."""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndTemplate.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__ind_diff_wrap

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='Inductor top layer ID',
            bot_lay_id='Inductor bot layer ID; same as top layer by default',
            n_turns='Number of turns; 1 by default',
            width='Metal width for inductor turns',
            spacing='Metal spacing between inductor turns',
            radius_x='radius along X-axis in R0 orientation of single inductor, will be rotated by 90 degrees',
            radius_y='radius along Y-axis in R0 orientation of single inductor, will be rotated by 90 degrees',
            term_sp='Spacing between inductor terminals',
            common_term='True to have one common terminal for differential inductors; False by default',

            w_ring='True to have guard ring, False by default',
            ring_specs='Specs for guard ring, Optional',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            bot_lay_id=-1,
            n_turns=1,
            common_term=False,
            w_ring=False,
            ring_specs=None,
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
        common_term: bool = self.params['common_term']

        w_ring: bool = self.params['w_ring']
        ring_specs: Optional[Mapping[str, Any]] = self.params['ring_specs']

        # make inductor core
        core_params = dict(
            lay_id=lay_id,
            bot_lay_id=bot_lay_id,
            n_turns=n_turns,
            width=width,
            spacing=spacing,
            radius_x=radius_x,
            radius_y=radius_y,
            term_sp=-1,
            ind_shape='Rectangle',
        )
        core_master: IndCore = self.new_template(IndCore, params=core_params)

        # make inductor guard ring
        if w_ring:
            ring_width: int = ring_specs['width']
            ring_spacing: int = ring_specs['spacing']
            ring_gap_spacing: int = ring_specs.get('gap_spacing', ring_spacing)
            gap = term_sp + 2 * width + 2 * ring_gap_spacing + ring_width
            if common_term:
                gap_top = width + 2 * ring_gap_spacing + ring_width
                ring_sup_top = 'P2_R'
            else:
                gap_top = gap
                ring_sup_top = 'P24_R'
            ring_params = dict(
                lay_id=lay_id,
                bot_lay_id=bot_lay_id,
                width=ring_width,
                gap=gap,
                gap_top=gap_top,
                radius_x=term_sp // 2 + 2 * radius_y + width + ring_spacing + ring_width // 2,
                radius_y=radius_x + width // 2 + ring_spacing + ring_width // 2,
                ring_sup='P13_R',
                ring_sup_top=ring_sup_top,
                ring_pin_w=term_sp + 2 * width,
            )
            dx = dy = ring_width + ring_spacing
            ring_master: IndRing = self.new_template(IndRing, params=ring_params)
            ring_inst = self.add_instance(ring_master, inst_name='XRING')
            for pin in ['P13_R', ring_sup_top]:
                self.reexport(ring_inst.get_port(pin))
            self._actual_bbox = ring_master.actual_bbox
        else:
            raise NotImplementedError

        # place 2 inductors
        self.add_instance(core_master, inst_name='XCORE_L', xform=Transform(dx=dx + 2 * radius_y + width,
                                                                            dy=dy,
                                                                            mode=Orientation.R90))
        self.add_instance(core_master, inst_name='XCORE_R', xform=Transform(dx=dx + 2 * radius_y + width + term_sp,
                                                                            dy=dy,
                                                                            mode=Orientation.MXR90))

        # draw leads and add pins
        width2 = width // 2
        res1_l = width // 4
        res2_l = width // 2
        res3_l = width // 4 * 3
        res4_l = width
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]

        bot_term_coords = [(dx + 2 * radius_y + width2, dy + width2),
                           (dx + 2 * radius_y + width + term_sp + width2, dy + width2)]
        term1, term3 = self._draw_leads(lay_id, width, bot_term_coords, res1_l, res3_l)
        self.add_pin_primitive('P1', lp[0], term1)
        self.add_pin_primitive('P3', lp[0], term3)

        top_term_coords = [(dx + 2 * radius_y + width2, dy + 2 * radius_x + width2),
                           (dx + 2 * radius_y + width + term_sp + width2, dy + 2 * radius_x + width2)]
        if common_term:
            self._draw_bridge(top_term_coords[0], top_term_coords[-1], lay_id, lay_id, lay_id, width, PathStyle.extend)
            top_term_coord = (dx + 2 * radius_y + width + term_sp // 2, dy + 2 * radius_x + width2)
            term2 = self._draw_lead(lay_id, width, top_term_coord, res2_l, self._actual_bbox.yh, True)
        else:
            term2, term4 = self._draw_leads(lay_id, width, top_term_coords, res2_l, res4_l, self._actual_bbox.yh, True)
            self.add_pin_primitive('P4', lp[0], term4)
        self.add_pin_primitive('P2', lp[0], term2)

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
            res3_l=res3_l,
            res4_l=res4_l,
            res_w=width,
            res_layer=lay_id,
            common_term=common_term,
            w_ring=w_ring,
        )
