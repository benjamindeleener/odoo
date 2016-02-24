# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from openerp.addons.sale.tests.test_sale_common import TestSale


class TestSaleExpense(TestSale):
    def test_sale_expense(self):
        """ Test the behaviour of sales orders when managing expenses """
        # create a so with a product invoiced on delivery
        prod = self.env.ref('product.product_product_1')
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'partner_invoice_id': self.partner.id,
            'partner_shipping_id': self.partner.id,
            'order_line': [(0, 0, {'name': prod.name, 'product_id': prod.id, 'product_uom_qty': 2, 'product_uom': prod.uom_id.id, 'price_unit': prod.list_price})],
            'pricelist_id': self.env.ref('product.list0').id,
        })
        so._compute_tax_id()
        so.action_confirm()
        so._create_analytic_account()  # normally created at so confirmation when you use the right products
        init_price = so.amount_total

        # create some expense and validate it (expense at cost)
        prod_exp_1 = self.env.ref('hr_expense.air_ticket')
        company = self.env.ref('base.main_company')
        journal = self.env['account.journal'].create({'name': 'Purchase Journal - Test', 'code': 'HRTPJ', 'type': 'purchase', 'company_id': company.id})
        account_payable = self.env['account.account'].create({'code': 'X1111', 'name': 'HR Expense - Test Payable Account', 'user_type_id': self.env.ref('account.data_account_type_payable').id, 'reconcile': True})
        employee = self.env['hr.employee'].create({'name': 'Test employee', 'user_id': self.user.id, 'address_home_id': self.user.partner_id.id})
        self.user.partner_id.property_account_payable_id = account_payable.id
        exp = self.env['hr.expense'].create({
            'name': 'Air Travel',
            'product_id': prod_exp_1.id,
            'analytic_account_id': so.project_id.id,
            'unit_amount': 621.54,
            'journal_id': journal.id,
            'employee_id': employee.id,
        })
        # Submit to Manager
        exp.submit_expenses()
        # Approve
        exp.approve_expenses()
        # Create Expense Entries
        exp.action_move_create()
        # expense should now be in sales order
        self.assertTrue(prod_exp_1 in map(lambda so: so.product_id, so.order_line), 'Sale Expense: expense product should be in so')
        sol = so.order_line.filtered(lambda sol: sol.product_id.id == prod_exp_1.id)
        self.assertEqual((sol.price_unit, sol.qty_delivered), (621.54, 1.0), 'Sale Expense: error when invoicing an expense at cost')
        self.assertEqual(so.amount_total, init_price, 'Sale Expense: price of so not updated after adding expense')

        # create some expense and validate it (expense at sales price)
        init_price = so.amount_total
        prod_exp_2 = self.env.ref('hr_expense.car_travel')
        exp = self.env['hr.expense'].create({
            'name': 'Car Travel',
            'product_id': prod_exp_2.id,
            'analytic_account_id': so.project_id.id,
            'product_uom_id': self.env.ref('product.product_uom_km').id,
            'unit_amount': 0.15,
            'quantity': 100,
            'journal_id': journal.id,
            'employee_id': employee.id,
        })
        # Submit to Manager
        exp.submit_expenses()
        # Approve
        exp.approve_expenses()
        # Create Expense Entries
        exp.action_move_create()
        # expense should now be in sales order
        self.assertTrue(prod_exp_2 in map(lambda so: so.product_id, so.order_line), 'Sale Expense: expense product should be in so')
        sol = so.order_line.filtered(lambda sol: sol.product_id.id == prod_exp_2.id)
        self.assertEqual((sol.price_unit, sol.qty_delivered), (prod_exp_2.list_price, 100.0), 'Sale Expense: error when invoicing an expense at cost')
        self.assertEqual(so.amount_total, init_price, 'Sale Expense: price of so not updated after adding expense')
        # self.assertTrue(so.invoice_status, 'no', 'Sale Expense: expenses should not impact the invoice_status of the so')

        # both expenses should be invoiced
        inv_id = so.action_invoice_create()
        inv = self.env['account.invoice'].browse(inv_id)
        self.assertEqual(inv.amount_untaxed, 621.54 + (prod_exp_2.list_price * 100.0), 'Sale Expense: invoicing of expense is wrong')

    def test_cost_invoicing(self):
        """ Test confirming a vendor invoice to cost on the so """
        serv_cost = self.env.ref('product.service_cost_01')
        prod_gap = self.env.ref('product.product_product_1')
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'partner_invoice_id': self.partner.id,
            'partner_shipping_id': self.partner.id,
            'order_line': [(0, 0, {'name': prod_gap.name, 'product_id': prod_gap.id, 'product_uom_qty': 2, 'product_uom': prod_gap.uom_id.id, 'price_unit': prod_gap.list_price})],
            'pricelist_id': self.env.ref('product.list0').id,
        })
        so.action_confirm()
        so._create_analytic_account()
        inv_partner = self.env.ref('base.res_partner_2')
        company = self.env.ref('base.main_company')
        journal = self.env['account.journal'].create({'name': 'Purchase Journal - Test', 'code': 'STPJ', 'type': 'purchase', 'company_id': company.id})
        account_payable = self.env['account.account'].create({'code': 'X1111', 'name': 'Sale - Test Payable Account', 'user_type_id': self.env.ref('account.data_account_type_payable').id, 'reconcile': True})
        account_income = self.env['account.account'].create({'code': 'X1112', 'name': 'Sale - Test Account', 'user_type_id': self.env.ref('account.data_account_type_direct_costs').id})
        invoice_vals = {
            'name': '',
            'type': 'in_invoice',
            'partner_id': inv_partner.id,
            'invoice_line_ids': [(0, 0, {'name': serv_cost.name, 'product_id': serv_cost.id, 'quantity': 2, 'uom_id': serv_cost.uom_id.id, 'price_unit': serv_cost.standard_price, 'account_analytic_id': so.project_id.id, 'account_id': account_income.id})],
            'account_id': account_payable.id,
            'journal_id': journal.id,
            'currency_id': company.currency_id.id,
        }
        inv = self.env['account.invoice'].create(invoice_vals)
        inv.signal_workflow('invoice_open')
        sol = so.order_line.filtered(lambda l: l.product_id == serv_cost)
        self.assertTrue(sol, 'Sale: cost invoicing does not add lines when confirming vendor invoice')
        self.assertTrue(sol.price_unit == 160 and sol.qty_delivered == 2 and sol.product_uom_qty == sol.qty_invoiced == 0, 'Sale: line is wrong after confirming vendor invoice')
