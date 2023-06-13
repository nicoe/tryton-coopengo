# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.model import MultiValueMixin, ValueMixin
from trytond.pool import Pool
from trytond.tools.multivalue import migrate_property

party_sequence = fields.Many2One('ir.sequence', 'Party Sequence',
    domain=[
        ('code', '=', 'party.party'),
        ],
    help="Used to generate the party code.")
party_lang = fields.Many2One("ir.lang", 'Party Language',
    help="The default language for new parties.")


class Configuration(ModelSingleton, ModelSQL, ModelView, MultiValueMixin):
    'Party Configuration'
    __name__ = 'party.configuration'

    party_sequence = fields.MultiValue(party_sequence)
    party_lang = fields.MultiValue(party_lang)

    @classmethod
    def default_party_sequence(cls, **pattern):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('party', 'sequence_party')
        except KeyError:
            return None


class _ConfigurationValue(ModelSQL):

    _configuration_value_field = None

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(_ConfigurationValue, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append(cls._configuration_value_field)
        value_names.append(cls._configuration_value_field)
        migrate_property(
            'party.configuration', field_names, cls, value_names,
            fields=fields)


class ConfigurationSequence(_ConfigurationValue, ModelSQL, ValueMixin):
    'Party Configuration Sequence'
    __name__ = 'party.configuration.party_sequence'
    party_sequence = party_sequence
    _configuration_value_field = 'party_sequence'

    @classmethod
    def check_xml_record(cls, records, values):
        return True


class ConfigurationLang(_ConfigurationValue, ModelSQL, ValueMixin):
    'Party Configuration Lang'
    __name__ = 'party.configuration.party_lang'
    party_lang = party_lang
    _configuration_value_field = 'party_lang'

    @classmethod
    def restore_default_party_lang_from_4_2(cls):
        from trytond.transaction import Transaction
        from sql import Null, Table, Cast
        from sql.operators import Concat
        from trytond.pool import Pool

        if not backend.TableHandler.table_exist('ir_property'):
            return

        pool = Pool()
        property = Table('ir_property')
        Lang = pool.get('ir.lang')
        field = pool.get('ir.model.field').__table__()
        lang = Lang.__table__()
        cursor = Transaction().connection.cursor()

        query_table = property.join(lang, condition=(
                property.value == Concat('ir.lang,', Cast(lang.id, 'VARCHAR'))
                )).join(field, condition=((property.field == field.id) &
                        (field.name == 'lang')))

        cursor.execute(
            *query_table.select(lang.id, where=property.res == Null))
        result = cursor.fetchone()
        if result:
            result = list(result)
            default_lang = Lang(result[0])
            print('Default Language restored [%s]' % default_lang.rec_name)
            pool.get('party.configuration.party_lang'
                ).create([{'party_lang': default_lang}])
        else:
            print('No default language on party configuration found')

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        super(ConfigurationLang, cls)._migrate_property(field_names,
            value_names, fields)
        cls.restore_default_party_lang_from_4_2()
