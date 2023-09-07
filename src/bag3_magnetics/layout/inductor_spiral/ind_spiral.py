from typing import Mapping, Any

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param

from pybag.enum import Orientation
from pybag.core import Transform

from .util import IndSpiralTemplate
from .ind_spiral_core import IndSpiralCore


class IndSpiral(IndSpiralTemplate):
    """Spiral inductor with multiple turns across multiple layers, 'R0' orientation"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndSpiralTemplate.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            n_turns='Number of turns; 1 by default',
            lay_id='Inductor top layer ID',
            bot_lay_id='Inductor bottom layer ID',
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
        bot_lay_id: int = self.params['bot_lay_id']
        n_layers = lay_id - bot_lay_id + 1
        if n_layers & 1:
            raise ValueError('This generator expects even number of layers so that both ends of the spiral are on '
                             'the outside')
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        lead_width: int = self.params['lead_width']
        lead_spacing: int = self.params['lead_spacing']

        # check feasibility
        outer_radius = radius + width // 2
        _turns = n_turns + 1
        assert outer_radius >= _turns * (width + spacing), f'Either increase radius={radius} or decrease ' \
                                                           f'width={width} or spacing={spacing} or n_turns={n_turns}'

        sch_params = dict()
        for _lay_id in range(lay_id, bot_lay_id - 1, -1):
            draw_lead = _lay_id == lay_id or _lay_id == bot_lay_id
            _master: IndSpiralCore = self.new_template(IndSpiralCore,
                                                       params=dict(n_turns=n_turns, lay_id=_lay_id, radius=radius,
                                                                   width=width, spacing=spacing, lead_width=lead_width,
                                                                   lead_spacing=lead_spacing, interleave=False,
                                                                   draw_lead=draw_lead))
            _bbox = _master.actual_bbox
            flip = (lay_id & 1) != (_lay_id & 1)

            _top_lp = self.grid.tech_info.get_lay_purp_list(_lay_id)[0]
            _bot_lp = self.grid.tech_info.get_lay_purp_list(_lay_id - 1)[0]
            _bot_dir = self.grid.get_direction(_lay_id - 1)

            _xshift = (lead_width + lead_spacing) // 2
            if flip:
                transform = Transform(dx=_bbox.xh, mode=Orientation.MY)
                _inst = self.add_instance(_master, inst_name=f'XCORE_{_lay_id}', xform=transform)
                if _lay_id != bot_lay_id:
                    # draw via outside spiral
                    xm, ym = _master.vertex_out
                    xm -= _xshift
                    via_bbox = BBox(xm - _xshift, ym - width // 2, xm + _xshift, ym + width // 2)
                    self.add_via(via_bbox, _bot_lp, _top_lp, _bot_dir, extend=False)
            else:
                _inst = self.add_instance(_master, inst_name=f'XCORE_{_lay_id}')

                # draw via inside spiral
                xm, ym = _master.vertex_in
                xm += _xshift

                via_bbox = BBox(xm - _xshift, ym - width // 2, xm + _xshift, ym + width // 2)
                self.add_via(via_bbox, _bot_lp, _top_lp, _bot_dir, extend=False)

            if draw_lead:
                # add metal resistor
                term: BBox = _inst.get_pin('term0')
                mres_w = term.w
                mres_l = mres_w // 2
                _rbox = BBox(term.xl, term.yl - mres_l, term.xh, term.yl)
                self.add_res_metal(_lay_id, _rbox)
                _name = 'plus' if _lay_id == lay_id else 'minus'
                sch_params[_name] = dict(w=mres_w, l=mres_l, layer=_lay_id)

                # extend metal beyond metal resistor
                lower = term.yl - mres_l - mres_w // 4 - mres_w
                self.add_rect(_top_lp, BBox(term.xl, lower, term.xh, term.yh))
                self.add_pin_primitive(_name, _top_lp[0], BBox(term.xl, lower, term.xh, lower + mres_w), hide=True)

        # set size
        self._actual_bbox = BBox(0, 0, 2 * outer_radius, 2 * outer_radius)
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)

        self.sch_params = sch_params
