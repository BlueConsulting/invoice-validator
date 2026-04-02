
from django.core.management.base import BaseCommand
import pandas as pd
from accounts.models import HSN, SAC
 


class Command(BaseCommand):
    help = "Import HSN and SAC data from Excel"

    def handle(self, *args, **kwargs):

        file_path = r"C:\Users\Dell\OneDrive\Desktop\Invoice\HSN_SAC__1_.xlsx"

        # ================= HSN =================
        #df = pd.read_excel(file_path, sheet_name="HSN_MSTR", dtype=str)
        df = pd.read_excel(file_path, sheet_name="HSN_MSTR", dtype=str, engine="openpyxl")

        #print("Total rows read:", len(df))

        #print(df.columns)  

        #print(repr(row.get("block_credit")))

        df.columns = df.columns.str.strip()

        df = df.rename(columns={
            "HSN_CD": "hsn_with_zero",
            "HSN_CD.1": "hsn_without_zero",
            "HSN_Description": "description",
            "IGST": "igst",
            "Blocked Credit": "block_credit"
        })

        #for _, row in df.iterrows():
        for i, row in df.iterrows():
            
            #if i < 20:
                #print(repr(row.get("block_credit"))) 

            hsn_code = str(row.get("hsn_with_zero")).strip() if pd.notna(row.get("hsn_with_zero")) else None
            if not hsn_code:
                continue

            hsn_code = hsn_code.zfill(8)

            description = str(row.get("description")).strip() if pd.notna(row.get("description")) else ""
            
            # handle IGST value which can be in decimal (0.12) or percentage (12%)
            igst_raw = row.get("igst")
            if pd.isna(igst_raw):
                continue

            try:
                igst_value = float(igst_raw)

                # If Excel gave decimal (0.12), convert to 12
                if igst_value <= 1:
                    igst_value = igst_value * 100

                igst = int(round(igst_value))

            except:
                continue

            #igst = str(igst_raw).replace('%', '').strip()
            #if igst == "":
            #    continue

            block_credit = str(row.get("block_credit")).strip() if pd.notna(row.get("block_credit")) else None

            HSN.objects.update_or_create(
                hsn_code=hsn_code,
                defaults={
                    "description": description,
                    "tax_rate": igst,
                    "block_credit": block_credit,
                    "rcm": None
                }
            )

        self.stdout.write(self.style.SUCCESS("HSN Data Imported Successfully"))

        # ================= SAC =================
        df = pd.read_excel(file_path, sheet_name="SAC_MSTR", dtype=str)
        df.columns = df.columns.str.strip()

        df = df.rename(columns={
            "SAC_CD": "sac_code",
            "SAC_Description": "description",
            "IGST": "igst"
        })

        for _, row in df.iterrows():

            sac_code = str(row.get("sac_code")).strip() if pd.notna(row.get("sac_code")) else None
            if not sac_code:
                continue

            description = str(row.get("description")).strip() if pd.notna(row.get("description")) else ""
            
            '''
            igst_raw = row.get("igst")
            if pd.isna(igst_raw):
                continue

            igst = str(igst_raw).replace('%', '').strip()
            if igst == "":
                continue
            '''
            igst_raw = row.get("igst")

            if pd.isna(igst_raw):
                continue

            try:
                igst_value = float(igst_raw)

                # Convert decimal (0.18 → 18)
                if igst_value <= 1:
                    igst_value *= 100

                igst = int(round(igst_value))

            except:
                continue


            SAC.objects.update_or_create(
                sac_code=sac_code,
                defaults={
                    "description": description,
                    "tax_rate": igst,
                    "block_credit": None,
                    "rcm": None
                }
            )

        self.stdout.write(self.style.SUCCESS("SAC Data Imported Successfully"))




