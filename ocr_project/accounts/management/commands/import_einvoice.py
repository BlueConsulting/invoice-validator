from django.core.management.base import BaseCommand
import pandas as pd
from accounts.models import EInvoiceRegister

class Command(BaseCommand):
    help = "Import E-Invoice Register Data"

    def handle(self, *args, **kwargs):

        file_path = r"C:\Users\Dell\OneDrive\Desktop\Invoice\EInvoiceRegisterExcel.xlsx"

        df = pd.read_excel(file_path, dtype=str)
        df.columns = df.columns.str.strip()

        for _, row in df.iterrows():
            try:
                EInvoiceRegister.objects.update_or_create(
                    irn=row['IRN'],
                    defaults={
                        'supplier_gstin': row['Supplier GSTIN'],
                        'document_number': row['Document Number'],
                        'document_date': pd.to_datetime(row['Document Date']),
                        'supply_type': row['Supply Type Code'],
                        'amount': row['Total Invoice Amount( ₹)'],
                        'eway_bill_no': row.get('e-Way Bill No. (if any)', None),
                        'irn_status': row['IRN Status'],
                        'ack_no': row['Ack. No'],
                        'irn_date': pd.to_datetime(row['IRN Date']),
                    }
                )
            except Exception as e:
                print("Error:", e)

        self.stdout.write(self.style.SUCCESS("E-Invoice Data Imported Successfully"))


