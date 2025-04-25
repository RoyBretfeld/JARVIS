import requests

def test_weather_api():
    api_key = "7dcccd22f8c2d34cf7c5736b8f5f0c59"
    city = "Dresden,01139,DE"
    units = "metric"
    lang = "de"
    
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units={units}&lang={lang}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Fehler: {str(e)}")
        return False

if __name__ == "__main__":
    test_weather_api() 