import requests
from datetime import datetime


def get_met_office_data(location_id, api_key, source):
    """Fetch data from the Met Office API for the given location ID and format it."""
    url = f"http://datapoint.metoffice.gov.uk/public/data/val/wxobs/all/json/{location_id}?res=hourly&key={api_key}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Raise an error for bad responses
        data = response.json()

        # Extract the last period's weather data
        last_period = data['SiteRep']['DV']['Location']['Period'][-1]['Rep'][-1]
        
        met_office_data_doc = {
            "source": source,
            "temperature": round(float(last_period['T']), 2),
            "humidity": round(float(last_period['H']), 2),
            "pressure": round(float(last_period['P']), 2),
            "wind": round(float(last_period['S']), 2)
        }

        ## DEBUG
        ## print(f"[DEBUG] - {data['SiteRep']['DV']['Location']['Period'][-1]['Rep'][-1]}")

        return met_office_data_doc
 

    except requests.exceptions.RequestException as e:
        print(f"[ERROR {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Axios Met Office error: {e}")
        return None
