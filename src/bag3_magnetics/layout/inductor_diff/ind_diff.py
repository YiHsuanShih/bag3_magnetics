from typing import Mapping, Any

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BBox
from bag.layout.routing.base import TrackManager
from bag.util.immutable import Param

from pybag.enum import Orientation, Orient2D
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
        # actual BBox may extend outside first quadrant
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
            port_xl='x co-ordinate of left port',
            port_xr='x co-ordinate of right port',
            tr_manager='Track Manager',
        )

    def draw_layout(self) -> None:
        n_turn: int = self.params['n_turn']
        lay_id: int = self.params['lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        tr_manager: TrackManager = self.params['tr_manager']

        # check feasibility
        assert radius + width // 2 >= (2 * n_turn + 1) * (width + spacing), 'Inductor is infeasible.'

        port_xl: int = self.params['port_xl']
        port_xr: int = self.params['port_xr']

        core_master: IndDiffCore = self.new_template(IndDiffCore, params=dict(n_turn=n_turn, lay_id=lay_id,
                                                                              radius=radius, width=width,
                                                                              spacing=spacing, port_xl=port_xl,
                                                                              port_xr=port_xr, tr_manager=tr_manager))

        core0 = self.add_instance(core_master, inst_name='XCORE0')
        actual_bbox = core_master.actual_bbox
        transform = Transform(dx=actual_bbox.xh + actual_bbox.xl, dy=actual_bbox.yh + actual_bbox.yl,
                              mode=Orientation.R180)
        core1 = self.add_instance(core_master, inst_name='XCORE1', xform=transform)

        # --- Metal resistors --- #
        plus0 = core0.get_pin('term0')
        minus0 = core0.get_pin('term1')

        plus1 = core1.get_pin('term0')
        minus1 = core1.get_pin('term1')

        port_lay_id = lay_id - 1
        if self.grid.get_direction(port_lay_id) != Orient2D.y:
            raise ValueError(f'This generator expects port_layer={port_lay_id} to be vertical.')
        mres_w = plus0.bound_box.w
        mres_l0 = mres_w // 4  # plus0
        mres_l1 = mres_w // 2  # minus0
        mres_l2 = mres_w  # plus1
        mres_l3 = mres_w * 2  # minus1
        mres_sp = mres_l0

        # add metal resistors
        plus0_rbox = BBox(plus0.bound_box.xl, plus0.lower - mres_l0, plus0.bound_box.xh, plus0.lower)
        self.add_res_metal(port_lay_id, plus0_rbox)
        minus1_rbox = BBox(minus1.bound_box.xl, plus0.lower - mres_l3, minus1.bound_box.xh, plus0.lower)
        self.add_res_metal(port_lay_id, minus1_rbox)

        plus1_rbox = BBox(plus1.bound_box.xl, plus1.upper, plus1.bound_box.xh, plus1.upper + mres_l2)
        self.add_res_metal(port_lay_id, plus1_rbox)
        minus0_rbox = BBox(minus0.bound_box.xl, plus1.upper, minus0.bound_box.xh, plus1.upper + mres_l1)
        self.add_res_metal(port_lay_id, minus0_rbox)

        # extend metal beyond metal resistors
        lower = plus0.lower - mres_l3 - mres_sp - mres_w
        plus0_ext = self.add_wires(port_lay_id, plus0.track_id.base_index, lower=lower, upper=lower + mres_w,
                                   width=plus0.track_id.width)
        self.extend_wires(plus0, lower=lower)
        minus1_ext = self.add_wires(port_lay_id, minus1.track_id.base_index, lower=lower, upper=lower + mres_w,
                                    width=minus1.track_id.width)
        self.extend_wires(minus1, lower=lower)

        upper = plus1.upper + mres_l3 + mres_sp + mres_w
        plus1_ext = self.add_wires(port_lay_id, plus1.track_id.base_index, lower=upper - mres_w, upper=upper,
                                   width=plus1.track_id.width)
        self.extend_wires(plus1, upper=upper)
        minus0_ext = self.add_wires(port_lay_id, minus0.track_id.base_index, lower=upper - mres_w, upper=upper,
                                    width=minus0.track_id.width)
        self.extend_wires(minus0, upper=upper)

        self.add_pin('plus0', plus0_ext)
        self.add_pin('minus0', minus0_ext)
        self.add_pin('plus1', plus1_ext)
        self.add_pin('minus1', minus1_ext)

        # set size
        self._lead_lower = lower
        self._lead_upper = upper
        self._actual_bbox = actual_bbox
        self.set_size_from_bound_box(lay_id, BBox(0, 0, self._actual_bbox.xh, self._actual_bbox.yh), round_up=True)

        self.sch_params = dict(
            plus0=dict(w=mres_w, l=mres_l0, layer=port_lay_id),
            minus0=dict(w=mres_w, l=mres_l1, layer=port_lay_id),
            plus1=dict(w=mres_w, l=mres_l2, layer=port_lay_id),
            minus1=dict(w=mres_w, l=mres_l3, layer=port_lay_id),
        )
