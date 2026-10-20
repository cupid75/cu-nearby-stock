from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
import app as service


@pytest.fixture
def client():
    service.products_cache.data.clear()
    service.stock_cache.data.clear()
    service.limits.data.clear()
    with TestClient(service.app) as client:
        yield client


def row(code, stock, lat=37.5665, lon=126.978):
    return dict(storeCd=code, storeNm='테스트점', stock=stock, latVal=lat,
                longVal=lon, addrFst='서울', addrDetail='주소')


QUERY = dict(item_code='8809599361965', on_item_no='2026090068415', lat=37.5665, lon=126.978, radius=2)


def test_stock_states_radius_distance_and_cache(client):
    rows = [row('one', '8'), row('two', '0'), row('three', None), row('far', '2', 37.60), row('bad', '1', None)]
    with patch.object(service, 'upstream', return_value={'storeList':rows}) as upstream:
        first = client.post('/api/stock', json=QUERY).json()
        second = client.post('/api/stock', json={**QUERY, 'radius':5}).json()
    assert first['returned_count'] == 5
    assert first['missing_coordinates'] == 1
    assert [s['status'] for s in first['stores']] == ['in_stock', 'sold_out', 'unknown']
    assert first['in_stock_count'] == first['sold_out_count'] == first['unknown_count'] == 1
    assert first['stores'][0]['distance_m'] == 0
    assert second['within_radius_count'] == 4
    assert second['cached'] is True and second['checked_at'] == first['checked_at']
    assert upstream.call_count == 1


@pytest.mark.parametrize('value', [None, '', '-1', 'unknown', True, '1.5'])
def test_unknown_quantity_never_becomes_sold_out(value):
    stores, _, _ = service.normalize_stores([row('test', value)], 37.5665,126.978)
    assert stores[0]['status'] == 'unknown' and stores[0]['quantity'] is None


def test_bad_response_and_connection_not_sold_out(client):
    with patch.object(service, 'upstream', return_value={'other':[]}):
        assert client.post('/api/stock', json=QUERY).status_code == 502
    with patch.object(service, 'upstream', side_effect=HTTPException(502,'연결 오류')) as upstream:
        response = client.post('/api/stock', json=QUERY)
        assert response.status_code == 502 and 'stores' not in response.json()
        assert upstream.call_count == 1


@pytest.mark.parametrize('status', [401,403,429])
def test_upstream_rejection_stops_without_retry(status):
    with patch.object(service, 'cu_request', return_value={'status':status}) as request:
        with pytest.raises(HTTPException):
            service.upstream('/api/store', {})
        assert request.call_count == 1


def test_ten_requests_per_minute(client):
    result = {'data':{'stockResult':{'result':{'rows':[], 'total_count':0}}}}
    with patch.object(service, 'upstream', return_value=result) as upstream:
        for _ in range(10):
            assert client.post('/api/products', json={'keyword':'빵'}).status_code == 200
        assert client.post('/api/products', json={'keyword':'빵'}).status_code == 429
        assert upstream.call_count == 1
    assert 'cu_session' in client.cookies


def test_cache_expiry():
    cache = service.TTLCache(30)
    with patch.object(service.time, 'monotonic', return_value=100):
        cache.put('coordinates', {'value':1})
        assert cache.get('coordinates') == {'value':1}
    with patch.object(service.time, 'monotonic', return_value=130):
        assert cache.get('coordinates') is None
        assert not cache.data


def test_inputs_and_no_location_in_url(client):
    for query in [{**QUERY,'radius':3}, {**QUERY,'lat':0}, {**QUERY,'item_code':'<script>'}]:
        assert client.post('/api/stock', json=query).status_code == 422
    assert client.get('/api/stock').status_code == 405
    assert client.get('/').status_code == 200
    assert client.get('/api/config').headers['cache-control'] == 'no-store'


def test_search_normalizes_minimal_fields(client):
    data = {'data':{'stockResult':{'result':{'rows':[{'fields':{'item_nm':'트러플하몽스틱', 'item_cd':'123', 'on_item_no':'456', 'secret':'not exposed'}}]}}}}
    with patch.object(service, 'upstream', return_value=data) as upstream:
        answer = client.post('/api/products', json={'keyword':'트러플'}).json()
        assert answer['products'][0]['item_code'] == '123'
        assert 'secret' not in answer['products'][0]
        assert client.post('/api/products', json={'keyword':'트러플'}).json()['cached'] is True
        assert upstream.call_count == 1
