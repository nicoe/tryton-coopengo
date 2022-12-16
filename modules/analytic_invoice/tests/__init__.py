# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.analytic_invoice.tests.test_analytic_invoice import suite
except ImportError:
    from .test_analytic_invoice import suite

__all__ = ['suite']
