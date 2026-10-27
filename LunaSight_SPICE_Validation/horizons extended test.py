
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
START_TIME='2026-11-02 14:12:30'
STOP_TIME='2026-11-02 14:12:50'
STEP_SIZE='20'
TIME_DIGITS='SECONDS'
QUANTITIES='4,13,20,21'
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
        print("ERROR: Response is not valid JSON.")
        print(response.text)
        raise SystemExit(1)

    if result.get("error"):
        print("HORIZONS API ERROR:")
        print(result["error"])
        if result.get("result"):
            print(result["result"])
        raise SystemExit(1)

    ephemeris = result.get("result", "")

    if "$$SOE" not in ephemeris or "$$EOE" not in ephemeris:
        print("ERROR: Ephemeris data markers were not found.")
        print(ephemeris)
        raise SystemExit(1)

    print("\nAPI SOURCE:")
    print(result.get("signature", {}).get("source", "Unknown"))

    print("\nFULL EPHEMERIS RESULT:")
    print(ephemeris)

except requests.RequestException as error:
    print("HTTP REQUEST ERROR:")
    print(error)
