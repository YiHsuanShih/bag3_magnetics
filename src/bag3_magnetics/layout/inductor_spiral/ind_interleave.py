from typing import Mapping, Any

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param

from pybag.enum import Orientation
from pybag.core import Transform

from .util import IndSpiralTemplate
from .ind_spiral_core import IndSpiralCore


class IndInterleave(IndSpiralTemplate):
    """interleaved spiral inductors with multiple turns, 'R0' orientation"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndSpiralTemplate.__init__(self, temp_db, params, **kwargs)
        self._lead_lower = 0
        self._lead_upper = 0

    @property
    def lead_lower(self) -> int:
        # bottom lead may extend beyond first quadrant
        return self._lead_lower

    @property
    def lead_upper(self) -> int:
        return self._lead_upper

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            n_turns='Number of turns; 1 by default',
            lay_id='Inductor layer ID',
            radius='Outermost radius',
            width='Width of inductor sides',
            spacing='Spacing between inductor turns',
            lead_width='Width of inductor leads',
            lead_spacing='Spacing between inductor leads',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            n_turns=1,
        )

    def draw_layout(self) -> None:
        n_turns: int = self.params['n_turns']
        lay_id: int = self.params['lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        lead_width: int = self.params['lead_width']
        lead_spacing: int = self.params['lead_spacing']

        # check feasibility
        outer_radius = radius + width // 2
        _turns = 2 * n_turns + 1
        assert outer_radius >= _turns * (width + spacing), f'Either increase radius={radius} or decrease ' \
                                                           f'width={width} or spacing={spacing} or n_turns={n_turns}'

        core_master: IndSpiralCore = self.new_template(IndSpiralCore,
                                                       params=dict(n_turns=n_turns, lay_id=lay_id, radius=radius,
                                                                   width=width, spacing=spacing, lead_width=lead_width,
                                                                   lead_spacing=lead_spacing, interleave=True))

        core0 = self.add_instance(core_master, inst_name='XCORE0')
        _bbox = core_master.actual_bbox

        transform = Transform(dx=_bbox.xh, dy=_bbox.yh, mode=Orientation.R180)
        core1 = self.add_instance(core_master, inst_name='XCORE1', xform=transform)

        # draw leads
        self._draw_leads(lay_id, core0.get_pin('term0'), core0.get_pin('term1'), core1.get_pin('term0'),
                         core1.get_pin('term1'))

        # set size
        self._actual_bbox = _bbox
        self.set_size_from_bound_box(lay_id, _bbox, round_up=True)

    def _draw_leads(self, lay_id: int, plus0: BBox, minus0: BBox, plus1: BBox, minus1: BBox) -> None:
        port_lay_id = lay_id - 1
        lp_lead = self.grid.tech_info.get_lay_purp_list(port_lay_id)[0]

        # define metal resistor dimensions
        mres_w = plus0.w
        mres_l0 = mres_w // 4  # plus0
        mres_l1 = mres_w // 2  # minus0
        mres_l2 = mres_w  # plus1
        mres_l3 = mres_w * 2  # minus1
        mres_sp = mres_l0

        # add metal resistors
        plus0_rbox = BBox(plus0.xl, plus0.yl - mres_l0, plus0.xh, plus0.yl)
        self.add_res_metal(port_lay_id, plus0_rbox)
        minus1_rbox = BBox(minus1.xl, plus0.yl - mres_l3, minus1.xh, plus0.yl)
        self.add_res_metal(port_lay_id, minus1_rbox)

        plus1_rbox = BBox(plus1.xl, plus1.yh, plus1.xh, plus1.yh + mres_l2)
        self.add_res_metal(port_lay_id, plus1_rbox)
        minus0_rbox = BBox(minus0.xl, plus1.yh, minus0.xh, plus1.yh + mres_l1)
        self.add_res_metal(port_lay_id, minus0_rbox)

        # extend metal beyond metal resistors
        lower = plus0.yl - mres_l3 - mres_sp - mres_w
        self.add_rect(lp_lead, BBox(plus0.xl, lower, plus0.xh, plus0.yh))
        self.add_pin_primitive('plus0', lp_lead[0], BBox(plus0.xl, lower, plus0.xh, lower + mres_w), hide=True)
        self.add_rect(lp_lead, BBox(minus1.xl, lower, minus1.xh, plus0.yh))
        self.add_pin_primitive('minus1', lp_lead[0], BBox(minus1.xl, lower, minus1.xh, lower + mres_w), hide=True)

        upper = plus1.yh + mres_l3 + mres_sp + mres_w
        self.add_rect(lp_lead, BBox(plus1.xl, plus1.yl, plus1.xh, upper))
        self.add_pin_primitive('plus1', lp_lead[0], BBox(plus1.xl, upper - mres_w, plus1.xh, upper), hide=True)
        self.add_rect(lp_lead, BBox(minus0.xl, minus0.yl, minus0.xh, upper))
        self.add_pin_primitive('minus0', lp_lead[0], BBox(minus0.xl, upper - mres_w, minus0.xh, upper), hide=True)

        # set properties
        self._lead_lower = lower
        self._lead_upper = upper

        self.sch_params = dict(
            plus0=dict(w=mres_w, l=mres_l0, layer=port_lay_id),
            minus0=dict(w=mres_w, l=mres_l1, layer=port_lay_id),
            plus1=dict(w=mres_w, l=mres_l2, layer=port_lay_id),
            minus1=dict(w=mres_w, l=mres_l3, layer=port_lay_id),
        )
