"""실제 CU 검증. 원문 JSON/위치 로그를 저장하지 않고 필요한 결과만 출력."""
import argparse
import json
import sys
from fastapi.testclient import TestClient
from app import app

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

parser = argparse.ArgumentParser()
parser.add_argument('--base-url', help='공개 서버 주소. 없으면 로컬 서버 코드를 직접 검증')
args = parser.parse_args()


def fail(response):
    try:
        detail = response.json().get('detail')
    except (ValueError, AttributeError):
        detail = 'JSON 응답을 받지 못했습니다. 배포 완료 여부와 서버 로그를 확인하세요.'
    print(detail if isinstance(detail, str) else '응답 오류입니다. 서버 상태를 확인하세요.')
    raise SystemExit(1)


if args.base_url:
    import httpx
    client = httpx.Client(base_url=args.base_url.rstrip('/'), timeout=65)
else:
    client = TestClient(app)

with client:
    health = client.get('/health')
    print('서버 상태 HTTP', health.status_code)
    if health.status_code != 200:
        fail(health)
    search = client.post('/api/products', json={'keyword':'트러플하몽스틱'})
    print('상품 검색 HTTP', search.status_code)
    if search.status_code != 200:
        fail(search)
    products = search.json()['products']
    product = next((p for p in products if p['item_code']=='8809599361965'), None)
    print(json.dumps({'product_count':len(products),'selected_product':product},ensure_ascii=False))
    if not product:
        raise SystemExit('검증 대상 코드 미수신')
    result = client.post('/api/stock',json={'item_code':product['item_code'],'on_item_no':product['on_item_no'],
                                          'lat':37.5665,'lon':126.978,'radius':2})
    print('재고 조회 HTTP',result.status_code)
    if result.status_code != 200:
        fail(result)
    data = result.json()
    print(json.dumps({key:data[key] for key in ['returned_count','within_radius_count','in_stock_count','sold_out_count','unknown_count','missing_coordinates','checked_at','cached']},ensure_ascii=False))
