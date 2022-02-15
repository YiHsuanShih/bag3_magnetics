from typing import Mapping, Any, Optional, Type

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.design.module import Module

from pybag.enum import PathStyle
from pybag.core import Transform

from .ind_diff import IndDiff
from ...schematic.ind_diff_wrap import bag3_magnetics__ind_diff_wrap


class IndDiffWrap(TemplateBase):
    """Interleaved assymmetric differential inductors"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__ind_diff_wrap

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            n_turn='Number of turns',
            lay_id='Inductor layer ID',
            radius='Outermost radius',
            width='Width of inductor sides',
            spacing='Spacing between inductor turns',
            ring_width='Width of guard ring',
            ring_spacing='Spacing outer inductor turn and guard ring',
            lead_width='Width of inductor leads',
            lead_spacing='Spacing between inductor leads',
        )

    def draw_layout(self) -> None:
        n_turn: int = self.params['n_turn']
        lay_id: int = self.params['lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        ring_width: int = self.params['ring_width']
        ring_spacing: int = self.params['ring_spacing']
        lead_width: int = self.params['lead_width']
        lead_spacing: int = self.params['lead_spacing']

        # check feasibility
        outer_radius = radius + width // 2
        assert outer_radius >= (2 * n_turn + 1) * (width + spacing), 'Inductor is infeasible.'
        outer_radius += ring_spacing + ring_width

        core_master: IndDiff = self.new_template(IndDiff, params=dict(n_turn=n_turn, lay_id=lay_id, radius=radius,
                                                                      width=width, spacing=spacing,
                                                                      lead_width=lead_width, lead_spacing=lead_spacing))
        core_bbox = core_master.actual_bbox
        actual_bbox = BBox(core_bbox.xl, min(core_bbox.yl, core_master.lead_lower),
                           core_bbox.xh, max(core_bbox.yh, core_master.lead_upper))

        xform = Transform(dx=(2 * outer_radius - actual_bbox.w) // 2 - actual_bbox.xl,
                          dy=(2 * outer_radius - actual_bbox.h) // 2 - actual_bbox.yl)
        core = self.add_instance(core_master, inst_name='XDIFF', xform=xform)
        for pin_name in ('plus0', 'minus0', 'plus1', 'minus1'):
            self.reexport(core.get_port(pin_name))

        # --- guard ring --- #
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        ring_bbox = BBox(0, 0, 2 * outer_radius, 2 * outer_radius)
        rw2 = ring_width // 2
        coords = [(ring_bbox.xl + rw2, ring_bbox.yl + rw2), (ring_bbox.xh - rw2, ring_bbox.yl + rw2),
                  (ring_bbox.xh - rw2, ring_bbox.yh - rw2), (ring_bbox.xl + rw2, ring_bbox.yh - rw2),
                  (ring_bbox.xl + rw2, ring_bbox.yl + rw2)]
        for idx in range(4):
            self.add_path(lp, ring_width, [coords[idx], coords[idx + 1]], PathStyle.extend)

        # guard ring pins below leads for EM sims
        ref0_bbox = BBox(ring_bbox.xm - ring_width, ring_bbox.yl,
                         ring_bbox.xm + ring_width, ring_bbox.yl + ring_width)
        self.add_pin_primitive('ref0', lp[0], ref0_bbox)

        ref1_bbox = BBox(ring_bbox.xm - ring_width, ring_bbox.yh - ring_width,
                         ring_bbox.xm + ring_width, ring_bbox.yh)
        self.add_pin_primitive('ref1', lp[0], ref1_bbox)

        # set size
        self.set_size_from_bound_box(lay_id, ring_bbox, round_up=True)

        # TODO: draw fill

        # add inductor ID layer
        id_lp = self.grid.tech_info.tech_params['inductor'].get('id_lp', [])
        for _lp in id_lp:
            self.add_rect(_lp, ring_bbox)

        self.sch_params = core_master.sch_params
