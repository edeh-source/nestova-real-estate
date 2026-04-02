# management/commands/populate_locations.py
from django.core.management.base import BaseCommand
from property.models import State, City

class Command(BaseCommand):
    help = 'Populate Nigerian states and cities'

    def handle(self, *args, **kwargs):
        nigerian_locations = {
            'Abia': {
                'code': 'AB',
                'cities': ['Aba', 'Umuahia', 'Ohafia', 'Arochukwu', 'Bende', 'Isiala Ngwa']
            },
            'Adamawa': {
                'code': 'AD',
                'cities': ['Yola', 'Mubi', 'Numan', 'Jimeta', 'Ganye']
            },
            'Akwa Ibom': {
                'code': 'AK',
                'cities': ['Uyo', 'Eket', 'Ikot Ekpene', 'Oron', 'Abak']
            },
            'Anambra': {
                'code': 'AN',
                'cities': ['Awka', 'Onitsha', 'Nnewi', 'Ekwulobia', 'Ihiala', 'Aguata', 'Ekwusigo']
            },
            'Bauchi': {
                'code': 'BA',
                'cities': ['Bauchi', 'Azare', 'Misau', 'Ningi', 'Jama\'are']
            },
            'Bayelsa': {
                'code': 'BY',
                'cities': ['Yenagoa', 'Brass', 'Odi', 'Amassoma', 'Twon-Brass']
            },
            'Benue': {
                'code': 'BE',
                'cities': ['Makurdi', 'Gboko', 'Otukpo', 'Katsina-Ala', 'Vandeikya']
            },
            'Borno': {
                'code': 'BO',
                'cities': ['Maiduguri', 'Biu', 'Bama', 'Dikwa', 'Monguno']
            },
            'Cross River': {
                'code': 'CR',
                'cities': ['Calabar', 'Ugep', 'Ogoja', 'Ikom', 'Obudu']
            },
            'Delta': {
                'code': 'DE',
                'cities': ['Asaba', 'Warri', 'Sapele', 'Ughelli', 'Agbor', 'Kwale']
            },
            'Ebonyi': {
                'code': 'EB',
                'cities': ['Abakaliki', 'Afikpo', 'Onueke', 'Ezza', 'Ishielu']
            },
            'Edo': {
                'code': 'ED',
                'cities': ['Benin City', 'Auchi', 'Ekpoma', 'Uromi', 'Igarra']
            },
            'Ekiti': {
                'code': 'EK',
                'cities': ['Ado Ekiti', 'Ikere', 'Ilawe', 'Ise', 'Emure']
            },
            'Enugu': {
                'code': 'EN',
                'cities': ['Enugu', 'Nsukka', 'Oji River', 'Agbani', 'Awgu']
            },
            'Gombe': {
                'code': 'GO',
                'cities': ['Gombe', 'Kumo', 'Deba', 'Kaltungo', 'Billiri']
            },
            'Imo': {
                'code': 'IM',
                'cities': ['Owerri', 'Orlu', 'Okigwe', 'Mbaise', 'Oguta', 'Ngor Okpala']
            },
            'Jigawa': {
                'code': 'JI',
                'cities': ['Dutse', 'Hadejia', 'Gumel', 'Kazaure', 'Ringim']
            },
            'Kaduna': {
                'code': 'KD',
                'cities': ['Kaduna', 'Zaria', 'Kafanchan', 'Kagoro', 'Zonkwa']
            },
            'Kano': {
                'code': 'KN',
                'cities': ['Kano', 'Wudil', 'Gaya', 'Bichi', 'Rano']
            },
            'Katsina': {
                'code': 'KT',
                'cities': ['Katsina', 'Daura', 'Funtua', 'Malumfashi', 'Dutsin-Ma']
            },
            'Kebbi': {
                'code': 'KE',
                'cities': ['Birnin Kebbi', 'Argungu', 'Zuru', 'Yauri', 'Gwandu']
            },
            'Kogi': {
                'code': 'KO',
                'cities': ['Lokoja', 'Okene', 'Kabba', 'Idah', 'Ankpa']
            },
            'Kwara': {
                'code': 'KW',
                'cities': ['Ilorin', 'Offa', 'Jebba', 'Lafiagi', 'Pategi']
            },
            'Lagos': {
                'code': 'LA',
                'cities': ['Ikeja', 'Lagos Island', 'Surulere', 'Lekki', 'Ikorodu', 'Epe', 'Badagry', 'Victoria Island', 'Yaba', 'Apapa', 'Mushin', 'Oshodi', 'Agege']
            },
            'Nasarawa': {
                'code': 'NA',
                'cities': ['Lafia', 'Keffi', 'Akwanga', 'Nasarawa', 'Doma']
            },
            'Niger': {
                'code': 'NI',
                'cities': ['Minna', 'Suleja', 'Bida', 'Kontagora', 'Lapai']
            },
            'Ogun': {
                'code': 'OG',
                'cities': ['Abeokuta', 'Ijebu Ode', 'Sagamu', 'Ota', 'Ilaro']
            },
            'Ondo': {
                'code': 'ON',
                'cities': ['Akure', 'Ondo', 'Owo', 'Ikare', 'Ore']
            },
            'Osun': {
                'code': 'OS',
                'cities': ['Osogbo', 'Ile-Ife', 'Ilesa', 'Ede', 'Iwo']
            },
            'Oyo': {
                'code': 'OY',
                'cities': ['Ibadan', 'Ogbomosho', 'Oyo', 'Iseyin', 'Saki']
            },
            'Plateau': {
                'code': 'PL',
                'cities': ['Jos', 'Bukuru', 'Pankshin', 'Shendam', 'Langtang']
            },
            'Rivers': {
                'code': 'RI',
                'cities': ['Port Harcourt', 'Obio-Akpor', 'Eleme', 'Okrika', 'Bonny', 'Degema']
            },
            'Sokoto': {
                'code': 'SO',
                'cities': ['Sokoto', 'Tambuwal', 'Gwadabawa', 'Bodinga', 'Wamako']
            },
            'Taraba': {
                'code': 'TA',
                'cities': ['Jalingo', 'Wukari', 'Ibi', 'Bali', 'Gembu']
            },
            'Yobe': {
                'code': 'YO',
                'cities': ['Damaturu', 'Potiskum', 'Gashua', 'Nguru', 'Geidam']
            },
            'Zamfara': {
                'code': 'ZA',
                'cities': ['Gusau', 'Kaura Namoda', 'Talata Mafara', 'Anka', 'Bungudu']
            },
            'FCT': {
                'code': 'FC',
                'cities': ['Abuja', 'Gwagwalada', 'Kubwa', 'Nyanya', 'Karu', 'Maitama', 'Wuse', 'Asokoro', 'Garki', 'Gwarinpa']
            }
        }
        
        created_states = 0
        created_cities = 0
        
        for state_name, data in nigerian_locations.items():
            # Create or get state
            state, state_created = State.objects.get_or_create(
                code=data['code'],
                defaults={'name': state_name}
            )
            
            if state_created:
                created_states += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created state: {state_name}'))
            
            # Create cities for this state
            for city_name in data['cities']:
                city, city_created = City.objects.get_or_create(
                    name=city_name,
                    state=state
                )
                
                if city_created:
                    created_cities += 1
                    self.stdout.write(f'  ✓ Created city: {city_name}')
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully populated locations!'))
        self.stdout.write(self.style.SUCCESS(f'  - States created: {created_states}'))
        self.stdout.write(self.style.SUCCESS(f'  - Cities created: {created_cities}'))
        self.stdout.write(self.style.SUCCESS(f'  - Total states: {State.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'  - Total cities: {City.objects.count()}'))