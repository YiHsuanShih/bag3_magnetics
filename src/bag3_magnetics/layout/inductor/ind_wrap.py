# -*- coding: utf-8 -*-
import numpy as np
from typing import List, Mapping, Any, Union, Optional, Type

from bag.layout.template import TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.design.module import Module

from pybag.enum import Orientation
from pybag.core import Transform

from .util import IndTemplate, round_up
from .ind_core import IndCore
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
            lead_len='inductor terminal length',

            w_ring='True to have guard ring, False by default',
            ring_specs='Specs for guard ring, Optional',
            # ring_spacing='spacing between ring and inductor',
            # ring_width='ring width',
            # ring_gap='gap distance between rings',
            # ring_turn='ring turn number',
            # ring_laylist='ring layer list',
            # ring_conn_n='ring connection numbers',
            # ring_conn_width='ring connection width',

            center_tap='True to have center tap, False by default',
            center_tap_specs='Specs for center tap, Optional',
            # res3_l='length of metal resistor connecting to PC',
            # tap_len='inductor tap length',

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

            min_width='minimum width because of CV via',
            min_spacing='minimum spacing between turns',
            res1_l='length of metal resistor connecting to P1',
            res2_l='length of metal resistor connecting to P2',
            pin_len='pin length',
            res_space='metal resistor space to pin',
            # debug_ring='True to debug ring',
            orient='orientation of inductor',
            short_terms='True to make shorted terminals'
        )

    @classmethod
    def get_default_param_values(cls) -> Mapping[str, Any]:
        return dict(
            orient=Orientation.R0,
            # debug_ring=False,
            short_terms=False,
            w_ring=False,
            ring_specs=None,
            center_tap=False,
            center_tap_specs=None,
        )

    def draw_layout(self):
        n_turn: int = self.params['n_turn']
        layid: int = self.params['layid']
        radius: int = self.params['radius']
        spacing: int = self.params['spacing']
        width: int = self.params['width']
        opening: int = self.params['opening']
        via_width: int = self.params['via_width']
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

        min_width: int = self.params['min_width']
        min_spacing: int = self.params['min_spacing']
        res1_l: int = self.params['res1_l']
        res2_l: int = self.params['res2_l']
        pin_len: int = self.params['pin_len']
        res_space: int = self.params['res_space']
        # debug_ring: bool = self.params['debug_ring']
        # short_terms: bool = self.params['short_terms']
        orient: Union[str, Orientation] = self.params['orient']
        if isinstance(orient, str):
            orient = Orientation[orient]

        # current generator limitations
        if w_ring and center_tap:
            raise ValueError('Generator does not support both w_ring and center_tap being True simultaneously.')

        # hard coded number of side
        n_side = 8

        ind_params = dict(
            n_turn=n_turn,
            layid=layid,
            radius=radius,
            spacing=spacing,
            width=width,
            opening=opening,
            via_width=via_width,
            min_width=min_width,
            min_spacing=min_spacing,
        )

        ind_master: IndCore = self.new_template(IndCore, params=ind_params)

        # draw guard ring
        if w_ring:
            ring_spacing: int = ring_specs['ring_spacing']
            ring_width: int = ring_specs['ring_width']
            ring_gap: int = ring_specs['ring_gap']
            ring_turn: int = ring_specs['ring_turn']
            ring_laylist: List[int] = ring_specs['ring_laylist']
            ring_conn_n: int = ring_specs['ring_conn_n']
            ring_conn_width: int = ring_specs['ring_conn_width']

            # ring half length
            tot_dim = ind_master.tot_dim + 2 * (ring_spacing + ring_width)
            ring_hflen = -(- tot_dim // 2) - (ring_width // 2)
            ring_conn, ring_lenarr = self._draw_ind_ring(ring_hflen, ring_width, ring_gap, ring_turn,
                                                         ring_conn_n, ring_conn_width, width, opening,
                                                         layid, ring_laylist, orient=orient,
                                                         pin_len=pin_len)
            ring_len = tot_dim = ring_lenarr[-1] + ring_width // 2
            self.add_pin('VSS', ring_conn)
            offset = (tot_dim - ind_master.tot_dim) // 2
        else:
            ring_width = 0
            ring_len = 0
            offset = 0
            tot_dim = ind_master.tot_dim

        lead_coord = ind_master.lead_coord
        ind_lead_coord = []
        center_tap_coord = ind_master.center_tap_coord
        if orient is Orientation.R0:
            xform = Transform(dx=offset, dy=offset)
            for coord in lead_coord:
                ind_lead_coord.append((coord[0] + offset, coord[1] + offset))
            ind_center_tap_coord = (center_tap_coord[0] + offset, center_tap_coord[1] + offset)
        elif orient is Orientation.R90:
            xform = Transform(dx=tot_dim - offset, dy=offset, mode=orient)
            for coord in lead_coord:
                ind_lead_coord.append((coord[0] + tot_dim - offset, coord[1] + offset))
            ind_center_tap_coord = (center_tap_coord[0] + tot_dim - offset, center_tap_coord[1] + offset)
        else:
            raise NotImplementedError(f'orient={orient} not implemented yet.')
        # place inductor
        self.add_instance(ind_master, inst_name='XIND', xform=xform)

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
            tap = self._draw_center_tap(width, n_turn, tap_len, layid, pin_len, res3_l, res_space, ind_center_tap_coord)
            self.add_pin('PC', tap)
        else:
            res3_l = 0

        # set array_box
        self.set_size_from_bound_box(layid, BBox(0, 0, tot_dim, tot_dim), round_up=True)

        # Step 8: get schematic parameters
        self.sch_params = dict(
            res1_l=res1_l,
            res2_l=res2_l,
            res3_l=res3_l,
            res_w=term_res_w,
            res_layer=layid,
            center_tap=center_tap,
            # short_terms=short_terms,
        )
