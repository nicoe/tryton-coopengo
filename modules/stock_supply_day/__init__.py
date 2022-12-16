# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import purchase


def register():
    Pool.register(
        purchase.ProductSupplier,
        purchase.ProductSupplierDay,
        module='stock_supply_day', type_='model')
