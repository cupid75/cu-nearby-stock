"""CU 주변 재고. 좌표는 로그/파일에 기록하지 않고 재고 캐시에 최대 30초만 사용."""
import asyncio
from collections import OrderedDict, deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import hashlib
import hmac
import http.cookiejar
import math
import os
from pathlib import Path
import secrets
import time
import urllib.request

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
from cu_stock_check import request as cu_request

ROOT = Path(__file__).parent


@asynccontextmanager
async def lifespan(app):
    async def clean():
        while True:
            await asyncio.sleep(1)
            stock_cache.purge()
            products_cache.purge()
            limits.purge()
    cleanup = asyncio.create_task(clean())
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup


app = FastAPI(title="CU 주변 재고", docs_url=None, redoc_url=None, lifespan=lifespan)
SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32)).encode()
gate = asyncio.Lock()  # 한 프로세스, 같은 조회는 캐시로 합치고 CU 동시 호출 방지


class TTLCache:
    def __init__(self, ttl, maximum=512):
        self.ttl, self.maximum, self.data = ttl, maximum, OrderedDict()

    def purge(self):
        now = time.monotonic()
        for key in list(self.data):
            if self.data[key][0] <= now:
                del self.data[key]

    def get(self, key):
        self.purge()
        row = self.data.get(key)
        return row[1] if row else None

    def put(self, key, value):
        self.purge()
        self.data[key] = (time.monotonic() + self.ttl, value)
        while len(self.data) > self.maximum:
            self.data.popitem(last=False)


products_cache, stock_cache = TTLCache(600), TTLCache(30)
limits = TTLCache(60, 10000)


@app.middleware("http")
async def session_and_headers(request: Request, call_next):
    token = request.cookies.get("cu_session", "")
    ident, _, signature = token.partition(".")
    expected = hmac.new(SECRET, ident.encode(), hashlib.sha256).hexdigest()
    valid = len(ident) == 32 and hmac.compare_digest(signature, expected)
    if not valid:
        ident = secrets.token_hex(16)
        token = ident + "." + hmac.new(SECRET, ident.encode(), hashlib.sha256).hexdigest()
    request.state.user = ident
    response = await call_next(request)
    if not valid:
        response.set_cookie("cu_session", token, httponly=True, samesite="lax",
                            secure=os.environ.get("COOKIE_SECURE") == "1")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Permissions-Policy"] = "geolocation=(self)"
    return response


def rate_limit(request):
    now = time.monotonic()
    # IP는 원문 대신 메모리 내 해시로 60초 사용. 전달 헤더는 신뢰하지 않음.
    ip = request.client.host if request.client else "unknown"
    keys = [("user:" + request.state.user, 10),
            ("ip:" + hashlib.sha256(ip.encode()).hexdigest(), 60)]
    for key, maximum in keys:
        hits = limits.get(key) or deque()
        while hits and hits[0] <= now - 60:
            hits.popleft()
        if len(hits) >= maximum:
            raise HTTPException(429, "요청이 많습니다. 1분 뒤 버튼을 눌러 다시 확인해 주세요.",
                                headers={"Retry-After": "60"})
    for key, _ in keys:
        hits = limits.get(key) or deque()
        hits.append(now)
        limits.put(key, hits)


def upstream(path, body):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    for endpoint, payload in [("/api/search/display/stock", {}), (path, body)]:
        result = cu_request(opener, endpoint, payload, app_headers=True, quiet=True)
        status = result.get("status")
        if status in (401, 403, 429):
            raise HTTPException(503, "CU에서 접근 또는 요청을 제한했습니다. 자동 재시도하지 않습니다.")
        if status != 200 or not isinstance(result.get("json"), dict):
            raise HTTPException(502, "CU 연결 오류입니다. 품절 여부는 알 수 없습니다.")
    return result["json"]


class SearchInput(BaseModel):
    keyword: str = Field(min_length=1, max_length=60)


class StockInput(BaseModel):
    item_code: str = Field(pattern=r"^[0-9]{1,30}$")
    on_item_no: str = Field(default="", pattern=r"^[0-9]{0,30}$")
    lat: float = Field(ge=33, le=39)
    lon: float = Field(ge=124, le=132)
    radius: Literal[1, 2, 5] = 2


def stock_body(query):
    return {"latVal": str(query.lat), "longVal": str(query.lon),
            "baseLatVal": str(query.lat), "baseLongVal": str(query.lon),
            "tabId": "2", "filterSvcList": [], "filterAdtList": [],
            "stockCdcYn": "N", "searchStock": False, "pickupType": "change",
            "getRoute": "IOS", "areaTplNo": "0", "childMealPickUpYn": "N",
            "isCurrentSearch": "N", "pageType": "search_improve stock_sch_improve",
            "searchWord": "", "isRecommend": "Y", "recommendId": "stock",
            "jipCd": query.item_code, "itemCd": query.item_code, "item_cd": query.item_code,
            "onItemNo": query.on_item_no}


def distance(lat, lon, a, b):
    p, q = math.radians(lat), math.radians(a)
    h = math.sin((q-p)/2)**2 + math.cos(p)*math.cos(q)*math.sin(math.radians(b-lon)/2)**2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def normalize_stores(rows, lat, lon):
    stores, seen, missing_coordinates = [], set(), 0
    for row in rows:
        if not isinstance(row, dict) or not row.get("storeCd"):
            continue
        code = str(row["storeCd"])
        if code in seen:
            continue
        seen.add(code)
        raw = row.get("stock")
        value = str(raw).strip()
        qty = int(value) if not isinstance(raw, bool) and value.isascii() and value.isdigit() else None
        try:
            a, b = float(row["latVal"]), float(row["longVal"])
            if not (33 <= a <= 39 and 124 <= b <= 132):
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            missing_coordinates += 1
            continue
        address = " ".join(str(row.get(k) or "").strip() for k in ("addrFst", "addrDetail")).strip()
        if not address:
            address = " ".join(str(row.get(k) or "").strip() for k in ("doroStoreAddr1", "doroStoreAddr2")).strip()
        stores.append({"code": code, "name": str(row.get("storeNm") or "CU 매장"),
                       "quantity": qty, "status": "unknown" if qty is None else "in_stock" if qty else "sold_out",
                       "address": address or "주소 미확인", "lat": a, "lon": b,
                       "distance_m": round(distance(lat, lon, a, b))})
    return sorted(stores, key=lambda s: s["distance_m"]), len(seen), missing_coordinates


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cu-nearby-stock"}


@app.get("/api/config")
async def config():
    return {"kakao_js_key": os.environ.get("KAKAO_JS_KEY", "")}


@app.post("/api/products")
async def search(query: SearchInput, request: Request):
    rate_limit(request)
    word = query.keyword.strip()
    if not word:
        raise HTTPException(422, "검색어를 입력해 주세요.")
    async with gate:
        cached = products_cache.get(word)
        if cached is not None:
            return {**cached, "cached": True}
        data = await asyncio.to_thread(upstream, "/api/search/rest/stock/main", {
            "searchWord": word, "prevSearchWord": "", "spellModifyUseYn": "N",
            "offset": 0, "limit": 20, "searchSort": "recom"})
        try:
            result = data["data"]["stockResult"]["result"]
            rows = result["rows"]
            if not isinstance(rows, list):
                raise TypeError()
            products = []
            for row in rows:
                f = row.get("fields", {})
                if f.get("item_cd") and f.get("item_nm"):
                    products.append({"name": str(f["item_nm"]), "item_code": str(f["item_cd"]),
                                     "on_item_no": str(f.get("on_item_no") or ""), "price": f.get("hyun_maega")})
        except (KeyError, TypeError, AttributeError):
            raise HTTPException(502, "CU 상품 응답 형식이 달라 검색 결과를 확인할 수 없습니다.")
        answer = {"products": products, "total": result.get("total_count", len(products)), "cached": False}
        products_cache.put(word, answer)
        return answer


@app.post("/api/stock")
async def stock(query: StockInput, request: Request):
    rate_limit(request)
    key = (query.item_code, query.on_item_no, query.lat, query.lon)
    async with gate:
        cached = stock_cache.get(key)
        hit = cached is not None
        if not hit:
            data = await asyncio.to_thread(upstream, "/api/store", stock_body(query))
            if not isinstance(data.get("storeList"), list):
                raise HTTPException(502, "CU 매장 응답 형식이 달라 수량을 확인할 수 없습니다.")
            stores, total, missing = normalize_stores(data["storeList"], query.lat, query.lon)
            cached = {"stores": stores, "returned_count": total, "missing_coordinates": missing,
                      "checked_at": datetime.now(timezone.utc).isoformat()}
            stock_cache.put(key, cached)
    stores = [s for s in cached["stores"] if s["distance_m"] <= query.radius * 1000]
    return {**cached, "stores": stores, "radius_km": query.radius, "cached": hit,
            "within_radius_count": len(stores),
            "in_stock_count": sum(s["status"] == "in_stock" for s in stores),
            "sold_out_count": sum(s["status"] == "sold_out" for s in stores),
            "unknown_count": sum(s["status"] == "unknown" for s in stores)}


@app.get("/")
async def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
