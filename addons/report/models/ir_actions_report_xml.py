# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report.xml'

    paperformat_id = fields.Many2one('report.paperformat', 'Paper format')

    @api.multi
    def associated_view(self):
        """Used in the ir.actions.report.xml form view in order to search naively after the view(s)
        used in the rendering.
        """
        self.ensure_one()
        action_ref = self.env.ref('base.action_ui_view', False)
        if not action_ref:
            return False
        action_data = action_ref.read()[0]
        action_data['domain'] = [('name', 'ilike', self.report_name.split('.')[1]), ('type', '=', 'qweb')]
        return action_data
