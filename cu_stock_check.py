"""CU 실제 응답 검사. Python 표준 라이브러리만 사용합니다."""
import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = "https://www.pocketcu.co.kr"
APP_USER_AGENT = ("Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Version/4.0 Chrome/138.0.0.0 "
                  "Mobile Safari/537.36;BGFCU")


def request(opener, path, body=None, app_headers=False, quiet=False):
    headers = {"User-Agent": APP_USER_AGENT if app_headers else "Mozilla/5.0",
               "Accept": "application/json, text/javascript, */*; q=0.01" if app_headers else "application/json, text/html;q=0.9",
               "Referer": BASE + "/", "X-Requested-With": "XMLHttpRequest"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    result = {"path": path, "method": req.get_method(), "request_body": body}
    try:
        with opener.open(req, timeout=25) as response:
            result.update(status=response.status, final_url=response.url)
            raw = response.read(4_000_000).decode("utf-8", "replace")
        try:
            result["json"] = json.loads(raw)
        except ValueError:
            result["text_preview"] = raw[:3000]
    except urllib.error.HTTPError as exc:
        result.update(status=exc.code, error=exc.reason,
                      text_preview=exc.read(3000).decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result["error"] = str(exc)
    if not quiet:
        print(f"{path}: HTTP {result.get('status', '-')} {result.get('error', '')}", flush=True)
        time.sleep(1)
    return result


def main():
    parser = argparse.ArgumentParser(description="CU 상품 검색/재고 연동 가능성 검사")
    parser.add_argument("--keyword", default="맛피아")
    parser.add_argument("--output", default="cu_check_result.json")
    parser.add_argument("--app-headers", action="store_true", help="공개 구현의 앱 식별 헤더로 비교")
    parser.add_argument("--item-code", help="매장 수량을 검사할 상품 코드. 자동 선택하지 않음")
    parser.add_argument("--on-item-no", default="")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    args = parser.parse_args()
    if args.item_code and (args.lat is None or args.lon is None):
        parser.error("--item-code 사용 시 --lat, --lon을 지정하세요.")
    if args.lat is not None and not -90 <= args.lat <= 90:
        parser.error("위도 범위를 확인하세요.")
    if args.lon is not None and not -180 <= args.lon <= 180:
        parser.error("경도 범위를 확인하세요.")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = {"checked_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "keyword": args.keyword,
              "app_headers": args.app_headers,
              "requests": [], "products": [], "stock_verified": False}
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def probe(path, body=None):
        result = request(opener, path, body, args.app_headers)
        report["requests"].append(result)
        return result
    probe("/search/stock/main")
    probe("/api/search/display/stock", {})
    for keyword in dict.fromkeys([args.keyword, "감자스틱"]):
        response = probe("/api/search/rest/stock/main", {
            "searchWord": keyword, "prevSearchWord": "", "spellModifyUseYn": "N",
            "offset": 0, "limit": 20, "searchSort": "recom"})
        payload = response.get("json", {})
        if response.get("status") in (401, 403, 429):
            print("접근 제한 응답입니다. 추가 검색을 중단합니다.")
            break
        try:
            result = payload["data"]["stockResult"]["result"]
            rows = result["rows"]
            for row in rows:
                fields = row.get("fields", {})
                if fields and fields not in report["products"]:
                    report["products"].append(fields)
            print(f"검색어 {keyword}: {result.get('total_count')}개", flush=True)
        except (KeyError, TypeError):
            print("상품 목록 형식 미확인. 응답 원문을 결과 파일에 기록했습니다.")
    report["verdict"] = "매장별 재고 미확인"
    blocked = any(r.get("status") in (401, 403, 429) for r in report["requests"])
    if args.item_code and not blocked:
        report["stock_query"] = {"item_code": args.item_code, "on_item_no": args.on_item_no,
                                 "lat": args.lat, "lon": args.lon}
        response = probe("/api/store", {
            "latVal": str(args.lat), "longVal": str(args.lon),
            "baseLatVal": str(args.lat), "baseLongVal": str(args.lon),
            "tabId": "2", "filterSvcList": [], "filterAdtList": [],
            "stockCdcYn": "N", "searchStock": False, "pickupType": "change",
            "getRoute": "IOS", "areaTplNo": "0", "childMealPickUpYn": "N",
            "isCurrentSearch": "N", "pageType": "search_improve stock_sch_improve",
            "searchWord": "", "isRecommend": "Y", "recommendId": "stock",
            "jipCd": args.item_code, "itemCd": args.item_code, "item_cd": args.item_code,
            "onItemNo": args.on_item_no})
        data = response.get("json")
        stores = data.get("storeList", []) if isinstance(data, dict) else []
        report["stores"] = []
        if response.get("status") == 200 and isinstance(stores, list):
            for store in stores:
                if not isinstance(store, dict) or not store.get("storeCd"):
                    continue
                raw_stock = store.get("stock")
                stock = None
                if not isinstance(raw_stock, bool):
                    value = str(raw_stock).strip()
                    if value.isascii() and value.isdigit():
                        stock = int(value)
                report["stores"].append({"code": store.get("storeCd"), "name": store.get("storeNm"),
                                         "stock": stock, "raw_stock": raw_stock})
            report["stock_verified"] = any(s["stock"] is not None for s in report["stores"])
        if report["stock_verified"]:
            report["verdict"] = "지정한 상품 코드와 좌표로 매장별 수량 수신. 원하는 상품인지는 별도 확인 필요"
        print(f"매장 {len(report['stores'])}개, 수량 응답 확인: {report['stock_verified']}")
        blocked = blocked or response.get("status") in (401, 403, 429)
    if blocked:
        report["verdict"] = "접근 제한으로 상품/재고 연동 검증 실패. 품절 여부는 알 수 없음"
    report["next_step"] = ("포켓CU 앱의 정상 재고조회에서 사용되는 요청 형식과 인증 필요 여부 확인"
                           if blocked else "상품 코드와 점포별 수량 응답 검증 필요")
    if report["stock_verified"]:
        report["next_step"] = "사용자가 원하는 정확한 상품과 실제 조회 지역을 확정"
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"상품 {len(report['products'])}개 수신. 결과 저장: {Path(args.output).resolve()}")
    return 0 if report["products"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
