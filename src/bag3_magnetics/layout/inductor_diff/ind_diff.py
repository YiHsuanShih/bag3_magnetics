from typing import Mapping, Any

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param

from pybag.enum import Orientation
from pybag.core import Transform

from .ind_diff_core import IndDiffCore


class IndDiff(TemplateBase):
    """Interleaved assymmetric differential inductors"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox: BBox = BBox(0, 0, 0, 0)
        self._lead_lower = 0
        self._lead_upper = 0

    @property
    def actual_bbox(self) -> BBox:
        # actual BBox may extend because of grid quantization
        return self._actual_bbox

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
            n_turn='Number of turns',
            lay_id='Inductor layer ID',
            radius='Outermost radius',
            width='Width of inductor sides',
            spacing='Spacing between inductor turns',
            lead_width='Width of inductor leads',
            lead_spacing='Spacing between inductor leads',
        )

    def draw_layout(self) -> None:
        n_turn: int = self.params['n_turn']
        lay_id: int = self.params['lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        lead_width: int = self.params['lead_width']
        lead_spacing: int = self.params['lead_spacing']

        # check feasibility
        assert radius + width // 2 >= (2 * n_turn + 1) * (width + spacing), 'Inductor is infeasible.'

        core_master: IndDiffCore = self.new_template(IndDiffCore, params=dict(n_turn=n_turn, lay_id=lay_id,
                                                                              radius=radius, width=width,
                                                                              spacing=spacing, lead_width=lead_width,
                                                                              lead_spacing=lead_spacing))

        core0 = self.add_instance(core_master, inst_name='XCORE0')
        _bbox = core_master.actual_bbox

        transform = Transform(dx=_bbox.xh, dy=_bbox.yh, mode=Orientation.R180)
        core1 = self.add_instance(core_master, inst_name='XCORE1', xform=transform)

        # --- Metal resistors --- #
        plus0: BBox = core0.get_pin('term0')
        minus0: BBox = core0.get_pin('term1')

        plus1: BBox = core1.get_pin('term0')
        minus1: BBox = core1.get_pin('term1')

        port_lay_id = lay_id - 1
        lp_lead = self.grid.tech_info.get_lay_purp_list(port_lay_id)[0]

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
        self.add_pin_primitive('plus0', lp_lead[0], BBox(plus0.xl, lower, plus0.xh, lower + mres_w))
        self.add_rect(lp_lead, BBox(minus1.xl, lower, minus1.xh, plus0.yh))
        self.add_pin_primitive('minus1', lp_lead[0], BBox(minus1.xl, lower, minus1.xh, lower + mres_w))

        upper = plus1.yh + mres_l3 + mres_sp + mres_w
        self.add_rect(lp_lead, BBox(plus1.xl, plus1.yl, plus1.xh, upper))
        self.add_pin_primitive('plus1', lp_lead[0], BBox(plus1.xl, upper - mres_w, plus1.xh, upper))
        self.add_rect(lp_lead, BBox(minus0.xl, minus0.yl, minus0.xh, upper))
        self.add_pin_primitive('minus0', lp_lead[0], BBox(minus0.xl, upper - mres_w, minus0.xh, upper))

        # set size
        self._lead_lower = lower
        self._lead_upper = upper
        self._actual_bbox = _bbox
        self.set_size_from_bound_box(lay_id, _bbox, round_up=True)

        self.sch_params = dict(
            plus0=dict(w=mres_w, l=mres_l0, layer=port_lay_id),
            minus0=dict(w=mres_w, l=mres_l1, layer=port_lay_id),
            plus1=dict(w=mres_w, l=mres_l2, layer=port_lay_id),
            minus1=dict(w=mres_w, l=mres_l3, layer=port_lay_id),
        )
