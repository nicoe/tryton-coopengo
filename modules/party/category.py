# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.conditionals import Coalesce
from sql.operators import Equal

from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, Exclude, tree)

SEPARATOR = ' / '


class Category(DeactivableMixin, tree(separator=' / '), ModelSQL, ModelView):
    "Category"
    __name__ = 'party.category'
    name = fields.Char(
        "Name", required=True, translate=True,
        help="The main identifier of the category.")
    parent = fields.Many2One(
        'party.category', "Parent", select=True,
        help="Add the category below the parent.")
    childs = fields.One2Many(
        'party.category', 'parent', "Children",
        help="Add children below the category.")

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('name_parent_exclude',
                Exclude(t, (t.name, Equal), (Coalesce(t.parent, -1), Equal)),
                'party.msg_category_name_unique'),
            ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Category, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 4.6: replace unique by exclude
        table_h.drop_constraint('name_parent_uniq')

    @classmethod
    def validate(cls, categories):
        super(Category, cls).validate(categories)
        cls.check_recursion(categories)
        for category in categories:
            category.check_name()

    def check_name(self):
        if SEPARATOR in self.name:
            self.raise_user_error('wrong_name', (self.name,))

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + SEPARATOR + self.name
        return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if isinstance(clause[2], str):
            values = clause[2].split(SEPARATOR)
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name))
                field = 'parent.' + field
            return domain
        # TODO Handle list
        return [('name',) + tuple(clause[1:])]
