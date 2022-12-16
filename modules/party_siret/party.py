#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields
from trytond.pyson import Not, Bool, Eval
import luhn


class Party(Model):
    _name = 'party.party'

    siren = fields.Char('SIREN', select=1, states={
        'readonly': Not(Bool(Eval('active'))),
        }, size=9)

    def __init__(self):
        super(Party, self).__init__()
        self._constraints += [
            ('check_siren', 'invalid_siren'),
        ]
        self._error_messages.update({
            'invalid_siren': 'Invalid SIREN number!',
        })

    def check_siren(self, ids):
        '''
        Check validity of SIREN
        '''
        for party in self.browse(ids):
            if party.siren:
                if len(party.siren) != 9 or not luhn.validate(party.siren):
                    return False
        return True

Party()
