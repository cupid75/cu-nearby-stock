"""브라우저 회귀검사용 별도 서버. CU 호출 없음. 공개 배포에 사용 금지.
실행: python -m uvicorn tests.ui_fixture_server:app --port 8001 --no-access-log
"""
from fastapi.responses import HTMLResponse
from fastapi import Request
import app as service

stock_calls = 0
stock_requests = 0


def fixture_upstream(path, body):
    global stock_calls
    if 'main' in path:
        return {'data': {'stockResult': {'result': {'total_count': 1, 'rows': [
            {'fields': {'item_nm':'검증용 트러플하몽스틱','item_cd':'123', 'on_item_no':'456','hyun_maega':'1900'}}]}}}}
    if body['itemCd'] == '123':
        stock_calls += 1
        return {'storeList': [
            {'storeCd':'one','storeNm':'검증용 재고점','stock':'3','latVal':37.567,'longVal':126.978,'addrFst':'검증용 주소'},
            {'storeCd':'two','storeNm':'검증용 품절점','stock':'0','latVal':37.568,'longVal':126.978,'addrFst':'검증용 주소'},
            {'storeCd':'three','storeNm':'검증용 미확인점','stock':None,'latVal':37.569,'longVal':126.978,'addrFst':'검증용 주소'}]}
    raise RuntimeError('fixture only')


service.upstream = fixture_upstream
app = service.app
app.router.routes = [r for r in app.router.routes if getattr(r, 'path', None) != '/']


@app.middleware('http')
async def count_stock_requests(request, call_next):
    global stock_requests
    if request.url.path == '/api/stock':
        stock_requests += 1
    return await call_next(request)


@app.get('/fixture-metrics')
async def fixture_metrics():
    return {'stock_requests': stock_requests, 'upstream_stock_calls': stock_calls}


@app.get('/')
async def test_index(request: Request):
    scenario = request.query_params.get('scenario')
    action = {'denied': 'fail({code:1})', 'unavailable': 'fail({code:2})', 'timeout': 'fail({code:3})'}.get(scenario,
        'ok({coords:{latitude:37.5665,longitude:126.978}})')
    script = """<aside style="background:#fff1b8;padding:12px;font-size:14px" id="fixture-banner">화면 검증용 가상 데이터 · 실제 재고 아님 · GPS 호출 <span id="gps-calls">0</span>회</aside>
<script>let calls=0; Object.defineProperty(navigator,'geolocation',{value:{getCurrentPosition(ok,fail){document.querySelector('#gps-calls').textContent=String(++calls); ACTION;}}});</script>""".replace('ACTION', action)
    html = (service.ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
    return HTMLResponse(html.replace('<body>', '<body>' + script))
