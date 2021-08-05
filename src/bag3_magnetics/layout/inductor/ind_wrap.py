# -*- coding: utf-8 -*-
from typing import Mapping, Any, Union, Optional, Type

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.design.module import Module

from pybag.enum import Orientation, RoundMode
from pybag.core import Transform

from .util import IndTemplate
from .ind_core import IndCore
from .ind_ring import IndRing
from ...schematic.ind_wrap import bag3_magnetics__ind_wrap


class IndWrap(IndTemplate):
    """A wrapper for Inductor.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        IndTemplate.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_schematic_class(cls) -> Optional[Type[Module]]:
        return bag3_magnetics__ind_wrap

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        """Returns a dictionary containing parameter descriptions.

        Override this method to return a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Mapping[str, str]
            dictionary from parameter name to description.
        """
        return dict(
            n_turn='inductor turn number',
            layid='inductor layer id',
            radius='inductor outer radius',
            spacing='inductor turn space',
            width='inductor width',
            opening='inductor opening',
            via_width='inductor via width at bridges',
            min_width='minimum width because of CV via',
            min_spacing='minimum spacing between turns',

            lead_len='inductor terminal length',

            w_ring='True to have guard ring, False by default',
            ring_specs='Specs for guard ring, Optional',

            center_tap='True to have center tap, False by default',
            center_tap_specs='Specs for center tap, Optional',

            # dum_wid_list='dummy metal side width list',
            # dum_den_list='dummy metal density list',
            #
            # blk_layer_list='dummy block layers',
            # use_layer_list='dummy use layers',

            # w_shield='with shield or not',
            # w_dummy='with dummy or not',
            # dum_indlay='with inductor layer dummy or not',
            # dum_bdglay='with inductor-1 layer dummy or not',
            # dum_lowlay='with low layer dummy or not',
            # dum_pood='with poly/od dummy or not',

            res1_l='length of metal resistor connecting to P1',
            res2_l='length of metal resistor connecting to P2',
            pin_len='pin length',
            pin_tr_w='pin track width',
            res_space='metal resistor space to pin',
            orient='orientation of inductor',
            short_terms='True to make shorted terminals',

            w_fill='True to have metal fill',
            fill_specs='Specs for metal fill',
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            orient=Orientation.R0,
            short_terms=False,
            w_ring=False,
            ring_specs=None,
            center_tap=False,
            center_tap_specs=None,
            w_fill=False,
            fill_specs=None,
            pin_tr_w=1,
        )

    def draw_layout(self):
        n_turn: int = self.params['n_turn']
        layid: int = self.params['layid']
        radius: int = self.params['radius']
        spacing: int = self.params['spacing']
        width: int = self.params['width']
        opening: int = self.params['opening']
        via_width: int = self.params['via_width']
        min_width: int = self.params['min_width']
        min_spacing: int = self.params['min_spacing']

        lead_len: int = self.params['lead_len']

        w_ring: bool = self.params['w_ring']
        ring_specs: Optional[Mapping[str, Any]] = self.params['ring_specs']

        center_tap: bool = self.params['center_tap']
        center_tap_specs: Optional[Mapping[str, Any]] = self.params['center_tap_specs']

        # w_shield: bool = self.params['w_shield']
        # w_dummy: bool = self.params['w_dummy']
        # dum_indlay: int = self.params['dum_indlay']
        # dum_bdglay: int = self.params['dum_bdglay']
        # dum_lowlay: int = self.params['dum_lowlay']
        # dum_pood: int = self.params['dum_pood']

        res1_l: int = self.params['res1_l']
        res2_l: int = self.params['res2_l']
        pin_len: int = self.params['pin_len']
        pin_tr_w: int = self.params['pin_tr_w']
        res_space: int = self.params['res_space']
        orient: Union[str, Orientation] = self.params['orient']
        if isinstance(orient, str):
            orient = Orientation[orient]

        w_fill: bool = self.params['w_fill']
        fill_specs: Optional[Mapping[str, Any]] = self.params['fill_specs']

        # current generator limitations
        if w_ring and center_tap:
            raise ValueError('Generator does not support both w_ring and center_tap being True simultaneously.')

        # hard coded number of side
        n_side = 8

        # make inductor core
        ind_params = dict(
            n_side=n_side,
            n_turn=n_turn,
            layid=layid,
            radius=radius,
            spacing=spacing,
            width=width,
            opening=opening,
            orient=orient,
            via_width=via_width,
            min_width=min_width,
            min_spacing=min_spacing,
        )
        ind_master: IndCore = self.new_template(IndCore, params=ind_params)

        # make inductor guard ring
        if w_ring:
            ring_params = dict(
                **ring_specs,
                core_dim=ind_master.tot_dim,
                core_opening=ind_master.opening,
                core_width=width,
                layid=layid,
                orient=orient,
                pin_len=pin_len,
                pin_tr_w=pin_tr_w,
            )
            ring_master: IndRing = self.new_template(IndRing, params=ring_params)

            ring_width: int = ring_specs['ring_width']
            ring_len = tot_dim = ring_master.tot_dim
            offset = (ring_len - ind_master.tot_dim) // 2
        else:
            ring_width = 0
            ring_len = 0
            ring_master: Optional[IndRing] = None
            offset = 0
            tot_dim = ind_master.tot_dim

        # find extra ring offset for putting lead on grid
        ind_lead_coord = []
        for coord in ind_master.lead_coord:
            ind_lead_coord.append((coord[0] + offset, coord[1] + offset))

        if orient in (Orientation.R0, Orientation.MY) and layid % 2 == 1 or \
                orient is Orientation.R270 and layid % 2 == 0:
            term0_idx = self.grid.coord_to_track(layid, ind_lead_coord[0][1], RoundMode.NEAREST)
            term1_idx = self.grid.coord_to_track(layid, ind_lead_coord[1][1], RoundMode.NEAREST)
            term0_coord = self.grid.track_to_coord(layid, term0_idx)
            term1_coord = self.grid.track_to_coord(layid, term1_idx)
            offset2 = (term0_coord + term1_coord - ind_lead_coord[0][1] - ind_lead_coord[1][1]) // 2
            offset_ring_x = 0
            offset_ring_y = offset2
        elif orient is Orientation.R270 and layid % 2 == 1 or \
                orient in (Orientation.R0, Orientation.MY) and layid % 2 == 0:
            term0_idx = self.grid.coord_to_track(layid - 1, ind_lead_coord[0][0], RoundMode.NEAREST)
            term1_idx = self.grid.coord_to_track(layid - 1, ind_lead_coord[1][0], RoundMode.NEAREST)
            term0_coord = self.grid.track_to_coord(layid - 1, term0_idx)
            term1_coord = self.grid.track_to_coord(layid - 1, term1_idx)
            offset2 = (term0_coord + term1_coord - ind_lead_coord[0][0] - ind_lead_coord[1][0]) // 2
            offset_ring_x = offset2
            offset_ring_y = 0
        else:
            raise NotImplementedError('Not supported yet.')

        # find overall Transform
        xform = Transform(dx=offset_ring_x + offset, dy=offset_ring_y + offset)
        xform_ring = Transform(dx=offset_ring_x, dy=offset_ring_y)

        # update coords of ind_master
        ind_path_coord = []
        for turn in ind_master.path_coord:
            path_n = []
            for path in turn:
                coord_n = []
                for coord in path:
                    coord_n.append((coord[0] + xform.x, coord[1] + xform.y))
                path_n.append(coord_n)
            ind_path_coord.append(path_n)

        ind_lead_coord = []
        for coord in ind_master.lead_coord:
            ind_lead_coord.append((coord[0] + xform.x, coord[1] + xform.y))

        center_tap_coord = ind_master.center_tap_coord
        ind_center_tap_coord = (center_tap_coord[0] + xform.x, center_tap_coord[1] + xform.y)

        # place inductor
        self.add_instance(ind_master, inst_name='XIND', xform=xform)

        # place inductor guard ring
        if w_ring:
            # update coords of ring_master
            ring_path_coord = []
            for turn in ring_master.inner_path_coord:
                path_n = []
                for path in turn:
                    coord_n = []
                    for coord in path:
                        coord_n.append((coord[0] + xform_ring.x, coord[1] + xform_ring.y))
                    path_n.append(coord_n)
                ring_path_coord.append(path_n)
            ring_inst = self.add_instance(ring_master, inst_name='XRING', xform=xform_ring)
            self.reexport(ring_inst.get_port('VSS'))
            if orient is Orientation.R0:
                self.reexport(ring_inst.get_port('VSS1'))
        else:
            ring_path_coord = None

        # draw leads
        term0, term1, term_res_w = self._draw_lead(layid, width, lead_len, ind_lead_coord, pin_len,
                                                   res1_l, res2_l, res_space, ring_len, ring_width, orient)
        # add pins
        self.add_pin('P1', term0)
        self.add_pin('P2', term1)
        if orient in (Orientation.MY, Orientation.R180, Orientation.R270):
            res1_l, res2_l = res2_l, res1_l

        # draw center tap
        if center_tap:
            res3_l: int = center_tap_specs['res3_l']
            tap_len: int = center_tap_specs['tap_len']
            tap = self._draw_center_tap(width, n_turn, tap_len, layid, pin_len, res3_l, res_space, ind_center_tap_coord,
                                        orient)
            self.add_pin('PC', tap)
        else:
            res3_l = 0

        # draw fill
        if w_fill:
            self._draw_fill(n_side, ind_path_coord, width, layid, fill_specs, ring_path_coord, ring_width, orient)

        # set array_box
        self.set_size_from_bound_box(layid, BBox(0, 0, tot_dim + offset_ring_x, tot_dim + offset_ring_y), round_up=True)

        # add inductor ID layer
        id_lp = self.grid.tech_info.tech_params['inductor']['id_lp']
        self.add_rect(id_lp, BBox(offset_ring_x, offset_ring_y, tot_dim + offset_ring_x, tot_dim + offset_ring_y))

        # Step 8: get schematic parameters
        self.sch_params = dict(
            res1_l=res1_l,
            res2_l=res2_l,
            res3_l=res3_l,
            res_w=term_res_w,
            res_layer=layid,
            center_tap=center_tap,
            w_ring=w_ring,
        )
