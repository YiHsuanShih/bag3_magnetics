from typing import Mapping, Any, Optional, Type

from bag.layout.template import TemplateDB
from bag.util.immutable import Param
from bag.layout.util import BBox
from bag.design.module import Module

from pybag.core import Transform

from .util import IndSpiralTemplate
from .ind_spiral import IndSpiral
from .ind_interleave import IndInterleave
from .ind_spiral_ring import IndSpiralRing
from ...schematic.ind_spiral_wrap import bag3_magnetics__ind_spiral_wrap
from ...schematic.ind_interleave_wrap import bag3_magnetics__ind_interleave_wrap


class IndWrap(IndSpiralTemplate):
    """A wrapper for spiral Inductor."""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndSpiralTemplate.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            n_turns='Number of turns; 1 by default',
            lay_id='Inductor layer ID',
            bot_lay_id='Inductor bottom layer ID',
            radius='Outermost radius',
            width='Width of inductor sides',
            spacing='Spacing between inductor turns',
            interleave='True to leave space between spiral turns for interleaving; False by default',
            lead_width='Width of inductor leads',
            lead_spacing='Spacing between inductor leads',

            w_ring='True to have guard ring, False by default',
            ring_specs='Specs for guard ring, Optional',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            n_turns=1,
            bot_lay_id=-1,
            interleave=False,
            w_ring=False,
            ring_specs=None,
        )

    def draw_layout(self) -> None:
        n_turns: int = self.params['n_turns']
        lay_id: int = self.params['lay_id']
        bot_lay_id: int = self.params['bot_lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        interleave: bool = self.params['interleave']
        lead_width: int = self.params['lead_width']
        lead_spacing: int = self.params['lead_spacing']

        w_ring: bool = self.params['w_ring']
        ring_specs: Optional[Mapping[str, Any]] = self.params['ring_specs']

        # make core
        core_params = dict(
            n_turns=n_turns,
            lay_id=lay_id,
            radius=radius,
            width=width,
            spacing=spacing,
            lead_width=lead_width,
            lead_spacing=lead_spacing,
        )
        if interleave:
            core_master: IndInterleave = self.new_template(IndInterleave, params=core_params)
        else:
            core_params['bot_lay_id'] = bot_lay_id
            core_master: IndSpiral = self.new_template(IndSpiral, params=core_params)
        sch_params = dict(**core_master.sch_params, w_ring=w_ring)

        # make inductor guard ring
        if w_ring:
            ring_width: int = ring_specs['width']
            ring_spacing: int = ring_specs['spacing']
            ring_params = dict(
                lay_id=lay_id,
                bot_lay_id=bot_lay_id,
                width=ring_width,
                gap=lead_spacing + 2 * lead_width + 2 * ring_spacing + ring_width,
                radius=radius + width // 2 + ring_spacing + ring_width // 2,
            )
            dx = dy = ring_width + ring_spacing
            ring_master: IndSpiralRing = self.new_template(IndSpiralRing, params=ring_params)
            ring_inst = self.add_instance(ring_master, inst_name='XRING')
            if interleave:
                self.reexport(ring_inst.get_port('ref0'), hide=False)
                self.reexport(ring_inst.get_port('ref1'), hide=False)
            else:
                self.reexport(ring_inst.get_port('ref_p'), hide=False)
                self.reexport(ring_inst.get_port('ref_m'), hide=False)
            self._actual_bbox = ring_master.actual_bbox
        else:
            dx = dy = 0
            self._actual_bbox = core_master.actual_bbox

        # place core
        core = self.add_instance(core_master, inst_name='XCORE', xform=Transform(dx=dx, dy=dy))
        if interleave:
            port_lay_id = lay_id - 1
            self._extend_lead_vert(core.get_pin('plus0'), -1, self._actual_bbox.yl, port_lay_id, 'plus0')
            self._extend_lead_vert(core.get_pin('minus1'), -1, self._actual_bbox.yl, port_lay_id, 'minus1')

            self._extend_lead_vert(core.get_pin('plus1'), 1, self._actual_bbox.yh, port_lay_id, 'plus1')
            self._extend_lead_vert(core.get_pin('minus0'), 1, self._actual_bbox.yh, port_lay_id, 'minus0')
        else:
            self._extend_lead_vert(core.get_pin('plus'), -1, self._actual_bbox.yl, lay_id, 'plus')
            self._extend_lead_vert(core.get_pin('minus'), -1, self._actual_bbox.yl, bot_lay_id, 'minus')

        # add inductor ID layer
        id_lp = self.grid.tech_info.tech_params['inductor'].get('id_lp', [])
        for _lp in id_lp:
            self.add_rect(_lp, self._actual_bbox)

        # set size
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)

        # get schematic parameters
        self.sch_params = sch_params

    def _extend_lead_vert(self, lead_bbox: BBox, direction: int, y_targ: int, lay_id: int, name: str) -> None:
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        _h = lead_bbox.h
        if direction == 1:
            # extend up
            rect_bbox = BBox(lead_bbox.xl, lead_bbox.yh, lead_bbox.xh, y_targ)
            pin_bbox = BBox(lead_bbox.xl, y_targ - _h, lead_bbox.xh, y_targ)
        elif direction == -1:
            # extend down
            rect_bbox = BBox(lead_bbox.xl, y_targ, lead_bbox.xh, lead_bbox.yl)
            pin_bbox = BBox(lead_bbox.xl, y_targ, lead_bbox.xh, y_targ + _h)
        else:
            raise ValueError(f'Unknown direction={direction}. Use -1 or +1.')
        self.add_rect(lp, rect_bbox)
        self.add_pin_primitive(name, lp[0], pin_bbox)


class IndSpiralWrap(IndWrap):
    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__ind_spiral_wrap


class IndInterleaveWrap(IndWrap):
    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__ind_interleave_wrap
