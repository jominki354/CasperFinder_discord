import urllib.request, json

url = "https://casper.hyundai.com/gw/wp/product/v2/product/exhibition/cars/E20260277"
payload = {
    "carCode": "AX05",
    "subsidyRegion": "1100",
    "exhbNo": "E20260277",
    "sortCode": "10",
    "deliveryAreaCode": "B",
    "deliveryLocalAreaCode": "B0",
    "carBodyCode": "",
    "carEngineCode": "",
    "carTrimCode": "",
    "exteriorColorCode": "",
    "interiorColorCode": [],
    "deliveryCenterCode": "",
    "wpaScnCd": "",
    "optionFilter": "",
    "pageNo": 1,
    "pageSize": 18,
}

headers = {
    "Content-Type": "application/json;charset=utf-8",
    "Accept": "application/json, text/plain, */*",
    "ep-channel": "wpc",
    "ep-version": "v2",
    "service-type": "product",
    "x-b3-sampled": "1",
    "Referer": "https://casper.hyundai.com/vehicles/car-list/promotion",
    "Origin": "https://casper.hyundai.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-UX-State-Key": "52ddaace-68a0-4c42-9593-051de2d84755",
    "Cookie": "TS0123d4c1=018c6589df29c44e93c55ef65ae9418532eb5a250b1bd170e77bf9e1546f109f3b2d4b7aaa069bb3e950b8e17f4b0a114ef1eae9b5; s_ecid=MCMID%7C26794578677682929782252266854367829990",
}

req = urllib.request.Request(
    url, data=json.dumps(payload).encode(), headers=headers, method="POST"
)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print(f"Count: {data.get('data', {}).get('totalCount')}")
        if data.get("data", {}).get("totalCount") > 0:
            print(data["data"]["discountsearchcars"][0]["carNm"])
            print("Successfully bypassed!")
except Exception as e:
    print("Error:", e)
