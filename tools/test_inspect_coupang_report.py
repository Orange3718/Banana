import io
import tempfile
from pathlib import Path
import unittest
import zipfile
from inspect_coupang_report import inspect_report, preserve_receipt


def workbook(body='', duplicate=False):
    out = io.BytesIO()
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="clicks" r:id="a"/><sheet name="orders" r:id="b"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="a" Target="worksheets/a.xml"/><Relationship Id="b" Target="worksheets/b.xml"/></Relationships>')
        header = '<row r="1"><c r="A1" t="inlineStr"><is><t>날짜</t></is></c>'
        if duplicate:
            header += '<c r="B1" t="inlineStr"><is><t>날짜</t></is></c>'
        header += '</row>'
        for letter in 'ab':
            archive.writestr(f'xl/worksheets/{letter}.xml', f'<worksheet xmlns="{ns}"><sheetData>{header}{body}</sheetData></worksheet>')
    return out.getvalue()


class ReportTests(unittest.TestCase):
    def test_empty_is_not_zero(self):
        result = inspect_report(workbook())
        self.assertEqual(result['state'], 'empty_report')
        self.assertIsNone(result['confirmed_commission'])
        self.assertFalse(result['eligible_for_financial_posting'])

    def test_numeric_zero_is_a_data_row(self):
        result = inspect_report(workbook('<row r="2"><c r="A2"><v>0</v></c></row>'))
        self.assertEqual(result['state'], 'mapping_required')
        self.assertEqual(result['sheets'][0]['data_rows'], 1)
        self.assertFalse(result['eligible_for_financial_posting'])

    def test_duplicate_headers_preserved_and_flagged(self):
        result = inspect_report(workbook(duplicate=True))
        self.assertIn('clicks:duplicate_headers', result['issues'])
        self.assertEqual(result['sheets'][0]['headers'], ['날짜', '날짜'])

    def test_formulas_rejected(self):
        with self.assertRaises(ValueError):
            inspect_report(workbook('<row r="2"><c r="A2"><f>1+1</f><v>2</v></c></row>'))

    def test_receipt_idempotent_and_conflict_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            data = workbook()
            result = inspect_report(data)
            receipt = preserve_receipt(directory, data, result)
            self.assertEqual(receipt, preserve_receipt(directory, data, result))
            self.assertEqual(len(list(Path(directory).iterdir())), 2)
            Path(receipt).write_text('conflicting fixture')
            with self.assertRaises(ValueError):
                preserve_receipt(directory, data, result)
            self.assertEqual(Path(receipt).read_text(), 'conflicting fixture')


if __name__ == '__main__':
    unittest.main()
