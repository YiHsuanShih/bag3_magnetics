from typing import Mapping, Any

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle

from .util import IndSpiralTemplate, compute_vertices


class IndSpiralCore(IndSpiralTemplate):
    """Spiral inductor Core with multiple turns, 'R0' orientation"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndSpiralTemplate.__init__(self, temp_db, params, **kwargs)
        self._vertex_out = (0, 0)
        self._vertex_in = (0, 0)

    @property
    def vertex_out(self) -> PointType:
        """Outermost vertex of spiral"""
        return self._vertex_out

    @property
    def vertex_in(self) -> PointType:
        """Innermost vertex of spiral"""
        return self._vertex_in

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            n_turns='Number of turns; 1 by default',
            lay_id='Inductor layer ID',
            radius='Outermost radius',
            width='Width of inductor sides',
            spacing='Spacing between inductor turns',
            interleave='True to leave space between spiral turns for interleaving; False by default',
            lead_width='Width of inductor leads',
            lead_spacing='Spacing between inductor leads',
            draw_lead='True to draw lead when interleave=False; leads are always drawn if interleave=True',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            n_turns=1,
            interleave=False,
            draw_lead=True,
        )

    def draw_layout(self) -> None:
        n_turns: int = self.params['n_turns']
        lay_id: int = self.params['lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        interleave: bool = self.params['interleave']
        lead_width: int = self.params['lead_width']
        lead_spacing: int = self.params['lead_spacing']
        draw_lead: bool = self.params['draw_lead']
        draw_lead = interleave or draw_lead

        # check feasibility
        outer_radius = radius + width // 2
        _turns = 2 * n_turns + 1 if interleave else n_turns + 1
        assert outer_radius >= _turns * (width + spacing), f'Either increase radius={radius} or decrease ' \
                                                           f'width={width} or spacing={spacing} or n_turns={n_turns}'

        dx = (lead_width + lead_spacing) // 2
        vertices = compute_vertices(n_turns, radius, width, spacing, dx, interleave, draw_lead)
        self._vertex_out = vertices[0]
        self._vertex_in = vertices[-1]

        # draw paths
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        num_vertices = len(vertices)
        for idx in range(num_vertices - 1):
            self.add_path(lp, width, [vertices[idx], vertices[idx + 1]], PathStyle.round)

        port_lay_id = lay_id - 1 if interleave else lay_id
        lp_lead = self.grid.tech_info.get_lay_purp_list(port_lay_id)[0]
        if interleave:
            # draw leads on lay_id - 1 for interleaved case
            port_dir = self.grid.get_direction(port_lay_id)

            term0_x, term0_y = vertices[0]
            via0_bbox = BBox(term0_x - lead_width // 2, term0_y - width // 2,
                             term0_x + lead_width // 2, term0_y + width // 2)
            lead0_bbox = BBox(via0_bbox.xl, 0, via0_bbox.xh, via0_bbox.yh)
            self.add_rect(lp_lead, lead0_bbox)
            self.add_via(via0_bbox, lp_lead, lp, port_dir, extend=False)
            self.add_pin_primitive('term0', lp_lead[0], lead0_bbox, hide=True)

            term1_x, term1_y = vertices[-1]
            via1_bbox = BBox(term1_x - lead_width // 2, term1_y - width // 2,
                             term1_x + lead_width // 2, term1_y + width // 2)
            lead1_bbox = BBox(via1_bbox.xl, via1_bbox.yl, via1_bbox.xh, 2 * outer_radius)
            self.add_rect(lp_lead, lead1_bbox)
            self.add_via(via1_bbox, lp_lead, lp, port_dir, extend=False)
            self.add_pin_primitive('term1', lp_lead[0], lead1_bbox, hide=True)
        elif draw_lead:
            # draw lead on lay_id for non-interleaved case
            term0_x, term0_y = vertices[0]
            lead0_bbox = BBox(term0_x - lead_width // 2, 0,
                              term0_x + lead_width // 2, term0_y + width // 2)
            self.add_rect(lp_lead, lead0_bbox)
            self.add_pin_primitive('term0', lp_lead[0], lead0_bbox, hide=True)

        # set size
        self._actual_bbox = BBox(0, 0, 2 * outer_radius, 2 * outer_radius)
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)
