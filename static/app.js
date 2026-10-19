'use strict';
const $ = id => document.getElementById(id);
const state = {view: 'home', location: null, product: null, result: null, busy: false, map: null, mapBounds: null, overlays: [], selectedPin: null, selectedStore: null, revision: 0, placeRevision: 0};
let mapStarted = false;
function showPage(focusHeading=false) {
  let results = location.hash === '#results' && !!state.product;
  if(location.hash === '#results' && !state.product) history.replaceState(null, '', '#home');
  const enteringResults = results && state.view !== 'results';
  state.view = results ? 'results' : 'home';
  $('home-page').hidden = results; $('results-page').hidden = !results;
  document.title = results ? `${state.product.name} · CU 근처 재고` : 'CU 근처 재고 찾기';
  if(results) {
    $('results-page-title').textContent = state.product.name;
    $('query-controls').open = !state.location;
    if(!mapStarted) { mapStarted = true; initMap(); }
  }
  requestAnimationFrame(() => {
    window.scrollTo(0, 0);
    if(results && state.map) { state.map.relayout(); if(state.result) renderMap(); }
    if(focusHeading) $(results ? 'results-page-title' : 'home-title').focus({preventScroll:true});
  });
  if(enteringResults && state.location) checkStock();
}
window.addEventListener('hashchange', () => showPage(true));
function openResults() { if(location.hash === '#results') showPage(true); else location.hash = 'results'; }
const groups = {
  'quick-mat': ['트러플하몽스틱', '트러플하몽깡', '트러플하몽칩'],
  'quick-res': ['제나의딸기잼샌드', '원이의옥수수크림빵', '메이의시나몬롤', '리브의초코호떡', '미나미의메론빵']
};
function status(message, error=false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
function ready() {
  $('check').disabled = state.busy || !state.location || !state.product;
  $('product-form').querySelector('button').disabled = state.busy;
  document.querySelectorAll('.chips button').forEach(button => { button.disabled = state.busy; });
}
function clearResult() {
  state.revision++; state.result = null;
  state.mapBounds = null;
  closeMapDetail();
  $('query-guide').hidden = false;
  $('result-count').textContent = '조회 전'; $('summary').textContent = 'CU에서 조회된 매장만 표시합니다.';
  $('stores').replaceChildren(el('p', '위치·상품·반경을 바꾸면 재고 확인 버튼을 눌러 주세요.', 'empty'));
  state.overlays.forEach(x => x.setMap(null)); state.overlays = [];
}
function el(tag, text, cls) { const node = document.createElement(tag); if(text != null) node.textContent = text; if(cls) node.className = cls; return node; }
async function api(path, body) {
  const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await response.json();
  if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '입력값을 확인해 주세요.');
  return data;
}
function setLocation(lat, lon, label) {
  state.location = {lat, lon}; clearResult(); $('location-label').textContent = `선택 위치: ${label}`;
  $('location-message').hidden = true;
  $('query-location').textContent = label; $('query-controls').open = false;
  status('주변 재고 확인 버튼을 눌러 주세요.'); ready();
  if(state.map) state.map.setCenter(new kakao.maps.LatLng(lat, lon));
}
$('gps').addEventListener('click', () => {
  if(!window.isSecureContext) return gpsFail({code:'insecure'});
  if(!navigator.geolocation) return gpsFail({code:'unsupported'});
  $('gps').disabled = true; $('gps').textContent = '현재 위치 확인 중…';
  $('gps').setAttribute('aria-busy', 'true');
  $('location-message').hidden = false; $('location-message').classList.remove('error');
  $('location-message').textContent = '위치 권한을 요청하면 허용해 주세요. 최대 12초 동안 확인해요.';
  status('현재 위치를 한 번 확인하고 있어요…');
  try { navigator.geolocation.getCurrentPosition(position => {
    resetGpsButton();
    const {latitude, longitude} = position.coords;
    if(latitude < 33 || latitude > 39 || longitude < 124 || longitude > 132) return gpsFail({code:'outside'});
    setLocation(latitude, longitude, '현재 위치');
  }, gpsFail, {enableHighAccuracy:true, timeout:12000, maximumAge:0});
  } catch { gpsFail({code:'blocked'}); }
});
function resetGpsButton() {
  $('gps').disabled = false; $('gps').textContent = '내 위치 한 번 확인하기';
  $('gps').setAttribute('aria-busy', 'false');
}
function gpsFail(error) {
  resetGpsButton(); $('query-controls').open = true; $('location-details').open = true;
  const reasons = {
    1: '브라우저 또는 기기에서 위치 사용을 허용하지 않았어요. 위치 권한을 확인하거나 동네·역으로 검색해 주세요.',
    2: '기기에서 현재 위치를 알아내지 못했어요. 기기의 위치 기능을 확인하거나 동네·역으로 검색해 주세요.',
    3: '12초 안에 위치를 확인하지 못했어요. 다시 눌러 확인하거나 동네·역으로 검색해 주세요.',
    unsupported: '이 브라우저에서는 위치 확인을 지원하지 않아요. 다른 브라우저를 사용하거나 동네·역으로 검색해 주세요.',
    blocked: '브라우저에서 위치 확인 요청을 실행하지 못했어요. 위치 권한을 확인하거나 동네·역으로 검색해 주세요.',
    insecure: '현재 접속 주소에서는 위치 확인을 사용할 수 없어요. 공개 사이트는 HTTPS 주소로 접속하거나 동네·역으로 검색해 주세요.',
    outside: '현재 위치가 서비스 조회 범위 밖이에요. 국내 동네·역 이름으로 검색해 주세요.'
  };
  const message = reasons[error?.code] || '위치를 확인할 수 없어요. 동네·역 이름으로 검색해 주세요.';
  $('location-message').hidden = false; $('location-message').classList.add('error');
  $('location-message').textContent = message; status(message, true);
}
let placesService = null;
$('place-form').addEventListener('submit', event => {
  event.preventDefault(); const keyword = $('place-input').value.trim();
  if(!keyword) return;
  if(!placesService) { $('place-message').textContent = '장소 검색을 준비하지 못했어요. 카카오지도 설정 후 사용할 수 있습니다.'; return; }
  const revision = ++state.placeRevision;
  $('places').replaceChildren(); $('place-message').textContent = '장소를 검색하고 있어요…';
  placesService.keywordSearch(keyword, (rows, resultStatus) => {
    if(revision !== state.placeRevision) return;
    if(resultStatus !== kakao.maps.services.Status.OK) { $('place-message').textContent = resultStatus === kakao.maps.services.Status.ZERO_RESULT ? '검색 결과가 없어요. 다른 이름을 입력해 주세요.' : '장소 검색 연결 오류입니다. 잠시 뒤 직접 다시 검색해 주세요.'; return; }
    $('place-message').textContent = '기준으로 삼을 장소를 선택해 주세요.';
    rows.slice(0,7).forEach(place => {
      const li = el('li'), button = el('button', place.place_name); button.type = 'button';
      button.append(el('small', place.road_address_name || place.address_name));
      button.addEventListener('click', () => {
        if(state.busy) return;
        setLocation(Number(place.y), Number(place.x), place.place_name);
        $('places').replaceChildren(); $('place-message').textContent = `${place.place_name} 선택됨`;
        $('place-input').blur();
      }); li.append(button); $('places').append(li);
    });
  });
});
for(const [id, words] of Object.entries(groups)) words.forEach(word => {
  const button = el('button'); button.type = 'button'; button.append(el('span', word));
  button.addEventListener('click', () => { $('product-input').value = word; searchProducts(word); }); $(id).append(button);
});
$('product-form').addEventListener('submit', event => {event.preventDefault(); searchProducts($('product-input').value.trim());});
async function searchProducts(word) {
  if(!word || state.busy) return;
  $('product-input').blur();
  $('products').setAttribute('aria-busy', 'true');
  state.busy = true; state.product = null; clearResult(); ready(); $('selection').hidden = true;
  $('products').replaceChildren(); $('product-message').textContent = '상품을 검색하고 있어요…'; status('CU 상품 목록을 확인하고 있어요…');
  $('product-message').classList.remove('error');
  $('product-choice-title').hidden = true; $('product-tip').hidden = true;
  try {
    const data = await api('/api/products', {keyword:word});
    $('product-choice-title').hidden = !data.products.length;
    $('product-tip').hidden = !data.products.length || Number(data.total) <= data.products.length;
    $('product-message').textContent = data.products.length ? `검색된 상품 ${data.products.length}개` : '상품이 검색되지 않았어요. 다른 이름으로 검색해 주세요.';
    data.products.forEach(product => {
      const li = el('li'), button = el('button'); button.type = 'button';
      const info = el('span', null, 'product-info'); info.append(el('span', product.name, 'product-name'));
      const price = Number(product.price); if(Number.isFinite(price) && price > 0) info.append(el('small', `${price.toLocaleString('ko-KR')}원`));
      button.append(info, el('span', '재고 보기 →', 'product-action'));
      button.addEventListener('click', () => {
        const changed = !state.product || state.product.item_code !== product.item_code || state.product.on_item_no !== product.on_item_no;
        state.product = product; if(changed) clearResult();
        $('selection').textContent = `선택 상품: ${product.name}`; $('selection').hidden = false;
        status(state.result ? '이전에 조회한 결과예요. 최신 재고는 주변 재고 확인을 눌러 주세요.' : state.location ? '주변 재고 확인 버튼을 눌러 주세요.' : '조회할 위치를 먼저 선택해 주세요.'); ready(); openResults();
      }); li.append(button); $('products').append(li);
    }); status(data.products.length ? '검색 결과에서 상품 하나를 선택해 주세요.' : '검색 결과가 없어요. 다른 상품명을 입력해 주세요.');
  } catch(error) { $('product-message').textContent = error.message; $('product-message').classList.add('error'); status(error.message, true); }
  finally { state.busy = false; $('products').setAttribute('aria-busy', 'false'); ready(); }
}
$('radius').addEventListener('change', clearResult);
$('show-all').addEventListener('change', renderStores);
$('choose-query').addEventListener('click', () => {
  $('query-controls').open = true;
  $('location-section').scrollIntoView({behavior:'auto', block:'start'});
  $('gps').focus({preventScroll:true});
});
$('check').addEventListener('click', checkStock);
async function checkStock() {
  if(state.busy || !state.location || !state.product) return;
  clearResult(); const revision = state.revision;
  state.busy = true; ready(); $('check').textContent = '재고 확인 중…';
  $('results').setAttribute('aria-busy', 'true'); status('CU에서 주변 매장 재고를 확인하고 있어요…');
  try {
    const data = await api('/api/stock', {...state.location, item_code:state.product.item_code, on_item_no:state.product.on_item_no, radius:Number($('radius').value)});
    if(revision !== state.revision) return;
    state.result = data; $('query-guide').hidden = true; renderStores(); renderMap();
    $('result-count').textContent = `재고 있음 ${data.in_stock_count}곳`;
    $('summary').textContent = `CU 조회 ${data.returned_count}곳 중 ${data.radius_km}km 안 ${data.within_radius_count}곳 · 품절 ${data.sold_out_count}곳 · 수량 미확인 ${data.unknown_count}곳${data.missing_coordinates ? ` · 좌표 미확인 ${data.missing_coordinates}곳 제외` : ''} · ${clock(data.checked_at)} 조회${data.cached ? ' (30초 캐시)' : ''}`;
    status(data.in_stock_count ? '재고 있는 매장을 가까운 순으로 표시했어요.' : '조회된 범위에서 재고 있는 매장을 찾지 못했어요. 주변 전체나 전국 품절을 뜻하지 않습니다.');
    if(state.view === 'results') $('results').scrollIntoView({behavior:'auto', block:'start'});
  } catch(error) {
    if(revision !== state.revision) return;
    $('stores').replaceChildren(el('p', '연결 오류로 수량을 확인하지 못했어요. 품절 여부는 알 수 없습니다.', 'empty')); status(error.message, true);
  } finally { state.busy = false; $('check').textContent = '주변 재고 확인'; $('results').setAttribute('aria-busy', 'false'); ready(); }
}
function clock(value) { return new Date(value).toLocaleTimeString('ko-KR', {hour:'2-digit',minute:'2-digit',second:'2-digit'}); }
function renderStores() {
  if(!state.result) return;
  const stores = state.result.stores.filter(s => $('show-all').checked || s.status === 'in_stock'); $('stores').replaceChildren();
  if(!stores.length) $('stores').append(el('p', '조회된 반경 안에 재고 있는 매장이 없어요. 품절·미확인도 보기로 상세 상태를 확인할 수 있어요.', 'empty'));
  stores.forEach(store => {
    const card = el('article', null, 'store'); card.id = `store-${store.code}`;
    const top = el('div', null, 'store-top'); top.append(el('h3', store.name), el('span', store.status === 'unknown' ? '수량 미확인' : store.quantity === 0 ? '품절' : `${store.quantity}개`, `stock ${store.status}`));
    card.append(top, el('p', store.address));
    const bottom = el('div', null, 'store-bottom');
    bottom.append(el('span', `직선 ${store.distance_m < 1000 ? store.distance_m + 'm' : (store.distance_m/1000).toFixed(1) + 'km'} · ${clock(state.result.checked_at)}`));
    const link = el('a', '카카오맵 길찾기 ↗'); link.href = `https://map.kakao.com/link/to/${encodeURIComponent('CU '+store.name)},${store.lat},${store.lon}`; link.target = '_blank'; link.rel = 'noopener noreferrer'; bottom.append(link); card.append(bottom); $('stores').append(card);
  });
}
function closeMapDetail(returnFocus=false) {
  const previous = state.selectedPin;
  if(previous) previous.setAttribute('aria-pressed', 'false');
  state.selectedPin = null; state.selectedStore = null;
  $('map-detail').hidden = true;
  document.querySelectorAll('.store.is-selected').forEach(card => card.classList.remove('is-selected'));
  if(returnFocus && previous?.isConnected) previous.focus({preventScroll:true});
}
$('map-detail-close').addEventListener('click', () => closeMapDetail(true));
$('map-detail').addEventListener('keydown', event => { if(event.key === 'Escape') closeMapDetail(true); });
$('map-detail-list').addEventListener('click', () => {
  if(!state.selectedStore) return;
  const card = $(`store-${state.selectedStore.code}`);
  if(card) { card.classList.add('is-selected'); card.scrollIntoView({behavior:'auto', block:'center'}); }
});
function showMapDetail(store, button) {
  closeMapDetail(); state.selectedPin = button; state.selectedStore = store;
  button.setAttribute('aria-pressed', 'true');
  $('map-detail-name').textContent = `CU ${store.name}`;
  $('map-detail-address').textContent = store.address;
  $('map-detail-meta').textContent = `재고 ${store.quantity}개 · 직선 ${store.distance_m < 1000 ? store.distance_m + 'm' : (store.distance_m/1000).toFixed(1) + 'km'} · ${clock(state.result.checked_at)} 조회`;
  $('map-detail-route').href = `https://map.kakao.com/link/to/${encodeURIComponent('CU '+store.name)},${store.lat},${store.lon}`;
  $('map-detail').hidden = false;
  $('map-detail').scrollIntoView({behavior:'auto', block:'nearest'});
}
function renderMap() {
  if(!state.map || !state.result || state.view !== 'results') return;
  closeMapDetail();
  state.overlays.forEach(x => x.setMap(null)); state.overlays = [];
  const bounds = new kakao.maps.LatLngBounds();
  const center = new kakao.maps.LatLng(state.location.lat, state.location.lon); bounds.extend(center);
  const centerDot = el('div', null, 'center-pin'); centerDot.setAttribute('role', 'img'); centerDot.setAttribute('aria-label', '선택한 조회 위치');
  const centerOverlay = new kakao.maps.CustomOverlay({map:state.map, position:center, content:centerDot, xAnchor:.5, yAnchor:.5, zIndex:3}); state.overlays.push(centerOverlay);
  state.result.stores.filter(s => s.status === 'in_stock').forEach(store => {
    const position = new kakao.maps.LatLng(store.lat, store.lon), button = el('button', null, 'pin'); button.type = 'button';
    button.setAttribute('aria-label', `${store.name} 재고 ${store.quantity}개`);
    button.setAttribute('aria-pressed', 'false'); button.setAttribute('aria-controls', 'map-detail');
    const face = el('span', null, 'pin-face'); face.setAttribute('aria-hidden', 'true');
    face.append(el('span', store.quantity > 99 ? '99+' : String(store.quantity), 'pin-count')); button.append(face);
    button.addEventListener('click', () => showMapDetail(store, button));
    state.overlays.push(new kakao.maps.CustomOverlay({map:state.map, position, content:button, yAnchor:1, zIndex:2})); bounds.extend(position);
  }); state.mapBounds = bounds; state.map.setBounds(bounds, 45, 40, 45, 40);
}
async function initMap() {
  try {
    const response = await fetch('/api/config'); const config = await response.json();
    if(!config.kakao_js_key) throw new Error('카카오지도 설정 전입니다. 지도·동네 검색은 설정 후 사용할 수 있어요. GPS와 재고 목록은 사용할 수 있습니다.');
    await new Promise((resolve,reject) => {
      const script = document.createElement('script');
      script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(config.kakao_js_key)}&libraries=services&autoload=false`;
      script.onload = resolve; script.onerror = () => reject(new Error('카카오지도를 불러오지 못했어요. 설정 또는 연결을 확인해 주세요.')); document.head.append(script);
    });
    if(!window.kakao?.maps) throw new Error('카카오지도 키와 사이트 주소 등록을 확인해 주세요.');
    kakao.maps.load(() => {
      state.map = new kakao.maps.Map($('map'), {center:new kakao.maps.LatLng(37.5665,126.978), level:5});
      placesService = new kakao.maps.services.Places(); $('map-message').hidden = true;
      $('place-message').textContent = '동네·역 이름으로 검색할 수 있어요.';
      if(state.location) state.map.setCenter(new kakao.maps.LatLng(state.location.lat,state.location.lon)); renderMap();
      let previousWidth = $('map').clientWidth;
      new ResizeObserver(() => {
        state.map.relayout();
        const width = $('map').clientWidth;
        if(width > 0 && width !== previousWidth && state.mapBounds) state.map.setBounds(state.mapBounds, 45, 40, 45, 40);
        previousWidth = width;
      }).observe($('map'));
    });
  } catch(error) { $('map-message').textContent = error.message; $('place-message').textContent = error.message; }
}
showPage();
