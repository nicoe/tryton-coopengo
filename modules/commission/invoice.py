# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow, fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

from trytond.modules.product import round_price


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'
    agent = fields.Many2One('commission.agent', 'Commission Agent',
        domain=[
            ('type_', '=', 'agent'),
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': Eval('type') == 'in',
            'readonly': Eval('state', '') != 'draft',
            },
        depends=['type', 'company', 'state'],
        help="The agent who receives a commission for the invoice.")

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        # Create commission only the first time the invoice is posted
        to_commission = [i for i in invoices
            if i.state not in ['posted', 'paid']]
        super(Invoice, cls).post(invoices)
        cls.create_commissions(to_commission)

    @classmethod
    def create_commissions(cls, invoices):
        pool = Pool()
        Commission = pool.get('commission')
        all_commissions = []
        for invoice in invoices:
            for line in invoice.lines:
                commissions = line.get_commissions()
                if commissions:
                    all_commissions.extend(commissions)

        Commission.save(all_commissions)
        return all_commissions

    @classmethod
    @Workflow.transition('paid')
    def paid(cls, invoices):
        super(Invoice, cls).paid(invoices)
        if invoices:
            cls._set_paid_commissions_dates(invoices)

    @classmethod
    def _set_paid_commissions_dates(cls, invoices):
        pool = Pool()
        Date = pool.get('ir.date')
        Commission = pool.get('commission')
        InvoiceLine = pool.get('account.invoice.line')

        today = Date.today()

        for sub_invoices in grouped_slice(invoices):
            ids = [i.id for i in sub_invoices]
            commissions = Commission.search([
                    ('date', '=', None),
                    ('origin', 'in', [str(x) for x in InvoiceLine.search(
                                [('invoice', 'in', ids)])]),
                    ])
            Commission.write(commissions, {
                    'date': today,
            })

    @classmethod
    def _get_commissions_to_delete(cls, ids):
        # Declared to be overloaded for performances improvements
        # We should improve or overload the field `reference`
        Commission = Pool().get('commission')
        return Commission.search([
                ('invoice_line', '=', None),
                ('origin.invoice', 'in', ids, 'account.invoice.line'),
                ])

    @classmethod
    def _get_commissions_to_cancel(cls, ids):
        # Declared to be overloaded for performances improvements
        # We should improve or overload the field `reference`
        Commission = Pool().get('commission')
        return Commission.search([
                ('invoice_line', '!=', None),
                ('origin.invoice', 'in', ids, 'account.invoice.line'),
                ])

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, invoices):
        # Because domain resolution of the field `reference` creates
        # a non-optimized query: we temporary created two function to be
        # overloaded
        # Issue: 2913
        pool = Pool()
        Commission = pool.get('commission')

        super(Invoice, cls).cancel(invoices)

        to_delete = []
        for sub_invoices in grouped_slice(invoices):
            ids = [i.id for i in sub_invoices]
            to_delete += cls._get_commissions_to_delete(ids)
            to_cancel = cls._get_commissions_to_cancel(ids)
            Commission.cancel(to_cancel)

        Commission.delete(to_delete)

    def _credit(self, **values):
        values.setdefault('agent', self.agent)
        return super()._credit(**values)


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    principal = fields.Many2One('commission.agent', 'Commission Principal',
        domain=[
            ('type_', '=', 'principal'),
            ('company', '=', Eval('_parent_invoice', {}).get('company',
                    Eval('company', -1))),
            ],
        states={
            'invisible': If(Bool(Eval('_parent_invoice')),
                Eval('_parent_invoice', {}).get('type') == 'in',
                Eval('invoice_type') == 'in'),
            }, depends=['invoice_type', 'company'],
        help="The principal who pays a commission for the invoice line.")
    commissions = fields.One2Many('commission', 'origin', 'Commissions',
        readonly=True,
        states={
            'invisible': ~Eval('commissions'),
            })
    from_commissions = fields.One2Many('commission', 'invoice_line',
        'From Commissions', readonly=True,
        states={
            'invisible': ~Eval('from_commissions'),
            })

    @property
    def agent_plans_used(self):
        "List of agent, plan tuple"
        used = []
        if self.invoice.agent:
            used.append((self.invoice.agent, self.invoice.agent.plan))
        if self.principal:
            used.append((self.principal, self.principal.plan))
        return used

    def get_commissions(self):
        pool = Pool()
        Commission = pool.get('commission')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        if self.type != 'line':
            return []

        today = Date.today()
        commissions = []
        for agent, plan in self.agent_plans_used:
            if not plan:
                continue
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.invoice.currency,
                    self.amount, agent.currency, round=False)
            amount = self._get_commission_amount(amount, plan)
            if amount:
                amount = round_price(amount)
            if not amount:
                continue

            commission = Commission()
            commission.origin = self
            if plan.commission_method == 'posting':
                commission.date = today
            commission.agent = agent
            commission.product = plan.commission_product
            commission.amount = amount
            commissions.append(commission)
        return commissions

    def _get_commission_amount(self, amount, plan, pattern=None):
        return plan.compute(amount, self.product, pattern=pattern)

    @fields.depends('product', 'principal')
    def on_change_product(self):
        super(InvoiceLine, self).on_change_product()
        if self.product:
            if self.product.principals:
                if self.principal not in self.product.principals:
                    self.principal = self.product.principal
            elif self.principal:
                self.principal = None

    @classmethod
    def view_attributes(cls):
        return super(InvoiceLine, cls).view_attributes() + [
            ('//page[@id="commissions"]', 'states', {
                    'invisible': Eval('type') != 'line',
                    })]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('commissions', None)
        default.setdefault('from_commissions', None)
        return super(InvoiceLine, cls).copy(lines, default=default)
