from typing import Mapping, Any, Optional, Type

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BBox
from bag.layout.routing.base import WDictType, SpDictType, TrackManager
from bag.util.immutable import Param
from bag.design.module import Module

from pybag.enum import Orient2D, PathStyle
from pybag.core import Transform

from .ind_diff import IndDiff
from ...schematic.ind_diff_wrap import bag3_magnetics__ind_diff_wrap


class IndDiffWrap(TemplateBase):
    """Interleaved assymmetric differential inductors"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox: BBox = BBox(0, 0, 0, 0)
        self._tr_manager = None

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__ind_diff_wrap

    @property
    def tr_manager(self) -> TrackManager:
        return self._tr_manager

    @property
    def actual_bbox(self) -> BBox:
        # actual BBox may extend outside first quadrant
        return self._actual_bbox

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
            tr_widths='Track widths dictionary',
            tr_spaces='Track spaces dictionary',
        )

    def draw_layout(self) -> None:
        n_turn: int = self.params['n_turn']
        lay_id: int = self.params['lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        ring_width: int = self.params['ring_width']
        ring_spacing: int = self.params['ring_spacing']
        tr_widths: WDictType = self.params['tr_widths']
        tr_spaces: SpDictType = self.params['tr_spaces']
        self._tr_manager = tr_manager = TrackManager(self.grid, tr_widths, tr_spaces)

        # check feasibility
        outer_radius = radius + width // 2
        assert outer_radius >= (2 * n_turn + 1) * (width + spacing), 'Inductor is infeasible.'
        outer_radius += ring_spacing + ring_width

        w_pitch, h_pitch = self.grid.get_size_pitch(lay_id)
        w_pitch2 = w_pitch // 2
        outer_radius = -(- outer_radius // w_pitch2) * w_pitch2
        radius = outer_radius - (ring_spacing + ring_width) - width // 2

        tot_h = -(- 2 * outer_radius // h_pitch) * h_pitch

        port_lay_id = lay_id - 1
        if self.grid.get_direction(port_lay_id) != Orient2D.y:
            raise ValueError(f'This generator expects port_layer={port_lay_id} to be vertical.')
        _, locs = tr_manager.place_wires(port_lay_id, ['sig_hs', 'sup', 'sig_hs'], center_coord=outer_radius)
        port_xl = self.grid.track_to_coord(port_lay_id, locs[0])
        port_xr = self.grid.track_to_coord(port_lay_id, locs[-1])

        core_master: IndDiff = self.new_template(IndDiff, params=dict(n_turn=n_turn, lay_id=lay_id, radius=radius,
                                                                      width=width, spacing=spacing, port_xl=port_xl,
                                                                      port_xr=port_xr, tr_manager=tr_manager))
        core_actual_bbox = core_master.actual_bbox
        actual_bbox = BBox(core_actual_bbox.xl, min(core_actual_bbox.yl, core_master.lead_lower),
                           core_actual_bbox.xh, max(core_actual_bbox.yh, core_master.lead_upper))

        xform = Transform(dy=(tot_h - actual_bbox.h) // 2 - actual_bbox.yl)
        core = self.add_instance(core_master, inst_name='XDIFF', xform=xform)
        for pin_name in ('plus0', 'minus0', 'plus1', 'minus1'):
            self.reexport(core.get_port(pin_name))

        # TODO: guard ring
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        off_y = (tot_h - 2 * outer_radius) // 2
        ring_bbox = BBox(0, off_y, 2 * outer_radius, tot_h - off_y)
        rw2 = ring_width // 2
        coords = [(ring_bbox.xl + rw2, ring_bbox.yl + rw2), (ring_bbox.xh - rw2, ring_bbox.yl + rw2),
                  (ring_bbox.xh - rw2, ring_bbox.yh - rw2), (ring_bbox.xl + rw2, ring_bbox.yh - rw2),
                  (ring_bbox.xl + rw2, ring_bbox.yl + rw2)]
        for idx in range(4):
            self.add_path(lp, ring_width, [coords[idx], coords[idx + 1]], PathStyle.extend)

        # set size
        tot_bbox = BBox(0, 0, 2 * outer_radius, tot_h)
        self.set_size_from_bound_box(lay_id, tot_bbox, round_up=True)

        # TODO: draw fill

        # add inductor ID layer
        id_lp = self.grid.tech_info.tech_params['inductor']['id_lp']
        self.add_rect(id_lp, ring_bbox)

        self.sch_params = core_master.sch_params
