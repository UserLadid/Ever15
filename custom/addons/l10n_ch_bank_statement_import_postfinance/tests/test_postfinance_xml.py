# Copyright 2015 Nicolas Bessi Camptocamp SA
# Copyright 2017-2019 Compassion CH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64
import re
import datetime
from odoo.modules import get_module_resource
from odoo.tests import common


def get_file_content(filename):
    filepath = get_module_resource(
        'l10n_ch_bank_statement_import_postfinance',
        'test_files',
        filename
    )
    with open(filepath, 'rb') as data_file:
        return data_file.read()


class PFXMLParserTest(common.TransactionCase):

    def setUp(self):
        super(PFXMLParserTest, self).setUp()
        self.data_file = get_file_content('demo_pf_ch.tar.gz')
        self.parser = self.env['account.statement.import.camt.parser']

    def test_file_uncompress(self):
        """Test that tar file is uncompressed correctly"""
        self.parser._check_postfinance_attachments(self.data_file)
        self.assertTrue(
            re.search(r'\<BkToCstmrStmt', self.parser.data_file.decode())
        )

    def test_parser_can_open_non_tar(self):
        """Test that non compressed file can be read"""
        raw = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.04"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="urn:iso:std:iso:20022:tech:xsd:camt.053.001.04
 camt.053.001.04.xsd">
<BkToCstmrStmt><GrpHdr></GrpHdr></BkToCstmrStmt>
</Document>
"""
        self.parser._check_postfinance_attachments(raw)
        self.assertEqual(self.parser.data_file, raw)

    def test_attachments_detection(self):
        """Test attachments detection"""
        self.parser._check_postfinance_attachments(self.data_file)
        self.assertIsNotNone(self.parser.attachments)

    def test_parse(self):
        """Test file is correctly parsed"""
        currency_code, account_number, statements = self.parser.parse(
            self.data_file)
        self.assertEqual('CH0309000000250090342', account_number)
        self.assertEqual('CHF', currency_code)
        self.assertIsInstance(statements, list)
        self.assertEqual(len(statements), 1)
        self.assertTrue(all(isinstance(x, dict) for x in statements))
        statement = statements[0]
        self.assertTrue(
            all(isinstance(x, dict)for x in statement['transactions']))
        self.assertEqual(559026015.20, statement['balance_start'])
        self.assertEqual(559048788.30, statement['balance_end_real'])
        self.assertEqual(9, len(statement['transactions']))
        first_transaction = {
            'file_ref': '20160414001203000300003',
            'amount': 50.0,
            'date': '2017-03-30',
            'ref': 'CLXPMZW000000004'
        }
        parsed_transaction = statement['transactions'][0]
        self.assertDictContainsSubset(first_transaction, parsed_transaction)

    def test_attachement_extraction(self):
        """Test if scan are extracted correctly"""
        attachments = self.parser.parse(self.data_file)[2][0]['attachments']
        self.assertEqual(
            set(['Statement File',
                 '20160414001203000300003', '20160414001203000300004',
                 '20160414001203000300005', '20160414001203000300006']),
            set([a[0] for a in attachments])
        )


class PostFinanceImportTest(common.TransactionCase):

    def setUp(self):
        super(PostFinanceImportTest, self).setUp()
        bank = self.env['res.partner.bank'].create({
            'acc_number': 'CH0309000000250090342',
            'partner_id': self.env.ref('base.main_partner').id,
            'company_id': self.env.ref('base.main_company').id,
            'bank_id': self.env.ref('base.res_bank_1').id,
        })
        self.env['account.journal'].create({
            'name': 'Bank Journal - (test postfinance)',
            'code': 'TBNKPFNC',
            'type': 'bank',
            'bank_account_id': bank.id,
        })
        self.company_a = self.env.ref('base.main_company')
        currency = self.env.ref('base.CHF')
        currency.active = True
        self.company_a.write(
            {'currency_id': currency.id}
        )

    def test_postfinance_xml_import(self):
        """Test if postfinance statement is correct"""
        action = self.env['account.statement.import'].create({
            'data_file': base64.b64encode(get_file_content(
                'demo_pf_ch.tar.gz')),
        }).import_file()
        statements = self.env['account.bank.statement'].browse(
            action['context'].get('statement_ids')
        )
        self.assertEqual(len(statements), 1)
        self.assertEqual(559026015.20, statements.balance_start)
        self.assertEqual(559048788.30, statements.balance_end_real)
        self.assertEqual(9, len(statements.line_ids))
        self.assertTrue(statements.journal_id)
        self.assertEqual(4, len(statements.mapped('line_ids.related_file')))
        st_line = statements.line_ids.sorted('id')[0]
        # Read common infos of first line
        self.assertEqual(st_line.date, datetime.date(2017, 3, 30))
        self.assertEqual(st_line.amount, 50.0)
        self.assertEqual(st_line.name, '20160414001203000300003')

        # Test image is in reconcile view
        lines_with_attach = statements.mapped('line_ids').filtered(
            'related_file')
        for line in lines_with_attach:
            data = self.env['account.reconciliation.widget']._get_statement_line(line)
            self.assertIn('img_src', data.keys())

        # Test click icon returns an action
        self.assertIsInstance(lines_with_attach[0].click_icon(), dict)
