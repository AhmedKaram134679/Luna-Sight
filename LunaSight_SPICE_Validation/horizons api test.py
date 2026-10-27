
import requests
import json

url = "https://ssd.jpl.nasa.gov/api/horizons_file.api"

horizons_input = """!$$SOF
COMMAND='399'
OBJ_DATA='NO'
MAKE_EPHEM='YES'
TABLE_TYPE='OBSERVER'
CENTER='coord@301'
COORD_TYPE='GEODETIC'
SITE_COORD='200,-88.45,0'
START_TIME='2026-11-02 14:15:15'
STOP_TIME='2026-11-02 14:15:30'
STEP_SIZE='15'
TIME_DIGITS='SECONDS'
QUANTITIES='4'
"""

try:
    response = requests.post(
        url,
        data={"format": "json"},
        files={
            "input": (
                "horizons_input.txt",
                horizons_input,
                "text/plain",
            )
        },
        timeout=90,
    )

    print("HTTP:", response.status_code)
    response.raise_for_status()

    try:
        result = response.json()
    except json.JSONDecodeError:
        print("The API did not return valid JSON.")
        print(response.text)
        raise SystemExit(1)

    if "error" in result:
        print("HORIZONS API ERROR:")
        print(result["error"])
        if "result" in result:
            print(result["result"])
    else:
        print("API signature:", result.get("signature"))
        print("HORIZONS RESULT:")
        print(result.get("result", json.dumps(result, indent=2)))

except requests.RequestException as error:
    print("HTTP REQUEST ERROR:")
    print(error)
