# -*- coding: utf-8 -*-

import time
from openerp import api, models


class ReportPartnerLedger(models.AbstractModel):
    _name = 'report.account_extra_reports.report_partnerledger'

    def _lines(self, data, partner):
        full_account = []
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        reconcile_clause = "" if data['form']['reconciled'] else "AND \"account_move_line\".reconciled = false "
        params = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        self.env.cr.execute(
            "SELECT \"account_move_line\".id, \"account_move_line\".date, j.code, acc.code as a_code, acc.name as a_name, \"account_move_line\".ref, m.name as move_name, \"account_move_line\".name, \"account_move_line\".debit, \"account_move_line\".credit, \"account_move_line\".amount_currency,\"account_move_line\".currency_id, c.symbol AS currency_code " \
            "FROM " + query_get_data[0] + " " \
            "LEFT JOIN account_journal j " \
                "ON (\"account_move_line\".journal_id = j.id) " \
            "LEFT JOIN account_account acc " \
                "ON (\"account_move_line\".account_id = acc.id) " \
            "LEFT JOIN res_currency c ON (\"account_move_line\".currency_id=c.id)" \
            "LEFT JOIN account_move m ON (m.id=\"account_move_line\".move_id)" \
            "WHERE \"account_move_line\".partner_id = %s " \
                "AND m.state IN %s " \
                "AND \"account_move_line\".account_id IN %s AND " + query_get_data[1] +" " \
                " " + reconcile_clause + " "\
                "ORDER BY \"account_move_line\".date",
                tuple(params))
        res = self.env.cr.dictfetchall()
        sum = 0.0
        for r in res:
            r['displayed_name'] = '-'.join(
                r['move_name'] not in ['', '/'] and [r['move_name']] or [] +
                r['ref'] not in ['', '/'] and [r['ref']] or [] +
                r['name'] not in ['', '/'] and [r['name']] or []
                )
            sum += r['debit'] - r['credit']
            r['progress'] = sum
            full_account.append(r)
        return full_account

    def _sum_partner(self, data, partner, field):
        if field not in ['debit', 'credit', 'debit - credit']:
            return
        result_tmp = 0.0
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        reconcile_clause = "" if data['form']['reconciled'] else "AND \"account_move_line\".reconciled = false "

        params = [partner.id, tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        self.env.cr.execute(
                "SELECT sum(" + field + ") " \
                "FROM " + query_get_data[0] + ",  " \
                "account_move AS m "
                "WHERE \"account_move_line\".partner_id = %s " \
                    "AND m.id = \"account_move_line\".move_id " \
                    "AND m.state IN %s "
                    "AND account_id IN %s" \
                    " " + reconcile_clause + " " \
                    "AND " + query_get_data[1] + " ",
                tuple(params))

        contemp = self.env.cr.fetchone()
        if contemp is not None:
            result_tmp = contemp[0] or 0.0
        else:
            result_tmp = result_tmp + 0.0

        return result_tmp

    @api.multi
    def render_html(self, data):
        data['computed'] = {}

        obj_partner = self.env['res.partner']
        query_get_data = self.env['account.move.line'].with_context(data['form'].get('used_context', {}))._query_get()
        data['computed']['move_state'] = ['draft', 'posted']
        if data['form'].get('target_move', 'all') == 'posted':
            data['computed']['move_state'] = ['posted']
        result_selection = data['form'].get('result_selection', 'customer')
        if result_selection == 'supplier':
            data['computed']['ACCOUNT_TYPE'] = ['payable']
        elif result_selection == 'customer':
            data['computed']['ACCOUNT_TYPE'] = ['receivable']
        else:
            data['computed']['ACCOUNT_TYPE'] = ['payable', 'receivable']

        self.env.cr.execute(
            "SELECT a.id " \
            "FROM account_account a " \
                'WHERE a.internal_type IN %s ' \
                "AND NOT a.deprecated", (tuple(data['computed']['ACCOUNT_TYPE']),))
        data['computed']['account_ids'] = [a for (a,) in self.env.cr.fetchall()]
        params = [tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        reconcile_clause = "" if data['form']['reconciled'] else "AND \"account_move_line\".reconciled = false "
        self.env.cr.execute(
                "SELECT DISTINCT \"account_move_line\".partner_id " \
                "FROM " + query_get_data[0] + ",account_account AS account, " \
                " account_move AS am " \
                "WHERE \"account_move_line\".partner_id IS NOT NULL " \
                    "AND \"account_move_line\".account_id = account.id " \
                    "AND am.id = \"account_move_line\".move_id " \
                    "AND am.state IN %s"
                    "AND \"account_move_line\".account_id IN %s " \
                    "AND " + query_get_data[1] +" " \
                    "AND NOT account.deprecated " + reconcile_clause + " ", tuple(params))
        partner_ids = [res['partner_id'] for res in self.env.cr.dictfetchall()]
        partners = obj_partner.browse(partner_ids)
        partners = sorted(partners, key=lambda x: (x.ref, x.name))

        docargs = {
            'doc_ids': partner_ids,
            'doc_model': self.env['res.partner'],
            'data': data,
            'docs': partners,
            'time': time,
            'lines': self._lines,
            'sum_partner': self._sum_partner,
        }
        return self.env['report'].render('account_extra_reports.report_partnerledger', docargs)
