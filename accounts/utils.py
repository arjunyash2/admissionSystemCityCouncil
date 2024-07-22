import requests


def fetch_school_details(place_id, lng, lat):

    api_key = 'iW9ceziSt7BhDuG3FZGbuRkk09ETfoDJznAqwbcjMBw'
    url = f'https://discover.search.hereapi.com/v1/discover?at=53.376093,-1.465203&q=schools&apiKey={api_key}'

    response = requests.get(url)
    data = response.json()

    for item in data['items']:
        if item['id'] == place_id:
            school_details = {
                'name': item['title'],
                'address': item['address']['label'],
                'latitude': item['position']['lat'],
                'longitude': item['position']['lng'],
                'distance': item.get('distance', None),
                'phone': item['contacts'][0]['phone'][0]['value'] if 'contacts' in item and 'phone' in item['contacts'][0] else None,
                'website': item['contacts'][0]['www'][0]['value'] if 'contacts' in item and 'www' in item['contacts'][0] else None,
                'email': item['contacts'][0]['email'][0]['value'] if 'contacts' in item and 'email' in item['contacts'][0] else None
            }

            return school_details

    return None
