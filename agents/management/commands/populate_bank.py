# management/commands/populate_banks.py
from django.core.management.base import BaseCommand
from agents.models import Bank

class Command(BaseCommand):
    help = 'Populate comprehensive Nigerian banks list'

    def handle(self, *args, **kwargs):
        nigerian_banks = [
            # Commercial Banks
            {'name': 'Access Bank', 'code': '044'},
            {'name': 'Citibank Nigeria', 'code': '023'},
            {'name': 'Ecobank Nigeria', 'code': '050'},
            {'name': 'Fidelity Bank', 'code': '070'},
            {'name': 'First Bank of Nigeria', 'code': '011'},
            {'name': 'First City Monument Bank (FCMB)', 'code': '214'},
            {'name': 'Globus Bank', 'code': '00103'},
            {'name': 'Guaranty Trust Bank (GTBank)', 'code': '058'},
            {'name': 'Heritage Bank', 'code': '030'},
            {'name': 'Keystone Bank', 'code': '082'},
            {'name': 'Lotus Bank', 'code': '303'},
            {'name': 'Parallex Bank', 'code': '104'},
            {'name': 'Polaris Bank', 'code': '076'},
            {'name': 'Premium Trust Bank', 'code': '105'},
            {'name': 'Providus Bank', 'code': '101'},
            {'name': 'Stanbic IBTC Bank', 'code': '221'},
            {'name': 'Standard Chartered Bank', 'code': '068'},
            {'name': 'Sterling Bank', 'code': '232'},
            {'name': 'SunTrust Bank', 'code': '100'},
            {'name': 'Titan Trust Bank', 'code': '102'},
            {'name': 'Union Bank of Nigeria', 'code': '032'},
            {'name': 'United Bank for Africa (UBA)', 'code': '033'},
            {'name': 'Unity Bank', 'code': '215'},
            {'name': 'Wema Bank', 'code': '035'},
            {'name': 'Zenith Bank', 'code': '057'},
            
            # Non-Interest Banks
            {'name': 'Jaiz Bank', 'code': '301'},
            {'name': 'TAJBank', 'code': '302'},
            
            # Digital/Mobile Banks
            {'name': 'Kuda Bank', 'code': '090267'},
            {'name': 'Rubies Bank', 'code': '125'},
            {'name': 'VFD Microfinance Bank', 'code': '566'},
            {'name': 'Sparkle Microfinance Bank', 'code': '51310'},
            
            # Payment Service Banks
            {'name': 'OPay', 'code': '999992'},
            {'name': 'PalmPay', 'code': '999991'},
            {'name': 'Moniepoint MFB', 'code': '50515'},
            {'name': 'Mint MFB', 'code': '50304'},
            {'name': 'Kuda MFB', 'code': '50211'},
            
            # Microfinance Banks (Major ones)
            {'name': 'LAPO Microfinance Bank', 'code': '50549'},
            {'name': 'AB Microfinance Bank', 'code': '51229'},
            {'name': 'Accion Microfinance Bank', 'code': '51204'},
            {'name': 'Advans La Fayette Microfinance Bank', 'code': '51314'},
            {'name': 'Amju Unique Microfinance Bank', 'code': '50926'},
            {'name': 'Balogun Gambari Microfinance Bank', 'code': '51311'},
            {'name': 'Bowen Microfinance Bank', 'code': '50931'},
            {'name': 'Carbon', 'code': '565'},
            {'name': 'CEMCS Microfinance Bank', 'code': '50823'},
            {'name': 'Covenant Microfinance Bank', 'code': '51127'},
            {'name': 'Eyowo', 'code': '50126'},
            {'name': 'Fairmoney Microfinance Bank', 'code': '51318'},
            {'name': 'Fina Trust Microfinance Bank', 'code': '51314'},
            {'name': 'FSDH Merchant Bank', 'code': '501'},
            {'name': 'Gomoney', 'code': '100022'},
            {'name': 'Hackman Microfinance Bank', 'code': '51251'},
            {'name': 'Hasal Microfinance Bank', 'code': '50383'},
            {'name': 'Ibile Microfinance Bank', 'code': '51244'},
            {'name': 'Infinity Microfinance Bank', 'code': '50457'},
            {'name': 'Mayfair MFB', 'code': '50563'},
            {'name': 'Mutual Trust Microfinance Bank', 'code': '51259'},
            {'name': 'Nigeria Inter-Bank Settlement System (NIBSS)', 'code': '000016'},
            {'name': 'NPF Microfinance Bank', 'code': '50629'},
            {'name': 'Page MFBank', 'code': '50746'},
            {'name': 'Parkway - ReadyCash', 'code': '311'},
            {'name': 'Paycom', 'code': '999993'},
            {'name': 'Petra Microfinance Bank', 'code': '50746'},
            {'name': 'Rand Merchant Bank', 'code': '502'},
            {'name': 'Rephidim Microfinance Bank', 'code': '50994'},
            {'name': 'Richway Microfinance Bank', 'code': '51286'},
            {'name': 'Seed Capital Microfinance Bank', 'code': '50800'},
            {'name': 'Stanford Microfinance Bank', 'code': '51310'},
            {'name': 'Stellas Microfinance Bank', 'code': '51253'},
            {'name': 'TCF MFB', 'code': '51211'},
            {'name': 'Tangerine Money', 'code': '51269'},
            {'name': 'Unical Microfinance Bank', 'code': '50871'},
            {'name': 'VTNetworks', 'code': '000026'},
            {'name': 'Xpress Payments', 'code': '100030'},
            
            # Merchant Banks
            {'name': 'Coronation Merchant Bank', 'code': '559'},
            {'name': 'FBN Merchant Bank', 'code': '413'},
            {'name': 'FSDH Merchant Bank', 'code': '501'},
            {'name': 'Greenwich Merchant Bank', 'code': '562'},
            {'name': 'Nova Merchant Bank', 'code': '561'},
            {'name': 'Rand Merchant Bank', 'code': '502'},
            
            # Other Financial Institutions
            {'name': 'FSDH Securities Limited', 'code': '501'},
            {'name': 'Paystack', 'code': 'PST'},
            {'name': 'Flutterwave', 'code': 'FLW'},
            {'name': 'Interswitch', 'code': 'ISW'},
            {'name': 'Paga', 'code': '100002'},
            {'name': 'Etranzact', 'code': '100021'},
            
            # Development Finance Institutions
            {'name': 'Bank of Industry', 'code': '070'},
            {'name': 'Bank of Agriculture', 'code': '044'},
            {'name': 'Federal Mortgage Bank of Nigeria', 'code': '070'},
            {'name': 'Infrastructure Bank', 'code': '070'},
            {'name': 'Nigeria Export-Import Bank', 'code': '601'},
            {'name': 'Urban Development Bank', 'code': '070'},
            
            # Additional Digital Banks & Fintech
            {'name': 'Alat by Wema', 'code': '035'},
            {'name': 'Brass', 'code': 'BRS'},
            {'name': 'Chipper Cash', 'code': 'CHP'},
            {'name': 'FairMoney', 'code': '51318'},
            {'name': 'GTWorld (GTBank)', 'code': '058'},
            {'name': 'HopePSBank', 'code': '120002'},
            {'name': 'Piggyvest', 'code': 'PGV'},
            {'name': 'Quickteller', 'code': 'QTL'},
            {'name': 'Raven Bank', 'code': 'RVN'},
            {'name': 'Smartcash Payment Service Bank', 'code': '51310'},
            {'name': 'Zinternet - STB', 'code': '100034'},
            
            # Credit Bureaus (if needed)
            {'name': 'CRC Credit Bureau', 'code': 'CRC'},
            {'name': 'First Central Credit Bureau', 'code': 'FCCB'},
        ]
        
        created_count = 0
        updated_count = 0
        
        for bank_data in nigerian_banks:
            bank, created = Bank.objects.get_or_create(
                code=bank_data['code'],
                defaults={'name': bank_data['name']}
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {bank.name}'))
            else:
                # Update name if it changed
                if bank.name != bank_data['name']:
                    bank.name = bank_data['name']
                    bank.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f'↻ Updated: {bank.name}'))
                else:
                    self.stdout.write(f'  Already exists: {bank.name}')
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully processed {len(nigerian_banks)} banks!'))
        self.stdout.write(self.style.SUCCESS(f'  - Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'  - Updated: {updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'  - Total: {Bank.objects.count()} banks in database'))