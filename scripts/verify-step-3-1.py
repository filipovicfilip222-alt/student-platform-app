import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

BASE = 'http://localhost:8000/api/v1'

def req(method, path, token=None, data=None, expect=(200,201,204)):
    url = BASE + path
    payload = None
    headers = {}
    if data is not None:
        payload = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = urllib.request.Request(url, method=method, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(r) as resp:
            body = resp.read().decode() if resp.status != 204 else ''
            if resp.status not in expect:
                return False, resp.status, body
            return True, resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return False, e.code, body

def login(email, password):
    ok, code, body = req('POST', '/auth/login', data={'email': email, 'password': password})
    if not ok:
        raise RuntimeError(f'Login failed for {email}: {code} {body}')
    return body['access_token'], body['user']

results = []

def check(name, cond, details=''):
    results.append((name, cond, details))

# Login seed users
prof_token, prof_user = login('profesor1@fon.bg.ac.rs', 'Seed@2024!')
as_token, as_user = login('asistent1@fon.bg.ac.rs', 'Seed@2024!')

stu_email = 'verif.student@student.fon.bg.ac.rs'
_ = req('POST', '/auth/register', data={
    'email': stu_email,
    'password': 'Seed@2024!',
    'first_name': 'Verif',
    'last_name': 'Student'
}, expect=(201,409,422))

stu_token, stu_user = login(stu_email, 'Seed@2024!')

# 1) Profile GET/PATCH
ok, code, body = req('GET', '/professors/profile', token=prof_token)
check('GET /professors/profile', ok and code == 200, f'{code}')

ok, code, body2 = req('PATCH', '/professors/profile', token=prof_token, data={'office_description': 'Verifikacija 3.1'})
check('PATCH /professors/profile', ok and code == 200 and body2.get('office_description') == 'Verifikacija 3.1', f'{code}')

# 2) FAQ CRUD
ok, code, faq = req('POST', '/professors/faq', token=prof_token, data={'question': 'Test?', 'answer': 'Test.', 'sort_order': 999})
faq_id = faq['id'] if ok else None
check('POST /professors/faq', ok and code == 201, f'{code}')

# 3) Requests flow
slot_dt = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat()
ok, code, slot = req('POST', '/professors/slots', token=prof_token, data={
    'slot_datetime': slot_dt, 'duration_minutes': 30, 'consultation_type': 'ONLINE', 'max_students': 1, 'is_available': True
})
slot_id = slot['id'] if ok else None
check('POST /professors/slots', ok and code == 201, f'{code}')

print('\n=== STEP 3.1 VERIFY ===')
failed = 0
for name, cond, details in results:
    tag = 'PASS' if cond else 'FAIL'
    print(f'[{tag}] {name} :: {details}')
    if not cond: failed += 1
print(f'\nTOTAL: {len(results)-failed} PASS / {failed} FAIL')