# -*- coding: utf-8 -*-
from typing import Mapping, Any, Sequence, Optional, Type, Tuple

from bag.typing import PointType
from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.design.module import Module

from pybag.core import Transform

from .ind_core import IndCore
from .ind_ring import IndRing
from ...schematic.ind_wrap import bag3_magnetics__ind_wrap


class IndWrap(TemplateBase):
    """A wrapper for Inductor."""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox = BBox(0, 0, 0, 0)

    @property
    def actual_bbox(self) -> BBox:
        return self._actual_bbox

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__ind_wrap

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='Inductor layer ID: top layer available in the process',
            n_turns='Number of turns',
            width='Metal width for inductor turns',
            spacing='Metal spacing between inductor turns',
            radius_x='radius along X-axis',
            radius_y='radius along Y-axis',
            term_len='Length of inductor terminals',
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
            ind_shape='Octagon',
            w_ring=False,
            ring_specs=None,
            w_fill=False,
            fill_specs=None,
        )

    def draw_layout(self) -> None:
        lay_id: int = self.params['lay_id']
        n_turns: int = self.params['n_turns']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        radius_x: int = self.params['radius_x']
        radius_y: int = self.params['radius_y']
        term_len: int = self.params['term_len']
        term_sp: int = self.params['term_sp']
        ind_shape: str = self.params['ind_shape']

        w_ring: bool = self.params['w_ring']
        ring_specs: Optional[Mapping[str, Any]] = self.params['ring_specs']

        w_fill: bool = self.params['w_fill']
        fill_specs: Optional[Mapping[str, Any]] = self.params['fill_specs']

        # make inductor core
        core_params = dict(
            lay_id=lay_id,
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
                width=ring_width,
                gap=term_sp + 2 * width + 2 * ring_spacing + ring_width,
                radius_x=radius_x + width // 2 + ring_spacing + ring_width // 2,
                radius_y=radius_y + width // 2 + ring_spacing + ring_width // 2,
                ring_sup=ring_sup,
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
        res1_l = width // 2
        res2_l = width // 4
        term0, term1 = self._draw_leads(lay_id, width, term_len, term_coords, res1_l, res2_l)

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
            self._draw_fill(n_sides, lay_id, fill_specs, core_master.turn_coords, width, dx, dy, ring_turn_coords,
                            ring_width)

        # add inductor ID layer
        id_lp = self.grid.tech_info.tech_params['inductor']['id_lp']
        self.add_rect(id_lp, self._actual_bbox)

        # set size
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)

        # get schematic parameters
        self.sch_params = dict(
            res1_l=res1_l,
            res2_l=res2_l,
            res_w=width,
            res_layer=lay_id,
            w_ring=w_ring,
            ring_sup=ring_sup,
        )
    
    def _draw_leads(self, lay_id: int, width: int, term_len: int, term_coords: Sequence[PointType], res1_l: int, 
                    res2_l: int) -> Tuple[BBox, BBox]:
        term_ext = width + max(res1_l, res2_l) + 2 * width
        term_len = max(term_ext, term_len)

        # BBox for lead metals
        _lower = min(0, term_coords[0][1] - term_len)
        _upper = term_coords[0][1]

        _bbox0 = BBox(term_coords[0][0] - width // 2, _lower, term_coords[0][0] + width // 2, _upper)
        _bbox1 = BBox(term_coords[1][0] - width // 2, _lower, term_coords[1][0] + width // 2, _upper)
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        self.add_rect(lp, _bbox0)
        self.add_rect(lp, _bbox1)

        # BBox for res_metal
        term0_res_bbox = BBox(_bbox0.xl, _upper - width - res1_l, _bbox0.xh, _upper - width)
        term1_res_bbox = BBox(_bbox1.xl, _upper - width - res2_l, _bbox1.xh, _upper - width)
        self.add_res_metal(lay_id, term0_res_bbox)
        self.add_res_metal(lay_id, term1_res_bbox)

        # BBox for pins
        term0 = BBox(_bbox0.xl, _bbox0.yl, _bbox0.xh, _bbox0.yl + width)
        term1 = BBox(_bbox1.xl, _bbox1.yl, _bbox1.xh, _bbox1.yl + width)
        return term0, term1

    def _draw_fill(self, n_sides: int, lay_id: int, fill_specs: Mapping[str, Any],
                   core_turn_coords: Sequence[Mapping[str, Sequence[PointType]]], width: int, dx: int, dy: int,
                   ring_turn_coords: Sequence[PointType], ring_width: int) -> None:
        fill_w: int = fill_specs['fill_w']
        fill_sp: int = fill_specs['fill_sp']
        inside_ring: bool = fill_specs.get('inside_ring', True)
        outside_ring: bool = fill_specs.get('outside_ring', True)

        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        w2 = width // 2
        rw2 = ring_width // 2

        if n_sides == 8:
            #          R0
            #       1-0  5-4
            #   2              3
            #   |              |
            #   |              |
            #   |              |
            #   3              2
            #       4-5  0-1

            # Step 1: draw inside ring
            if inside_ring:
                in_l = core_turn_coords[-1]['left']
                in_r = core_turn_coords[-1]['right']

                bbox_in = BBox(in_l[2][0] + w2 + fill_sp + dx, in_r[1][1] + w2 + fill_sp + dy,
                               in_r[2][0] - w2 - fill_sp + dx, in_l[1][1] - w2 - fill_sp + dy)
                bbox_in2 = BBox(in_l[1][0] + w2 + dx, in_r[2][1] + w2 + dy, in_r[1][0] - w2 + dx, in_l[2][1] - w2 + dy)

                tot_num_x = (bbox_in.w + fill_sp) // (fill_w + fill_sp)
                tot_len_x = tot_num_x * (fill_w + fill_sp) - fill_sp
                xl = bbox_in.xl + (bbox_in.w - tot_len_x) // 2

                tot_num_y = (bbox_in.h + fill_sp) // (fill_w + fill_sp)
                tot_len_y = tot_num_y * (fill_w + fill_sp) - fill_sp
                yl = bbox_in.yl + (bbox_in.h - tot_len_y) // 2

                for idx in range(tot_num_x):
                    for jdx in range(tot_num_y):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        if _xl + _yl < bbox_in.xl + bbox_in2.yl:
                            # lower left
                            continue
                        elif _yl + fill_w - _xl > bbox_in2.yh - bbox_in.xl:
                            # upper left
                            continue
                        elif _yl - _xl - fill_w < bbox_in2.yl - bbox_in.xh:
                            # lower right
                            continue
                        elif _xl + _yl + 2 * fill_w > bbox_in.xh + bbox_in2.yh:
                            # upper right
                            continue
                        self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))

            # Step 2: draw outside ring
            if outside_ring:
                out_l = core_turn_coords[0]['left']
                out_r = core_turn_coords[0]['right']

                bbox_out2 = BBox(out_l[1][0] - w2 - fill_sp + dx, out_r[2][1] - w2 - fill_sp + dy,
                                 out_r[1][0] + w2 + fill_sp + dx, out_l[2][1] + w2 + fill_sp + dy)
                bbox_out = BBox(out_l[2][0] - w2 + dx, out_r[1][1] - w2 + dy,
                                out_r[2][0] + w2 + dx, out_l[1][1] + w2 + dy)

                if ring_turn_coords:
                    #    R0
                    #  3-----2
                    #  |     |
                    #  |     |
                    #  4-5 0-1
                    rbbox = BBox(ring_turn_coords[3][0] + rw2 + fill_sp, ring_turn_coords[1][1] + rw2 + fill_sp,
                                 ring_turn_coords[1][0] - rw2 - fill_sp, ring_turn_coords[3][1] - rw2 - fill_sp)
                else:
                    rbbox = bbox_out

                tot_num_x = (rbbox.w + fill_sp) // (fill_w + fill_sp)
                tot_len_x = tot_num_x * (fill_w + fill_sp) - fill_sp
                xl = rbbox.xl + (rbbox.w - tot_len_x) // 2

                tot_num_y = (rbbox.h + fill_sp) // (fill_w + fill_sp)
                tot_len_y = tot_num_y * (fill_w + fill_sp) - fill_sp
                yl = rbbox.yl + (rbbox.h - tot_len_y) // 2

                for idx in range(tot_num_x):
                    for jdx in range(tot_num_y):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        if bbox_out2.xl < _xl < bbox_out2.xh - fill_w and _yl + fill_w < bbox_out.yl - fill_sp:
                            # keep-out
                            continue
                        elif _xl + fill_w < bbox_out.xl - fill_sp:
                            # left
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _xl > bbox_out.xh + fill_sp:
                            # right
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl > bbox_out.yh + fill_sp:
                            # top
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl + fill_w < bbox_out.yl - fill_sp:
                            # bottom
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _xl + _yl + 2 * fill_w < bbox_out.xl + bbox_out2.yl:
                            # lower left
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl - _xl - fill_w > bbox_out2.yh - bbox_out.xl:
                            # upper left
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl + fill_w - _xl < bbox_out2.yl - bbox_out.xh:
                            # lower right
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _xl + _yl > bbox_out.xh + bbox_out2.yh:
                            # upper right
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))

        elif n_sides == 4:
            #          R0
            #   1-----0  3-----2
            #   |              |
            #   |              |
            #   |              |
            #   2-----3  0-----1

            # Step 1: draw inside ring
            if inside_ring:
                in_l = core_turn_coords[-1]['left']
                in_r = core_turn_coords[-1]['right']

                bbox_in = BBox(in_l[1][0] + w2 + fill_sp + dx, in_r[1][1] + w2 + fill_sp + dy,
                               in_r[1][0] - w2 - fill_sp + dx, in_l[1][1] - w2 - fill_sp + dy)

                tot_num_x = (bbox_in.w + fill_sp) // (fill_w + fill_sp)
                tot_len_x = tot_num_x * (fill_w + fill_sp) - fill_sp
                xl = bbox_in.xl + (bbox_in.w - tot_len_x) // 2

                tot_num_y = (bbox_in.h + fill_sp) // (fill_w + fill_sp)
                tot_len_y = tot_num_y * (fill_w + fill_sp) - fill_sp
                yl = bbox_in.yl + (bbox_in.h - tot_len_y) // 2

                for idx in range(tot_num_x):
                    for jdx in range(tot_num_y):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))

            # Step 2: draw outside ring
            if outside_ring:
                out_l = core_turn_coords[0]['left']
                out_r = core_turn_coords[0]['right']

                bbox_out = BBox(out_l[1][0] - w2 - fill_sp + dx, out_r[1][1] - w2 - fill_sp + dy,
                                out_r[1][0] + w2 + fill_sp + dx, out_l[1][1] + w2 + fill_sp + dy)

                if ring_turn_coords:
                    #    R0
                    #  3-----2
                    #  |     |
                    #  |     |
                    #  4-5 0-1
                    rbbox = BBox(ring_turn_coords[3][0] + rw2 + fill_sp, ring_turn_coords[1][1] + rw2 + fill_sp,
                                 ring_turn_coords[1][0] - rw2 - fill_sp, ring_turn_coords[3][1] - rw2 - fill_sp)
                else:
                    return

                tot_num_x = (rbbox.w + fill_sp) // (fill_w + fill_sp)
                tot_len_x = tot_num_x * (fill_w + fill_sp) - fill_sp
                xl = rbbox.xl + (rbbox.w - tot_len_x) // 2

                tot_num_y = (rbbox.h + fill_sp) // (fill_w + fill_sp)
                tot_len_y = tot_num_y * (fill_w + fill_sp) - fill_sp
                yl = rbbox.yl + (rbbox.h - tot_len_y) // 2

                for idx in range(tot_num_x):
                    for jdx in range(tot_num_y):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        if bbox_out.xl < _xl < bbox_out.xh - fill_w and _yl + fill_w < bbox_out.yl - fill_sp:
                            # keep-out
                            continue
                        elif _xl + fill_w < bbox_out.xl - fill_sp:
                            # left
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _xl > bbox_out.xh + fill_sp:
                            # right
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl > bbox_out.yh + fill_sp:
                            # top
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl + fill_w < bbox_out.yl - fill_sp:
                            # bottom
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
        else:
            raise NotImplementedError(f'_draw_fill() is not implemented for n_sides={n_sides} yet.')
